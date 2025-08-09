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
PHONE_NUMBER_ID: int = int(os.getenv("PHONE_NUMBER_ID", 728231300374679))
ACCESS_TOKEN=os.getenv("WHATSAPP_ACCESS_TOKEN"," EAARtxxZAZBAGgBPJt2tyLQEtd0aj68ljIlz9F3ZAQmo2dTtZAkzdnbDt3g5pZA9cYpGWfDqgNf7a9evOSjaBmJhWB9s11mI4SSBypSYI768Ibil2aO2ZBZCLLoSFYfziMTUZCsboZBZA1ddcSIXf9MnZBFdp4QwFHQ9hJW2WNyUuMSxdrIASkc8WULYiXG2VkImxQZDZD")
@logger.catch
def whatsapp_messenger(llm_text_output: Any, recipient_number:str):
    if not ACCESS_TOKEN:
        raise ValueError("ACCESS_TOKEN is not valid")

    url = f"https://graph.facebook.com/v23.0/{PHONE_NUMBER_ID}/messages"

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
    
    response = requests.post(url, headers=headers, json=payload)
    #response.raise_for_status()  # Raises exception for HTTP errors
    logger.info(f"{response.json()}")
    """
    except requests.exceptions.RequestException as e:
        logger.debug(f"Error making request: {e}, {e.response.text}")
        if hasattr(e, "response") and e.response:
            logger.debug(f"Error details: {e.response.text}")
"""

# used for testing
#whatsapp_messenger("This is the test for Lantern", recipient_number="")
