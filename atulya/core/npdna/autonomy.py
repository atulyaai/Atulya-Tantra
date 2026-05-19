"""NP-DNA Autonomy Layer.

Implements the NpDnaAgent which wraps NpDnaCore in a ReAct (Reasoning and Acting)
execution loop, allowing the model to run search and memory storage tools.
"""
from __future__ import annotations
import re
import logging
from typing import Callable, Any
from .model import NpDnaCore

logger = logging.getLogger(__name__)

class NpDnaAgent:
    """ReAct-style autonomous agent wrapping NpDnaCore."""
    def __init__(self, core: NpDnaCore):
        self.core = core
        self.tools: dict[str, Callable[[str], str]] = {}
        
        # Register default cortex tools
        self.register_tool("cortex_search", self._cortex_search)
        self.register_tool("cortex_store", self._cortex_store)

    def register_tool(self, name: str, func: Callable[[str], str]) -> None:
        """Register a new python tool for the agent to call."""
        self.tools[name] = func
        logger.info("Tool '%s' registered with NpDnaAgent.", name)

    def _cortex_search(self, query: str) -> str:
        """Search memory cortex for query."""
        results = self.core.model.cortex.retrieve(query, top_k=2)
        if not results:
            return "No matching memories found."
        items = []
        for i, (text, score) in enumerate(results):
            items.append(f"Match {i+1} (score={score:.3f}): {text}")
        return "\n".join(items)

    def _cortex_store(self, fact: str) -> str:
        """Store a new fact in the memory cortex."""
        # Clean the fact/tag format
        fact_clean = fact.strip()
        self.core.model.cortex.store(fact_clean)
        # Force a save to disk if path is active
        if hasattr(self.core, "active_path") and self.core.active_path:
            self.core.save(self.core.active_path)
        return f"Successfully saved fact to cortex: '{fact_clean}'"

    def run(self, user_prompt: str, max_iterations: int = 5) -> str:
        """Execute the ReAct loop until response is reached or iteration limit is hit.

        Args:
            user_prompt: User request.
            max_iterations: Max ReAct steps to prevent infinite loop.

        Returns:
            The final text response from the agent.
        """
        # Format the system instructions
        system_instructions = (
            "You are an autonomous NP-DNA agent. Solve the user's goal by thinking step-by-step "
            "and invoking tools. Supported tools:\n"
            "  - Action: cortex_search[query]\n"
            "  - Action: cortex_store[fact]\n\n"
            "Format your output strictly using these tags:\n"
            "[Thought] Explain your reasoning here.\n"
            "Action: tool_name[arguments]\n"
            "[Observation] Results will be shown here.\n"
            "Action: respond[your final response to the user]\n"
        )
        
        context = f"{system_instructions}\nUser: {user_prompt}\n"
        
        for iteration in range(max_iterations):
            logger.info("NpDnaAgent iteration %d/%d", iteration + 1, max_iterations)
            
            # 1. Append [Thought] tag to prime the model
            current_prompt = context + "[Thought]"
            
            # 2. Generate response from the core model
            # Stop if we see [Observation] or similar tags
            output = self.core.generate(
                current_prompt,
                max_new_tokens=128,
                temperature=0.3,
                top_p=0.9
            )
            
            # Extract only the newly generated part
            new_text = output[len(current_prompt):].strip()
            logger.debug("Agent generated: %s", new_text)
            
            # Combine the thought to context
            context += "[Thought] " + new_text + "\n"
            
            # Parse for actions: Action: tool_name[args]
            # Match first action in the new text
            action_match = re.search(r"Action:\s*([a-zA-Z0-9_-]+)\[(.*?)\]", new_text)
            
            if not action_match:
                # If no formal action is generated, treat it as a direct response
                return new_text
            
            tool_name = action_match.group(1).strip()
            tool_arg = action_match.group(2).strip()
            
            if tool_name == "respond":
                return tool_arg
                
            if tool_name in self.tools:
                logger.info("Executing tool '%s' with arg: %s", tool_name, tool_arg)
                try:
                    observation = self.tools[tool_name](tool_arg)
                except Exception as e:
                    observation = f"Error executing tool: {str(e)}"
            else:
                observation = f"Unknown tool '{tool_name}'. Available: {list(self.tools.keys())}."
                
            logger.debug("Observation: %s", observation)
            
            # Append observation to context
            context += f"[Observation] {observation}\n"
            
        return "Agent failed to reach a conclusion within step limit."
