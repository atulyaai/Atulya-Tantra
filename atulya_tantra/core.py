"""
Tantra Core Engine
Central brain that orchestrates models, memory, and tools.
"""

import logging
import asyncio
from typing import Optional, Dict, Any

from .text_ai import TextAI
from .conversation_manager import ConversationManager
from .memory import MemoryManager
from .mcp_client import MCPClient, get_mcp_client
from .tools import (
    PriceChecker,
    get_price_checker,
    KnowledgeCache,
    get_knowledge_cache,
    IntelligentRouter
)
from .config_loader import get_config
from .constants import (
    VECTORS_DIR,
    MAX_CONVERSATION_HISTORY,
    DEFAULT_SYSTEM_PROMPT,
    ensure_directories
)

logger = logging.getLogger(__name__)

class TantraEngine:
    """
    The main brain of Tantra.
    Orchestrates:
    1. Intent Detection
    2. Tool Execution (Price, Search, etc.)
    3. Memory Retrieval (RAG)
    4. Response Generation
    5. Memory Storage
    """
    
    def __init__(
        self,
        text_model_name: Optional[str] = None,
        device: Optional[str] = None,
        hf_token: Optional[str] = None,
        cache_dir: Optional[str] = None,
        vision_ai: Optional[Any] = None,
        config_path: Optional[str] = None
    ):
        """
        Initialize Tantra Engine
        
        Args:
            text_model_name: Model name (default: from config)
            device: Device to use (default: from config)
            hf_token: HuggingFace token
            cache_dir: Cache directory
            vision_ai: Optional vision AI instance
            config_path: Path to config file
        """
        logger.info("Initializing Tantra Engine...")
        
        # Ensure directories exist
        ensure_directories()
        
        # Load configuration
        config = get_config(config_path)
        
        # 1. Initialize Text Model (only if VisionAI is not provided)
        self.vision_ai = vision_ai
        if not self.vision_ai:
            model_name = text_model_name or config.get_model_name()
            device_name = device or config.get_device()
            
            self.text_ai = TextAI(model_name, device_name, hf_token, cache_dir)
            self.text_ai.load_model()
        else:
            self.text_ai = None
            logger.info("Using VisionAI for generation")
        
        # 2. Initialize Conversation Manager
        system_prompt = config.get_system_prompt()
        max_history = config.get('conversation.max_history', MAX_CONVERSATION_HISTORY)
        self.conversation = ConversationManager(max_history=max_history, system_prompt=system_prompt)
        
        # 3. Initialize Memory & Cache
        self.memory = MemoryManager(persist_directory=str(VECTORS_DIR))
        self.knowledge_cache = get_knowledge_cache(self.memory)
        
        # 4. Initialize Tools
        self.price_checker = get_price_checker()
        self.mcp_client = get_mcp_client()
        
        # 5. Initialize Memory Extractor
        from .memory_extractor import MemoryExtractor
        self.extractor = MemoryExtractor()
        
        logger.info("✓ Tantra Engine Initialized")

    def process_message(self, user_message: str, image_data: Optional[str] = None) -> str:
        """
        Process a user message through the full AI pipeline
        """
        # 1. Add to conversation history
        # image_data can be a path or None
        self.conversation.add_user_message(user_message, image_path=image_data)
        
        # 2. Detect Intent & Execute Tools
        context_data = self._execute_tools(user_message)
        
        # 3. Retrieve Memory (RAG)
        memory_context = self._get_memory_context(user_message)
        
        # 4. Build Final Prompt
        messages = self.conversation.get_messages_for_model()
        
        # Inject context if available
        full_context = []
        if context_data:
            full_context.append(f"LIVE DATA:\n{context_data}")
        if memory_context:
            full_context.append(f"MEMORY:\n{memory_context}")
            
        if full_context:
            context_str = "\n\n".join(full_context)
            
            # Append context to the last user message
            last_msg = messages[-1]
            if last_msg['role'] == 'user':
                # Handle both text-only and multimodal content structures
                if isinstance(last_msg['content'], str):
                     last_msg['content'] += f"\n\n[CONTEXT]\n{context_str}\n[/CONTEXT]"
                elif isinstance(last_msg['content'], list):
                    for content_part in last_msg['content']:
                        if content_part['type'] == 'text':
                            content_part['text'] += f"\n\n[CONTEXT]\n{context_str}\n[/CONTEXT]"
                            break
            
        # 5. Generate Response
        max_tokens = get_config().get_max_tokens()
        
        if self.vision_ai:
            response_text = self.vision_ai.generate_response(messages, max_tokens=max_tokens)
        elif self.text_ai:
            response_text = self.text_ai.generate_response(messages, max_tokens=max_tokens)
        else:
            response_text = "Error: No model available."
        
        # 6. Store & Return
        self.conversation.add_assistant_message(response_text)
        self.memory.store_conversation(user_message, response_text)
        
        # 7. Extract & Store Structured Memory
        try:
            extracted_items = self.extractor.extract_from_message(user_message)
            for item_type, key, value in extracted_items:
                if item_type == "preference":
                    self.memory.store_preference(key, value)
                elif item_type == "fact":
                    self.memory.store_fact(f"{key}: {value}", source="auto_extraction")
        except Exception as e:
            logger.error(f"Memory extraction failed: {e}")
        
        return response_text

    def _execute_tools(self, message: str) -> Optional[str]:
        """
        Analyze message and execute appropriate tools
        """
        msg_lower = message.lower()
        results = []
        
        # --- Tool 1: Crypto & Gold Price (Unified) ---
        if 'news' not in msg_lower:
            is_price_query = any(k in msg_lower for k in ['price', 'cost', 'worth', 'value', 'rate', 'how much'])
            crypto_keywords = ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto']
            is_crypto = any(k in msg_lower for k in crypto_keywords)
            is_gold = 'gold' in msg_lower and any(k in msg_lower for k in ['india', 'inr', 'rupee'])
            stock_indicators = ['stock', 'share', 'market', 'inc.', 'inc', 'corp.', 'corp', 'ltd.', 'ltd', 'company']
            is_stock = any(k in msg_lower for k in stock_indicators) or message.isupper()
            
            print(f"DEBUG: msg='{message}', price={is_price_query}, crypto={is_crypto}, gold={is_gold}, stock={is_stock}")
            
            if is_price_query and (is_crypto or is_gold or is_stock):
                print("DEBUG: Calling Price Checker")
                price_result = self.price_checker.get_any_price(message)
                if price_result and "Unable" not in price_result:
                    results.append(f"Market Data: {price_result}")
                    logger.info(f"Tool Used: Price Checker ({message})")

        # --- Tool 2: Fact Check ---
        # Trigger: "check if", "is it true", "verify", "fact check"
        fact_check_triggers = ['check if', 'is it true', 'verify', 'fact check', 'is that correct']
        if any(t in msg_lower for t in fact_check_triggers):
            try:
                logger.info(f"Tool Used: Fact Check ({message})")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                fact_result = loop.run_until_complete(
                    self.mcp_client.fact_check(message)
                )
                loop.close()
                results.append(f"Fact Check Result: {fact_result}")
            except Exception as e:
                logger.error(f"Fact Check Failed: {e}")

        # --- Tool 3: MCP Search (Web) ---
        search_triggers = ['news', 'weather', 'stock', 'latest', 'current', 'today', 'who is', 'what is']
        needs_search = any(t in msg_lower for t in search_triggers)
        
        if needs_search and not results:
            query = message
            if 'news' in msg_lower:
                query = f"{message} latest headlines"
            elif 'weather' in msg_lower:
                query = f"current weather {message}"
            
            cached = self.knowledge_cache.get(query)
            if cached and cached['fresh']:
                results.append(f"Cached Search: {cached['data']}")
                logger.info("Tool Used: Cache Hit")
            else:
                try:
                    logger.info(f"Tool Used: MCP Search ({query})")
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    search_result = loop.run_until_complete(
                        self.mcp_client.web_search(query, max_results=3)
                    )
                    loop.close()
                    
                    if search_result and "No results" not in search_result:
                        results.append(f"Web Search Results:\n{search_result}")
                        self.knowledge_cache.set(query, search_result)
                except Exception as e:
                    logger.error(f"MCP Search Failed: {e}")

        return "\n\n".join(results) if results else None

    def _get_memory_context(self, message: str) -> Optional[str]:
        """Get relevant context from vector memory"""
        try:
            context = self.memory.search_all(message, n_results=2)
            parts = []
            
            if context['conversations']:
                parts.append("Past Conversations:")
                for c in context['conversations']:
                    parts.append(f"- {c['text'][:100]}...")
            
            if context['preferences']:
                parts.append("User Preferences:")
                for p in context['preferences']:
                    parts.append(f"- {p['text']}")
            
            # Also include relevant facts
            if context['facts']:
                parts.append("Relevant Facts:")
                for f in context['facts']:
                    parts.append(f"- {f['text']}")
                    
            return "\n".join(parts) if parts else None
        except Exception as e:
            logger.error(f"Memory retrieval failed: {e}")
            return None
