# routers/webhooks.py
from datetime import datetime
import json
from typing import Any, Dict
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Query
from fastapi.responses import  PlainTextResponse
from loguru import logger
from ollama import AsyncClient

from config import settings
from dependencies import get_ollama_client
from utils.db.base import execute_query
from utils.llm.text_processing import convert_llm_output_to_readable
from utils.whatsapp.whatsapp import whatsapp_messenger
from prompts import (
    PROMPT_WHATSAPP_ASSISTANT,
    PROMPT_EXTRACT_SQL_FILTERS,
    PROMPT_SUMMARIZE_SQL_RESULTS
)
import os
logger.add("./logs/webhooks.log", rotation="1 week")
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFICATION_TOKEN")
def build_query_from_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Builds a secure, parameterized SQL query from a dictionary of filters.
    This function contains the deterministic logic for SQL construction.
    """
    select_clause = filters.get("select_columns", "*")
    where_clauses = []
    params = {}

    # Default to person if not specified
    if "object_name" not in filters:
        filters["object_name"] = "person"
        
    for key, value in filters.items():
        if key in ["camera_name", "location", "object_name", "tracker_id"]:
            where_clauses.append(f"{key} = :{key}")
            params[key] = value
        elif key in ["start_time", "end_time"]:
            try:
                # Attempt to parse the string from the LLM into a datetime object.
                dt_object = datetime.strptime(str(value), '%Y-%m-%d %H:%M:%S')
                params[key] = dt_object
                
                # Add the corresponding clause
                if key == "start_time":
                    where_clauses.append("timestamp >= :start_time")
                else: # key == "end_time"
                    where_clauses.append("timestamp < :end_time")
            except (ValueError, TypeError):
                # If the LLM provides a malformed date string, log it and skip this filter.
                logger.error(f"LLM returned an invalid date format for '{key}': {value}. Skipping this filter.")
                continue
    where_sql = ""
    if where_clauses:
        where_sql = f"WHERE {' AND '.join(where_clauses)}"

    group_by_sql = ""
    if "group_by_columns" in filters:
        # Basic validation to prevent injection in group by
        safe_group_cols = ", ".join([col for col in filters["group_by_columns"].split(',') if col.strip().isalnum()])
        if safe_group_cols:
            group_by_sql = f"GROUP BY {safe_group_cols}"

    order_by_sql = ""
    if "order_by_clause" in filters:
        # This is less safe, but necessary for LIMIT. Trust the LLM's structured output.
        order_by_sql = filters["order_by_clause"]
    
    sql = f"SELECT {select_clause} FROM detection_logs {where_sql} {group_by_sql} {order_by_sql};"
    
    return {"sql": sql, "params": params}

async def process_authorized_query(
    user_question: str, ollama_client: AsyncClient
) -> str:
    """
    Handles a query from an authorized user using the robust filter extraction method.
    """
    logger.info("Processing query for an AUTHORIZED user.")
    
    # --- Step 1: Extract filter criteria using the LLM ---
    logger.info("Stage 1: Extracting filters from user question.")
    messages = [
        {"role": "system", "content": PROMPT_EXTRACT_SQL_FILTERS},
        {"role": "user", "content": user_question},
    ]
    
    response = await ollama_client.chat(
        model=settings.LLM_MODEL_ID,
        messages=messages,
        options={"temperature": 0.0}, # Be deterministic
        format="json" # Force JSON output
    )
    
    response_content = response.get("message", {}).get("content", "{}")
    try:
        filters = json.loads(response_content)
        logger.info(f"LLM extracted filters: {filters}")
    except json.JSONDecodeError:
        logger.error(f"LLM output was not valid JSON: {response_content}")
        return "I'm sorry, I had trouble understanding the structure of your request."

    if not filters:
        return "I couldn't identify any specific criteria in your query. Could you be more detailed?"

    # --- Step 2: Build the SQL query from the filters ---
    logger.info("Stage 2: Building SQL from extracted filters.")
    query_data = build_query_from_filters(filters)
    sql_query = query_data["sql"]
    sql_params = query_data["params"]
    
    # --- Step 3: Execute the query ---
    logger.info(f"Stage 3: Executing SQL: {sql_query} with params: {sql_params}")
    try:
        db_results = await execute_query(query=sql_query, params=sql_params)
    except Exception as e:
        logger.error(f"Database execution failed. Error: {e}", exc_info=True)
        return "There was an error retrieving data from the database."

    # --- Step 4: Summarize the results ---
    logger.info(f"Stage 4: Summarizing results for the user. Results: {db_results}")
    summary_prompt = (
        f"Based on my question, \"{user_question}\", provide a concise, natural language summary of this data: "
        f"{json.dumps(db_results, default=str)}"
    )
    summary_messages = [
        {"role": "system", "content": PROMPT_SUMMARIZE_SQL_RESULTS},
        {"role": "user", "content": summary_prompt},
    ]
    
    summary_response = await ollama_client.chat(model=settings.LLM_MODEL_ID, messages=summary_messages)
    final_answer = summary_response.get("message", {}).get("content", "I found data but had trouble summarizing it.")
        
    return final_answer

async def process_public_query(
    user_question: str, ollama_client: AsyncClient
) -> str:
    """
    Handles a query from a public user using the restrictive concierge prompt.
    """
    logger.info("Processing query for a PUBLIC user.")
    messages = [
        {"role": "system", "content": PROMPT_WHATSAPP_ASSISTANT},
        {"role": "user", "content": user_question},
    ]
    response = await ollama_client.chat(model=settings.LLM_MODEL_ID, messages=messages)
    return response.get("message", {}).get("content", "I am unable to respond at the moment.")

async def process_message_in_background(
    user_message: str, user_number: str
):
    """
    This function now checks authorization and routes to the appropriate processor.
    """
    ollama_client = get_ollama_client()
    final_response = ""
    
    try:
        # --- AUTHORIZATION CHECK ---
        if user_number in settings.NIGHTLY_REPORT_RECIPIENT_NUMBER:
            final_response = await process_authorized_query(user_message, ollama_client)
        else:
            final_response = await process_public_query(user_message, ollama_client)

        whatsapp_messenger(llm_text_output=convert_llm_output_to_readable(final_response), recipient_number=user_number)
        logger.success(f"Response sent to {user_number}.")

    except Exception as e:
        logger.error(f"Background task failed for {user_number}: {e}", exc_info=True)
        # Send a generic error message
        whatsapp_messenger(
            llm_text_output="I'm sorry, I encountered an internal error. Please try again later.",
            recipient_number=user_number
        )
@router.get("")
async def verify_whatsapp_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Handles webhook verification for the WhatsApp platform."""
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge, status_code=200)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("")
async def handle_whatsapp_message(request: Request, background_tasks: BackgroundTasks):
    """Handles incoming messages from WhatsApp."""
    try:
        data = await request.json()
        value = data["entry"][0]["changes"][0].get("value", {})
        if not value: return PlainTextResponse("OK")

        message_data = value.get("messages", [{}])[0]
        user_message = message_data.get("text", {}).get("body")
        user_number = message_data.get("from") # e.g., '254712345678'

        if not user_message or not user_number:
            logger.info("Webhook received, but no processable text message or sender number found.")
            return PlainTextResponse("OK")

        # Queue the processing and response to happen in the background
        background_tasks.add_task(process_message_in_background, user_message, user_number)

        return PlainTextResponse("Message acknowledged", status_code=200)

    except (KeyError, IndexError, TypeError) as e:
        logger.error(f"Error processing webhook payload: {e}", exc_info=True)
        return PlainTextResponse("Error", status_code=500)