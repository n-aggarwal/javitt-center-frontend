"""
Test script for the agentic workflow.

This script tests:
1. Schema cache initialization
2. Schema analysis with Bedrock
3. Data dictionary generation
4. Query processing with cached data
"""
import os
from dotenv import load_dotenv
from services.database import DatabaseService
from services.bedrock_client import BedrockClient
from services.agentic_workflow import AgenticWorkflow

# Load environment variables
load_dotenv()

DATABASE_PATH = os.getenv("DATABASE_PATH", "nl2sql_demo.sqlite")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")
CACHE_DIR = ".cache"

print("=" * 80)
print("Testing Agentic Workflow")
print("=" * 80)

# Initialize services
print("\n1. Initializing services...")
db_service = DatabaseService(DATABASE_PATH)
bedrock_client = BedrockClient(AWS_REGION, BEDROCK_MODEL_ID)
workflow = AgenticWorkflow(
    db_service=db_service,
    bedrock_client=bedrock_client,
    db_path=DATABASE_PATH,
    cache_dir=CACHE_DIR
)
print("✓ Services initialized")

# Check cache status
print("\n2. Checking cache status...")
cache_info = workflow.get_cache_info()
print(f"   Database: {cache_info['db_path']}")
print(f"   Database hash: {cache_info['db_hash']}")
print(f"   Has complete cache: {cache_info['has_complete_cache']}")

if not cache_info['has_complete_cache']:
    print("\n3. Initializing schema (this may take a minute)...")
    print("   Agent 1: Extracting schema...")
    print("   Agent 2: Analyzing schema with Bedrock...")
    print("   Agent 3: Generating data dictionary with Bedrock...")
    schema_info = workflow.initialize_schema()
    print("✓ Schema initialized successfully")
else:
    print("\n3. Loading schema from cache...")
    schema_info = workflow.get_database_info()
    print("✓ Schema loaded from cache")

# Display schema information
print("\n4. Schema Information:")
print(f"   Tables: {schema_info['tables']}")
print(f"\n   Raw Schema Preview:")
print("   " + schema_info['raw_schema'][:200] + "...")
print(f"\n   Data Dictionary Preview:")
print("   " + schema_info['data_dictionary'][:300] + "...")

# Test query processing
print("\n5. Testing query processing...")
test_queries = [
    "Show me the first 5 customers",
    "How many orders are there?",
    "What is the average order total?"
]

for i, query in enumerate(test_queries, 1):
    print(f"\n   Query {i}: {query}")
    result = workflow.process_query(query, include_explanation=True)

    if result['success']:
        print(f"   ✓ Generated SQL: {result['sql']}")
        print(f"   ✓ Results: {len(result['results'])} rows")
        if result.get('explanation'):
            print(f"   ✓ Explanation: {result['explanation'][:100]}...")
    else:
        print(f"   ✗ Error: {result['error']}")

# Display cache info again
print("\n6. Final cache status:")
cache_info = workflow.get_cache_info()
for cache_type, info in cache_info['cache_files'].items():
    print(f"   {cache_type}:")
    print(f"      Exists: {info['exists']}")
    print(f"      Size: {info['size']} bytes")
    print(f"      Path: {info['path']}")

print("\n" + "=" * 80)
print("Testing Complete!")
print("=" * 80)
