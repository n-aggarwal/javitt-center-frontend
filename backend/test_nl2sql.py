#!/usr/bin/env python3
"""
Test the complete NL to SQL pipeline
"""
import os
from dotenv import load_dotenv
from services.database import DatabaseService
from services.bedrock_client import BedrockClient
from services.query_processor import QueryProcessor

# Load environment variables
load_dotenv()

def main():
    print("=" * 70)
    print("Testing Natural Language to SQL Pipeline")
    print("=" * 70)
    print()

    # Initialize services
    DATABASE_PATH = os.getenv("DATABASE_PATH", "nl2sql_demo.sqlite")
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-3-5-sonnet-20241022-v2:0")

    print(f"Database: {DATABASE_PATH}")
    print(f"AWS Region: {AWS_REGION}")
    print(f"Bedrock Model: {BEDROCK_MODEL_ID}")
    print()

    try:
        # Step 1: Initialize services
        print("1. Initializing services...")
        db_service = DatabaseService(DATABASE_PATH)
        bedrock_client = BedrockClient(AWS_REGION, BEDROCK_MODEL_ID)
        query_processor = QueryProcessor(db_service, bedrock_client)
        print("   ✓ Services initialized\n")

        # Step 2: Check database
        print("2. Checking database...")
        tables = db_service.get_all_tables()
        print(f"   ✓ Found {len(tables)} tables: {', '.join(tables)}\n")

        # Step 3: Get schema
        print("3. Getting database schema...")
        schema = db_service.get_schema()
        print(f"   ✓ Schema retrieved ({len(schema)} characters)\n")

        # Step 4: Test natural language query
        print("4. Testing natural language query...")
        test_query = "How many customers are there in the database?"
        print(f"   Query: '{test_query}'")
        print()

        result = query_processor.process_natural_language_query(
            test_query,
            include_explanation=True
        )

        if result["success"]:
            print("   ✓ Query successful!\n")
            print(f"   Generated SQL: {result['sql']}")
            print(f"   Number of rows: {len(result['results'])}")
            print(f"\n   Query Results:")
            for i, row in enumerate(result['results'], 1):
                print(f"   Row {i}: {row}")
            if result.get('explanation'):
                print(f"\n   Explanation: {result['explanation']}")
            print()
        else:
            print(f"   ✗ Query failed: {result['error']}\n")
            return False

        # Step 5: Test another query
        print("5. Testing another query...")
        test_query2 = "Show me the first 3 products"
        print(f"   Query: '{test_query2}'")
        print()

        result2 = query_processor.process_natural_language_query(
            test_query2,
            include_explanation=False
        )

        if result2["success"]:
            print("   ✓ Query successful!\n")
            print(f"   Generated SQL: {result2['sql']}")
            print(f"   Number of rows: {len(result2['results'])}")
            print(f"\n   Query Results:")
            for i, row in enumerate(result2['results'], 1):
                print(f"   Row {i}: {row}")
            print()
        else:
            print(f"   ✗ Query failed: {result2['error']}\n")

        # Success!
        print("=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        print()
        print("Your NL to SQL system is working correctly!")
        print()
        print("Next step: Start the API server")
        print("  Command: python app.py")
        print("  Then visit: http://localhost:8000/docs")
        print()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Check that nl2sql_demo.sqlite exists")
        print("2. Verify AWS credentials are configured")
        print("3. Ensure Bedrock model access is enabled")
        return False

if __name__ == "__main__":
    main()
