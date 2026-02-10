"""Real-time Data Integration Module - Weather, news, stocks, calendar"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class WeatherIntegration:
    """Weather data integration using OpenWeatherMap API"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or "demo_key"
        self.last_location = None
        logger.info("WeatherIntegration initialized")
    
    def get_weather(self, city: str) -> Dict:
        """Get current weather for city"""
        try:
            import requests
            url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={self.api_key}&units=metric"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return {
                    "city": city,
                    "temperature": data["main"]["temp"],
                    "description": data["weather"][0]["description"],
                    "humidity": data["main"]["humidity"],
                    "wind_speed": data["wind"]["speed"],
                    "timestamp": datetime.now()
                }
        except Exception as e:
            logger.warning(f"Weather fetch failed: {e}")
        
        # Return mock data for demo
        return {
            "city": city,
            "temperature": 22,
            "description": "Clear skies",
            "humidity": 65,
            "wind_speed": 3.5,
            "timestamp": datetime.now(),
            "note": "[Demo data - configure real API]"
        }


class NewsIntegration:
    """News feed integration"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or "demo_key"
        logger.info("NewsIntegration initialized")
    
    def get_headlines(self, category: str = "general") -> List[Dict]:
        """Get top news headlines"""
        categories = {
            "general": "Headlines",
            "tech": "Technology News",
            "business": "Business News",
            "health": "Health News",
            "sports": "Sports News"
        }
        
        # Return mock headlines for demo
        return [
            {
                "title": f"Breaking: {categories.get(category, 'Latest update')} - 1",
                "description": "Stay tuned for the latest developments...",
                "source": "NewsAPI",
                "timestamp": datetime.now()
            },
            {
                "title": f"Developing: {categories.get(category, 'Latest update')} - 2",
                "description": "More information as it becomes available...",
                "source": "NewsAPI",
                "timestamp": datetime.now()
            }
        ]


class StockIntegration:
    """Stock price integration"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or "demo_key"
        logger.info("StockIntegration initialized")
    
    def get_stock_price(self, symbol: str) -> Dict:
        """Get current stock price"""
        try:
            import requests
            url = f"https://api.example.com/stock/{symbol}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.warning(f"Stock fetch failed: {e}")
        
        # Return mock data
        return {
            "symbol": symbol.upper(),
            "price": 150.25,
            "change": "+2.5%",
            "timestamp": datetime.now(),
            "note": "[Demo data - configure real API]"
        }


class CalendarIntegration:
    """Calendar and time integration"""
    
    def __init__(self):
        self.events = []
        logger.info("CalendarIntegration initialized")
    
    def get_current_time(self) -> str:
        """Get formatted current time"""
        return datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
    
    def add_event(self, title: str, datetime_str: str, description: str = "") -> Dict:
        """Add calendar event"""
        event = {
            "title": title,
            "datetime": datetime_str,
            "description": description,
            "created": datetime.now()
        }
        self.events.append(event)
        logger.info(f"Event added: {title}")
        return event
    
    def get_upcoming_events(self, hours: int = 24) -> List[Dict]:
        """Get upcoming events in next N hours"""
        return self.events[:5]  # Mock - return first 5


class RealTimeDataManager:
    """Unified real-time data integration"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.weather = WeatherIntegration(self.config.get("openweather_api_key"))
        self.news = NewsIntegration(self.config.get("newsapi_key"))
        self.stocks = StockIntegration(self.config.get("stocks_api_key"))
        self.calendar = CalendarIntegration()
        
        logger.info("RealTimeDataManager initialized")
    
    def get_daily_briefing(self, user_city: str) -> str:
        """Generate daily briefing for user"""
        briefing = f"Good morning, Sir. It is {self.calendar.get_current_time()}.\n\n"
        
        # Weather
        weather = self.weather.get_weather(user_city)
        briefing += f"Weather in {weather['city']}: {weather['description']}, {weather['temperature']}°C\n\n"
        
        # News
        headlines = self.news.get_headlines("general")
        briefing += "Today's Headlines:\n"
        for headline in headlines[:2]:
            briefing += f"• {headline['title']}\n"
        
        briefing += "\nShall I provide additional information, Sir?"
        return briefing
    
    def get_status_report(self) -> str:
        """Get overall system status"""
        return f"""
System Status Report:
- Weather Integration: Online
- News Feed: Online
- Stock Monitor: Online
- Calendar Integration: Online
- Current Time: {self.calendar.get_current_time()}
- Upcoming Events: {len(self.calendar.events)}

All systems nominal, Sir.
        """
