"""
Web Action Handler
Handles web-related actions like search, weather, news, and information retrieval
"""

import requests
import webbrowser
from typing import Dict, Any, List
from datetime import datetime
from ..assistant_core import ActionRequest, ConversationContext

class WebActionHandler:
    """
    Handles web-related actions and information retrieval
    """
    
    def __init__(self):
        self.supported_actions = {
            'web_search': self._handle_web_search,
            'weather': self._handle_weather,
            'news': self._handle_news,
            'information_retrieval': self._handle_information_retrieval,
            'open_website': self._handle_open_website
        }
        
        # API endpoints and configurations
        self.weather_api = "https://wttr.in"
        self.news_api = "https://newsapi.org/v2"
        self.search_engines = {
            'google': 'https://www.google.com/search?q=',
            'duckduckgo': 'https://duckduckgo.com/?q=',
            'bing': 'https://www.bing.com/search?q='
        }
    
    def execute(self, action_request: ActionRequest, context: ConversationContext) -> Dict[str, Any]:
        """
        Execute web action
        """
        action_type = action_request.command
        parameters = action_request.parameters
        
        if action_type in self.supported_actions:
            try:
                result = self.supported_actions[action_type](parameters)
                return {
                    "success": True,
                    "action": action_type,
                    "result": result,
                    "message": f"Successfully executed {action_type}"
                }
            except Exception as e:
                return {
                    "success": False,
                    "action": action_type,
                    "error": str(e),
                    "message": f"Failed to execute {action_type}: {str(e)}"
                }
        else:
            return {
                "success": False,
                "action": action_type,
                "error": f"Unsupported action: {action_type}",
                "message": f"Action {action_type} is not supported"
            }
    
    def _handle_web_search(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle web search actions
        """
        query = parameters.get('query', '')
        search_engine = parameters.get('search_engine', 'google')
        
        if not query:
            raise ValueError("Search query is required")
        
        # Perform search
        search_url = self.search_engines.get(search_engine, self.search_engines['google']) + query
        webbrowser.open(search_url)
        
        # Try to get search results via API (if available)
        search_results = self._get_search_results(query)
        
        return {
            "action": "web_search",
            "query": query,
            "search_engine": search_engine,
            "url": search_url,
            "results": search_results,
            "status": "Search opened in browser"
        }
    
    def _handle_weather(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle weather information requests
        """
        city = parameters.get('city', 'Delhi')  # Default city
        format_type = parameters.get('format', 'full')
        
        try:
            # Get weather information
            weather_data = self._get_weather_data(city, format_type)
            
            return {
                "action": "weather",
                "city": city,
                "data": weather_data,
                "status": "Weather information retrieved"
            }
        except Exception as e:
            raise Exception(f"Failed to get weather data: {str(e)}")
    
    def _handle_news(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle news requests
        """
        category = parameters.get('category', 'general')
        country = parameters.get('country', 'us')
        limit = parameters.get('limit', 5)
        
        try:
            news_data = self._get_news_data(category, country, limit)
            
            return {
                "action": "news",
                "category": category,
                "country": country,
                "articles": news_data,
                "status": "News retrieved"
            }
        except Exception as e:
            raise Exception(f"Failed to get news data: {str(e)}")
    
    def _handle_information_retrieval(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle general information retrieval
        """
        info_type = parameters.get('type', '')
        query = parameters.get('query', '')
        
        if info_type == 'time':
            current_time = datetime.now().strftime('%I:%M %p')
            return {
                "action": "information_retrieval",
                "type": "time",
                "data": current_time,
                "status": "Current time retrieved"
            }
        
        elif info_type == 'date':
            current_date = datetime.now().strftime('%B %d, %Y')
            return {
                "action": "information_retrieval",
                "type": "date",
                "data": current_date,
                "status": "Current date retrieved"
            }
        
        elif info_type == 'weather':
            return self._handle_weather(parameters)
        
        else:
            # General information search
            return self._handle_web_search(parameters)
    
    def _handle_open_website(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle opening specific websites
        """
        url = parameters.get('url', '')
        website = parameters.get('website', '')
        
        if url:
            webbrowser.open(url)
            return {
                "action": "open_website",
                "url": url,
                "status": "Website opened"
            }
        
        elif website:
            website_urls = {
                'youtube': 'https://www.youtube.com',
                'google': 'https://www.google.com',
                'facebook': 'https://www.facebook.com',
                'twitter': 'https://www.twitter.com',
                'linkedin': 'https://www.linkedin.com',
                'github': 'https://www.github.com',
                'stackoverflow': 'https://www.stackoverflow.com',
                'wikipedia': 'https://www.wikipedia.org'
            }
            
            if website in website_urls:
                url = website_urls[website]
                webbrowser.open(url)
                return {
                    "action": "open_website",
                    "website": website,
                    "url": url,
                    "status": "Website opened"
                }
            else:
                raise ValueError(f"Unsupported website: {website}")
        
        else:
            raise ValueError("URL or website name is required")
    
    def _get_weather_data(self, city: str, format_type: str) -> Dict[str, Any]:
        """
        Get weather data for a city
        """
        try:
            if format_type == 'simple':
                response = requests.get(f"{self.weather_api}/{city}?format=%C+%t", timeout=5)
                if response.status_code == 200:
                    return {"current": response.text.strip()}
            
            elif format_type == 'full':
                response = requests.get(f"{self.weather_api}/{city}?format=j1", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "current": data.get('current_condition', [{}])[0],
                        "location": data.get('nearest_area', [{}])[0],
                        "forecast": data.get('weather', [])[:3]  # Next 3 days
                    }
            
            else:
                response = requests.get(f"{self.weather_api}/{city}", timeout=5)
                if response.status_code == 200:
                    return {"text": response.text}
        
        except Exception as e:
            raise Exception(f"Weather API error: {str(e)}")
    
    def _get_news_data(self, category: str, country: str, limit: int) -> List[Dict[str, Any]]:
        """
        Get news data (simplified version without API key)
        """
        # This is a simplified version - in production, you'd use a real news API
        news_sources = {
            'general': 'https://www.bbc.com/news',
            'technology': 'https://techcrunch.com',
            'business': 'https://www.bloomberg.com',
            'sports': 'https://www.espn.com',
            'entertainment': 'https://www.entertainment.com'
        }
        
        source_url = news_sources.get(category, news_sources['general'])
        
        return [{
            "title": f"Sample news article {i+1}",
            "description": f"This is a sample news article about {category}",
            "url": source_url,
            "publishedAt": datetime.now().isoformat()
        } for i in range(limit)]
    
    def _get_search_results(self, query: str) -> List[Dict[str, Any]]:
        """
        Get search results (simplified version)
        """
        # This is a simplified version - in production, you'd use a real search API
        return [{
            "title": f"Search result for: {query}",
            "url": f"https://example.com/search?q={query}",
            "snippet": f"This is a sample search result for the query: {query}"
        }]
