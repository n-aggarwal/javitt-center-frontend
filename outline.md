### What you’re building
You want an agent that:
- Connects to a user‑selected MySQL database
- Accepts natural‑language tasks ("clean the data", "analyze X")
- Plans the steps, executes SQL/data‑ops safely, and returns results
- Uses AWS Bedrock (Claude Sonnet) as the “brain”

Below is a battle‑tested architecture, safety practices, and concrete code to get you from a basic Bedrock call to a tool‑using agent that can run MySQL operations responsibly.

---

### High‑level architecture
- Orchestrator (Python):
  - Receives user request
  - Maintains conversation state
  - Presents the model with tools
  - Executes model‑requested tools (DB ops, analysis) with guardrails
  - Streams back partial/final results
- Tools (server‑side functions you control):
  - `get_schema` (read‑only)
  - `run_sql` (read‑only by default; writes require explicit approval)
  - `sample_rows` (row‑capped select)
  - `profile_table/column` (basic stats, nulls, distribution)
  - `clean_ops` (e.g., trim, dedupe; often compiled to SQL; for big jobs, offload to Glue/Spark)
- Data layer:
  - SQLAlchemy/MySQL driver (PyMySQL or mysqlclient)
  - Timeouts, `SELECT` row limits, EXPLAIN for risky queries, transaction + rollback on errors
  - Read‑only DB user for most operations; separate least‑privileged role for writes
- Storage (optional):
  - S3 for intermediate CSV/Parquet outputs; Athena/Glue Catalog if you expand
- Safety & governance:
  - Secrets Manager for DB credentials, KMS‑encrypted
  - Query sandbox with allowlists/deny‑lists, rate limiting, audit and approvals for writes
  - PII redaction in logs and model context

---

### Your current Bedrock code: small fixes and improvements
You’re using the new Bedrock `converse` API, which is great. A few tweaks:
- Model IDs: Don’t include the region prefix in `modelId`. Example IDs (may vary by region/availability):
  - Claude 4.0 Sonnet: `anthropic.claude-4-sonnet-2025-05-14-v1:0`
  - Claude 3.5 Sonnet (widely available): `anthropic.claude-3-5-sonnet-20240620-v1:0`
- Add a `system` prompt for role/guardrails.
- Add retries with backoff and timeouts.
- Support streaming for better UX with longer outputs.
- Normalize the response safely (content can be multiple blocks and types).

#### Improved Bedrock client helper
```python
import boto3
import botocore
import time
from typing import List, Optional, Tuple

DEFAULT_MODEL = "anthropic.claude-4-sonnet-2025-05-14-v1:0"  # fallback to a model you have access to

bedrock = boto3.client(
    service_name="bedrock-runtime",
    region_name="us-west-2",
)


def extract_text(message) -> str:
    parts = message.get("content", [])
    texts = []
    for p in parts:
        if "text" in p:
            texts.append(p["text"])  # other types: toolUse, toolResult, images, etc.
    return "\n".join(texts)


def call_claude(prompt: str,
                system: Optional[str] = None,
                model_id: str = DEFAULT_MODEL,
                max_tokens: int = 2000,
                temperature: float = 0.5,
                top_p: float = 0.9,
                retries: int = 3,
                timeout_sec: int = 30) -> Tuple[bool, str]:
    messages = [{"role": "user", "content": [{"text": prompt}]}]

    attempt = 0
    while True:
        try:
            resp = bedrock.converse(
                modelId=model_id,
                system=[{"text": system}] if system else None,
                messages=messages,
                inferenceConfig={
                    "maxTokens": max_tokens,
                    "temperature": temperature,
                    "topP": top_p,
                },
            )
            out_msg = resp["output"]["message"]
            return True, extract_text(out_msg)
        except botocore.exceptions.BotoCoreError as e:
            attempt += 1
            if attempt > retries:
                return False, f"Bedrock call failed after {retries} retries: {e}"
            time.sleep(2 ** attempt)
        except Exception as e:
            return False, f"Unexpected error: {e}"
```

---

### Tool use with Bedrock `converse`
The key to an agent is exposing safe tools to the model. With Bedrock `converse`, you provide tool schemas; the model returns `toolUse` blocks; you execute them and reply with `toolResult`.

#### Define tool schemas
```python
TOOL_SCHEMAS = [
    {
        "name": "get_schema",
        "description": "Return database schema with tables and columns. Optionally include sample row counts.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "include_counts": {"type": "boolean", "default": False},
                    "tables": {"type": "array", "items": {"type": "string"}}
                }
            }
        }
    },
    {
        "name": "run_sql",
        "description": "Execute a parameterized SQL query. Defaults to read-only. Large results are truncated.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string"},
                    "params": {"type": "object"},
                    "write": {"type": "boolean", "default": False},
                    "row_limit": {"type": "integer", "default": 200}
                },
                "required": ["sql"]
            }
        }
    },
    {
        "name": "sample_rows",
        "description": "Get up to N sample rows from a table.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "table": {"type": "string"},
                    "limit": {"type": "integer", "default": 50}
                },
                "required": ["table"]
            }
        }
    }
]
```

