import boto3
import botocore
import time
from typing import Optional, Tuple, Dict, Any, List

# Default configuration for Bedrock usage in this app
DEFAULT_REGION = "us-west-2"
# Keep model ID in standard Bedrock format (region is not part of the modelId)
DEFAULT_MODEL_ID = "anthropic.claude-4-sonnet-2025-05-14-v1:0"


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

def generate_weather_api_calls(location):
    """
    Use Claude to intelligently generate National Weather Service API calls for a given location.
    This is where the "agentic" magic happens - AI planning the API calls.
    
    Args:
        location (str): The location provided by the user
    
    Returns:
        tuple: (success: bool, api_calls: list) - success status and list of API URLs or error message
    """
    # Create a detailed prompt that teaches Claude how to generate NWS API calls
    prompt = f"""
You are an expert at working with the National Weather Service (NWS) API.

Your task: Generate the NWS API URL to get weather forecast data for "{location}".

Instructions:
1. First, determine the approximate latitude and longitude coordinates for this location
2. Generate the NWS Points API URL: https://api.weather.gov/points/{{lat}},{{lon}}

For the coordinates, use your knowledge to estimate:
- Major cities: Use well-known coordinates
- ZIP codes: Estimate based on the area
- States: Use approximate center coordinates
- In case a location description is provided instead of a location name, please use the most likely city and state name as the location for the coordinates

Example for Seattle:
https://api.weather.gov/points/47.6062,-122.3321

Example for largest city in USA:
Based on your knowledge, you will establish location is New York City
https://api.weather.gov/points/40.7128,-74.0060

Now generate the API call (Points API) for the established location. 
Return ONLY the complete Points API URL, nothing else.
Format: https://api.weather.gov/points/LAT,LON
"""
    
    print(f"🧠 AI is analyzing '{location}' and generating weather API calls...")
    success, response = call_claude_sonnet(prompt)
    
    if success:
        # Clean up the response - sometimes Claude adds extra text
        api_url = response.strip()
        # Make sure we got a valid URL
        if api_url.startswith('https://api.weather.gov/points/'):
            return True, [api_url]  # Return as list for consistency
        else:
            return False, f"AI generated invalid URL: {api_url}"
    else:
        return False, response

def get_forecast_url_from_points_response(points_json):
    """
    Extract the forecast URL from the NWS Points API response.
    
    Args:
        points_json (str): JSON response from the Points API
    
    Returns:
        tuple: (success: bool, forecast_url: str) - success status and forecast URL or error message
    """
    try:
        data = json.loads(points_json)
        forecast_url = data['properties']['forecast']
        return True, forecast_url
    except (json.JSONDecodeError, KeyError) as e:
        return False, f"Error parsing Points API response: {str(e)}"

def process_weather_response(raw_json, location):
    """
    Use Claude to convert raw NWS API JSON into a human-readable weather summary.
    This is where AI processes complex data into useful information.
    
    Args:
        raw_json (str): Raw JSON response from NWS API
        location (str): Original location for context
    
    Returns:
        tuple: (success: bool, summary: str) - success status and processed summary or error message
    """
    prompt = f"""
You are a weather information specialist. I have raw National Weather Service forecast data for "{location}" that needs to be converted into a clear, helpful summary for a general audience.

Raw NWS API Response:
{raw_json}

Please create a weather summary that includes:
1. A brief introduction with the location
2. Current conditions and today's forecast
3. The next 2-3 days outlook with key details (temperature, precipitation, wind)
4. Any notable weather patterns or alerts
5. Format the response to be easy to read and understand

Make it informative and practical for someone planning their activities. Focus on being helpful and clear.
"""
    
    print(f"📊 AI is processing weather data and creating summary...")
    success, response = call_claude_sonnet(prompt)
    
    return success, response

def make_bedrock_client(region_name: str, profile_name: Optional[str] = None):
    """
    Create a Bedrock Runtime client and immediately validate AWS credentials/permissions.

    We validate using the Bedrock control-plane `list_foundation_models`, which is a
    lightweight, free call that requires correct region/credentials and Bedrock access.
    Any error (bad profile, missing permissions, region without Bedrock, network issues)
    will raise and be surfaced to the UI.
    """
    # Build a session from the requested profile/region
    if profile_name:
        session = boto3.Session(profile_name=profile_name, region_name=region_name)
    else:
        session = boto3.Session(region_name=region_name)

    # Create the runtime client we will return
    runtime_client = session.client("bedrock-runtime", region_name=region_name)

    # Validate credentials/permissions against the control-plane
    control_client = session.client("bedrock", region_name=region_name)
    success, response = call_claude_sonnet("Hello! Are you working today?")

    if success:
        print("✅ Connection successful!")
        print(f"Claude says: {response}")
    else:
        print("❌ Connection failed!")
        print(f"Error: {response}")
        raise

    # try:
    #     # Low-cost call; also confirms the service is available in this region
    #     control_client.list_foundation_models(maxResults=1)
    # except Exception:
    #     # Propagate any error so the caller can show an appropriate message
    #     raise

    return runtime_client


def extract_text_from_message(message: Dict[str, Any]) -> str:
    parts = message.get("content", []) or []
    texts: List[str] = []
    for p in parts:
        if isinstance(p, dict) and "text" in p:
            texts.append(p["text"])
    return "\n".join(texts).strip()


def call_model(client, prompt: str,
               system: Optional[str] = None,
               model_id: str = DEFAULT_MODEL_ID,
               max_tokens: int = 2000,
               temperature: float = 0.4,
               top_p: float = 0.9,
               retries: int = 3) -> Tuple[bool, str]:
    messages = [{"role": "user", "content": [{"text": prompt}]}]

    attempt = 0
    while True:
        try:
            resp = client.converse(
                modelId=model_id,
                system=[{"text": system}] if system else None,
                messages=messages,
                inferenceConfig={
                    "maxTokens": max_tokens,
                    "temperature": temperature,
                    "topP": top_p,
                },
            )
            msg = resp["output"]["message"]
            return True, extract_text_from_message(msg)
        except botocore.exceptions.BotoCoreError as e:
            attempt += 1
            if attempt > retries:
                return False, f"Bedrock call failed after {retries} retries: {e}"
            time.sleep(2 ** attempt)
        except Exception as e:
            return False, f"Unexpected error: {e}"