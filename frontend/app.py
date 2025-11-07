import streamlit as st
import requests
import json

st.set_page_config(page_title="Bedrock MySQL Data Agent", page_icon="🧠", layout="wide")

st.title("🧠 Bedrock MySQL Data Agent")

with st.sidebar:
    st.header("AWS & Model")
    region = st.text_input("AWS Region", value="us-east-1", help="Region where Bedrock is enabled")
    model_id = st.text_input("Model ID", value="us.anthropic.claude-3-5-sonnet-20241022-v2:0", help="Claude Sonnet model ID")
    aws_profile = st.text_input("AWS Profile (optional)", value="", help="Configured in backend")

    st.header("Database Connection")
    host = st.text_input("Host", value="localhost", disabled=True)
    port = st.number_input("Port", value=3306, step=1, disabled=True)
    user = st.text_input("User", value="root", disabled=True)
    password = st.text_input("Password", value="", type="password", disabled=True)
    database = st.text_input("Database", value="nl2sql_demo.sqlite", disabled=True)

    st.info("Database connection is managed by the backend (SQLite)")

    allow_writes = st.checkbox("Allow write operations (dangerous)", value=False, help="Backend enforces read-only mode", disabled=True)

    st.header("Backend Configuration")
    backend_url = st.text_input("Backend API URL", value="http://localhost:8000", help="URL of the FastAPI backend")

# Initialize session state for conversation history
if "history" not in st.session_state:
    st.session_state.history = []  # Stores conversation messages

if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []  # Stores messages for API

# Test backend connection
if st.sidebar.button("Test Backend Connection"):
    try:
        response = requests.get(f"{backend_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            st.sidebar.success(f"✓ Backend connected! Tables: {data.get('tables_count', 0)}")
        else:
            st.sidebar.error(f"Backend returned status: {response.status_code}")
    except Exception as e:
        st.sidebar.error(f"Failed to connect to backend: {e}")

st.subheader("Ask the agent")
user_msg = st.text_area("Your request", placeholder="e.g., How many customers do we have?")

col1, col2 = st.columns([1,1])
with col1:
    run_btn = st.button("Run")
with col2:
    clear_btn = st.button("Clear Conversation")

if clear_btn:
    st.session_state.history = []
    st.session_state.conversation_history = []
    st.rerun()

if run_btn and user_msg.strip():
    try:
        # Prepare request payload
        payload = {
            "query": user_msg.strip(),
            "include_explanation": True,
            "conversation_history": st.session_state.conversation_history
        }

        # Call backend API
        with st.spinner("Processing query..."):
            response = requests.post(
                f"{backend_url}/query",
                json=payload,
                timeout=30
            )

        if response.status_code == 200:
            result = response.json()

            # Add user message to history
            st.session_state.history.append({
                "role": "user",
                "content": user_msg.strip()
            })

            # Build assistant response
            if result.get("success"):
                assistant_response = f"""**Generated SQL:**
```sql
{result.get('sql', '')}
```

**Results:**
{result.get('row_count', 0)} rows returned

"""
                # Show sample results
                if result.get('results'):
                    results_preview = result['results'][:5]  # Show first 5 rows
                    assistant_response += f"```json\n{json.dumps(results_preview, indent=2)}\n```\n\n"

                # Add explanation
                if result.get('explanation'):
                    assistant_response += f"**Explanation:**\n{result['explanation']}"

                st.session_state.history.append({
                    "role": "assistant",
                    "content": assistant_response,
                    "sql": result.get('sql'),
                    "results": result.get('results')
                })

                # Update conversation history for API (keeping context)
                st.session_state.conversation_history.append({
                    "role": "user",
                    "content": user_msg.strip()
                })
                st.session_state.conversation_history.append({
                    "role": "assistant",
                    "content": result.get('explanation', '') or f"Executed SQL: {result.get('sql')}"
                })

            else:
                # Handle error
                error_msg = f"**Error:** {result.get('error', 'Unknown error')}\n\n"
                if result.get('sql'):
                    error_msg += f"**Generated SQL:**\n```sql\n{result['sql']}\n```\n\n"
                if result.get('explanation'):
                    error_msg += f"**Explanation:**\n{result['explanation']}"

                st.session_state.history.append({
                    "role": "assistant",
                    "content": error_msg
                })

            st.success("Query processed!")
            st.rerun()
        else:
            st.error(f"Backend error: {response.status_code} - {response.text}")

    except requests.exceptions.Timeout:
        st.error("Request timed out. Query took too long to process.")
    except requests.exceptions.ConnectionError:
        st.error(f"Could not connect to backend at {backend_url}. Make sure the backend is running.")
    except Exception as e:
        st.error(f"Agent error: {e}")

st.subheader("Conversation")
for msg in st.session_state.history:
    role = msg.get("role")
    content = msg.get("content", "")

    if role == "user":
        st.markdown(f"**User:** {content}")
    elif role == "assistant":
        st.markdown("**Assistant:**")
        st.markdown(content)

        # Show expandable full results if available
        if msg.get("results"):
            with st.expander("View Full Results"):
                st.json(msg["results"])

st.caption("Tip: The conversation maintains context - you can ask follow-up questions like 'what about orders?' or 'show me the top 10'")

st.divider()

st.subheader("Quick Start")
st.markdown("""
1. Make sure the backend is running: `cd backend && python app.py`
2. Test the backend connection using the sidebar button.
3. Ask the agent tasks like:
   - "How many customers do we have?"
   - "Show me the first 5 products"
   - "What's the total revenue from orders?"
   - Follow-up: "What about last month?" (uses conversation context)
""")

st.divider()

st.subheader("Backend Information")
col1, col2 = st.columns(2)

with col1:
    if st.button("Get Database Schema"):
        try:
            response = requests.get(f"{backend_url}/database/info", timeout=10)
            if response.status_code == 200:
                info = response.json()
                st.write("**Tables:**", ", ".join(info.get("tables", [])))
                with st.expander("View Full Schema"):
                    st.text(info.get("schema", ""))
            else:
                st.error(f"Error: {response.status_code}")
        except Exception as e:
            st.error(f"Error: {e}")

with col2:
    if st.button("Check Backend Health"):
        try:
            response = requests.get(f"{backend_url}/health", timeout=5)
            if response.status_code == 200:
                st.json(response.json())
            else:
                st.error(f"Backend unhealthy: {response.status_code}")
        except Exception as e:
            st.error(f"Error: {e}")
