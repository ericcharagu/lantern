import requests
import json
from datetime import datetime
from loguru import logger

# Test logger file
logger.add("./test.log", rotation="1 week")
# Base URL
BASE_URL = "http://localhost:8000"
LLM_MODEL = "qwen3:0.6b"


# Example 1: Health Check
def check_health():
    response = requests.get(f"{BASE_URL}/health")
    return response.json()


# Example 2: Quick Stats
def get_quick_stats():
    traffic_data = [
        {
            "timestamp": "2024-01-15T09:00:00Z",
            "location": "main_entrance",
            "count": 45,
            "direction": "entry",
        },
        {
            "timestamp": "2024-01-15T10:00:00Z",
            "location": "main_entrance",
            "count": 67,
            "direction": "entry",
        },
    ]

    response = requests.post(
        f"{BASE_URL}/quick-stats",
        json=traffic_data,
        headers={"Content-Type": "application/json"},
    )
    return response.json()


# Example 3: Full Analysis
def get_full_analysis():
    analysis_request = {
        "traffic_data": [
            {
                "timestamp": "2024-01-15T09:00:00Z",
                "location": "main_entrance",
                "count": 45,
                "direction": "entry",
                "weather": "sunny",
                "temperature": 22.5,
                "day_of_week": "monday",
                "is_holiday": False,
            },
            {
                "timestamp": "2024-01-15T10:00:00Z",
                "location": "main_entrance",
                "count": 67,
                "direction": "entry",
                "weather": "sunny",
                "temperature": 24.0,
                "day_of_week": "monday",
                "is_holiday": False,
            },
        ],
        "building_stats": {
            "building_id": "test_001",
            "building_name": "Lantern Serviced Apartments",
            "capacity": 200,
            "building_type": "residence",
        },
        "analysis_period": "daily",
        "include_predictions": False,
    }

    try:
        response = requests.post(
            f"{BASE_URL}/analyse",
            json=analysis_request,
            headers={"Content-Type": "application/json"},
        )
        return response.json()
    except ValueError as e:
        logger.debug({e})
    # return response.json()


# Usage
if __name__ == "__main__":
    # Check if API is running
    health = check_health()
    print("Health Check:", health)

    # Get quick stats
    quick_stats = get_quick_stats()
    print("Quick Stats:", json.dumps(quick_stats, indent=2))

    # Get full analysis
    full_analysis = get_full_analysis()
    print("Full Analysis:", json.dumps(full_analysis, indent=2))
