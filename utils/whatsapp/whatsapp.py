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
ACCESS_TOKEN = "EAARQrAKzcHUBPHeMdVZCZBX4yxr2bnZCdb8eY0oEbch0JsjNeSvz7qY1UWrb85ZC5B7x9sh3McJwI1gZC4BGKFpZBRMZBHHr0XoAFnI0vevJBSRuFpnPmEZAtEjvH91xXNWM8HZBuyhMZBoUOgJ8T5ZAgAMq4VCo1yKjo3nYzZCEg3ftyObzQrMjSs9LYfIRZCC2iKbZCdjyFJ2cplKzh2OnDDksKKlJZBEVgIxWtoJ0IWX8b0ZD"
# RECIPIENT_NUMBER = "447709769066"

# TODO:Add recepient number from the message sender
RECIPIENT_NUMBER = "+254736391323"


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
