import streamlit as st
from bedrock_client import make_bedrock_client, DEFAULT_MODEL_ID, extract_text_from_message
from agent import agent_multistep
import db_tools as dbt
import traceback

st.set_page_config(page_title="Bedrock MySQL Data Agent", page_icon="🧠", layout="wide")

st.title("🧠 Bedrock MySQL Data Agent")

with st.sidebar:
    st.header("AWS & Model")
    region = st.text_input("AWS Region", value="us-west-2", help="Region where Bedrock is enabled")
    model_id = st.text_input("Model ID", value=DEFAULT_MODEL_ID, help="Claude Sonnet model ID available in your account")
    aws_profile = st.text_input("AWS Profile (optional)", value="", help="If empty, default credentials/role are used")

    st.header("MySQL Connection")
    host = st.text_input("Host", value="localhost")
    port = st.number_input("Port", value=3306, step=1)
    user = st.text_input("User", value="root")
    password = st.text_input("Password", value="", type="password")
    database = st.text_input("Database", value="test")

    allow_writes = st.checkbox("Allow write operations (dangerous)", value=False, help="Unchecked = read-only")

if "history" not in st.session_state:
    st.session_state.history = []  # Bedrock messages format

if "client" not in st.session_state or st.button("Reconnect AWS Client"):
    try:
        client = make_bedrock_client(region, profile_name=aws_profile or None)
        st.session_state.client = client
        st.success("Connected to Bedrock client")
    except Exception as e:
        st.session_state.client = None
        st.error(f"Failed to create Bedrock client: {e}")

# Configure DB engine and write policy
if st.button("Connect Database"):
    try:
        db_url = dbt.make_db_url(host, int(port), user, password, database)
        dbt.set_engine(db_url)
        dbt.set_write_policy(allow_writes)
        st.success("Database configured.")
    except Exception as e:
        st.error(f"DB connection failed: {e}")
        st.code(traceback.format_exc())

st.subheader("Ask the agent")
user_msg = st.text_area("Your request", placeholder="e.g., Profile missing values by column in customers table")

col1, col2 = st.columns([1,1])
with col1:
    run_btn = st.button("Run")
with col2:
    clear_btn = st.button("Clear Conversation")

if clear_btn:
    st.session_state.history = []

# Tools implementation mapping for the agent
TOOLS_IMPL = {
    "get_schema": dbt.get_schema,
    "run_sql": dbt.run_sql,
    "sample_rows": dbt.sample_rows,
}

if run_btn and user_msg.strip():
    if st.session_state.client is None:
        st.warning("Please connect AWS client from the sidebar.")
    else:
        try:
            messages, tool_results = agent_multistep(
                client=st.session_state.client,
                history_messages=st.session_state.history,
                user_msg=user_msg.strip(),
                tools_impl=TOOLS_IMPL,
                model_id=model_id,
                max_iters=3,
            )
            st.session_state.history = messages
            st.success("Agent run complete.")
        except Exception as e:
            st.error(f"Agent error: {e}")
            st.code(traceback.format_exc())

st.subheader("Conversation")
for m in st.session_state.history:
    role = m.get("role")
    if role == "user":
        st.markdown(f"**User:** {m['content'][0].get('text','')}")
    else:
        # assistant messages may include toolUse; show any text parts
        texts = []
        for p in m.get("content", []) or []:
            if isinstance(p, dict) and "text" in p:
                texts.append(p["text"])
        if texts:
            st.markdown("**Assistant:**\n" + "\n\n".join(texts))

st.caption("Tip: Toggle 'Allow write operations' cautiously. This app enforces basic safety checks but cannot prevent all risky operations.")

st.divider()

st.subheader("Quick Start")
st.markdown("""
1. Fill AWS Region and Model ID (ensure model is enabled in your account).
2. Enter MySQL connection details and click 'Connect Database'.
3. Ask the agent tasks like:
   - "Show the schema and row counts for the main tables."
   - "Find duplicate customers by email and show top 10 domains."
   - "Trim whitespace in customers.name (requesting write approval)."
""")
