#!/usr/bin/env python3
from collections import defaultdict, deque

import os
from typing import Any
import uuid

from config import settings
from dependencies import llm_client
from dotenv import load_dotenv
from fastapi import Request
from loguru import logger
from ollama import AsyncClient
from schemas import  LlmRequestPayload
from transformers.utils import get_json_schema
from utils.cache import add_to_chat_history, get_chat_history
from utils.llm.llm_tools import internet_search_tool, user_query_to_sql
from utils.llm.text_processing import convert_llm_output_to_readable

# Load environment variables
load_dotenv()

# Adding logging information
logger.add("./logs/llm_app", rotation="10 MB")
llm_model = settings.LLM_MODEL_ID


class ChatHistory:
    def __init__(self):
        self.message_pairs = deque()
        self.pair_counter = defaultdict(int)
        self.pair_ids = {}

    def append(self, user_timestamp, user_message, llm_response):
        # Create a unique hashable key for the message pair
        pair_key = (tuple(user_message), tuple(llm_response))

        # If this pair already exists, increment its count
        if pair_key in self.pair_ids:
            pair_id = self.pair_ids[pair_key]
            self.pair_counter[pair_id] += 1

            # If count reached 3, remove the oldest occurrence
            if self.pair_counter[pair_id] >= 10:
                self._remove_oldest_occurrence(pair_id)
        else:
            # Create a new unique ID for this pair
            pair_id = str(uuid.uuid4())
            self.pair_ids[pair_key] = pair_id
            self.pair_counter[pair_id] = 1

            # Add to history
            self.message_pairs.append(
                {
                    "user_timestamp": user_timestamp,
                    "user_message": user_message,
                    "llm_response": llm_response,
                    "pair_id": pair_id,
                }
            )

    def _remove_oldest_occurrence(self, pair_id):
        # Find and remove the oldest occurrence of this pair
        for i, msg in enumerate(self.message_pairs):
            if msg["pair_id"] == pair_id:
                del self.message_pairs[i]
                break

        # Reset the counter for this pair
        self.pair_counter[pair_id] = 2  # Set to 2 since we removed one

    def get_history(self):
        return list(self.message_pairs)



tools: list[Any] = [get_json_schema(user_query_to_sql), get_json_schema(internet_search_tool)]
available_functions={"user_query_to_sql":user_query_to_sql, "internet_search_tool":internet_search_tool}
chat_history = ChatHistory()

# Optimized LLM pipeline
async def tool_checker(user_message:str) -> None:
    """ 
    Runs the tool call
    """
    messages=[{"role":"user", "content":user_message}]
    response = await llm_client.chat(
        model=llm_model,
        messages=messages,
        tools=tools,
        stream=False,
        options={
            "temperature": 0.1,
            # "max_tokens": 100,  # For smaller screens and less complications
            "top_p": 0.95,
            "top_k": 20,
            "min_p": 0,
            "repeat_penalty": 1,
        },
    )
    return response

async def llm_pipeline(request: Request, llm_request_payload: LlmRequestPayload) -> Any:
    try:
        # Redis client
        redis_client = request.app.state.redis

        chat_history: list[Any] = await get_chat_history(
            client=redis_client, user_number=llm_request_payload.user_number
        )

        final_user_content: str = (
            f"And this chat history: {chat_history}.\n"
            f"Answer the user's query: {llm_request_payload.user_message}\n"
            #f"{SECURITY_POST_PROMPT}" # Append security rules to every prompt
        )
        llm_request_payload.messages.append({"role":"user", "content":final_user_content})
        response = await llm_client.chat(
            model=llm_model,
            messages=llm_request_payload.messages,
            tools=tools,
            stream=False,
            options={
                "temperature": 0.1,
                # "max_tokens": 100,  # For smaller screens and less complications
                "top_p": 0.95,
                "top_k": 20,
                "min_p": 0,
                "repeat_penalty": 1,
            },
        )
        return response
    except Exception as e:
        logger.debug(f"Error generating repsonse with llm  {str(e)}", exc_info=True)
        return {
            "message": {
                "content": "I'm sorry, I encountered a system error and could not process your request. Please try again later."
            }
        }


# Optimized chatbot response for tool calling
