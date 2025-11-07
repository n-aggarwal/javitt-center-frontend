# Agentic Workflow Documentation

## Overview

This application implements an **agentic workflow** for natural language to SQL conversion using AWS Bedrock (Claude). The workflow consists of multiple specialized agents that work together to provide intelligent query processing.

## Architecture

### Key Components

1. **SchemaCache** (`services/schema_cache.py`)
   - Manages caching of schema and data dictionary
   - Uses MD5 hashing to detect database changes
   - Stores cache files in `.cache/` directory

2. **SchemaInitializer** (`services/schema_initializer.py`)
   - Orchestrates the initialization workflow
   - Runs three agents sequentially on database load
   - Manages cache lifecycle

3. **AgenticWorkflow** (`services/agentic_workflow.py`)
   - Main service for query processing
   - Ensures schema is initialized before queries
   - Provides interface for all operations

4. **BedrockClient** (`services/bedrock_client.py`)
   - AWS Bedrock API client
   - Provides AI-powered analysis and generation

5. **DatabaseService** (`services/database.py`)
   - SQLite database operations
   - Schema extraction
   - Query execution

## Agent Workflow

### Initialization Phase (Runs Once on DB Load)

#### Agent 1: Schema Extraction Agent
- **Purpose**: Extract raw schema and sample data from database
- **Input**: SQLite database file
- **Output**:
  - Raw schema string
  - Sample data (5 rows from each table)
- **Cache**: Saved to `.cache/{db_name}_{hash}_raw_schema.json`

#### Agent 2: Schema Analysis Agent
- **Purpose**: Analyze schema using AWS Bedrock to understand structure
- **Input**: Raw schema + sample data
- **Process**: Uses Claude to analyze:
  - Table purposes
  - Column meanings
  - Relationships (foreign keys, implied relationships)
  - Data patterns
- **Output**: Structured schema JSON
- **Cache**: Saved to `.cache/{db_name}_{hash}_structured_schema.json`

#### Agent 3: Data Dictionary Generation Agent
- **Purpose**: Generate comprehensive data dictionary
- **Input**: Structured schema + sample data
- **Process**: Uses Claude to infer:
  - Business rules
  - Column descriptions
  - Valid value ranges
  - Naming conventions
- **Output**: Human-readable data dictionary
- **Cache**: Saved to `.cache/{db_name}_{hash}_data_dictionary.json`

### Query Phase (Runs on Each Query)

#### Agent 4: Query Agent
- **Purpose**: Convert natural language to SQL and execute
- **Input**:
  - Natural language query
  - Cached schema
  - Cached data dictionary
  - Conversation history (optional)
- **Process**:
  1. Load cached schema and data dictionary
  2. Generate SQL using Bedrock with full context
  3. Execute SQL query
  4. Generate natural language explanation (optional)
- **Output**: Query results with explanation

## Cache Management

### Cache Directory Structure
```
.cache/
├── {db_name}_{db_hash}_raw_schema.json
├── {db_name}_{db_hash}_structured_schema.json
└── {db_name}_{db_hash}_data_dictionary.json
```

### Cache Invalidation
- Automatic: Cache is invalidated when database file changes (MD5 hash changes)
- Manual: Use `/schema/initialize` endpoint with `force_refresh: true`

## API Endpoints

### Query Endpoints

**POST /query**
- Process natural language query
- Automatically initializes schema on first use
- Returns SQL, results, and optional explanation

**POST /execute**
- Execute SQL directly without Bedrock
- Useful for testing

### Schema Management Endpoints

**POST /schema/initialize**
- Manually initialize or refresh schema
- Parameters:
  - `force_refresh`: boolean (default: false)
- Use cases:
  - Force refresh after database changes
  - Pre-initialize schema on startup

**GET /schema/cache-info**
- Get cache status and metadata
- Returns:
  - Cache file locations
  - File sizes
  - Database hash
  - Cache completeness status

**GET /database/info**
- Get complete database information
- Returns:
  - Raw schema
  - Structured schema
  - Data dictionary
  - Sample data

## Usage Examples

### Starting the Application

```bash
cd backend
python app.py
```

The agentic workflow will automatically initialize the schema on the first query.

### Pre-initializing Schema (Recommended)

```bash
curl -X POST http://localhost:8000/schema/initialize
```

This runs the initialization workflow before handling any queries, which:
- Improves first query response time
- Allows you to verify schema analysis
- Validates Bedrock connectivity

### Querying with Natural Language

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show me all customers who placed orders in the last month",
    "include_explanation": true
  }'
```

### Force Refresh Schema

```bash
curl -X POST http://localhost:8000/schema/initialize \
  -H "Content-Type: application/json" \
  -d '{"force_refresh": true}'
```

### Check Cache Status

```bash
curl http://localhost:8000/schema/cache-info
```

## Benefits of Agentic Workflow

1. **Performance**: Schema and data dictionary computed once, cached indefinitely
2. **Accuracy**: Rich context (schema + data dictionary + business rules) improves SQL generation
3. **Intelligence**: Bedrock analyzes schema to understand relationships and patterns
4. **Scalability**: Cache persists across server restarts
5. **Maintainability**: Clear separation of concerns with specialized agents

## Performance Considerations

### First Query (Cold Start)
- ~5-10 seconds (depends on database size and Bedrock latency)
- Runs all 3 initialization agents
- Creates cache files

### Subsequent Queries
- ~1-2 seconds (normal Bedrock latency)
- Uses cached schema and data dictionary
- No re-analysis needed

### Cache Size
- Typically < 100KB for most databases
- Grows linearly with number of tables/columns

## Troubleshooting

### Cache Issues
- Check cache directory permissions
- Verify `.cache/` directory exists
- Use `/schema/cache-info` to check cache status

### Bedrock Errors
- Verify AWS credentials in `.env`
- Check Bedrock model availability in region
- Review CloudWatch logs for API errors

### Schema Not Updating
- Database changes don't auto-refresh
- Use `force_refresh: true` to regenerate
- Or delete `.cache/` directory

## Configuration

### Environment Variables

```bash
DATABASE_PATH=nl2sql_demo.sqlite
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
CACHE_DIR=.cache
```

## Future Enhancements

- [ ] Support for multiple databases
- [ ] Incremental cache updates
- [ ] Vector embeddings for semantic search
- [ ] Query result caching
- [ ] Analytics on query patterns
- [ ] Auto-refresh on schema changes detection
