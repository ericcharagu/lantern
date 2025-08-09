# utils/app_tools.py
from typing import Dict, Any, List, Optional
import statistics

def calculate_traffic_statistics(analytics_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Processes the raw JSONB data from the new analytics SQL query into a structured
    Python dictionary for use in services and templates.
    """
    if not analytics_data:
        return {}

    stats = {}

    # Basic Stats
    basic_stats = analytics_data.get('basic_stats', [{}])[0]
    stats['total_detections'] = basic_stats.get('total_detections', 0)
    stats['active_cameras'] = basic_stats.get('active_cameras', 0)
    stats['unique_locations'] = basic_stats.get('unique_locations', 0)

    # Object Breakdown
    stats['object_breakdown'] = analytics_data.get('object_breakdown', [])
    if stats['object_breakdown']:
        stats['most_common_object'] = stats['object_breakdown'][0]
        person_detections = next((item['count'] for item in stats['object_breakdown'] if item['object_name'] == 'person'), 0)
        stats['total_person_detections'] = person_detections

    # Hourly Patterns
    hourly_patterns = analytics_data.get('hourly_patterns', [])
    if hourly_patterns:
        stats['busiest_hour_overall'] = max(hourly_patterns, key=lambda x: x['count'])
        stats['quietest_hour_overall'] = min(hourly_patterns, key=lambda x: x['count'])
    
    person_hourly = analytics_data.get('person_hourly_patterns', [])
    if person_hourly:
        stats['busiest_hour_person'] = max(person_hourly, key=lambda x: x['count'])
    
    # Location Ranking
    stats['location_ranking'] = analytics_data.get('location_ranking', [])
    if stats['location_ranking']:
        stats['busiest_location'] = stats['location_ranking'][0]

    # Peak Minute
    peak_minute = analytics_data.get('peak_minute', [{}])[0]
    stats['peak_minute'] = {
        "time": peak_minute.get('minute'),
        "count": peak_minute.get('count')
    } if peak_minute else {}

    return stats


def generate_insights(stats: Dict[str, Any]) -> List[str]:
    """Generates human-readable business insights from the processed statistics."""
    insights = []
    if not stats.get('total_detections'):
        return ["No detection data available for the selected period."]

    insights.append(f"A total of {stats['total_detections']:,} objects were detected across {stats['active_cameras']} active cameras.")
    
    if stats.get('most_common_object'):
        obj = stats['most_common_object']
        insights.append(f"The most frequently detected object was '{obj['object_name']}', with {obj['count']:,} instances.")

    if stats.get('total_person_detections'):
        person_percentage = (stats['total_person_detections'] / stats['total_detections']) * 100
        insights.append(f"Human traffic accounted for {stats['total_person_detections']:,} detections, making up {person_percentage:.1f}% of all activity.")

    if stats.get('busiest_hour_person'):
        hour = stats['busiest_hour_person']['hour']
        insights.append(f"Peak hour for human activity was {hour:02d}:00 - {(hour+1):02d}:00.")
    
    if stats.get('busiest_location'):
        loc = stats['busiest_location']
        insights.append(f"The busiest location was '{loc['location']}' with {loc['count']:,} total detections.")

    if stats.get('peak_minute', {}).get('count', 0) > 0:
        peak = stats['peak_minute']
        insights.append(f"The single busiest minute saw {peak['count']} detections at {peak['time']}.")

    return insights

def create_recommendations(stats: Dict[str, Any]) -> List[str]:
    """Generates actionable recommendations based on the analysis."""
    recommendations = []
    if not stats.get('total_detections'):
        return ["Insufficient data for recommendations."]

    if stats.get('busiest_hour_person'):
        hour = stats['busiest_hour_person']['hour']
        recommendations.append(f"Allocate security and staff resources to peak human traffic hours, especially around {hour:02d}:00.")

    if stats.get('busiest_location'):
        loc = stats['busiest_location']
        if loc['count'] > stats.get('total_detections', 0) * 0.4: # If one location has >40% of traffic
            recommendations.append(f"Investigate potential bottlenecks or high congestion at '{loc['location']}' due to its disproportionately high activity.")
    
    if stats.get('quietest_hour_overall'):
        hour = stats['quietest_hour_overall']['hour']
        recommendations.append(f"Schedule maintenance, cleaning, or deliveries during the quietest period, around {hour:02d}:00, to minimize disruption.")

    # Recommendation for non-person objects
    if stats.get('object_breakdown'):
        car_detections = next((item['count'] for item in stats['object_breakdown'] if item['object_name'] == 'car'), 0)
        if car_detections > 50: # Arbitrary threshold
             recommendations.append("Monitor parking areas for capacity and unauthorized vehicle activity, given the significant number of car detections.")
    
    return recommendations