# Natural Language to SQL Frontend

Streamlit-based frontend for the NL2SQL system with conversational capabilities.

## Features

- **Conversational Interface**: Ask follow-up questions with full context memory
- **Real-time SQL Generation**: See the generated SQL queries
- **Results Display**: View query results with expandable details
- **Database Explorer**: Check schema, tables, and backend health
- **Error Handling**: Clear error messages and explanations

## Setup

### 1. Install Dependencies

```bash
cd frontend
pip install -r requirements.txt
```

Or use a virtual environment:

```bash
cd frontend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Start the Backend

The frontend requires the backend API to be running:

```bash
cd ../backend
python app.py
```

The backend should be running at `http://localhost:8000`

### 3. Run the Frontend

```bash
streamlit run app.py
```

The frontend will open automatically in your browser at `http://localhost:8501`

## Usage

### Basic Queries

1. Type a natural language question in the text area
2. Click "Run" to execute
3. View the generated SQL, results, and explanation

**Example queries:**
- "How many customers do we have?"
- "Show me the first 5 products"
- "What's the total from all orders?"

### Conversational Queries

The system maintains conversation context, allowing follow-up questions:

```
You: "How many customers do we have?"
Bot: [Shows 150 customers]

You: "What about orders?"
Bot: [Understands you want a count of orders, shows 523 orders]

You: "Show me the top 10 by amount"
Bot: [Knows you're talking about orders, shows top 10]
```

### Sidebar Features

**Backend Configuration:**
- Set backend API URL (default: `http://localhost:8000`)
- Test connection with "Test Backend Connection" button

**Database Info:**
- AWS/Model settings are for display only (configured in backend)
- Database connection is managed by backend (SQLite)

**Backend Information:**
- "Get Database Schema" - View all tables and columns
- "Check Backend Health" - Verify backend is running

### Clear Conversation

Click "Clear Conversation" to reset the chat history and start fresh.

## Architecture

```
User Input
    ↓
Streamlit Frontend (port 8501)
    ↓ HTTP POST /query
    ↓ (includes conversation_history)
FastAPI Backend (port 8000)
    ↓
AWS Bedrock (Claude)
    ↓
SQL Generation
    ↓
SQLite Database
    ↓
Results + Explanation
    ↓
Display to User
```

## Conversation History

The frontend automatically maintains two types of history:

1. **Display History**: What you see in the UI (formatted messages)
2. **API History**: Sent to backend for context (user/assistant messages)

This enables Claude to understand context and answer follow-up questions intelligently.

## Customization

### Change Backend URL

In the sidebar, update the "Backend API URL" field to point to your backend.

### Styling

The UI matches the original agent design with:
- Sidebar configuration
- Two-column layout for buttons
- Expandable results
- Clear conversation display

## Troubleshooting

### "Could not connect to backend"
- Ensure backend is running: `cd backend && python app.py`
- Check backend URL in sidebar (default: `http://localhost:8000`)
- Test connection with "Test Backend Connection" button

### "Request timed out"
- Complex queries may take longer
- Check backend logs for errors
- Ensure AWS Bedrock credentials are configured

### No conversation context
- Make sure you're not clicking "Clear Conversation" between queries
- Check that conversation_history is being sent (visible in browser console)

## Development

### Running Locally

```bash
# Terminal 1: Backend
cd backend
source venv/bin/activate
python app.py

# Terminal 2: Frontend
cd frontend
source venv/bin/activate
streamlit run app.py
```

### Testing

Try these example conversations to test context:

```
1. "How many products are there?"
2. "Show me 3 examples"
3. "What categories do they belong to?"
```

## Production Deployment

For production deployment:

1. **Backend**: Deploy FastAPI to EC2, Lambda, or container service
2. **Frontend**: Deploy Streamlit to Streamlit Cloud, Heroku, or container
3. **Update CORS**: Configure backend CORS to allow frontend domain
4. **Update URL**: Set backend URL in frontend sidebar

## License

MIT
