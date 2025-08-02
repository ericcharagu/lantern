
from datetime import datetime, time, timedelta
from typing import  Any
from ddgs import DDGS
from loguru import logger
from utils.db.base import execute_query
async def user_query_to_sql(user_message: str) -> Any:
    """
    Converts natural language queries into SQL for detection_logs table. the schema classs for the table "detection_logs":
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

    
    Args:
        user_message: Natural language query (e.g., "How many people between 10pm and 5am")
    
    Returns:
        Dictionary containing:
        - sql: The complete SQL query string
        - params: Dictionary of query parameters
        - summary: Human-readable description of the query
    """
    # Initialize defaults
    filters = []
    params = {}
    select = "COUNT(*) AS count"
    group_by = ""
    order_by = ""
    time_range = None
    object_type = None
    
    # Convert to lowercase for easier matching
    query = user_message.lower()
    
    # 1. Handle object type filtering
    common_objects = ['person', 'car', 'truck', 'dog', 'cat']  # Extend as needed
    for obj in common_objects:
        if obj in query:
            object_type = obj
            filters.append("object_name = :object_name")
            params['object_name'] = obj
            select = f"COUNT(*) AS {obj}_count" if "how many" in query else "*"
            break
    
    # 2. Handle time ranges
    now = datetime.now()
    today = now.date()
    yesterday = today - timedelta(days=1)
    
    # Time range patterns
    if "last night" in query:
        time_range = (
            datetime.combine(yesterday, time(22, 0)),  # 10pm yesterday
            datetime.combine(today, time(5, 0))        # 5am today
        )
    elif "today" in query:
        time_range = (
            datetime.combine(today, time(0, 0)),
            now
        )
    elif "yesterday" in query:
        time_range = (
            datetime.combine(yesterday, time(0, 0)),
            datetime.combine(today, time(0, 0))
        )
    
    # Specific hour ranges (e.g., "between 10pm and 5am")
    if "between" in query and "and" in query:
        try:
            parts = query.split("between")[1].split("and")
            start_str, end_str = parts[0].strip(), parts[1].strip()
            
            def parse_time(t_str):
                if "pm" in t_str:
                    hour = int(t_str.split("pm")[0].strip())
                    return hour + 12 if hour < 12 else hour
                elif "am" in t_str:
                    hour = int(t_str.split("am")[0].strip())
                    return hour if hour != 12 else 0
                return int(t_str)
            
            start_hour = parse_time(start_str)
            end_hour = parse_time(end_str)
            
            base_date = yesterday if "last night" in query else today
            start_time = datetime.combine(base_date, time(start_hour, 0))
            end_time = datetime.combine(base_date, time(end_hour, 0))
            
            if end_hour < start_hour:
                end_time += timedelta(days=1)
            
            time_range = (start_time, end_time)
        except Exception:
            pass
    
    if time_range:
        filters.append("timestamp BETWEEN :start_time AND :end_time")
        params['start_time'] = time_range[0]
        params['end_time'] = time_range[1]
    
    # 3. Handle location/camera filters
    if "reception" in query:
        filters.append("location LIKE '%Reception%'")
    elif "entrance" in query:
        filters.append("location LIKE '%Entrance%'")
    
    # 4. Confidence threshold
    if "high confidence" in query:
        filters.append("confidence >= 0.8")
    elif "low confidence" in query:
        filters.append("confidence < 0.5")
    
    # 5. Build the SQL query
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    
    # For "show me all detections" type queries
    if "show" in query and "all" in query:
        select = "*"
        if "group by" in query:
            group_by = "GROUP BY object_name"
            select = "object_name, COUNT(*) as count"
            order_by = "ORDER BY count DESC"
    
    sql = f"""
    SELECT {select}
    FROM detection_logs
    {where_clause}
    {group_by}
    {order_by}
    """

    return await execute_query(query=sql.strip(), params=params)


def internet_search_tool(user_message:str, max_results:int=3) -> list[dict[str, Any]]:
    """
    Your only role is to perfom internet searches using the DuckDuckGo search tool. Restructure the query for better search.

    Args:
        user_message: User's query sent via whatsapp
        max_results: The highest number of individual sources retrieved by the search module

    Returns:
        list[dict[str, Any]]: contains the search results in a list. Each item of the list is a dict containing the actual response data
    """
    try:
        return DDGS().text(user_message, max_results=max_results)
    except ValueError as e:
        logger.error(f"Error during web search: {str(e)}")
        raise
