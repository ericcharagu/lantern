import requests
from typing import Any
from loguru import logger
from dotenv import load_dotenv
import os

# Load the env
load_dotenv()
# Logger file path
logger.add("./logs/whatsapp.log", rotation="1 week")
# Configuration
API_VERSION = "v22.0"
PHONE_NUMBER_ID: int = int(os.getenv("PHONE_NUMBER_ID", 0))

ACCESS_TOKEN = "EAARQrAKzcHUBPPel9M8KaUkx8n9sDhsh5gD9MV64GNWHs58zDGaxshDMSKrGMuTmZC8cnOlHW8I2tPjZAJIlFQMOIflhQx8AJNXm0gnsx2ot5Yph7C10tFAXhkJHzZAnafbqZC4ZChvOduYBE7FfElw6ojHahUcpkGGTZCTVfAlaLchdYstRNLR6tM6631b5qMwBZChKLvbUd8fZCNJo5fXzAZCxT6HWCEKDNdL924R4OZBHgZD"
@logger.catch
def whatsapp_messenger(llm_text_output: Any, recipient_number:str):
    if not ACCESS_TOKEN:
        raise ValueError("ACCESS_TOKEN is not valid")

    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": f"{recipient_number}",
        "type": "text",
        "text": {
            "body": llm_text_output,
        },
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # Raises exception for HTTP errors
    except requests.exceptions.RequestException as e:
        logger.debug(f"Error making request: {e}")
        if hasattr(e, "response") and e.response:
            logger.debug(f"Error details: {e.response.text}")


# used for testing
# whatsapp_messenger("This is the test for Lantern")
