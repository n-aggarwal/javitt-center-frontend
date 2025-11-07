from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
from dotenv import load_dotenv

from services.database import DatabaseService
from services.bedrock_client import BedrockClient
from services.agentic_workflow import AgenticWorkflow

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Natural Language to SQL API (Agentic)",
    description="Convert natural language queries to SQL using AWS Bedrock with agentic workflow",
    version="2.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
DATABASE_PATH = os.getenv("DATABASE_PATH", "nl2sql_demo.sqlite")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")
CACHE_DIR = os.getenv("CACHE_DIR", ".cache")

db_service = DatabaseService(DATABASE_PATH)
bedrock_client = BedrockClient(AWS_REGION, BEDROCK_MODEL_ID)

# Initialize agentic workflow (replaces query_processor)
agentic_workflow = AgenticWorkflow(
    db_service=db_service,
    bedrock_client=bedrock_client,
    db_path=DATABASE_PATH,
    cache_dir=CACHE_DIR
)


# Request/Response Models
class NaturalLanguageQuery(BaseModel):
    query: str
    include_explanation: bool = True
    conversation_history: List[Dict[str, Any]] = []


class DirectSQLQuery(BaseModel):
    sql: str


# API Endpoints
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Natural Language to SQL API (Agentic Workflow)",
        "version": "2.0.0",
        "description": "Agentic workflow with schema extraction, analysis, and data dictionary generation",
        "endpoints": {
            "POST /query": "Convert natural language to SQL and execute",
            "POST /execute": "Execute SQL query directly",
            "GET /database/info": "Get database schema and information",
            "GET /database/tables": "List all tables",
            "GET /database/schema": "Get the database schema",
            "POST /schema/initialize": "Initialize or refresh schema and data dictionary",
            "GET /schema/cache-info": "Get cache status information",
            "GET /health": "Health check"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check if database is accessible
        tables = db_service.get_all_tables()
        return {
            "status": "healthy",
            "database": "connected",
            "tables_count": len(tables)
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


@app.post("/query")
async def process_query(query_data: NaturalLanguageQuery):
    """
    Process a natural language query with conversation context.

    Uses the agentic workflow to:
    1. Automatically use cached schema and data dictionary
    2. Generate SQL using AWS Bedrock
    3. Execute the query
    4. Return results with optional explanation

    The schema and data dictionary are initialized once on first use and cached.
    """
    try:
        result = agentic_workflow.process_query(
            query_data.query,
            include_explanation=query_data.include_explanation,
            conversation_history=query_data.conversation_history
        )

        if not result["success"]:
            return {
                "success": False,
                "error": result["error"],
                "query": result["query"],
                "sql": result["sql"],
                "explanation": result.get("explanation")
            }

        return {
            "success": True,
            "query": result["query"],
            "sql": result["sql"],
            "results": result["results"],
            "columns": result["columns"],
            "row_count": len(result["results"]),
            "explanation": result.get("explanation")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/execute")
async def execute_sql(query_data: DirectSQLQuery):
    """
    Execute a SQL query directly without using Bedrock.

    Useful for testing or when you already have a SQL query.
    """
    try:
        result = agentic_workflow.execute_direct_sql(query_data.sql)

        if not result["success"]:
            return {
                "success": False,
                "error": result["error"],
                "sql": result["sql"]
            }

        return {
            "success": True,
            "sql": result["sql"],
            "results": result["results"],
            "columns": result["columns"],
            "row_count": len(result["results"])
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/database/info")
async def get_database_info():
    """
    Get comprehensive database information.

    Returns raw schema, structured schema, data dictionary, and sample data.
    Schema and data dictionary are generated once and cached.
    """
    try:
        info = agentic_workflow.get_database_info()
        return info

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/database/tables")
async def get_tables():
    """Get list of all tables in the database."""
    try:
        tables = db_service.get_all_tables()
        return {
            "tables": tables,
            "count": len(tables)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/database/schema")
async def get_schema():
    """Get the database schema as a formatted string."""
    try:
        schema = db_service.get_schema()
        return {
            "schema": schema
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SchemaInitializeRequest(BaseModel):
    force_refresh: bool = False


@app.post("/schema/initialize")
async def initialize_schema(request: SchemaInitializeRequest = SchemaInitializeRequest()):
    """
    Initialize or refresh schema and data dictionary.

    This endpoint runs the agentic workflow to:
    1. Extract schema from database
    2. Analyze schema with Bedrock
    3. Generate data dictionary with Bedrock
    4. Cache all results

    Args:
        force_refresh: If True, regenerate even if cache exists
    """
    try:
        result = agentic_workflow.initialize_schema(force_refresh=request.force_refresh)
        return {
            "success": True,
            "message": "Schema initialized successfully" if not request.force_refresh else "Schema refreshed successfully",
            "data": result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/schema/cache-info")
async def get_cache_info():
    """
    Get information about the schema cache status.

    Returns cache metadata, file paths, and status information.
    """
    try:
        info = agentic_workflow.get_cache_info()
        return info

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 8000))

    print(f"Starting Natural Language to SQL API on {host}:{port}")
    print(f"Database: {DATABASE_PATH}")
    print(f"AWS Region: {AWS_REGION}")
    print(f"Bedrock Model: {BEDROCK_MODEL_ID}")

    uvicorn.run(app, host=host, port=port)
