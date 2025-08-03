
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
async def user_query_to_sql(user_message:str, sql:str, params:dict[str, Any])->Any:

    """
    Converts natural language queries into SQL for detection_logs table. the schema class for the table.
    "detection_logs":
        id = Column(Integer, primary_key=True, autoincrement=True)
        timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
        camera_name = Column(String(100), nullable=False)
        location = Column(String(100))
        object_name = Column(String(50), nullable=False, index=True)
        confidence = Column(Float, nullable=False)
        box_x1 = Column(Float, nullable=False)
        box_y1 = Column(Float, nullable=False)
        box_x2 = Column(Float, nullable=False)
        box_y2 = Column(Float, nullable=False)
    
    Ensure to convert any time or date formats into the default datetime format( 2025-08-02 11:27:29.298631+00 ) for the sql statement

    filters = []
    select = "COUNT(*) as Count"
    group_by:str = ""
    order_by:str= ""
    time_range :datetime = None
    object_name:str="person"
    where_clause:str=""
    sql: str = SELECT {select} FROM detection_logs {where_clause} {group_by} {order_by}

    Args:
        user_message: Natural language query (e.g., "How many people between 10pm and 5am")
        sql: Template for the expected sql statement for the postgres db
        params: A dictionary contains the sql parameters for better retrieval
    
    Returns:
        The sql string to be used
    """
    return await execute_query(query=sql, params=params) 
    
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
