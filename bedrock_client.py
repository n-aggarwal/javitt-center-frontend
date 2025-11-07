import boto3
import botocore
import time
from typing import Optional, Tuple, Dict, Any, List

# Default model id; ensure this exact ID is enabled in your account/region or change in UI
DEFAULT_MODEL_ID = "anthropic.claude-4-sonnet-2025-05-14-v1:0"


def make_bedrock_client(region_name: str, profile_name: Optional[str] = None):
    """
    Create a Bedrock Runtime client. If profile_name is provided, use that AWS profile.
    """
    if profile_name:
        session = boto3.Session(profile_name=profile_name, region_name=region_name)
    else:
        session = boto3.Session(region_name=region_name)
    return session.client("bedrock-runtime", region_name=region_name)


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