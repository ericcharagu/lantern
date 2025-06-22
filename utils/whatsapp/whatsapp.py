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
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

# TODO:To be moved to secrets duting prod and when permanent Token acquired
ACCESS_TOKEN = "EAARQrAKzcHUBO5H9PNZBj0H6eV9ZBQU3PISb7ICTYh5ZBc7OacY1YdBpEzmPNlPitS3X57u0jXdE9uQ54RDmOyDGeiF5C1dWlS0HtF61GZCpGxhzW5YvXHJiMc3IOa7srZCHDWWKuY6RcQmwEX3Ymh4ftrrxIgEicssBBYH5EHgZBP1qplPtQJKSPdtFBHnV1Q2mU6DwG6f2gRTNaCUvbc49pvY6ZA6EXZBs"
# RECIPIENT_NUMBER = "447709769066"

# TODO:Add recepient number from the message sender
RECIPIENT_NUMBER = "+254736391323"


@logger.catch
def whatsapp_messenger(llm_text_output: Any):
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
        "to": f"{RECIPIENT_NUMBER}",
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
