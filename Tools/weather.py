"""
Weather utilities for Atulya Tantra AGI
"""

import requests
from typing import Dict, Any, Optional


def get_weather(city: str = "Delhi", country: str = "IN") -> Dict[str, Any]:
    """Get weather information for a city"""
    try:
        # Using wttr.in for weather data
        url = f"https://wttr.in/{city},{country}?format=j1"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            current = data.get("current_condition", [{}])[0]
            
            return {
                "city": city,
                "country": country,
                "temperature": current.get("temp_C"),
                "description": current.get("weatherDesc", [{}])[0].get("value"),
                "humidity": current.get("humidity"),
                "wind_speed": current.get("windspeedKmph"),
                "pressure": current.get("pressure"),
                "feels_like": current.get("FeelsLikeC")
            }
        else:
            return {"error": "Weather data unavailable"}
            
    except Exception as e:
        return {"error": f"Weather fetch failed: {str(e)}"}


def get_weather_forecast(city: str = "Delhi", country: str = "IN", days: int = 3) -> Dict[str, Any]:
    """Get weather forecast for a city"""
    try:
        url = f"https://wttr.in/{city},{country}?format=j1"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            forecast = data.get("weather", [])
            
            return {
                "city": city,
                "country": country,
                "forecast": forecast[:days]
            }
        else:
            return {"error": "Weather forecast unavailable"}
            
    except Exception as e:
        return {"error": f"Weather forecast fetch failed: {str(e)}"}


# Export public API
__all__ = [
    "get_weather",
    "get_weather_forecast"
]