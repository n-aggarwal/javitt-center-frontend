# Natural Language to SQL Backend

This backend converts natural language queries to SQL using AWS Bedrock and executes them against a SQLite database.

## Architecture

```
backend/
├── app.py                          # FastAPI application
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment variables template
├── nl2sql_demo.sqlite             # SQLite database
└── services/
    ├── __init__.py
    ├── database.py                # SQLite operations
    ├── bedrock_client.py          # AWS Bedrock integration
    └── query_processor.py         # Query orchestration
```

## Setup

### 1. Create a virtual environment (recommended)

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and add your AWS credentials:

```env
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
DATABASE_PATH=nl2sql_demo.sqlite
API_HOST=0.0.0.0
API_PORT=8000
```

### 4. Start the server

```bash
python app.py
```

Or use uvicorn directly:

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Endpoints

### GET /
Root endpoint with API information.

### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "tables_count": 3
}
```

### POST /query
Convert natural language to SQL and execute.

**Request:**
```json
{
  "query": "How many patients do we have?",
  "include_explanation": true
}
```

**Response:**
```json
{
  "success": true,
  "query": "How many patients do we have?",
  "sql": "SELECT COUNT(*) as patient_count FROM patients",
  "results": [{"patient_count": 150}],
  "columns": ["patient_count"],
  "row_count": 1,
  "explanation": "The database contains 150 patients in total."
}
```

### POST /execute
Execute SQL query directly (without Bedrock).

**Request:**
```json
{
  "sql": "SELECT * FROM patients LIMIT 5"
}
```

**Response:**
```json
{
  "success": true,
  "sql": "SELECT * FROM patients LIMIT 5",
  "results": [...],
  "columns": ["id", "name", "age", ...],
  "row_count": 5
}
```

### GET /database/info
Get database schema, tables, and sample data.

**Response:**
```json
{
  "tables": ["patients", "appointments", "doctors"],
  "schema": "Database Schema:\n\nTable: patients\n...",
  "sample_data": {
    "patients": [...]
  }
}
```

### GET /database/tables
List all tables in the database.

**Response:**
```json
{
  "tables": ["patients", "appointments", "doctors"],
  "count": 3
}
```

### GET /database/schema
Get the database schema as formatted text.

**Response:**
```json
{
  "schema": "Database Schema:\n\nTable: patients\n  - id (INTEGER) PRIMARY KEY\n  - name (TEXT) NOT NULL\n..."
}
```

## Testing the API

### Using curl

```bash
# Health check
curl http://localhost:8000/health

# Natural language query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me all patients", "include_explanation": true}'

# Direct SQL execution
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT * FROM patients LIMIT 5"}'

# Get database info
curl http://localhost:8000/database/info
```

### Using Python

```python
import requests

# Natural language query
response = requests.post(
    "http://localhost:8000/query",
    json={
        "query": "How many appointments are scheduled for today?",
        "include_explanation": True
    }
)
print(response.json())
```

### Using the Interactive API Docs

Navigate to `http://localhost:8000/docs` for the interactive Swagger UI documentation where you can test all endpoints.

## How It Works

1. **User sends natural language query** → POST /query endpoint
2. **Backend extracts database schema** → from SQLite
3. **Schema + Query sent to AWS Bedrock** → Claude generates SQL
4. **SQL is validated** → Only SELECT queries allowed
5. **SQL executed against SQLite** → Results retrieved
6. **Results + Query sent back to Bedrock** → Natural language explanation generated
7. **Response returned to user** → With SQL, results, and explanation

## Security Features

- **Read-only queries**: Only SELECT statements are allowed
- **SQL validation**: Dangerous operations (DROP, DELETE, UPDATE, etc.) are blocked
- **Error handling**: Graceful error messages for invalid queries
- **CORS enabled**: Configure origins in production

## AWS Bedrock Models

The default model is Claude 3.5 Sonnet, which provides excellent SQL generation capabilities. You can change the model in `.env`:

```env
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
```

Available models:
- `anthropic.claude-3-5-sonnet-20241022-v2:0` (recommended)
- `anthropic.claude-3-sonnet-20240229-v1:0`
- `anthropic.claude-3-haiku-20240307-v1:0`

## Troubleshooting

### AWS Credentials Error
Make sure your AWS credentials are properly configured in `.env` and have access to AWS Bedrock.

### Database Not Found
Ensure `nl2sql_demo.sqlite` exists in the backend directory and the path in `.env` is correct.

### Import Errors
Make sure you've installed all dependencies: `pip install -r requirements.txt`

### Bedrock Access Denied
Your AWS account needs access to AWS Bedrock. Request access in the AWS Console if needed.

## Development

To run in development mode with auto-reload:

```bash
uvicorn app:app --reload
```

## License

MIT