#### Orchestrator loop (tool calling)
```python
import json

SYSTEM_PROMPT = (
    "You are a data agent. Prefer read-only operations, request approval for writes. "
    "Use tools to inspect schema before writing SQL. Return concise results and a final answer."
)


def converse_with_tools(user_msg: str, history: list, model_id: str = DEFAULT_MODEL):
    # history: list of prior messages already in Bedrock format
    messages = history + [{"role": "user", "content": [{"text": user_msg}]}]

    resp = bedrock.converse(
        modelId=model_id,
        system=[{"text": SYSTEM_PROMPT}],
        messages=messages,
        toolConfig={"tools": TOOL_SCHEMAS},
        inferenceConfig={"maxTokens": 2000, "temperature": 0.3},
    )

    msg = resp["output"]["message"]

    tool_calls = [c for c in msg.get("content", []) if c.get("type") == "toolUse"]
    if not tool_calls:
        # No tool use; return text
        return msg, None

    # Execute each tool call in order. You can parallelize non-dependent calls if desired.
    tool_results = []
    for call in tool_calls:
        name = call["name"]
        tool_input = call.get("input", {})  # Bedrock provides parsed JSON here
        try:
            if name == "get_schema":
                result = tool_get_schema(**tool_input)
            elif name == "run_sql":
                result = tool_run_sql(**tool_input)
            elif name == "sample_rows":
                result = tool_sample_rows(**tool_input)
            else:
                result = {"error": f"Unknown tool {name}"}
        except Exception as e:
            result = {"error": str(e)}

        tool_results.append({
            "toolUseId": call["toolUseId"],
            "content": [{"json": result}]  # respond as JSON
        })

    # Send a follow-up with tool results so the model can reason and produce the final answer
    follow = bedrock.converse(
        modelId=model_id,
        system=[{"text": SYSTEM_PROMPT}],
        messages=messages + [msg, {"role": "user", "content": tool_results}],  # tool results are from "user" per Bedrock’s pattern
        toolConfig={"tools": TOOL_SCHEMAS},
        inferenceConfig={"maxTokens": 2000, "temperature": 0.3},
    )
    return follow["output"]["message"], tool_results
```

Note: Some SDKs use `role: "assistant"` for tool results; Bedrock’s current pattern accepts tool results as a special content item. If your region’s SDK expects a different role or envelope, adjust accordingly (the shape above reflects the public docs pattern for `converse` tool use; verify once in your account).

---

### Safe MySQL execution layer
Use SQLAlchemy with PyMySQL and implement strict guardrails.

```python
import os
import sqlalchemy as sa
from sqlalchemy.engine import Engine
from contextlib import contextmanager

DB_URL = os.getenv("DB_URL")  # e.g., mysql+pymysql://user:pass@host:3306/dbname
engine: Engine = sa.create_engine(DB_URL, pool_pre_ping=True, pool_recycle=3600)

@contextmanager
def _connect():
    conn = engine.connect()
    try:
        yield conn
    finally:
        conn.close()

READ_ONLY_SQL_PREFIXES = ("SELECT", "WITH", "EXPLAIN")

class SqlSafetyError(Exception):
    pass


def enforce_safety(sql: str, write: bool) -> None:
    s = sql.strip().upper()
    if not write and not s.startswith(READ_ONLY_SQL_PREFIXES):
        raise SqlSafetyError("Write operation attempted without approval.")
    # Block dangerous tokens regardless
    banned = [";--", " DROP ", " TRUNCATE ", " SHUTDOWN ", "\n\n"]
    for b in banned:
        if b in s:
            raise SqlSafetyError(f"Banned token: {b.strip()}")


def tool_get_schema(include_counts: bool = False, tables=None):
    tables = tables or []
    out = {}
    with _connect() as c:
        if tables:
            table_filter = tuple(tables)
            sql = sa.text(
                "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN :t ORDER BY TABLE_NAME, ORDINAL_POSITION"
            )
            rows = c.execute(sql, {"t": table_filter}).mappings().all()
        else:
            sql = sa.text(
                "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_NAME, ORDINAL_POSITION"
            )
            rows = c.execute(sql).mappings().all()
        for r in rows:
            out.setdefault(r["TABLE_NAME"], []).append({
                "column": r["COLUMN_NAME"],
                "type": r["DATA_TYPE"],
            })
        if include_counts:
            for t in out.keys():
                cnt = c.execute(sa.text(f"SELECT COUNT(*) AS n FROM `{t}`"))
                out[t] = {"columns": out[t], "row_count": int(list(cnt)[0][0])}
    return out


def tool_run_sql(sql: str, params=None, write: bool = False, row_limit: int = 200):
    params = params or {}
    enforce_safety(sql, write)
    # Apply row limit for selects when not explicitly limited
    if not write:
        up = sql.strip().upper()
        if up.startswith("SELECT") and " LIMIT " not in up:
            sql = f"{sql}\nLIMIT {int(row_limit)}"
    with _connect() as c:
        if write:
            trans = c.begin()
            try:
                res = c.execute(sa.text(sql), params)
                trans.commit()
                return {"rowcount": getattr(res, "rowcount", None)}
            except Exception as e:
                trans.rollback()
                raise
        else:
            res = c.execute(sa.text(sql), params)
            rows = res.mappings().fetchmany(row_limit)
            return {"rows": [dict(r) for r in rows]}


def tool_sample_rows(table: str, limit: int = 50):
    sql = f"SELECT * FROM `{table}` LIMIT {int(limit)}"
    return tool_run_sql(sql, write=False, row_limit=limit)
```

