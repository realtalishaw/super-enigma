"""
Enhanced suggestions service that uses semantic search for better tool recommendations.
"""

import logging
from typing import List, Dict, Any, Optional
import json

from core.semantic_search.search_service import SemanticSearchService
from pathlib import Path

logger = logging.getLogger(__name__)

class SemanticSuggestionsService:
    """
    Service that provides enhanced tool suggestions using semantic search.
    """
    
    def __init__(self, search_service: Optional[SemanticSearchService] = None):
        """
        Initialize the semantic suggestions service.
        
        Args:
            search_service: Optional pre-initialized search service
        """
        self.search_service = search_service or self._create_search_service()
    
    def _create_search_service(self) -> SemanticSearchService:
        """Create a search service instance."""
        project_root = Path(__file__).parent.parent.parent.parent
        index_path = project_root / "data" / "semantic_index"
        
        return SemanticSearchService(
            embedding_model="all-MiniLM-L6-v2",
            index_path=index_path
        )
    
    def get_tool_suggestions(
        self, 
        user_prompt: str, 
        max_suggestions: int = 10,
        include_actions: bool = True,
        include_triggers: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get tool suggestions based on user prompt using semantic search.
        
        Args:
            user_prompt: User's natural language prompt
            max_suggestions: Maximum number of suggestions to return
            include_actions: Whether to include action tools
            include_triggers: Whether to include trigger tools
            
        Returns:
            List of tool suggestions with metadata
        """
        try:
            # Determine filter types
            filter_types = []
            if include_actions:
                filter_types.append("action")
            if include_triggers:
                filter_types.append("trigger")
            
            # Perform semantic search
            search_results = self.search_service.search(
                query=user_prompt,
                k=max_suggestions * 2,  # Get more results for better filtering
                filter_types=filter_types
            )
            
            # Process and format results
            suggestions = []
            for result in search_results[:max_suggestions]:
                item = result["item"]
                suggestion = self._format_tool_suggestion(item, result["similarity_score"])
                if suggestion:
                    suggestions.append(suggestion)
            
            logger.info(f"Generated {len(suggestions)} tool suggestions for prompt: '{user_prompt[:50]}...'")
            return suggestions
            
        except Exception as e:
            logger.error(f"Error generating tool suggestions: {e}")
            return []
    
    def get_workflow_suggestions(
        self, 
        user_prompt: str, 
        max_suggestions: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get workflow suggestions by finding related tools and suggesting combinations.
        
        Args:
            user_prompt: User's natural language prompt
            max_suggestions: Maximum number of workflow suggestions
            
        Returns:
            List of workflow suggestions
        """
        try:
            # Get tool suggestions
            tool_suggestions = self.get_tool_suggestions(
                user_prompt, 
                max_suggestions=max_suggestions * 2
            )
            
            # Group tools by type and provider
            triggers = [t for t in tool_suggestions if t.get("tool_type") == "trigger"]
            actions = [t for t in tool_suggestions if t.get("tool_type") == "action"]
            
            # Generate workflow suggestions
            workflows = []
            
            # Simple trigger + action combinations
            for trigger in triggers[:3]:  # Limit triggers
                for action in actions[:5]:  # Limit actions per trigger
                    workflow = {
                        "name": f"{trigger['name']} → {action['name']}",
                        "description": f"When {trigger['description']}, then {action['description']}",
                        "trigger": trigger,
                        "actions": [action],
                        "confidence": (trigger["similarity_score"] + action["similarity_score"]) / 2,
                        "workflow_type": "simple"
                    }
                    workflows.append(workflow)
            
            # Sort by confidence and limit results
            workflows.sort(key=lambda x: x["confidence"], reverse=True)
            return workflows[:max_suggestions]
            
        except Exception as e:
            logger.error(f"Error generating workflow suggestions: {e}")
            return []
    
    def get_similar_tools(
        self, 
        tool_item: Dict[str, Any], 
        max_similar: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find tools similar to a given tool.
        
        Args:
            tool_item: Tool to find similar tools for
            max_similar: Maximum number of similar tools to return
            
        Returns:
            List of similar tools
        """
        try:
            similar_results = self.search_service.search_similar_tools(
                tool_item=tool_item,
                k=max_similar,
                exclude_self=True
            )
            
            similar_tools = []
            for result in similar_results:
                tool = self._format_tool_suggestion(result["item"], result["similarity_score"])
                if tool:
                    similar_tools.append(tool)
            
            return similar_tools
            
        except Exception as e:
            logger.error(f"Error finding similar tools: {e}")
            return []
    
    def _format_tool_suggestion(
        self, 
        item: Dict[str, Any], 
        similarity_score: float
    ) -> Optional[Dict[str, Any]]:
        """
        Format a search result item into a tool suggestion.
        
        Args:
            item: Search result item
            similarity_score: Similarity score from search
            
        Returns:
            Formatted tool suggestion or None if invalid
        """
        try:
            if item.get("type") not in ["action", "trigger"]:
                return None
            
            suggestion = {
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "description": item.get("description", ""),
                "tool_type": item.get("tool_type", item.get("type")),
                "provider_id": item.get("provider_id", ""),
                "provider_name": item.get("provider_name", ""),
                "similarity_score": similarity_score,
                "parameters": item.get("parameters", []),
                "examples": item.get("examples", []),
                "metadata": item.get("metadata", {})
            }
            
            return suggestion
            
        except Exception as e:
            logger.error(f"Error formatting tool suggestion: {e}")
            return None
    
    def get_search_stats(self) -> Dict[str, Any]:
        """Get statistics about the semantic search system."""
        try:
            return self.search_service.get_index_stats()
        except Exception as e:
            logger.error(f"Error getting search stats: {e}")
            return {}
