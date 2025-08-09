from requests.models import Response


import requests
import os 
from loguru import logger
PHONE_NUMBER_ID:int=0
ACCESS_TOKEN:str=""
url =f"https://graph.facebook.com/v23.0/{PHONE_NUMBER_ID}/register"
headers: dict[str, str] = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json",
}

payload: dict[str, str] = {
    "messaging_product": "whatsapp",
    "cc": "+254",
    "phone_number": "748277538",
    "method": "sms",
    "cert":"CngKNAiOnc35hNf8AhIGZW50OndhIhtMYW50ZXJuIFNlcnZpY2VkIEFwYXJ0bWVudHNQjZ3cxAYaQDyKvUpcDA3ZgwFBsIFcRjia5CpqC0hp+nSvIkmbQdTuch9qK3NTQIyfuk2RFHJ6X61ZyosXDkxjD29fLZwo7wkSL20Ua8+d9a6W81qysJ2oai2dWOPiWcb4BctRXYyLHPzLs+qqZpUsN6xsDbYPmxjf", 
    "pin":"123456"

    }

response: Response = requests.post(url, headers=headers, json=payload)
logger.info(response.json())