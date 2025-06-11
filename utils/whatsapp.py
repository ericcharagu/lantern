import requests
from typing import Any
from loguru import logger

# Logger file path
logger.add("./logs/whatsapp.log", rotation="700 MB")
# Configuration
API_VERSION = "v22.0"
PHONE_NUMBER_ID = "605403165986839"
ACCESS_TOKEN = "EAARQrAKzcHUBO837rONnGd7uexXaKt1r7ew5XBEGpRe89dy2gghzcAV4F8RMeUkr8x0ssCdGvGZAHNNXqapZCQ1ekbNx7QL4Ub0PsZA4ZCaNBQq9r7itKU2utlq1JvczsUdkyAbKpTLLL2QPgvDc4Q6DDQ29A6AovfaBx5xBeEKvzPVhB7sziaCekzRHXGo9dtFTLtE1mDKQv6f0jIkkHmSx4fHY0ZBmh"
# RECIPIENT_NUMBER = "447709769066"
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
# whatsapp_messenger("This is the test for lantern")
