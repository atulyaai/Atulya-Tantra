"""
Tools Module
Combines search, routing, price checking, and knowledge caching
"""

import logging
from typing import Optional, Dict, Any
from duckduckgo_search import DDGS
import time
import yfinance as yf
import requests

logger = logging.getLogger(__name__)


# ============================================================================
# SEARCH ENGINE
# ============================================================================

class SearchEngine:
    """Online search engine using DuckDuckGo"""
    
    def __init__(self):
        self.ddgs = DDGS()

    def search(self, query: str, max_results: int = 5) -> str:
        """
        Search the web for the given query
        
        Args:
            query: The search query
            max_results: Maximum number of results to return
            
        Returns:
            Formatted string of search results
        """
        try:
            logger.info(f"Searching web for: {query}")
            results = self.ddgs.text(query, max_results=max_results)
            
            if not results:
                return "No search results found."
                
            formatted_results = "Context from Online Search:\n"
            for i, res in enumerate(results, 1):
                title = res.get('title', 'No Title')
                body = res.get('body', 'No Description')
                href = res.get('href', '#')
                formatted_results += f"[{i}] {title}\n    {body}\n    Source: {href}\n\n"
                
            return formatted_results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return f"Error performing search: {str(e)}"


# ============================================================================
# INTELLIGENT ROUTER
# ============================================================================

class IntelligentRouter:
    """Uses AI to decide when and what to search"""
    
    def __init__(self, text_ai):
        self.text_ai = text_ai
    
    def should_search(self, user_question: str) -> Dict[str, Any]:
        """
        Ask AI if this question needs web search
        
        Returns:
            {
                'needs_search': bool,
                'search_query': str or None,
                'reason': str
            }
        """
        analysis_prompt = [{
            "role": "system",
            "content": [{
                "type": "text",
                "text": """You are a search decision assistant. Analyze if a question needs current web data.

Reply ONLY in this format:
SEARCH: yes/no
QUERY: [what to search, or 'none']
REASON: [brief reason]

Examples:
Q: What is the price of Bitcoin?
SEARCH: yes
QUERY: Bitcoin price USD today
REASON: Prices change constantly

Q: Who won the game today?
SEARCH: yes
QUERY: [sport mentioned] game results today
REASON: Current event

Q: What is Python?
SEARCH: no
QUERY: none
REASON: General programming knowledge"""
            }]
        }, {
            "role": "user",
            "content": [{
                "type": "text",
                "text": f"Q: {user_question}"
            }]
        }]
        
        try:
            response = self.text_ai.generate_response(
                analysis_prompt,
                max_tokens=100,
                temperature=0.3
            )
            
            lines = response.strip().split('\n')
            result = {
                'needs_search': False,
                'search_query': None,
                'reason': 'Unknown'
            }
            
            for line in lines:
                if line.startswith('SEARCH:'):
                    result['needs_search'] = 'yes' in line.lower()
                elif line.startswith('QUERY:'):
                    query = line.replace('QUERY:', '').strip()
                    result['search_query'] = query if query.lower() != 'none' else None
                elif line.startswith('REASON:'):
                    result['reason'] = line.replace('REASON:', '').strip()
            
            logger.info(f"Search decision: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Search decision failed: {e}")
            needs = any(word in user_question.lower() for word in 
                       ['today', 'now', 'current', 'latest', 'price', 'news'])
            return {
                'needs_search': needs,
                'search_query': user_question if needs else None,
                'reason': 'Fallback heuristic'
            }


# ============================================================================
# PRICE CHECKER
# ============================================================================

