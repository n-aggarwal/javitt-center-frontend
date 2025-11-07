# Import necessary libraries
import boto3        # AWS SDK for Python - allows us to interact with AWS services
import json         # For handling JSON data
import subprocess   # For running system commands like curl
import time         # For adding delays and timing operations
from datetime import datetime  # For timestamps and date operations
import mysql.connector
from mysql.connector import Error


def call_claude_sonnet(prompt):
    """
    This function sends a prompt to Claude 4.0 Sonnet and gets a response.
    This is the "brain" of our agent - where the AI thinking happens.
    
    Args:
        prompt (str): The question or instruction we want to send to Claude
    
    Returns:
        tuple: (success: bool, response: str) - success status and Claude's response or error message
    """
    # Create a connection to Amazon Bedrock service
    # Bedrock is AWS's service for accessing AI models like Claude
    bedrock = boto3.client(
        service_name='bedrock-runtime',  # Specify we want the runtime version for making AI calls
        region_name='us-west-2'          # AWS region - using us-west-2 as specified
    )
    
    try:
        # Send our prompt to Claude and get a response
        response = bedrock.converse(
            # Specify which version of Claude we want to use
            modelId='us.anthropic.claude-sonnet-4-20250514-v1:0',  # Claude 4.0 Sonnet
            
            # Format our message - Claude expects messages in a specific structure
            messages=[
                {
                    "role": "user",                    # We are the user asking a question
                    "content": [{"text": prompt}]      # Our actual question/prompt
                }
            ],
            
            # Configure how Claude should respond
            inferenceConfig={
                "maxTokens": 2000,    # Maximum length of response (tokens ≈ words)
                "temperature": 0.7,   # Creativity level (0=very focused, 1=very creative)
                "topP": 0.9          # Another creativity control parameter
            }
        )
        
        # Extract the actual text response from Claude's response structure
        # The response comes nested in a complex structure, so we dig down to get the text
        return True, response['output']['message']['content'][0]['text']
        
    except Exception as e:
        # If something goes wrong, return an error message
        return False, f"Error calling Claude: {str(e)}"

# Test our connection to Claude
if __name__ == "__main__":
    print("🧪 Testing connection to Claude 4.0 Sonnet...")
    success, response = call_claude_sonnet("Hello! Are you working today?")
    
    if success:
        print("✅ Connection successful!")
        print(f"Claude says: {response}")
    else:
        print("❌ Connection failed!")
        print(f"Error: {response}")

def execute_curl_command(url):
    """
    Execute a curl command to fetch data from an API.
    This is how our agent "acts" in the real world - making HTTP requests.
    
    Args:
        url (str): The URL to fetch data from
    
    Returns:
        tuple: (success: bool, response: str) - success status and API response or error message
    """
    try:
        # Use curl command to make HTTP request
        # curl is a command-line tool for making HTTP requests
        result = subprocess.run(
            ['curl', '-s', url],  # -s flag makes curl silent (no progress info)
            capture_output=True,   # Capture the output so we can process it
            text=True,            # Return output as text (not bytes)
            timeout=30            # Give up after 30 seconds
        )
        
        # Check if the command was successful
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, f"Curl command failed: {result.stderr}"
            
    except subprocess.TimeoutExpired:
        return False, "Request timed out after 30 seconds"
    except Exception as e:
        return False, f"Error executing curl: {str(e)}"


def connect_to_mysql():
    # Collect MySQL connection info from user
    host = input("Enter MySQL host (default: localhost): ").strip() or "localhost"
    user = input("Enter MySQL username: ").strip()
    password = input("Enter MySQL password: ").strip()
    database = input("Enter database name (optional): ").strip()
    
    try:
        # Connect to MySQL
        conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database if database else None
        )

        if conn.is_connected():
            print("✅ Successfully connected to MySQL!")
            return conn

    except Error as e:
        print(f"❌ Error: {e}")
        return None


# Example usage:
if __name__ == "__main__":
    connection = connect_to_mysql()
    if connection:
        connection.close()
