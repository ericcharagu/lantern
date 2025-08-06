
import asyncio
from datetime import datetime, time, timedelta
from typing import  Any
from ddgs import DDGS
from loguru import logger
from utils.db.base import async_engine, execute_query
from sqlalchemy import text
from utils.timezone import nairobi_tz

# Initialize defaults
filters = []
params:dict[str, Any] = {}
select = "COUNT (*) AS count"
group_by:str = ""
order_by:str= ""
time_range = None
object_name = None
where_clause:str=""
sql: str = f""" SELECT {select} FROM detection_logs {where_clause} {group_by} {order_by}"""

#Current time
user_query_to_sql: dict={
  "tools": [
    {
      "function_declarations": [
        {
          "name": "user_query_to_sql",
          "description": "Translates a user's natural language question into a secure, parameterized PostgreSQL query to be executed against the 'detection_logs' table. This tool is responsible for understanding the user's intent, identifying filters, aggregations, and groupings, and constructing the appropriate SQL string and parameters dictionary.",
          "parameters": {
            "type": "OBJECT",
            "properties": {
              "sql": {
                "type": "STRING",
                "description": "A valid, parameterized PostgreSQL query string. For example: 'SELECT COUNT(*) FROM detection_logs WHERE object_name = :object_name AND timestamp >= :start_time;'"
              },
              "params": {
                "type": "OBJECT",
                "description": "A dictionary of parameters used in the SQL query to prevent injection. The keys must match the parameter names in the SQL string. For example: {'object_name': 'person', 'start_time': '2025-08-03 11:15:00.000000+00'}",
                "properties": {}
              }
            },
            "required": ["sql", "params"]
          }
        }
      ]
    }
  ],
  "tool_config": {
    "llm_instructions": [
      {
        "instruction": "Your primary task is to act as an expert SQL generator. You will be given a user's question and you must convert it into a valid PostgreSQL query and a corresponding parameters dictionary based on the rules and context provided. You MUST ALWAYS use parameterized queries to prevent SQL injection.",
        "context": {
          "db_schema": {
            "table_name": "detection_logs",
            "columns": [
              {"name": "id", "type": "BIGINT", "description": "Primary key"},
              {"name": "timestamp", "type": "TIMESTAMPTZ", "description": "UTC timestamp of the detection. Format: 'YYYY-MM-DD HH:MI:SS.ffffff+zz'"},
              {"name": "tracker_id", "type": "INTEGER", "description": "Persistent ID for a tracked object"},
              {"name": "camera_name", "type": "VARCHAR(100)", "description": "Name of the camera"},
              {"name": "location", "type": "VARCHAR(100)", "description": "General location of the camera"},
              {"name": "object_name", "type": "VARCHAR(50)", "description": "Name of the detected object (e.g., 'person')"},
              {"name": "confidence", "type": "REAL", "description": "Model confidence score"},
              {"name": "box_x1", "type": "REAL", "description": "Bounding box coordinate"},
              {"name": "box_y1", "type": "REAL", "description": "Bounding box coordinate"},
              {"name": "box_x2", "type": "REAL", "description": "Bounding box coordinate"},
              {"name": "box_y2", "type": "REAL", "description": "Bounding box coordinate"}
            ]
          },
          "camera_context": {
            "description": "Use the exact 'name' and 'location' values from this dictionary when a user refers to a specific area. User input is case-insensitive, but your output must match these strings exactly.",
            "cameras": {
              "1": {"name": "Third Floor Left", "location": "Third Floor"},
              "2": {"name": "Inner Reception", "location": "Ground Floor"},
              "3": {"name": "Exit Gate Wall", "location": "exit_gate"},
              "4": {"name": "Main Gate", "location": "main_entrance"},
              "5": {"name": "Third Floor Right", "location": "Third Floor"},
              "6": {"name": "First Floor Right", "location": "First Floor"},
              "7": {"name": "Ground Floor Right", "location": "Ground Floor"},
              "8": {"name": "Second Floor Right", "location": "Second Floor"},
              "10": {"name": "Main Entrance", "location": "main_entrance"},
              "11": {"name": "First Floor Stairs", "location": "First Floor"},
              "12": {"name": "Third Floor Stairs", "location": "Third Floor"},
              "13": {"name": "Front Left", "location": "Ground Floor"},
              "14": {"name": "Floor Right", "location": "Ground Floor"},
              "15": {"name": "Borehole", "location": "Borehole"},
              "17": {"name": "Fourth Floor Stairs", "location": "Fourth Floor"},
              "18": {"name": "Fourth Floor Left", "location": "Fourth Floor"},
              "19": {"name": "Ground Floor Stairs", "location": "Ground Floor"},
              "20": {"name": "Fourth Floor Right", "location": "Fourth Floor"},
              "21": {"name": "Exit Gate", "location": "exit_gate"},
              "23": {"name": "Restaurant 1", "location": "restaurant"},
              "24": {"name": "Second Floor Stairs", "location": "Second Floor"},
              "25": {"name": "Kitchen", "location": "restaurant"},
              "26": {"name": "Staff Entrance", "location": "yard"},
              "27": {"name": "Rear Wall", "location": "yard"},
              "28": {"name": "Server Room", "location": "Second Floor"},
              "29": {"name": "Restaurant 2", "location": "restaurant"},
              "30": {"name": "Reception", "location": "Ground Floor"},
              "31": {"name": "Ground Floor Left", "location": "Ground Floor"},
              "32": {"name": "First Floor Left", "location": "First Floor"}
            }
          },
          "rules": [
            "Unless the user specifies another object, ALWAYS assume they are asking about 'person'.",
            "You MUST convert all relative time references (e.g., 'today', 'last 2 hours', 'yesterday at 4pm') into absolute UTC timestamps in the format 'YYYY-MM-DD HH:MI:SS.ffffff+00' for the 'params' dictionary. Assume the current time is 2025-08-03 12:30:00 UTC.",
            "For counting queries, use 'SELECT COUNT(*) FROM ...'. For unique counts, use 'SELECT COUNT(DISTINCT column_name) FROM ...'.",
            "For grouping queries (e.g., 'by location', 'per hour'), use the 'GROUP BY' clause and include the grouping column in the SELECT statement.",
            "When selecting columns, always select the raw data. Do not attempt to format it (e.g., into sentence case)."
          ]
        },
        "examples": [
          {
            "user_message": "How many people were seen at the main entrance in the last hour?",
            "tool_code": "print(user_query_to_sql(sql='SELECT COUNT(*) FROM detection_logs WHERE object_name = :object_name AND camera_name = :camera_name AND timestamp >= :start_time;', params={'object_name': 'person', 'camera_name': 'Main Entrance', 'start_time': '2025-08-03 11:30:00.000000+00'}))"
          },
          {
            "user_message": "Show me the tracker IDs for people seen on the Third Floor yesterday.",
            "tool_code": "print(user_query_to_sql(sql='SELECT DISTINCT tracker_id, timestamp, camera_name FROM detection_logs WHERE object_name = :object_name AND location = :location AND timestamp BETWEEN :start_time AND :end_time ORDER BY timestamp DESC;', params={'object_name': 'person', 'location': 'Third Floor', 'start_time': '2025-08-02 00:00:00.000000+00', 'end_time': '2025-08-02 23:59:59.999999+00'}))"
          },
          {
            "user_message": "Give me the hourly person count for the whole building today.",
            "tool_code": "print(user_query_to_sql(sql='SELECT EXTRACT(HOUR FROM timestamp) as hour, COUNT(*) as count FROM detection_logs WHERE object_name = :object_name AND timestamp >= :start_date GROUP BY hour ORDER BY hour;', params={'object_name': 'person', 'start_date': '2025-08-03 00:00:00.000000+00'}))"
          }
        ]
      }
    ]
  }
}   
async def internet_search_tool(user_message:str, max_results:int=3) -> list[dict[str, Any]]:
    """
    Your only role is to perfom internet searches using the DuckDuckGo search tool. Restructure the query for better search.

    Args:
        user_message: User's query sent via whatsapp
        max_results: The highest number of individual sources retrieved by the search module

    Returns:
        list[dict[str, Any]]: contains the search results in a list. Each item of the list is a dict containing the actual response data
    """
    try:
        # Run the synchronous DDGS call in a thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,  # Uses default ThreadPoolExecutor
            lambda: DDGS().text(user_message, max_results=max_results)
        )
    except ValueError as e:
        logger.error(f"Error during web search: {str(e)}")
        raise