class PriceChecker:
    """Check prices for crypto, stocks, and gold"""
    
    def __init__(self):
        self.search_engine = SearchEngine()
    
    def get_crypto_price(self, crypto_id: str) -> Optional[str]:
        """Get cryptocurrency price from CoinGecko"""
        try:
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={crypto_id}&vs_currencies=usd"
            response = requests.get(url, timeout=5)
            data = response.json()
            
            if crypto_id in data:
                price = data[crypto_id]['usd']
                return f"${price:,.2f}"
            return None
        except Exception as e:
            logger.error(f"CoinGecko API error: {e}")
            return None
    
    def get_stock_price(self, symbol: str) -> Optional[str]:
        """Get stock price from Yahoo Finance"""
        try:
            ticker = yf.Ticker(symbol)
            price = ticker.fast_info.last_price
            if price:
                return f"${price:.2f}"
            return None
        except Exception as e:
            logger.error(f"Stock price error for {symbol}: {e}")
            return None
    
    def get_gold_price_inr(self) -> Optional[str]:
        """Get gold price in INR per 10g"""
        try:
            gold = yf.Ticker("GC=F")
            usdinr = yf.Ticker("USDINR=X")
            
            gold_price = gold.fast_info.last_price
            rate = usdinr.fast_info.last_price
            
            if gold_price and rate:
                price_per_ounce_inr = gold_price * rate
                price_per_gram_inr = price_per_ounce_inr / 31.1035
                price_per_10g_inr = price_per_gram_inr * 10
                return f"₹{price_per_10g_inr:,.0f} per 10g"
            return None
        except Exception as e:
            logger.error(f"Gold price error: {e}")
            return None
    
    def get_any_price(self, query: str) -> str:
        """Detect and get price for any asset"""
        query_lower = query.lower()
        
        # Crypto
        if 'bitcoin' in query_lower or 'btc' in query_lower:
            price = self.get_crypto_price('bitcoin')
            if price:
                return f"Bitcoin (BTC): {price}"
        
        if 'ethereum' in query_lower or 'eth' in query_lower:
            price = self.get_crypto_price('ethereum')
            if price:
                return f"Ethereum (ETH): {price}"
        
        # Gold
        if 'gold' in query_lower and any(k in query_lower for k in ['india', 'inr', 'rupee']):
            price = self.get_gold_price_inr()
            if price:
                return f"Gold (India): {price}"
        
        # Stock (extract symbol)
        words = query.split()
        for word in words:
            if word.isupper() and len(word) <= 5:
                price = self.get_stock_price(word)
                if price:
                    return f"{word}: {price}"
        
        return "Unable to fetch price. Please specify crypto/stock symbol or 'gold India'."


# ============================================================================
# KNOWLEDGE CACHE
# ============================================================================

class KnowledgeCache:
    """Smart caching for search results and facts"""
    
    def __init__(self, memory_manager):
        self.memory = memory_manager
        self.cache = {}
        self.ttl = {
            'price': 300,      # 5 minutes
            'news': 3600,      # 1 hour
            'fact': 86400,     # 24 hours
            'general': 3600    # 1 hour
        }
    
    def _get_cache_type(self, query: str) -> str:
        """Determine cache type based on query"""
        query_lower = query.lower()
        if any(k in query_lower for k in ['price', 'cost', 'worth']):
            return 'price'
        if any(k in query_lower for k in ['news', 'latest', 'today']):
            return 'news'
        if any(k in query_lower for k in ['what is', 'who is', 'define']):
            return 'fact'
        return 'general'
    
    def get(self, query: str) -> Optional[Dict[str, Any]]:
        """Get cached result if fresh"""
        if query in self.cache:
            entry = self.cache[query]
            cache_type = self._get_cache_type(query)
            age = time.time() - entry['timestamp']
            
            if age < self.ttl[cache_type]:
                logger.info(f"Cache hit for: {query} (age: {age:.0f}s)")
                return {'data': entry['data'], 'fresh': True}
            else:
                logger.info(f"Cache expired for: {query}")
                del self.cache[query]
        
        return None
    
    def set(self, query: str, data: str):
        """Cache result"""
        self.cache[query] = {
            'data': data,
            'timestamp': time.time()
        }
        logger.info(f"Cached: {query}")


# ============================================================================
# SINGLETON INSTANCES
# ============================================================================

_price_checker_instance: Optional[PriceChecker] = None
_knowledge_cache_instance: Optional[KnowledgeCache] = None


def get_price_checker() -> PriceChecker:
    """Get global PriceChecker instance"""
    global _price_checker_instance
    if _price_checker_instance is None:
        _price_checker_instance = PriceChecker()
    return _price_checker_instance


def get_knowledge_cache(memory_manager) -> KnowledgeCache:
    """Get global KnowledgeCache instance"""
    global _knowledge_cache_instance
    if _knowledge_cache_instance is None:
        _knowledge_cache_instance = KnowledgeCache(memory_manager)
    return _knowledge_cache_instance
