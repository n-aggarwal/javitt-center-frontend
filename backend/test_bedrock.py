#!/usr/bin/env python3
"""
Test script to verify AWS Bedrock access and Claude model availability
"""
import boto3
import json
import sys


def test_bedrock_access():
    """Test if we can access Bedrock service"""
    print("=" * 60)
    print("Testing AWS Bedrock Access")
    print("=" * 60)

    try:
        client = boto3.client('bedrock', region_name='us-east-1')
        models = client.list_foundation_models()
        print("✓ Bedrock service is accessible")
        print(f"✓ Found {len(models['modelSummaries'])} total models\n")
        return True
    except Exception as e:
        print(f"✗ Cannot access Bedrock service")
        print(f"Error: {e}\n")
        return False


def check_claude_models():
    """Check which Claude models are available"""
    print("Checking for Claude/Anthropic models...")
    print("-" * 60)

    try:
        client = boto3.client('bedrock', region_name='us-east-1')
        models = client.list_foundation_models()

        claude_models = [
            m for m in models['modelSummaries']
            if 'anthropic' in m['modelId'].lower()
        ]

        if claude_models:
            print(f"✓ Found {len(claude_models)} Claude models:\n")
            for model in claude_models:
                print(f"  • {model['modelId']}")
                print(f"    Name: {model.get('modelName', 'N/A')}")
                print(f"    Provider: {model.get('providerName', 'N/A')}")
                print()
            return True
        else:
            print("✗ No Claude models found")
            print("You need to request model access in AWS Console:")
            print("AWS Console → Bedrock → Model access → Manage model access\n")
            return False

    except Exception as e:
        print(f"✗ Error checking models: {e}\n")
        return False


def test_claude_invoke():
    """Test actually invoking Claude model"""
    print("Testing Claude model invocation...")
    print("-" * 60)

    model_id = 'us.anthropic.claude-3-5-sonnet-20241022-v2:0'

    try:
        client = boto3.client('bedrock-runtime', region_name='us-east-1')

        request = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 100,
            "messages": [
                {
                    "role": "user",
                    "content": "Say hello in one sentence"
                }
            ],
            "temperature": 0.7
        }

        print(f"Invoking model: {model_id}")

        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(request)
        )

        result = json.loads(response['body'].read())
        claude_response = result['content'][0]['text']

        print("✓ Claude invocation successful!\n")
        print(f"Claude's response: {claude_response}\n")
        return True

    except client.exceptions.AccessDeniedException:
        print(f"✗ Access denied to model: {model_id}")
        print("You need to request access to this model:")
        print("AWS Console → Bedrock → Model access → Enable Claude models\n")
        return False
    except Exception as e:
        print(f"✗ Error invoking Claude: {e}")
        print(f"Error type: {type(e).__name__}\n")
        return False


def test_sql_generation():
    """Test SQL generation (simplified version of what your app does)"""
    print("Testing SQL generation capability...")
    print("-" * 60)

    try:
        client = boto3.client('bedrock-runtime', region_name='us-east-1')

        schema = """
Table: patients
  - id (INTEGER) PRIMARY KEY
  - name (TEXT)
  - age (INTEGER)
"""

        prompt = f"""You are a SQL expert. Given a database schema and a natural language question, generate a valid SQLite query.

{schema}

User Question: How many patients are over 65 years old?

Generate ONLY the SQL query, no explanations.

SQL Query:"""

        request = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 500,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1
        }

        response = client.invoke_model(
            modelId='us.anthropic.claude-3-5-sonnet-20241022-v2:0',
            body=json.dumps(request)
        )

        result = json.loads(response['body'].read())
        sql = result['content'][0]['text'].strip()

        print("✓ SQL generation successful!\n")
        print(f"Generated SQL: {sql}\n")
        return True

    except Exception as e:
        print(f"✗ Error generating SQL: {e}\n")
        return False


def main():
    """Run all tests"""
    print("\n")

    # Test 1: Bedrock Access
    if not test_bedrock_access():
        print("❌ Bedrock is not accessible. Check AWS credentials.\n")
        sys.exit(1)

    # Test 2: Claude Models
    if not check_claude_models():
        print("❌ Claude models not available. Enable them in AWS Console.\n")
        sys.exit(1)

    # Test 3: Invoke Claude
    if not test_claude_invoke():
        print("❌ Cannot invoke Claude. Check model access permissions.\n")
        sys.exit(1)

    # Test 4: SQL Generation
    if not test_sql_generation():
        print("❌ SQL generation failed.\n")
        sys.exit(1)

    # All tests passed
    print("=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print("Your backend is ready to use AWS Bedrock.\n")
    print("Next steps:")
    print("1. Set up your .env file (copy from .env.example)")
    print("2. Run: python app.py")
    print("3. Test API at: http://localhost:8000/docs")
    print()


if __name__ == "__main__":
    main()
