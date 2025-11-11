# Natural Language to SQL with RAG

> AI-powered SQL query generation using AWS Bedrock and Retrieval-Augmented Generation

## Demo: https://drive.google.com/file/d/167DM_eJb-sea7svHPTWDAYsI-Gm5SGpM/view?usp=sharing

## What It Does

Ask questions in plain English, get SQL queries and results automatically. The system uses RAG (Retrieval-Augmented Generation) to learn from similar examples and generate more accurate SQL queries.

**Example:**
- You ask: *"How many customers do we have?"*
- It generates: `SELECT COUNT(*) FROM customers`
- Returns the answer with explanation

## Features

-  **Natural Language to SQL** - Ask questions in plain English
-  **RAG-Enhanced** - Learns from 50+ example queries for better accuracy
-  **Auto Schema Analysis** - Automatically understands your database structure
-  **Conversational** - Maintains context across multiple questions
-  **Fast** - Caches schema and embeddings for quick responses

## Tech Stack

- **Backend:** FastAPI + AWS Bedrock (Claude 3.5 Sonnet)
- **Frontend:** Streamlit
- **Database:** SQLite
- **RAG:** Sentence-Transformers + FAISS
- **AI:** AWS Bedrock Claude 3.5 Sonnet v2

## Quick Start

### Prerequisites

- Python 3.8+
- AWS Account with Bedrock access
- AWS credentials configured

### Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd javitt-center-frontend

# Install backend dependencies
cd backend
pip install -r requirements.txt

# Configure AWS credentials
aws configure
# Enter your AWS Access Key ID and Secret Access Key
```

### Running the App

**Terminal 1 - Backend:**
```bash
cd backend
python app.py
# Runs on http://localhost:8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
streamlit run app.py
# Runs on http://localhost:8501


### Open the App

Visit **http://localhost:8501** in your browser and start asking questions!

## How It Works

1. **Schema Analysis** - Automatically extracts and analyzes database structure
2. **RAG Retrieval** - Finds similar example queries from vector database
3. **SQL Generation** - Claude generates SQL using schema + similar examples
4. **Query Execution** - Runs the SQL and returns results
5. **Natural Explanation** - Explains results in plain English

## API Endpoints

```
POST   /query                    - Ask a question, get SQL + results
POST   /rag/generate-examples    - Generate 50 example queries
GET    /rag/info                 - View RAG system stats
GET    /rag/examples             - View all example queries
GET    /database/info            - View database schema
GET    /health                   - Health check
```

## Project Structure

```
.
├── backend/
│   ├── app.py                   # FastAPI server
│   ├── services/
│   │   ├── bedrock_client.py    # AWS Bedrock integration
│   │   ├── rag_service.py       # RAG with FAISS
│   │   ├── example_generator.py # Auto-generate examples
│   │   └── agentic_workflow.py  # Main orchestration
│   ├── data/                    # RAG examples storage
│   └── nl2sql_demo.sqlite       # Demo database
└── frontend/
    └── app.py                   # Streamlit UI
```

## AWS Setup

1. Create AWS account at https://aws.amazon.com
2. Go to IAM → Create user with `AmazonBedrockFullAccess`
3. Generate access keys
4. Enable Bedrock model access for Claude 3.5 Sonnet v2
5. Run `aws configure` and enter credentials

## Built For

AWS Bedrock Hackathon

## License

MIT
