#!/usr/bin/env python3

import valkey
from ollama import AsyncClient
from config import settings

# Initialize clients once and reuse them
ollama_client = AsyncClient(host=settings.OLLAMA_HOST)
valkey_client = valkey.Valkey(
    host=settings.VALKEY_HOST, port=settings.VALKEY_PORT, db=0, decode_responses=True
)


# Dependency provider functions
def get_valkey_client():
    return valkey_client


def get_ollama_client():
    return ollama_client
