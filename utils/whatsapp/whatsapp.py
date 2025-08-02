import requests
from typing import Any
from loguru import logger
from dotenv import load_dotenv
import os

# Load the env
load_dotenv()
# Logger file path
logger.add("./logs/whatsapp.log", rotation="700 MB")
# Configuration
API_VERSION = "v22.0"
PHONE_NUMBER_ID: int = int(os.getenv("PHONE_NUMBER_ID", 0))

# TODO:To be moved to secrets duting prod and when permanent Token acquired
ACCESS_TOKEN = "EAARQrAKzcHUBPKmq2aZCdE7PKgkZCQ7pAqK52fGY37G7fSlr6q1aoCgHqgsNNjpjwhMJ0do3im8eT4Uw9ZAgjB35epJuxh5OPOo0jzCoXUZAZAZCUOYIiwmn5Rc0Fqg5OqDZCKFik49Mgsn60wRAapNtqV1Bsis5ZAiEHXidaR3ZB1IXbaZC38Sjml6Av5Ph9ZBDPEwss18cjjbSKDlWXsnHohSZAEokEYNicYXe31WE4OgZD"
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

        print(f"Status Code: {response.status_code}")
        print("Response Headers:")
        for header, value in response.headers.items():
            print(f"{header}: {value}")
        print("\nResponse Body:")
        print(response.json())
    except requests.exceptions.RequestException as e:
        logger.debug(f"Error making request: {e}")
        if hasattr(e, "response") and e.response:
            logger.debug(f"Error details: {e.response.text}")


# used for testing
# whatsapp_messenger("This is the test for Lantern")