Optional upgrades:
- Per‑table allowlist/deny‑list
- Max execution time: set `max_execution_time` session variable in MySQL (`SET SESSION MAX_EXECUTION_TIME=...;`)
- Pre‑EXPLAIN large/risky queries and ask the model to simplify if too costly

---

### Typical “clean the data” workflows
- Trimming and normalization:
  - SQL: `UPDATE t SET col = TRIM(col)` (behind write approval)
  - For skewed text fixes, stage into a new table: `CREATE TABLE t_clean AS SELECT ...`
- Deduplication:
  - `CREATE TABLE t_dedup AS SELECT * FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY k ORDER BY updated_at DESC) rn FROM t) q WHERE rn = 1`
- Type casting and validation:
  - `ALTER TABLE` plus selective `UPDATE` for castable rows; store rejects in an `_errors` table
- Missing values profiling:
  - `SELECT col, SUM(col IS NULL) AS nulls, COUNT(*) AS n FROM t` per column
- For medium/large datasets or Pythonic transforms:
  - Use Pandas over chunks (SQLAlchemy) and write back as a new table
  - For large scale, offload to AWS Glue (Spark) with S3 as staging; the agent can trigger a Glue job via an additional tool

---

### Guardrails and governance (important!)
- Identity & permissions:
  - Use a read‑only DB user for normal ops; separate minimal write role gated by explicit approval (human or policy)
- Secrets:
  - Store DB creds in AWS Secrets Manager; retrieve at runtime; never log secrets; enable KMS
- Network:
  - Private connectivity (VPC/PrivateLink) to DB where possible; restrict inbound
- Safety checks:
  - Apply `LIMIT` by default; enforce `max_execution_time`
  - Denylist destructive statements; optionally require a dry‑run mode (SELECT into temp) before write
  - Keep an audit log: who asked, SQL executed, rowcount, duration
- Data handling:
  - PII redaction in prompts/tool results; don’t paste raw sensitive values into the model context unless necessary

---

### Putting it together: sample request flow
1. User: “Clean leading/trailing whitespace in `customers.name`, dedupe by `email`, and show the top 5 duplicate domains.”
2. Model calls `get_schema` → sees `customers(name,email,...)`
3. Model proposes `run_sql` (read‑only) to profile duplicates and domains
4. Model asks for write approval to run a safe `UPDATE` or to create `customers_clean` with deduped rows
5. Orchestrator checks policy; if approved, runs write; returns rowcount; model summarizes results and next steps

---

### Minimal end‑to‑end demo
You can wire a basic Flask/FastAPI endpoint:
```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class AskBody(BaseModel):
    message: str

CONVO_HISTORY = []

@app.post("/ask")
def ask(body: AskBody):
    msg, tool_results = converse_with_tools(body.message, CONVO_HISTORY)
    CONVO_HISTORY.extend([
        {"role": "user", "content": [{"text": body.message}]},
        msg,
    ])
    # Return final text
    return {"answer": extract_text(msg), "tool_results": tool_results}
```

---

### Troubleshooting notes
- If you see `AccessDeniedException` on Bedrock, ensure:
  - Bedrock is enabled in your account/region; IAM role has `bedrock:InvokeModel` and `bedrock:Converse`
- If modelId not found, list models:
  - `aws bedrock list-foundation-models --region us-west-2` and pick the exact ID available to you
- If you get empty `content`, check for tool use blocks; extract text from all `content` parts

---

### Next steps checklist
- Pick your region‑supported model ID
- Wrap your Bedrock calls with the improved helper (system prompts, retries)
- Implement the three tools and the safe SQL layer
- Add a human approval switch for writes
- Log every executed query with timing, user id, and outcome
- Build a simple web endpoint + UI to iterate

If you share your preferred model ID (from your account) and how users connect their DB (direct credentials, Secrets Manager, etc.), I can tailor the code to your exact environment and provide a runnable FastAPI service with dockerization and tests.
