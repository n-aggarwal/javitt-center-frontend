from typing import List, Dict, Any, Optional, Tuple
from bedrock_client import DEFAULT_MODEL_ID
import json

SYSTEM_PROMPT = (
    "You are a cautious data agent.\n"
    "- Prefer read-only operations; request approval for writes.\n"
    "- Always inspect schema before complex SQL.\n"
    "- Keep results concise; include next steps when helpful.\n"
)

TOOL_SCHEMAS = [
    {
        "name": "get_schema",
        "description": "Return database schema with tables and columns. Optionally include row counts.",
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
        "description": "Execute SQL. Defaults to read-only. Results truncated by row_limit.",
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
        "description": "Return up to N rows from a table.",
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


def _extract_tool_calls(message: Dict[str, Any]) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []
    for part in message.get("content", []) or []:
        if isinstance(part, dict) and part.get("type") == "toolUse":
            calls.append(part)
    return calls


def agent_step(client,
               history_messages: List[Dict[str, Any]],
               user_msg: Optional[str] = None,
               model_id: str = DEFAULT_MODEL_ID,
               tools_impl: Optional[Dict[str, Any]] = None,
               max_tokens: int = 2000,
               temperature: float = 0.3) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Perform a single model step. If the model uses tools, execute them and return final follow-up message.
    Returns (final_message, tool_results_sent)
    """
    messages = list(history_messages)
    if user_msg is not None:
        messages.append({"role": "user", "content": [{"text": user_msg}]})

    resp = client.converse(
        modelId=model_id,
        system=[{"text": SYSTEM_PROMPT}],
        messages=messages,
        toolConfig={"tools": TOOL_SCHEMAS},
        inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
    )
    msg = resp["output"]["message"]

    tool_calls = _extract_tool_calls(msg)
    if not tool_calls:
        return msg, []

    # Execute tools
    tool_results: List[Dict[str, Any]] = []
    tools_impl = tools_impl or {}
    for call in tool_calls:
        name = call.get("name")
        tool_input = call.get("input", {})
        try:
            if name in tools_impl:
                result = tools_impl[name](**tool_input)
            else:
                result = {"error": f"Unknown tool: {name}"}
        except Exception as e:
            result = {"error": str(e)}
        tool_results.append({
            "toolUseId": call.get("toolUseId"),
            "content": [{"json": result}]
        })

    # Follow-up so the model can produce the final answer
    follow = client.converse(
        modelId=model_id,
        system=[{"text": SYSTEM_PROMPT}],
        messages=messages + [msg, {"role": "user", "content": tool_results}],
        toolConfig={"tools": TOOL_SCHEMAS},
        inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
    )
    return follow["output"]["message"], tool_results


def agent_multistep(client,
                    history_messages: List[Dict[str, Any]],
                    user_msg: str,
                    tools_impl: Dict[str, Any],
                    model_id: str = DEFAULT_MODEL_ID,
                    max_iters: int = 3) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Run up to max_iters of tool-using cycles until no new tool call appears.
    Returns (all_messages_appended, last_tool_results)
    """
    messages = list(history_messages)
    tool_results: List[Dict[str, Any]] = []
    final_msg: Optional[Dict[str, Any]] = None

    # First step with the user's message
    msg, tool_results = agent_step(client, messages, user_msg=user_msg, tools_impl=tools_impl, model_id=model_id)
    messages.extend([
        {"role": "user", "content": [{"text": user_msg}]},
        msg,
    ])

    # If tools were used, we may iterate again (the follow-up might include new toolUse)
    iters = 1
    while iters < max_iters:
        next_calls = _extract_tool_calls(msg)
        if not next_calls:
            break
        # Execute another cycle without adding a new user message
        msg, tool_results = agent_step(client, messages, user_msg=None, tools_impl=tools_impl, model_id=model_id)
        messages.append(msg)
        iters += 1

    return messages, tool_results
