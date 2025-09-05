"""
DSL LLM Generator Service

Uses Claude (Anthropic) to generate workflow DSL templates from natural language prompts.
Implements a two-step RAG workflow: Tool Retrieval + Focused Generation.
Integrates with the catalog system to ensure valid triggers and actions.
"""

import logging
import json
import httpx
import asyncio
from typing import Dict, Any, Optional, List
from .models import GenerationRequest, GenerationResponse, GenerationContext, CatalogContext
from .catalog_manager import CatalogManager
from .context_builder import ContextBuilder
from .prompt_builder import PromptBuilder
from .ai_client import AIClient
from .response_parser import ResponseParser
from .workflow_validator import WorkflowValidator

from core.config import settings
from core.semantic_search.search_service import SemanticSearchService


logger = logging.getLogger(__name__)

def log_json_pretty(data: Any, prefix: str = "", max_length: int = 2000):
    """Helper function to log JSON data in a pretty format with length limits"""
    try:
        if isinstance(data, (dict, list)):
            json_str = json.dumps(data, indent=2, default=str)
            if len(json_str) > max_length:
                json_str = json_str[:max_length] + "... [TRUNCATED]"
            logger.info(f"{prefix}\n{json_str}")
        else:
            logger.info(f"{prefix}: {data}")
    except Exception as e:
        logger.error(f"Failed to log JSON data: {e}")
        logger.info(f"{prefix}: {str(data)[:500]}")

def log_function_entry(func_name: str, **kwargs):
    """Log function entry with parameters"""
    logger.info(f"🔵 ENTERING {func_name}")
    for key, value in kwargs.items():
        if isinstance(value, (dict, list)):
            log_json_pretty(value, f"  📥 {key}:")
        else:
            logger.info(f"  📥 {key}: {value}")

def log_function_exit(func_name: str, result: Any = None, success: bool = True):
    """Log function exit with result"""
    status = "✅" if success else "❌"
    logger.info(f"{status} EXITING {func_name}")
    if result is not None:
        if isinstance(result, (dict, list)):
            log_json_pretty(result, f"  📤 Result:")
        else:
            logger.info(f"  📤 Result: {result}")


class DSLGeneratorService:
    """
    Service for generating workflow DSL templates using Claude LLM.
    
    This service implements a two-step RAG workflow:
    1. Tool Retrieval: Intelligently selects relevant tools from the catalog
    2. Focused Generation: Uses Claude with targeted tools to generate workflows
    
    This approach is much more reliable than sending the entire catalog to the LLM.
    """
    
    # System-essential tools that must be available when Groq analysis fails
    SYSTEM_ESSENTIAL_TRIGGERS = [
        {
            'slug': 'SCHEDULE_BASED',
            'name': 'Schedule Based Trigger',
            'description': 'A trigger that runs on a schedule (e.g., "every day", "at 8 AM", "on Fridays").',
            'toolkit_slug': 'system',
            'toolkit_name': 'System',
            'trigger_slug': 'SCHEDULE_BASED',
            'metadata': {'type': 'schedule_based'}
        }
    ]
    
    # Golden toolkits that get priority boost in semantic search results
    GOLDEN_TOOLKITS = {
        "gmail", "discord", "slack", "whatsapp", "telegram", "twitter", "reddit", 
        "linkedin", "facebook", "instagram", "youtube", "tiktok", "spotify", 
        "google_calendar", "google_drive", "google_photos", "dropbox", "onedrive", 
        "notion", "todoist", "coinbase", "shopify", "stripe", "google_maps", 
        "google_sheets", "google_docs", "google_slides", "google_tasks", "excel", 
        "trello", "asana", "ticktick", "canva", "pushbullet", "pexels", "tinypng", 
        "splitwise", "ynab", "foursquare", "surveymonkey", "listennotes"
    }
    
    def __init__(self, anthropic_api_key: Optional[str] = None):
        """
        Initialize the DSL generator service.
        
        Args:
            anthropic_api_key: Anthropic API key for Claude access (optional, will use config if not provided)
        """
        # Initialize core components
        self.catalog_manager = CatalogManager()
        self.context_builder = ContextBuilder(self.catalog_manager)
        self.prompt_builder = PromptBuilder()
        self.ai_client = AIClient(anthropic_api_key)
        self.response_parser = ResponseParser()
        self.workflow_validator = WorkflowValidator()
        
        # Initialize semantic search service
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        index_path = project_root / "data" / "semantic_index"
        self.semantic_search = SemanticSearchService(index_path=index_path)

        
        # Groq configuration for tool retrieval (from config)
        self.groq_api_key = settings.groq_api_key
        self.groq_base_url = "https://api.groq.com/openai/v1"
        self.groq_model = "llama-3.1-8b-instant"  # Current fast model for tool retrieval
        
        # Tool selection limits to keep context concise
        self.max_triggers = settings.max_triggers
        self.max_actions = settings.max_actions
        self.max_providers = settings.max_providers
        
        # Maximum regeneration attempts to prevent infinite loops
        self.max_regeneration_attempts = 3
        
        # Rate limiting for Claude API calls
        self.claude_rate_limit_delay = settings.claude_rate_limit_delay
        self.max_rate_limit_delay = settings.max_rate_limit_delay
    
    def set_global_cache(self, processed_catalog: Dict[str, Any]):
        """Set the catalog cache from the global cache service"""
        self.catalog_manager.set_global_cache(processed_catalog)
    
    async def initialize(self):
        """Initialize all service components"""
        try:
            # Initialize catalog manager
            await self.catalog_manager.initialize()
            
            # Preload catalog cache
            await self.catalog_manager.preload_catalog_cache()
            
            logger.info("DSL Generator service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize DSL Generator service: {e}")
            # Don't raise - allow service to continue in limited mode
    
    async def generate_workflow(self, request: GenerationRequest) -> GenerationResponse:
        """
        Generate a workflow DSL template using the new two-step RAG workflow.
        
        Args:
            request: Generation request with user prompt and context
            
        Returns:
            GenerationResponse with DSL template and missing fields
        """
        log_function_entry("generate_workflow", request=request)
        
        try:
            # Check for vagueness and return exemplar workflows if detected
            is_vague = await self._detect_vagueness(request.user_prompt)
            if is_vague:
                logger.info(f"🔍 Vague prompt detected. Returning exemplar workflows for '{is_vague['reason']}'.")
                return self._get_exemplar_workflows(is_vague['reason'])
            
            # Ensure service is initialized
            if not self.catalog_manager.catalog_service:
                logger.info("🔧 Service not initialized, initializing now...")
                await self.initialize()
            
            # Step 1: Tool Retrieval - Get relevant tools from catalog
            logger.info("🔍 Step 1: Performing tool retrieval...")
            pruned_catalog_context = await self._retrieve_relevant_tools(request)
            
            if not pruned_catalog_context:
                logger.error("❌ Tool retrieval failed - no context returned")
                result = GenerationResponse(
                    success=False,
                    error_message="Failed to retrieve relevant tools from catalog",
                    missing_fields=[],
                    confidence=0.0
                )
                log_function_exit("generate_workflow", result, success=False)
                return result
            
            logger.info(f"✅ Tool retrieval complete. Found {len(pruned_catalog_context.get('triggers', []))} triggers and {len(pruned_catalog_context.get('actions', []))} actions")
            log_json_pretty(pruned_catalog_context, "📋 Retrieved catalog context:")
            
            # Limit tools to keep context concise and prevent Claude API size limits
            logger.info("🔧 Limiting tools for Claude context...")
            limited_catalog_context = self._limit_tools_for_context(pruned_catalog_context)
            log_json_pretty(limited_catalog_context, "📋 Limited catalog context:")
            
            # Step 2: Focused Generation - Generate workflow with targeted tools
            logger.info("🤖 Step 2: Performing focused generation...")
            result = await self._generate_with_validation_loop(request, limited_catalog_context)
            log_function_exit("generate_workflow", result, success=result.success)
            return result
            
        except Exception as e:
            logger.error(f"❌ Workflow generation failed: {e}")
            result = GenerationResponse(
                success=False,
                error_message=str(e),
                missing_fields=[],
                confidence=0.0
            )
            log_function_exit("generate_workflow", result, success=False)
            return result

    async def generate_multiple_workflows(self, request: GenerationRequest, num_workflows: int = 1) -> List[GenerationResponse]:
        """
        Generate multiple workflow DSL templates in parallel.
        
        Args:
            request: Generation request with user prompt and context
            num_workflows: Number of workflows to generate (1-5)
            
        Returns:
            List of GenerationResponse objects
        """
        if num_workflows < 1 or num_workflows > 5:
            raise ValueError("num_workflows must be between 1 and 5")
        
        if num_workflows == 1:
            # Single generation - use the existing method
            response = await self.generate_workflow(request)
            return [response]
        
        logger.info(f"Generating {num_workflows} workflows in parallel...")
        
        # Create tasks for parallel generation
        tasks = []
        for i in range(num_workflows):
            # Create a slightly modified request for each generation to add variety
            modified_request = GenerationRequest(
                user_prompt=request.user_prompt,
                selected_apps=request.selected_apps,
                user_id=request.user_id,
                workflow_type=request.workflow_type,
                complexity=request.complexity
            )
            
            # Add a small variation to the prompt to encourage diversity
            if i > 0:
                modified_request.user_prompt = f"{request.user_prompt} (variation {i+1})"
            
            task = self.generate_workflow(modified_request)
            tasks.append(task)
        
        # Execute all generations in parallel
        try:
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results and handle any exceptions
            processed_responses = []
            for i, response in enumerate(responses):
                if isinstance(response, Exception):
                    logger.warning(f"Generation {i+1} failed: {response}")
                    # Create a fallback response for failed generations
                    fallback_response = GenerationResponse(
                        success=False,
                        error_message=f"Generation failed: {str(response)}",
                        missing_fields=[],
                        confidence=0.0
                    )
                    processed_responses.append(fallback_response)
                else:
                    processed_responses.append(response)
            
            logger.info(f"Successfully generated {len(processed_responses)} workflows")
            return processed_responses
            
        except Exception as e:
            logger.error(f"Parallel workflow generation failed: {e}")
            # Fallback to single generation
            fallback_response = await self.generate_workflow(request)
            return [fallback_response]
    
    async def _retrieve_relevant_tools(self, request: GenerationRequest) -> Optional[Dict[str, Any]]:
        """
        Step 1: Intelligently retrieve relevant tools using semantic search + Groq LLM analysis.
        
        This method implements the "Retrieval" step of the RAG workflow:
        1. Semantic search finds potentially relevant tools
        2. Groq LLM analyzes those tools and selects the best ones for the specific task
        3. If selected_apps provided: Filters results to only those providers
        
        Args:
            request: Generation request with user prompt and context
            
        Returns:
            Pruned catalog context with only relevant tools, or None if failed
        """
        log_function_entry("_retrieve_relevant_tools", request=request)
        
        try:
            logger.info(f"🔍 Using semantic search + Groq LLM analysis for tool retrieval")
            logger.info(f"📝 User prompt: {request.user_prompt[:100]}...")
            if request.selected_apps:
                logger.info(f"🎯 Selected apps filter: {request.selected_apps}")
            else:
                logger.info("🎯 No selected apps filter - will search all providers")
            
            # Step 1: Use semantic search to find potentially relevant tools
            logger.info("🔍 Step 1a: Running semantic search...")
            search_results = self.semantic_search.search(
                query=request.user_prompt,
                k=100,  # Get more results for Groq to analyze
                filter_types=["action", "trigger"],  # Only get tools, not providers
                filter_providers=request.selected_apps if request.selected_apps else None
            )
            
            if not search_results:
                logger.warning("⚠️ No semantic search results found")
                log_function_exit("_retrieve_relevant_tools", None, success=False)
                return None
            
            logger.info(f"✅ Semantic search found {len(search_results)} potentially relevant tools")
            log_json_pretty(search_results[:5], "📋 Sample semantic search results (first 5):")
            
            # Apply Golden Toolkit priority boost
            logger.info("⭐ Applying Golden Toolkit priority boost...")
            boosted_results = self._apply_golden_toolkit_boost(search_results)
            logger.info(f"✅ Applied priority boost to {len(boosted_results)} results")
            
            # Pre-filter semantic search results to keep only top N most relevant
            logger.info("🔧 Pre-filtering semantic results to keep top 5 triggers and top 15 actions...")
            prefiltered_results = self._prefilter_semantic_results(
                boosted_results, 
                max_triggers=5, 
                max_actions=15,
                selected_apps=request.selected_apps
            )
            logger.info(f"✅ Pre-filtered from {len(search_results)} to {len(prefiltered_results)} results")
            
            # Convert semantic search results to the expected catalog format
            logger.info("🔄 Converting semantic results to catalog format...")
            semantic_context = self._convert_semantic_results_to_catalog(prefiltered_results)
            log_json_pretty(semantic_context, "📋 Converted semantic context:")
            
            # Step 2: Use Groq LLM to analyze and select the best tools for the specific task
            # ALWAYS use semantic search results for Groq analysis, regardless of selected_apps
            # This prevents prompt bloat and maintains efficiency
            if self.groq_api_key:
                logger.info("🤖 Using Groq LLM to analyze and select best tools from semantic results")
                pruned_context = await self._groq_analyze_semantic_results(request.user_prompt, semantic_context)
            else:
                logger.info("⏭️ Skipping Groq analysis (no API key available)")
                pruned_context = semantic_context
            
            log_json_pretty(pruned_context, "📋 Pruned context after Groq analysis:")
            
            # Apply tool limits to keep context concise
            logger.info("🔧 Applying tool limits for context...")
            limited_context = self._limit_tools_for_context(pruned_context)
            
            logger.info(f"✅ Final pruned context: {len(limited_context.get('triggers', []))} triggers, {len(limited_context.get('actions', []))} actions")
            log_json_pretty(limited_context, "📋 Final limited context:")
            
            log_function_exit("_retrieve_relevant_tools", limited_context, success=True)
            return limited_context
                
        except Exception as e:
            logger.error(f"❌ Semantic + Groq tool retrieval failed: {e}")
            # Fallback to basic search if semantic search fails
            logger.info("🔄 Falling back to basic search...")
            result = await self._fallback_basic_search_from_catalog(request)
            log_function_exit("_retrieve_relevant_tools", result, success=result is not None)
            return result
    
    def _convert_semantic_results_to_catalog(self, search_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Convert semantic search results to the expected catalog format.
        
        Args:
            search_results: List of semantic search results
            
        Returns:
            Catalog format with triggers, actions, and providers
        """
        pruned_context = {
            'triggers': [],
            'actions': [],
            'providers': {}
        }
        
        # Always include essential system tools
        self._add_essential_system_tools(pruned_context)
        
        for result in search_results:
            item = result['item']
            item_type = item.get('type', '')
            provider_id = item.get('provider_id', '')
            provider_name = item.get('provider_name', '')
            
            # Add provider info if not already present
            if provider_id and provider_id not in pruned_context['providers']:
                pruned_context['providers'][provider_id] = {
                    'name': provider_name or provider_id,
                    'description': item.get('description', ''),
                    'category': item.get('category', '')
                }
            
            # Convert to catalog format based on type
            if item_type == 'trigger':
                catalog_trigger = {
                    'slug': item.get('slug', ''),
                    'name': item.get('name', ''),
                    'description': item.get('description', ''),
                    'toolkit_slug': provider_id,
                    'toolkit_name': provider_name,
                    'trigger_slug': item.get('slug', ''),
                    'metadata': item.get('metadata', {}),
                    'similarity_score': result.get('similarity_score', 0.0)
                }
                pruned_context['triggers'].append(catalog_trigger)
                
            elif item_type == 'action':
                catalog_action = {
                    'slug': item.get('slug', ''),
                    'name': item.get('name', ''),
                    'description': item.get('description', ''),
                    'toolkit_slug': provider_id,
                    'toolkit_name': provider_name,
                    'action_slug': item.get('slug', ''),
                    'metadata': item.get('metadata', {}),
                    'similarity_score': result.get('similarity_score', 0.0)
                }
                pruned_context['actions'].append(catalog_action)
        
        # Sort by similarity score (highest first)
        pruned_context['triggers'].sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
        pruned_context['actions'].sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
        
        logger.info(f"Converted {len(search_results)} semantic results to {len(pruned_context['triggers'])} triggers and {len(pruned_context['actions'])} actions")
        
        return pruned_context
    
    def _add_essential_system_tools(self, pruned_context: Dict[str, Any]) -> None:
        """
        Add essential system tools that should always be available.
        
        Args:
            pruned_context: The catalog context to add essential tools to
        """
        # Add system provider
        pruned_context['providers']['system'] = {
            'name': 'System',
            'description': 'System-level tools and triggers for workflow automation',
            'category': 'system',
            'slug': 'system'
        }
        
        # Add SCHEDULE_BASED trigger
        schedule_trigger = {
            'slug': 'SCHEDULE_BASED',
            'name': 'Schedule Based Trigger',
            'description': 'Trigger that runs on a schedule (cron-based)',
            'toolkit_slug': 'system',
            'toolkit_name': 'System',
            'trigger_slug': 'SCHEDULE_BASED',
            'metadata': {
                'type': 'schedule_based',
                'essential': True
            },
            'similarity_score': 1.0  # High score to ensure it's always available
        }
        
        # Only add if not already present
        existing_schedule = any(t.get('trigger_slug') == 'SCHEDULE_BASED' for t in pruned_context['triggers'])
        if not existing_schedule:
            pruned_context['triggers'].append(schedule_trigger)
            logger.info("✅ Added essential SCHEDULE_BASED trigger to catalog context")
        
        logger.info("✅ Added essential system tools to catalog context")
    
    def _prefilter_semantic_results(self, search_results: List[Dict[str, Any]], max_triggers: int = 5, max_actions: int = 15, selected_apps: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Pre-filter semantic search results to keep only the top N most relevant results.
        If selected_apps is provided, ensures balanced representation across apps.
        
        Args:
            search_results: List of semantic search results
            max_triggers: Maximum number of triggers to keep
            max_actions: Maximum number of actions to keep
            selected_apps: Optional list of selected app slugs for balanced selection
            
        Returns:
            Pre-filtered list of semantic search results
        """
        triggers = []
        actions = []
        
        # Separate triggers and actions
        for result in search_results:
            item_type = result['item'].get('type', '')
            if item_type == 'trigger':
                triggers.append(result)
            elif item_type == 'action':
                actions.append(result)
        
        # If selected_apps is provided, use balanced selection per app
        if selected_apps and len(selected_apps) > 1:
            logger.info(f"🎯 Using balanced selection across {len(selected_apps)} apps: {selected_apps}")
            top_triggers = self._select_balanced_tools(triggers, max_triggers, selected_apps, "triggers")
            top_actions = self._select_balanced_tools(actions, max_actions, selected_apps, "actions")
        elif not selected_apps:
            # For vague prompts: auto-select best golden apps, then apply balanced selection
            logger.info("🎯 No selected apps - auto-selecting best golden apps for balanced selection")
            auto_selected_apps = self._auto_select_golden_apps(triggers + actions, max_apps=4)
            if auto_selected_apps and len(auto_selected_apps) > 1:
                logger.info(f"⭐ Auto-selected golden apps: {auto_selected_apps}")
                top_triggers = self._select_balanced_tools(triggers, max_triggers, auto_selected_apps, "triggers")
                top_actions = self._select_balanced_tools(actions, max_actions, auto_selected_apps, "actions")
            else:
                # Fallback to original behavior if no golden apps found
                logger.info("⚠️ No golden apps found - using pure semantic ranking")
                triggers.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
                actions.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
                top_triggers = triggers[:max_triggers]
                top_actions = actions[:max_actions]
        else:
            # Single app selected: use original behavior
            logger.info(f"🎯 Single app selected - using pure semantic ranking for {selected_apps[0]}")
            triggers.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
            actions.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
            
            top_triggers = triggers[:max_triggers]
            top_actions = actions[:max_actions]
        
        # Always ensure system tools are available (for schedule-based workflows)
        self._ensure_system_tools_available(top_triggers, top_actions)
        
        # Combine and return
        prefiltered = top_triggers + top_actions
        
        logger.info(f"Pre-filtered results: {len(top_triggers)} triggers (from {len(triggers)}), {len(top_actions)} actions (from {len(actions)})")
        
        return prefiltered
    
    def _select_balanced_tools(self, tools: List[Dict[str, Any]], max_tools: int, selected_apps: List[str], tool_type: str) -> List[Dict[str, Any]]:
        """
        Select tools ensuring balanced representation across selected apps.
        
        Args:
            tools: List of tools (triggers or actions) to select from
            max_tools: Maximum number of tools to select
            selected_apps: List of selected app slugs
            tool_type: Type of tools being selected ("triggers" or "actions")
            
        Returns:
            List of selected tools with balanced app representation
        """
        if not tools or not selected_apps:
            return tools[:max_tools]
        
        # Group tools by provider/app
        tools_by_app = {}
        for tool in tools:
            provider_id = tool['item'].get('provider_id', '').lower()
            if provider_id not in tools_by_app:
                tools_by_app[provider_id] = []
            tools_by_app[provider_id].append(tool)
        
        # Sort tools within each app by similarity score
        for app in tools_by_app:
            tools_by_app[app].sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
        
        # Calculate tools per app (roughly equal distribution)
        num_apps = len(selected_apps)
        tools_per_app = max(1, max_tools // num_apps)  # At least 1 tool per app
        remaining_tools = max_tools - (tools_per_app * num_apps)
        
        selected_tools = []
        app_counts = {}
        
        # First pass: allocate base number of tools per app
        for app in selected_apps:
            app_lower = app.lower()
            if app_lower in tools_by_app:
                # Take up to tools_per_app tools from this app
                app_tools = tools_by_app[app_lower][:tools_per_app]
                selected_tools.extend(app_tools)
                app_counts[app_lower] = len(app_tools)
                logger.debug(f"📊 {tool_type.capitalize()} from {app}: {len(app_tools)} tools")
            else:
                app_counts[app_lower] = 0
                logger.warning(f"⚠️ No {tool_type} found for selected app: {app}")
        
        # Second pass: distribute remaining tools to apps with highest scores
        if remaining_tools > 0:
            # Collect remaining tools from all apps, sorted by score
            remaining_candidates = []
            for app in selected_apps:
                app_lower = app.lower()
                if app_lower in tools_by_app:
                    # Get tools beyond what we already selected
                    already_selected = app_counts.get(app_lower, 0)
                    remaining_from_app = tools_by_app[app_lower][already_selected:]
                    remaining_candidates.extend(remaining_from_app)
            
            # Sort by similarity score and take the best remaining tools
            remaining_candidates.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
            selected_tools.extend(remaining_candidates[:remaining_tools])
        
        # Sort final selection by similarity score
        selected_tools.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
        
        # Log the final distribution
        final_counts = {}
        for tool in selected_tools:
            app = tool['item'].get('provider_id', '').lower()
            final_counts[app] = final_counts.get(app, 0) + 1
        
        logger.info(f"📊 Balanced {tool_type} selection: {dict(final_counts)} (total: {len(selected_tools)})")
        
        return selected_tools
    
    def _auto_select_golden_apps(self, tools: List[Dict[str, Any]], max_apps: int = 4) -> List[str]:
        """
        Auto-select the best golden apps based on semantic relevance for vague prompts.
        
        Args:
            tools: List of tools (triggers + actions) from semantic search
            max_apps: Maximum number of apps to auto-select
            
        Returns:
            List of auto-selected golden app slugs
        """
        if not tools:
            return []
        
        # Group tools by provider and calculate relevance scores
        app_scores = {}
        app_tool_counts = {}
        
        for tool in tools:
            provider_id = tool['item'].get('provider_id', '').lower()
            similarity_score = tool.get('similarity_score', 0.0)
            
            # Only consider golden toolkits
            if provider_id in self.GOLDEN_TOOLKITS:
                if provider_id not in app_scores:
                    app_scores[provider_id] = 0.0
                    app_tool_counts[provider_id] = 0
                
                # Accumulate scores and count tools
                app_scores[provider_id] += similarity_score
                app_tool_counts[provider_id] += 1
        
        if not app_scores:
            logger.warning("⚠️ No golden toolkit tools found in semantic search results")
            return []
        
        # Calculate average relevance score per app
        app_avg_scores = {}
        for app, total_score in app_scores.items():
            tool_count = app_tool_counts[app]
            avg_score = total_score / tool_count if tool_count > 0 else 0.0
            app_avg_scores[app] = avg_score
        
        # Sort apps by average relevance score (highest first)
        sorted_apps = sorted(app_avg_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Take top N apps
        selected_apps = [app for app, score in sorted_apps[:max_apps]]
        
        # Log the selection process
        logger.info(f"⭐ Golden app selection process:")
        for i, (app, score) in enumerate(sorted_apps[:max_apps]):
            tool_count = app_tool_counts[app]
            logger.info(f"  {i+1}. {app}: avg_score={score:.3f}, tools={tool_count}")
        
        if len(sorted_apps) > max_apps:
            logger.info(f"  ... and {len(sorted_apps) - max_apps} more apps not selected")
        
        logger.info(f"🎯 Auto-selected {len(selected_apps)} golden apps: {selected_apps}")
        
        return selected_apps
    
    def _ensure_system_tools_available(self, top_triggers: List[Dict[str, Any]], top_actions: List[Dict[str, Any]]) -> None:
        """
        Ensure that system tools (like SCHEDULE_BASED trigger) are always available in the final selection.
        
        Args:
            top_triggers: List of selected triggers
            top_actions: List of selected actions
        """
        # Check if SCHEDULE_BASED trigger is already present
        has_schedule_trigger = any(
            t.get('item', {}).get('slug') == 'SCHEDULE_BASED' or 
            t.get('item', {}).get('trigger_slug') == 'SCHEDULE_BASED'
            for t in top_triggers
        )
        
        if not has_schedule_trigger:
            # Add SCHEDULE_BASED trigger to the top of the list
            schedule_trigger = {
                'item': {
                    'type': 'trigger',
                    'provider_id': 'system',
                    'provider_name': 'System',
                    'slug': 'SCHEDULE_BASED',
                    'name': 'Schedule Based Trigger',
                    'description': 'Trigger that runs on a schedule (cron-based)',
                    'metadata': {'type': 'schedule_based', 'essential': True}
                },
                'similarity_score': 1.0  # High score to ensure it's prioritized
            }
            
            # Insert at the beginning to ensure it's always available
            top_triggers.insert(0, schedule_trigger)
            logger.info("✅ Added SCHEDULE_BASED trigger to ensure schedule-based workflows are supported")
    
    def _apply_golden_toolkit_boost(self, search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply priority boost to golden toolkit results.
        
        Args:
            search_results: List of semantic search results
            
        Returns:
            List of search results with boosted scores for golden toolkits
        """
        boosted_results = []
        boosted_count = 0
        
        for result in search_results:
            # Create a copy to avoid modifying the original
            boosted_result = result.copy()
            
            # Check if this result is from a golden toolkit
            provider_id = result['item'].get('provider_id', '').lower()
            if provider_id in self.GOLDEN_TOOLKITS:
                # Boost the similarity score by 1.5x
                original_score = result.get('similarity_score', 0.0)
                boosted_result['similarity_score'] = original_score * 1.5
                boosted_count += 1
                logger.debug(f"⭐ Boosted {provider_id} score from {original_score:.3f} to {boosted_result['similarity_score']:.3f}")
            
            boosted_results.append(boosted_result)
        
        # Sort results by boosted similarity score (highest first)
        boosted_results.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
        
        logger.info(f"⭐ Applied priority boost to {boosted_count} golden toolkit results")
        
        return boosted_results
    
    async def _groq_analyze_semantic_results(self, user_prompt: str, semantic_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use Groq LLM to analyze semantic search results and select the best tools for the specific task.
        
        Args:
            user_prompt: The user's natural language prompt
            semantic_context: Context from semantic search results
            
        Returns:
            Refined catalog context with the best tools selected by Groq
        """
        try:
            # Prepare the tools for Groq analysis
            all_tools = []
            
            # Add triggers
            for trigger in semantic_context.get('triggers', []):
                all_tools.append({
                    'type': 'trigger',
                    'name': trigger.get('name', ''),
                    'description': trigger.get('description', ''),
                    'toolkit': trigger.get('toolkit_name', ''),
                    'slug': trigger.get('slug', ''),
                    'similarity_score': trigger.get('similarity_score', 0.0)
                })
            
            # Add actions
            for action in semantic_context.get('actions', []):
                all_tools.append({
                    'type': 'action',
                    'name': action.get('name', ''),
                    'description': action.get('description', ''),
                    'toolkit': action.get('toolkit_name', ''),
                    'slug': action.get('slug', ''),
                    'similarity_score': action.get('similarity_score', 0.0)
                })
            
            if not all_tools:
                logger.warning("No tools to analyze with Groq")
                return semantic_context
            
            # Create Groq prompt for tool analysis
            groq_prompt = self._build_groq_tool_analysis_prompt(user_prompt, all_tools)
            
            # Call Groq API
            logger.info(f"Calling Groq API to analyze {len(all_tools)} tools...")
            response = await self._call_groq_api(groq_prompt)
            
            if not response:
                logger.warning("Groq API call failed, returning semantic results as-is")
                # Inject system-essential triggers into the fallback context
                semantic_context['triggers'].extend(self.SYSTEM_ESSENTIAL_TRIGGERS)
                logger.info("Injecting system-essential triggers into fallback context.")
                return semantic_context
            
            # Parse Groq response to get selected tools
            selected_tools = self._parse_groq_tool_selection(response)
            
            if not selected_tools:
                logger.warning("Failed to parse Groq response, returning semantic results as-is")
                # Inject system-essential triggers into the fallback context
                semantic_context['triggers'].extend(self.SYSTEM_ESSENTIAL_TRIGGERS)
                logger.info("Injecting system-essential triggers into fallback context.")
                return semantic_context
            
            # Filter the semantic context based on Groq selection
            refined_context = self._filter_context_by_groq_selection(semantic_context, selected_tools)
            
            # --- FALLBACK LOGIC: If filtering resulted in zero tools, use a subset of semantic results ---
            total_filtered_tools = len(refined_context.get('triggers', [])) + len(refined_context.get('actions', []))
            if total_filtered_tools == 0:
                logger.warning("⚠️ Tool filtering resulted in zero tools! Using fallback logic...")
                
                # Take the top 5 most relevant tools from semantic search as fallback
                fallback_triggers = semantic_context.get('triggers', [])[:3]  # Top 3 triggers
                fallback_actions = semantic_context.get('actions', [])[:5]    # Top 5 actions
                
                # Inject system-essential triggers into the fallback context
                fallback_triggers.extend(self.SYSTEM_ESSENTIAL_TRIGGERS)
                logger.info("Injecting system-essential triggers into zero-tools fallback context.")
                
                refined_context = {
                    'triggers': fallback_triggers,
                    'actions': fallback_actions,
                    'providers': semantic_context.get('providers', {})
                }
                
                logger.info(f"🔄 Fallback: Using top {len(fallback_triggers)} triggers and {len(fallback_actions)} actions from semantic search")
            
            logger.info(f"Groq analysis selected {len(selected_tools)} tools from {len(all_tools)} semantic results")
            
            return refined_context
            
        except Exception as e:
            logger.error(f"Groq analysis failed: {e}")
            return semantic_context
    
    def _build_groq_tool_analysis_prompt(self, user_prompt: str, tools: List[Dict[str, Any]]) -> str:
        """Build the prompt for Groq to analyze and select the best tools."""
        
        # Group tools by type for better organization
        triggers = [t for t in tools if t['type'] == 'trigger']
        actions = [t for t in tools if t['type'] == 'action']
        
        prompt = f"""You are an expert workflow automation analyst. Your task is to analyze a user's request and select the most relevant tools from a list of semantically similar tools.

USER REQUEST: "{user_prompt}"

AVAILABLE TOOLS:

TRIGGERS ({len(triggers)} available):
"""
        
        for i, trigger in enumerate(triggers, 1):
            prompt += f"{i}. {trigger['name']} ({trigger['toolkit']})\n"
            prompt += f"   Description: {trigger['description'][:200]}...\n"
            prompt += f"   Similarity Score: {trigger['similarity_score']:.3f}\n\n"
        
        prompt += f"\nACTIONS ({len(actions)} available):\n"
        
        for i, action in enumerate(actions, 1):
            prompt += f"{i}. {action['name']} ({action['toolkit']})\n"
            prompt += f"   Description: {action['description'][:200]}...\n"
            prompt += f"   Similarity Score: {action['similarity_score']:.3f}\n\n"
        
        prompt += """
ANALYSIS TASK:
1. Analyze the user's request to understand what they want to accomplish
2. Select the most relevant triggers and actions that would be needed for this workflow
3. Consider both semantic similarity and practical workflow requirements
4. Aim for 3-8 total tools (mix of triggers and actions)
5. Prioritize tools with higher similarity scores but also consider workflow logic

RESPONSE FORMAT:
Return a JSON object with this exact structure:
{
  "selected_triggers": [
    {
      "name": "exact tool name",
      "toolkit": "exact toolkit name",
      "reason": "why this trigger is needed"
    }
  ],
  "selected_actions": [
    {
      "name": "exact tool name", 
      "toolkit": "exact toolkit name",
      "reason": "why this action is needed"
    }
  ],
  "analysis": "Brief explanation of your selection reasoning"
}

IMPORTANT: Use the exact tool names and toolkit names as shown in the list above."""
        
        return prompt
    
    async def _call_groq_api(self, prompt: str) -> Optional[str]:
        """Call the Groq API to analyze tools."""
        try:
            import httpx
            
            # Log the input prompt for debugging
            logger.info(f"Groq API call - Input prompt length: {len(prompt)} characters")
            logger.debug(f"Groq API call - Input prompt:\n{prompt}")
            
            headers = {
                "Authorization": f"Bearer {self.groq_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "openai/gpt-oss-20b",  # DO NOT CHANGE THIS MODEL
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.1,  # Low temperature for consistent analysis
                "max_tokens": 8192,
                "response_format": {"type": "json_object"}
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.groq_base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    response_content = result["choices"][0]["message"]["content"]
                    
                    # Log the output response for debugging
                    logger.info(f"Groq API call - Response length: {len(response_content)} characters")
                    logger.debug(f"Groq API call - Response content:\n{response_content}")
                    
                    return response_content
                else:
                    logger.error(f"Groq API error: {response.status_code} - {response.text}")
                    logger.error(f"Groq API call - Failed request payload: {payload}")
                    return None
                    
        except Exception as e:
            logger.error(f"Groq API call failed: {e}")
            logger.error(f"Groq API call - Input prompt that failed:\n{prompt}")
            return None
    
    def _parse_groq_tool_selection(self, response: str) -> List[Dict[str, Any]]:
        """Parse Groq response to extract selected tools."""
        try:
            import json
            import re
            
            # ALWAYS log the raw Groq response for debugging
            logger.info(f"🔍 Raw Groq Response (length: {len(response)}):\n{response}")
            
            # Use regex to find the JSON block, ignoring other text
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                logger.error("No JSON object found in Groq response.")
                return []
            
            json_str = json_match.group(0)
            logger.info(f"🔍 Extracted JSON string (length: {len(json_str)}):\n{json_str}")
            
            # Wrap JSON parsing in try-except for better error handling
            try:
                data = json.loads(json_str)
                logger.info(f"🔍 Successfully parsed JSON with keys: {list(data.keys())}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode JSON from Groq: {e}")
                return []
            except Exception as e:
                logger.error(f"An unexpected error occurred during Groq parsing: {e}")
                return []
            
            selected_tools = []
            
            # --- NEW LOGIC: Parse selected_triggers and selected_actions arrays ---
            # Parse triggers
            for trigger_obj in data.get('selected_triggers', []):
                if 'name' in trigger_obj:
                    selected_tools.append({
                        'name': trigger_obj['name'],  # Use the name for matching
                        'type': 'trigger',
                        'reason': trigger_obj.get('reason', '')
                    })
            
            # Parse actions
            for action_obj in data.get('selected_actions', []):
                if 'name' in action_obj:
                    selected_tools.append({
                        'name': action_obj['name'],  # Use the name for matching
                        'type': 'action',
                        'reason': action_obj.get('reason', '')
                    })
            # --- END OF NEW LOGIC ---
            
            logger.info(f"Successfully parsed {len(selected_tools)} tools from Groq response.")
            logger.info(f"Selected tool names: {[t['name'] for t in selected_tools]}")
            return selected_tools
            
        except Exception as e:
            logger.error(f"Failed to parse Groq response: {e}")
            logger.error(f"Raw Groq Response that caused exception:\n{response}")
            return []
    
    def _filter_context_by_groq_selection(self, semantic_context: Dict[str, Any], selected_tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Filter the semantic context based on Groq's tool selection."""
        
        # Create sets of selected tool names for efficient lookup
        selected_trigger_names = {t['name'] for t in selected_tools if t['type'] == 'trigger'}
        selected_action_names = {t['name'] for t in selected_tools if t['type'] == 'action'}
        
        logger.info(f"Selected trigger names: {selected_trigger_names}")
        logger.info(f"Selected action names: {selected_action_names}")
        
        # Filter triggers by name
        filtered_triggers = []
        for trigger in semantic_context.get('triggers', []):
            if trigger.get('name') in selected_trigger_names:
                filtered_triggers.append(trigger)
                logger.info(f"✅ Matched trigger: {trigger.get('name')}")
            else:
                logger.debug(f"❌ Trigger not selected: {trigger.get('name')}")
        
        # Filter actions by name
        filtered_actions = []
        for action in semantic_context.get('actions', []):
            if action.get('name') in selected_action_names:
                filtered_actions.append(action)
                logger.info(f"✅ Matched action: {action.get('name')}")
            else:
                logger.debug(f"❌ Action not selected: {action.get('name')}")
        
        # Build refined context
        refined_context = {
            'triggers': filtered_triggers,
            'actions': filtered_actions,
            'providers': semantic_context.get('providers', {})
        }
        
        logger.info(f"Filtered context: {len(filtered_triggers)} triggers, {len(filtered_actions)} actions")
        
        return refined_context
    
    async def _build_groq_tool_selection_prompt(self, user_prompt: str, available_toolkits: list[dict]) -> str:
        """
        Builds a sophisticated prompt for Groq to pre-plan the workflow by selecting
        the exact trigger and action slugs.
        """
        
        # --- IMPROVEMENT: Format the full tool list for the LLM ---
        # This gives the LLM the necessary context to choose specific, valid tools.
        tool_context_str = ""
        
        # Get the full catalog data
        catalog_data = await self.catalog_manager.get_catalog_data()
        
        for toolkit in available_toolkits:
            tool_context_str += f"\n- Toolkit: {toolkit['slug']}\n"
            tool_context_str += f"  Description: {toolkit['description']}\n"
            
            # Get triggers and actions for this toolkit from the catalog data
            toolkit_slug = toolkit['slug']
            toolkit_data = catalog_data.get(toolkit_slug, {})
            
            # Get triggers and actions directly from the toolkit data
            triggers = toolkit_data.get('triggers', [])
            actions = toolkit_data.get('actions', [])
            
            if triggers:
                tool_context_str += "  Triggers:\n"
                for t in triggers:
                    slug = t.get('slug') or t.get('name')
                    desc = t.get('description', 'No description.')
                    tool_context_str += f"    - slug: \"{slug}\", description: \"{desc}\"\n"
            
            if actions:
                tool_context_str += "  Actions:\n"
                for a in actions:
                    slug = a.get('slug') or a.get('name')
                    desc = a.get('description', 'No description.')
                    tool_context_str += f"    - slug: \"{slug}\", description: \"{desc}\"\n"

        prompt = f"""You are an expert workflow architect. 
        Your job is to analyze a user's request and design a logical sequence of operations by selecting ONE trigger and one or more actions from a comprehensive catalog of available tools.

<user_request>
{user_prompt}
</user_request>

<available_tools>
{tool_context_str}
</available_tools>

**IMPORTANT: Understanding Trigger Types**
There are two kinds of trigger available:

1. **event_based**: These are triggers from the <available_tools> list (e.g.; "SALESFORCE_NEW_LEAD_TRIGGER"). Use one of these when the user wants to start a workflow based on an event in a specific application.
2. **schedule_based**" This is a generic trigger for time-based workflows. You MUST use the exact slug "SCHEDULE_BASED" for the `trigger_slug` if the user's request mentions a schedule, like "every morning", "at 8 PM", "on Fridays", "weekly", or any other time-based interval.

**Your Task:**
Your thought process MUST follow these steps in order:

1.  **Trigger Type Analysis:** First, Analyze the <user_request> to determine the trigger type. Is it **event_based** (starts when something happens in an app) or **schedule_based** (starts at a specific time or interval like "every day")

2. **Tool Selection:**
    * If the trigger type is **schedule_based**, your `trigger_slug` MUST be exactly "SCHEDULE_BASED". Then, select the actions needed to fufill the request.
    * If the trigger type is **event_based**, select exactly INE trigger from the <available_tools> list that matches the event. Then select the necessary actions.
    
3. **JSON OUTPUT:** Your response MUST be a JSON object with three keys: "reasoning", "trigger_slug", and "action_slugs". In your reasoning, you must state the trigger type you identified and why.


**Rules for Tool Selection:**
- ⚠️  **GOLDEN RULE:** If the user's request contains ANY time-based words (e.g., "every morning", "at 8 PM", "daily", "weekly", "on Fridays"), you MUST use "SCHEDULE_BASED" as the `trigger_slug`. This rule overrides all other keywords or application names mentioned in the prompt.
- ⚠️ CRITICAL: If your analysis in Step 1 identifies a schedule, you MUST use "SCHEDULE_BASED" as the `trigger_slug`. No exceptions.
- If the request is time-based, you MUST use "SCHEDULE_BASED" as the `trigger_slug`.
- For `event_based` triggers, the slug in your response MUST be an EXACT match to a slug from the **Triggers** section of `<available_tools>`.
- Action slugs in your response MUST be an EXACT match to a slug from the **Actions** section of `<available_tools>`.
- ⚠️  CRITICAL: NEVER use a trigger slug as an action slug or vice versa. Triggers and actions are completely separate.
- ⚠️  CRITICAL: You MUST use the EXACT slug names as they appear in the <available_tools> section. Do not modify, abbreviate, or guess action names.
- If a suitable workflow cannot be built, return `null` for `trigger_slug` and an empty list for `action_slugs`.

**Example 1 (Event-Based):**
<user_request>
When I get a new lead in Salesforce, add them to a Google Sheet and send a celebration message in Slack.
</user_request>

**Expected JSON Response:**
{{
    "reasoning": "The workflow starts with an event, when a new lead is created in Salesforce. Then, it adds a new row to a Google Sheet. Finally, it posts a message to a Slack channel.",
    "trigger_slug": "SALESFORCE_NEW_LEAD_TRIGGER",
    "action_slugs": ["GOOGLESHEETS_CREATE_SPREADSHEET_ROW", "SLACK_SEND_MESSAGE"]
}}

**Example 2 (Schedule-Based):**
<user_request>
Every Friday, get the total number of new customers from Stripe and post it to the #weekly-summary Slack channel.
</user_request>

**Expected JSON Response:**
{{
    "reasoning": "The workflow needs to run on a schedule, specifically every Friday. Therefore, a schedule-based trigger is required. The first action is to list customers from Stripe to get the data. The second action is to post the summarized data to a Slack channel.",
    "trigger_slug": "SCHEDULE_BASED",
    "action_slugs": ["STRIPE_LIST_CUSTOMERS", "SLACK_SEND_MESSAGE"]
}}

Now, analyze the user request provided at the top and generate the JSON response."""
        
        return prompt
    
    async def _groq_analyze_selected_apps(self, user_prompt: str, selected_apps: List[str]) -> Dict[str, Any]:
        """
        Use the original Groq approach for selected apps - builds toolkit context and gets exact tool selection.
        """
        log_function_entry("_groq_analyze_selected_apps", user_prompt=user_prompt, selected_apps=selected_apps)
        
        try:
            # Prepare available toolkits for the selected apps
            logger.info("🔍 Preparing available toolkits for selected apps...")
            available_toolkits = []
            catalog_data = await self.catalog_manager.get_catalog_data()
            log_json_pretty(list(catalog_data.keys())[:10], "📋 Available catalog providers (first 10):")
            
            for app_slug in selected_apps:
                logger.info(f"🔍 Looking for toolkit: {app_slug}")
                if app_slug in catalog_data:
                    toolkit_data = catalog_data[app_slug]
                    available_toolkits.append({
                        'slug': app_slug,
                        'description': toolkit_data.get('description', '')
                    })
                    logger.info(f"✅ Found toolkit: {app_slug}")
                    log_json_pretty(toolkit_data, f"📋 Toolkit data for {app_slug}:")
                else:
                    logger.warning(f"⚠️ Toolkit not found in catalog: {app_slug}")
            
            if not available_toolkits:
                logger.warning("❌ No toolkits found for selected apps")
                result = {'triggers': [], 'actions': [], 'providers': {}}
                log_function_exit("_groq_analyze_selected_apps", result, success=False)
                return result
            
            log_json_pretty(available_toolkits, "📋 Available toolkits for Groq analysis:")
            
            # Build the original Groq prompt
            logger.info("🔧 Building Groq tool selection prompt...")
            groq_prompt = await self._build_groq_tool_selection_prompt(user_prompt, available_toolkits)
            logger.info(f"📝 Groq prompt length: {len(groq_prompt)} characters")
            logger.info(f"📝 Groq prompt preview: {groq_prompt[:500]}...")
            
            # Call Groq API
            logger.info(f"🤖 Calling Groq API to analyze {len(available_toolkits)} selected toolkits...")
            response = await self._call_groq_api(groq_prompt)
            
            if not response:
                logger.warning("❌ Groq API call failed, returning empty context with system essential tools")
                result = {
                    'triggers': self.SYSTEM_ESSENTIAL_TRIGGERS.copy(),
                    'actions': [],
                    'providers': {}
                }
                logger.info("Injecting system-essential triggers into selected apps fallback context.")
                log_function_exit("_groq_analyze_selected_apps", result, success=False)
                return result
            
            logger.info(f"✅ Groq API response received: {len(response)} characters")
            logger.info(f"📝 Groq response: {response}")
            
            # Parse Groq response to get exact tool selection
            logger.info("🔍 Parsing Groq tool selection response...")
            tool_selection = self._parse_groq_tool_selection_response(response)
            
            if not tool_selection:
                logger.warning("❌ Failed to parse Groq tool selection, returning empty context")
                result = {'triggers': [], 'actions': [], 'providers': {}}
                log_function_exit("_groq_analyze_selected_apps", result, success=False)
                return result
            
            log_json_pretty(tool_selection, "📋 Parsed tool selection:")
            
            # Convert tool selection to catalog format
            logger.info("🔄 Converting tool selection to catalog format...")
            catalog_context = self._convert_tool_selection_to_catalog(tool_selection, catalog_data)
            
            logger.info(f"✅ Groq selected: {tool_selection.get('trigger_slug', 'None')} trigger, {len(tool_selection.get('action_slugs', []))} actions")
            log_json_pretty(catalog_context, "📋 Final catalog context:")
            
            log_function_exit("_groq_analyze_selected_apps", catalog_context, success=True)
            return catalog_context
            
        except Exception as e:
            logger.error(f"❌ Groq selected apps analysis failed: {e}")
            result = {'triggers': [], 'actions': [], 'providers': {}}
            log_function_exit("_groq_analyze_selected_apps", result, success=False)
            return result
    
    def _parse_groq_tool_selection_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse the original Groq tool selection response."""
        try:
            import json
            import re
            
            # ALWAYS log the raw Groq response for debugging
            logger.info(f"🔍 Raw Groq Tool Selection Response (length: {len(response)}):\n{response}")
            
            # Use regex to find the JSON block, ignoring other text
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                logger.error("No JSON object found in Groq tool selection response.")
                return None
            
            json_str = json_match.group(0)
            logger.info(f"🔍 Extracted JSON string (length: {len(json_str)}):\n{json_str}")
            
            # Wrap JSON parsing in try-except for better error handling
            try:
                data = json.loads(json_str)
                logger.info(f"🔍 Successfully parsed JSON with keys: {list(data.keys())}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode JSON from Groq tool selection: {e}")
                return None
            except Exception as e:
                logger.error(f"An unexpected error occurred during Groq tool selection parsing: {e}")
                return None
            
            return {
                'reasoning': data.get('reasoning', ''),
                'trigger_slug': data.get('trigger_slug'),
                'action_slugs': data.get('action_slugs', [])
            }
            
        except Exception as e:
            logger.error(f"Failed to parse Groq tool selection response: {e}")
            logger.error(f"Raw Groq Response:\n{response}")
            return None
    
    def _convert_tool_selection_to_catalog(self, tool_selection: Dict[str, Any], catalog_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Groq tool selection to catalog format."""
        log_function_entry("_convert_tool_selection_to_catalog", tool_selection=tool_selection)
        
        catalog_context = {
            'triggers': [],
            'actions': [],
            'providers': {}
        }
        
        # Find and add the selected trigger
        trigger_slug = tool_selection.get('trigger_slug')
        logger.info(f"🔍 Processing trigger: {trigger_slug}")
        
        if trigger_slug:
            if trigger_slug == 'SCHEDULE_BASED':
                # Add a schedule-based trigger
                logger.info("📅 Adding SCHEDULE_BASED trigger")
                catalog_context['triggers'].append({
                    'slug': 'SCHEDULE_BASED',
                    'name': 'Schedule Based Trigger',
                    'description': 'Trigger that runs on a schedule',
                    'toolkit_slug': 'system',
                    'toolkit_name': 'System',
                    'trigger_slug': 'SCHEDULE_BASED',
                    'metadata': {'type': 'schedule_based'}
                })
                
                # Add the system provider to the providers dictionary
                # This ensures the validator recognizes "system" as a valid toolkit_slug
                catalog_context['providers']['system'] = {
                    'name': 'System',
                    'description': 'System-level tools and triggers for workflow automation',
                    'category': 'system',
                    'slug': 'system',
                    'actions': [],  # System provider has no actions
                    'triggers': []  # System provider has no triggers (schedule is handled separately)
                }
                logger.info("🔧 Added system provider to catalog context")
            else:
                # Find the trigger in the catalog
                logger.info(f"🔍 Searching for trigger '{trigger_slug}' in catalog...")
                trigger_found = False
                for provider_slug, provider_data in catalog_data.items():
                    triggers = provider_data.get('triggers', [])
                    for trigger in triggers:
                        if trigger.get('slug') == trigger_slug:
                            logger.info(f"✅ Found trigger '{trigger_slug}' in provider '{provider_slug}'")
                            catalog_context['triggers'].append({
                            'slug': trigger.get('slug', ''),
                            'name': trigger.get('name', ''),
                            'description': trigger.get('description', ''),
                            'toolkit_slug': provider_slug,
                            'toolkit_name': provider_data.get('name', ''),
                            'trigger_slug': trigger.get('slug', ''),
                            'metadata': trigger
                        })
                        
                                                    # Add provider info
                        catalog_context['providers'][provider_slug] = {
                            'name': provider_data.get('name', ''),
                            'description': provider_data.get('description', ''),
                            'category': provider_data.get('category', ''),
                            'slug': provider_slug,
                            'actions': provider_data.get('actions', []),
                            'triggers': provider_data.get('triggers', [])
                        }
                        trigger_found = True
                        break
                    if trigger_found:
                        break
                
                if not trigger_found:
                    logger.warning(f"⚠️ Trigger '{trigger_slug}' not found in catalog")
        
        # Find and add the selected actions
        action_slugs = tool_selection.get('action_slugs', [])
        logger.info(f"🔍 Processing {len(action_slugs)} actions: {action_slugs}")
        
        for action_slug in action_slugs:
            logger.info(f"🔍 Searching for action '{action_slug}' in catalog...")
            action_found = False
            # Find the action in the catalog
            for provider_slug, provider_data in catalog_data.items():
                actions = provider_data.get('actions', [])
                for action in actions:
                    if action.get('slug') == action_slug:
                        logger.info(f"✅ Found action '{action_slug}' in provider '{provider_slug}'")
                        catalog_context['actions'].append({
                            'slug': action.get('slug', ''),
                            'name': action.get('name', ''),
                            'description': action.get('description', ''),
                            'toolkit_slug': provider_slug,
                            'toolkit_name': provider_data.get('name', ''),
                            'action_slug': action.get('slug', ''),
                            'metadata': action
                        })
                        
                        # Add provider info if not already present
                        if provider_slug not in catalog_context['providers']:
                            catalog_context['providers'][provider_slug] = {
                                'name': provider_data.get('name', ''),
                                'description': provider_data.get('description', ''),
                                'category': provider_data.get('category', ''),
                                'slug': provider_slug,
                                'actions': provider_data.get('actions', []),
                                'triggers': provider_data.get('triggers', [])
                            }
                        action_found = True
                        break
                if action_found:
                    break
            
            if not action_found:
                logger.warning(f"⚠️ Action '{action_slug}' not found in catalog")
        
        logger.info(f"✅ Converted tool selection to {len(catalog_context['triggers'])} triggers and {len(catalog_context['actions'])} actions")
        log_json_pretty(catalog_context, "📋 Final converted catalog context:")
        
        log_function_exit("_convert_tool_selection_to_catalog", catalog_context, success=True)
        return catalog_context
    
    async def _fallback_basic_search_from_catalog(self, request: GenerationRequest) -> Optional[Dict[str, Any]]:
        """
        Fallback method that uses the original catalog-based search if semantic search fails.
        """
        try:
            processed_catalog = await self.catalog_manager.get_catalog_data()
            
            if not processed_catalog:
                logger.error("No catalog cache available for fallback search")
                return None
            
            # Get processed triggers and actions from catalog manager
            processed_triggers = self.catalog_manager.extract_triggers(processed_catalog)
            processed_actions = self.catalog_manager.extract_actions(processed_catalog)
            
            # Create a processed catalog structure
            processed_catalog = {
                'providers': processed_catalog,
                'triggers': processed_triggers,
                'actions': processed_actions
            }
            
            # Use the original search methods as fallback
            if request.selected_apps:
                logger.info(f"Fallback: Using strict keyword-based search for selected apps: {request.selected_apps}")
                return self._strict_keyword_search(processed_catalog, request.selected_apps)
            else:
                logger.info("Fallback: Using LLM-based intelligent search for user prompt")
                return await self._llm_based_tool_search(processed_catalog, request.user_prompt)
                
        except Exception as e:
            logger.error(f"Fallback search also failed: {e}")
            return None
    
    def _limit_tools_for_context(self, pruned_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Intelligently limit the number of tools to keep the context concise.
        
        Args:
            pruned_context: Full pruned catalog context
            
        Returns:
            Limited catalog context with reasonable number of tools
        """
        logger.info(f"Limiting tools: {len(pruned_context.get('triggers', []))} triggers, {len(pruned_context.get('actions', []))} actions")
        
        limited_context = {
            'triggers': [],
            'actions': [],
            'providers': {}
        }
        
        # Limit triggers (keep most relevant ones)
        triggers = pruned_context.get('triggers', [])
        if len(triggers) > self.max_triggers:
            # Sort by relevance (prioritize those with meaningful slugs and better descriptions)
            def trigger_relevance_score(trigger):
                score = 0
                # Prioritize meaningful slugs
                if not trigger.get('trigger_slug', '').startswith('unknown'):
                    score += 100
                # Bonus for descriptive names
                if trigger.get('name') and len(trigger.get('name', '')) > 3:
                    score += 50
                # Bonus for descriptions
                if trigger.get('description') and len(trigger.get('description', '')) > 10:
                    score += 25
                # Prefer shorter, cleaner slugs
                slug = trigger.get('trigger_slug', '')
                if slug and '_' in slug:
                    score += 10
                return score
            
            sorted_triggers = sorted(triggers, key=trigger_relevance_score, reverse=True)
            limited_context['triggers'] = sorted_triggers[:self.max_triggers]
            logger.info(f"Limited triggers from {len(triggers)} to {len(limited_context['triggers'])}")
        else:
            limited_context['triggers'] = triggers
        
        # Limit actions (keep most relevant ones)
        actions = pruned_context.get('actions', [])
        if len(actions) > self.max_actions:
            # Sort by relevance (prioritize those with meaningful slugs and better descriptions)
            def action_relevance_score(action):
                score = 0
                # Prioritize meaningful slugs
                if not action.get('action_slug', '').startswith('unknown'):
                    score += 100
                # Bonus for descriptive names
                if action.get('name') and len(action.get('name', '')) > 3:
                    score += 50
                # Bonus for descriptions
                if action.get('description') and len(action.get('description', '')) > 10:
                    score += 25
                # Prefer shorter, cleaner slugs
                slug = action.get('action_slug', '')
                if slug and '_' in slug:
                    score += 10
                return score
            
            sorted_actions = sorted(actions, key=action_relevance_score, reverse=True)
            limited_context['actions'] = sorted_actions[:self.max_actions]
            logger.info(f"Limited actions from {len(actions)} to {len(limited_context['actions'])}")
        else:
            limited_context['actions'] = actions
        
        # Limit providers (keep only those that have tools selected)
        selected_provider_slugs = set()
        for trigger in limited_context['triggers']:
            selected_provider_slugs.add(trigger.get('toolkit_slug', ''))
        for action in limited_context['actions']:
            selected_provider_slugs.add(action.get('toolkit_slug', ''))
        
        providers = pruned_context.get('providers', {})
        limited_providers = {}
        count = 0
        for slug in selected_provider_slugs:
            if slug in providers and count < self.max_providers:
                limited_providers[slug] = providers[slug]
                count += 1
        
        limited_context['providers'] = limited_providers
        logger.info(f"Limited providers to {len(limited_context['providers'])} relevant ones")
        
        # Log final counts and sample tools
        logger.info(f"Final context: {len(limited_context['triggers'])} triggers, {len(limited_context['actions'])} actions, {len(limited_context['providers'])} providers")
        
        # Log sample of selected tools
        if limited_context['triggers']:
            sample_triggers = [t.get('trigger_slug', 'unknown') for t in limited_context['triggers'][:3]]
            logger.info(f"Selected triggers: {sample_triggers}")
        if limited_context['actions']:
            sample_actions = [a.get('action_slug', 'unknown') for a in limited_context['actions'][:3]]
            logger.info(f"Selected actions: {sample_actions}")
        
        return limited_context
    
    def _strict_keyword_search(self, processed_catalog: Dict[str, Any], selected_apps: List[str]) -> Optional[Dict[str, Any]]:
        """
        Perform strict keyword-based search for selected apps.
        
        Args:
            processed_catalog: Processed catalog with triggers, actions, and providers at top level
            selected_apps: List of app/toolkit slugs to search for
            
        Returns:
            Pruned catalog context with only tools from selected apps
        """
        pruned_context = {
            'triggers': [],
            'actions': [],
            'providers': {}
        }
        
        # Get the processed data
        all_triggers = processed_catalog.get('triggers', [])
        all_actions = processed_catalog.get('actions', [])
        all_providers = processed_catalog.get('providers', {})
        
        # Filter triggers by selected apps
        for trigger in all_triggers:
            toolkit_slug = trigger.get('toolkit_slug')
            if toolkit_slug in selected_apps:
                pruned_context['triggers'].append(trigger)
        
        # Filter actions by selected apps
        for action in all_actions:
            toolkit_slug = action.get('toolkit_slug')
            if toolkit_slug in selected_apps:
                pruned_context['actions'].append(action)
        
        # Add provider info for selected apps
        for app_slug in selected_apps:
            if app_slug in all_providers:
                provider_data = all_providers[app_slug]
                pruned_context['providers'][app_slug] = {
                    'name': provider_data.get('name', app_slug),
                    'description': provider_data.get('description', ''),
                    'category': provider_data.get('category', '')
                }
        
        logger.info(f"Strict search found {len(pruned_context['triggers'])} triggers and {len(pruned_context['actions'])} actions")
        
        # Log sample of found tools
        if pruned_context['triggers']:
            sample_triggers = [t.get('slug', 'unknown') for t in pruned_context['triggers'][:3]]
            logger.info(f"Sample triggers found: {sample_triggers}")
        if pruned_context['actions']:
            sample_actions = [a.get('slug', 'unknown') for a in pruned_context['actions'][:3]]
            logger.info(f"Sample actions found: {sample_actions}")
        
        return pruned_context
    
    async def _llm_based_tool_search(self, processed_catalog: Dict[str, Any], user_prompt: str) -> Optional[Dict[str, Any]]:
        """
        Uses Groq LLM to analyze the user prompt and find relevant tools.
        
        Args:
            processed_catalog: Processed catalog with triggers, actions, and providers at top level.
            user_prompt: The user's natural language prompt.
            
        Returns:
            Pruned catalog context with only relevant tools, or None if failed
        """
        if not self.groq_api_key:
            logger.warning("No Groq API key available, falling back to basic search")
            return self._fallback_basic_search(processed_catalog, user_prompt)
        
        logger.info("Groq API key found, performing intelligent tool search...")
        
        # Prepare available toolkits for the prompt (limit to first 50 to avoid payload size issues)
        available_toolkits = []
        if isinstance(processed_catalog, dict):
            # Handle the processed catalog structure with providers, triggers, actions
            if 'providers' in processed_catalog:
                # The providers key contains the raw catalog data
                providers_data = processed_catalog.get('providers', {})
                for slug, data in providers_data.items():
                    if isinstance(data, dict) and 'name' in data:  # Skip non-provider keys
                        available_toolkits.append({
                            'slug': slug,
                            'description': data.get('description', '')
                        })
                        if len(available_toolkits) >= 50:  # Limit to 50 providers
                            break
            else:
                # Handle legacy format where each key is a provider slug
                for slug, data in processed_catalog.items():
                    if isinstance(data, dict) and 'name' in data:  # Skip non-provider keys
                        available_toolkits.append({
                            'slug': slug,
                            'description': data.get('description', '')
                        })
                        if len(available_toolkits) >= 50:  # Limit to 50 providers
                            break
        elif isinstance(processed_catalog, list):
            for item in processed_catalog:
                if isinstance(item, dict):
                    slug = item.get('slug') or item.get('toolkit_slug')
                    if slug:
                        available_toolkits.append({
                            'slug': slug,
                            'description': item.get('description', '')
                        })
        
        if not available_toolkits:
            logger.warning("No toolkits available for Groq analysis")
            return self._fallback_basic_search(processed_catalog, user_prompt)
        
        # Use the original Groq prompt method
        prompt = await self._build_groq_tool_selection_prompt(user_prompt, available_toolkits)
        
        # Prepare Groq API request using proper client
        try:
            from groq import Groq
            client = Groq(api_key=self.groq_api_key)
            
            response = client.chat.completions.create(
                model=self.groq_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=1,
                max_completion_tokens=8192,
                top_p=1,
                reasoning_effort="medium",
                stream=False,
                response_format={"type": "json_object"},
                stop=None
            )
            
            # Extract the response content
            groq_response_text = response.choices[0].message.content
            logger.info(f"Groq API response received: {groq_response_text}")
            
            # Parse the JSON response
            import json
            groq_response = json.loads(groq_response_text)
            
            # Extract the required toolkits from Groq response
            required_toolkits = groq_response.get("required_toolkits", [])
            
            if not required_toolkits:
                logger.warning("Groq returned no required toolkits")
                return self._fallback_basic_search(processed_catalog, user_prompt)
            
            logger.info(f"Groq identified required toolkits: {required_toolkits}")
            
            # Use the strict keyword search with the identified toolkits
            return self._strict_keyword_search(processed_catalog, required_toolkits)
            
        except Exception as e:
            logger.error(f"Groq API call failed: {e}")
            return self._fallback_basic_search(processed_catalog, user_prompt)
    
    def _fallback_basic_search(self, processed_catalog: Dict[str, Any], user_prompt: str) -> Dict[str, Any]:
        """
        Fallback search when Groq analysis fails or returns no results.
        
        Args:
            processed_catalog: Full catalog cache (can be dict or list)
            user_prompt: The user's original prompt
            
        Returns:
            Basic pruned catalog context with a subset of tools
        """
        logger.info("Using fallback basic search")
        
        pruned_context = {
            'triggers': [],
            'actions': [],
            'providers': {}
        }
        
        # Handle both dict and list catalog structures
        if isinstance(processed_catalog, dict):
            # Handle new format with providers, triggers, actions at top level
            if 'providers' in processed_catalog:
                # New format: take first 10 providers
                providers = processed_catalog.get('providers', {})
                provider_count = 0
                for app_slug, app_data in list(providers.items())[:10]:
                    if provider_count >= 10:
                        break
                        
                    # Add provider info
                    pruned_context['providers'][app_slug] = {
                        'name': app_data.get('name', app_slug),
                        'description': app_data.get('description', ''),
                        'category': app_data.get('category', '')
                    }
                    
                    # Add triggers for this provider
                    for trigger in processed_catalog.get('triggers', []):
                        if trigger.get('toolkit_slug') == app_slug:
                            pruned_context['triggers'].append(trigger)
                    
                    # Add actions for this provider
                    for action in processed_catalog.get('actions', []):
                        if action.get('toolkit_slug') == app_slug:
                            pruned_context['actions'].append(action)
                    
                    provider_count += 1
            else:
                # Legacy format: take first 10 providers
                provider_count = 0
                for app_slug, app_data in list(processed_catalog.items())[:10]:
                    if provider_count >= 10:
                        break
                        
                    # Add provider info
                    pruned_context['providers'][app_slug] = {
                        'name': app_data.get('name', app_slug),
                        'description': app_data.get('description', ''),
                        'category': app_data.get('category', '')
                    }
                
                # Add triggers for this provider
                for trigger in processed_catalog.get('triggers', []):
                    if trigger.get('toolkit_slug') == app_slug:
                        pruned_context['triggers'].append(trigger)
                
                # Add actions for this provider  
                for action in processed_catalog.get('actions', []):
                    if action.get('toolkit_slug') == app_slug:
                        pruned_context['actions'].append(action)
                
                provider_count += 1
        
        elif isinstance(processed_catalog, list):
            # Handle list format (legacy)
            for app_data in processed_catalog[:10]:
                if isinstance(app_data, dict):
                    app_slug = app_data.get('slug') or app_data.get('toolkit_slug')
                    
                    # Add provider info
                    pruned_context['providers'][app_slug] = {
                        'name': app_data.get('name', app_slug),
                        'description': app_data.get('description', ''),
                        'category': app_data.get('category', '')
                    }
                    
                    # Add triggers and actions from the app_data
                    for trigger_data in app_data.get('triggers', []):
                        if isinstance(trigger_data, dict):
                            pruned_context['triggers'].append({
                                'toolkit_slug': app_slug,
                                'trigger_slug': trigger_data.get('slug', ''),
                                **trigger_data
                            })
                    
                    for action_data in app_data.get('actions', []):
                        if isinstance(action_data, dict):
                            pruned_context['actions'].append({
                                'toolkit_slug': app_slug,
                                'action_slug': action_data.get('slug', ''),
                                **action_data
                            })
        
        logger.info(f"Fallback search found {len(pruned_context['triggers'])} triggers and {len(pruned_context['actions'])} actions")
        return pruned_context

    async def _build_groq_tool_selection_prompt(self, user_prompt: str, available_toolkits: list[dict]) -> str:
        """
        Builds a sophisticated prompt for Groq to pre-plan the workflow by selecting
        the exact trigger and action slugs.
        """
        
        # --- IMPROVEMENT: Format the full tool list for the LLM ---
        # This gives the LLM the necessary context to choose specific, valid tools.
        tool_context_str = ""
        
        # Get the full catalog data
        catalog_data = await self.catalog_manager.get_catalog_data()
        
        for toolkit in available_toolkits:
            tool_context_str += f"\n- Toolkit: {toolkit['slug']}\n"
            tool_context_str += f"  Description: {toolkit['description']}\n"
            
            # Get triggers and actions for this toolkit from the catalog data
            toolkit_slug = toolkit['slug']
            toolkit_data = catalog_data.get(toolkit_slug, {})
            
            # Get triggers and actions directly from the toolkit data
            triggers = toolkit_data.get('triggers', [])
            actions = toolkit_data.get('actions', [])
            
            if triggers:
                tool_context_str += "  Triggers:\n"
                for t in triggers:
                    slug = t.get('slug') or t.get('name')
                    desc = t.get('description', 'No description.')
                    tool_context_str += f"    - slug: \"{slug}\", description: \"{desc}\"\n"
            
            if actions:
                tool_context_str += "  Actions:\n"
                for a in actions:
                    slug = a.get('slug') or a.get('name')
                    desc = a.get('description', 'No description.')
                    tool_context_str += f"    - slug: \"{slug}\", description: \"{desc}\"\n"

        prompt = f"""You are an expert workflow architect. Your job is to analyze a user's request and design a logical sequence of operations by selecting ONE trigger and one or more actions from a comprehensive catalog of available tools.

<user_request>
{user_prompt}
</user_request>

<available_tools>
{tool_context_str}
</available_tools>

**IMPORTANT: Understanding Trigger Types**
There are two kinds of trigger available:

1. **event_based**: These are triggers from the <available_tools> list (e.g.; "SALESFORCE_NEW_LEAD_TRIGGER"). Use one of these when the user wants to start a workflow based on an event in a specific application.
2. **schedule_based**" This is a generic trigger for time-based workflows. You MUST use the exact slug "SCHEDULE_BASED" for the `trigger_slug` if the user's request mentions a schedule, like "every morning", "at 8 PM", "on Fridays", "weekly", or any other time-based interval.

**Your Task:**
1.  **Reasoning:** First, think step-by-step about how to accomplish the user's goal with the available tools.
2.  **Tool Selection:** Based on your reasoning, select exactly ONE trigger and a sequence of one or more actions.
3.  **JSON Output:** Your response MUST be a JSON object with three keys: "reasoning", "trigger_slug", and "action_slugs".

**Rules for Tool Selection:**
- If the request is time-based, you MUST use "SCHEDULE_BASED" as the `trigger_slug`.
- For `event_based` triggers, the slug in your response MUST be an EXACT match to a slug from the **Triggers** section of `<available_tools>`.
- Action slugs in your response MUST be an EXACT match to a slug from the **Actions** section of `<available_tools>`.
- ⚠️  CRITICAL: NEVER use a trigger slug as an action slug or vice versa. Triggers and actions are completely separate.
- ⚠️  CRITICAL: You MUST use the EXACT slug names as they appear in the <available_tools> section. Do not modify, abbreviate, or guess action names.
- If a suitable workflow cannot be built, return `null` for `trigger_slug` and an empty list for `action_slugs`.

**Example 1 (Event-Based):**
<user_request>
When I get a new lead in Salesforce, add them to a Google Sheet and send a celebration message in Slack.
</user_request>

**Expected JSON Response:**
{{
    "reasoning": "The workflow starts with an event, when a new lead is created in Salesforce. Then, it adds a new row to a Google Sheet. Finally, it posts a message to a Slack channel.",
    "trigger_slug": "SALESFORCE_NEW_LEAD_TRIGGER",
    "action_slugs": ["GOOGLESHEETS_CREATE_SPREADSHEET_ROW", "SLACK_SEND_MESSAGE"]
}}

**Example 2 (Schedule-Based):**
<user_request>
Every Friday, get the total number of new customers from Stripe and post it to the #weekly-summary Slack channel.
</user_request>

**Expected JSON Response:**
{{
    "reasoning": "The workflow needs to run on a schedule, specifically every Friday. Therefore, a schedule-based trigger is required. The first action is to list customers from Stripe to get the data. The second action is to post the summarized data to a Slack channel.",
    "trigger_slug": "SCHEDULE_BASED",
    "action_slugs": ["STRIPE_LIST_CUSTOMERS", "SLACK_SEND_MESSAGE"]
}}

Now, analyze the user request provided at the top and generate the JSON response."""
        
        return prompt

    def _validate_generated_workflow(self, workflow_data: Dict[str, Any], catalog_context: Dict[str, Any]) -> List[str]:
        """Validate the generated workflow against the available tools and schema requirements."""
        errors = []
        
        # Create toolkit mapping for validation
        toolkit_mapping = self._create_toolkit_mapping(catalog_context)
        
        # Validate triggers
        if "triggers" in workflow_data.get("workflow", {}):
            for trigger in workflow_data["workflow"]["triggers"]:
                toolkit_slug = trigger.get("toolkit_slug")
                trigger_slug = trigger.get("composio_trigger_slug")
                
                if not toolkit_slug:
                    errors.append("Missing toolkit_slug in trigger")
                elif toolkit_slug not in toolkit_mapping:
                    errors.append(f"Unknown toolkit: {toolkit_slug}")
                elif trigger_slug:
                    if toolkit_slug in toolkit_mapping and "triggers" in toolkit_mapping[toolkit_slug]:
                        if trigger_slug not in toolkit_mapping[toolkit_slug]["triggers"]:
                            errors.append(f"Unknown trigger '{trigger_slug}' in toolkit '{toolkit_slug}'")
                    else:
                        errors.append(f"Toolkit '{toolkit_slug}' has no triggers")
        
        # Validate actions
        if "actions" in workflow_data.get("workflow", {}):
            for action in workflow_data["workflow"]["actions"]:
                toolkit_slug = action.get("toolkit_slug")
                action_name = action.get("action_name")
                
                if not toolkit_slug:
                    errors.append("Missing toolkit_slug in action")
                elif toolkit_slug not in toolkit_mapping:
                    errors.append(f"Unknown toolkit: {toolkit_slug}")
                elif action_name:
                    if toolkit_slug in toolkit_mapping and "actions" in toolkit_mapping[toolkit_slug]:
                        if action_name not in toolkit_mapping[toolkit_slug]["actions"]:
                            errors.append(f"Unknown action '{action_name}' in toolkit '{toolkit_slug}'")
                    else:
                        errors.append(f"Toolkit '{toolkit_slug}' has no actions")
                
                # Validate required_inputs
                required_inputs = action.get("required_inputs", [])
                if isinstance(required_inputs, list):
                    for input_param in required_inputs:
                        if not isinstance(input_param, dict):
                            errors.append(f"Invalid required_inputs format in action {action.get('id', 'unknown')}")
                            continue
                        
                        if "name" not in input_param:
                            errors.append(f"Missing 'name' in required_inputs for action {action.get('id', 'unknown')}")
                        if "source" not in input_param:
                            errors.append(f"Missing 'source' in required_inputs for action {action.get('id', 'unknown')}")
                        if "type" not in input_param:
                            errors.append(f"Missing 'type' in required_inputs for action {action.get('id', 'unknown')}")
                        else:
                            valid_types = ["string", "number", "boolean", "array"]
                            if input_param["type"] not in valid_types:
                                errors.append(f"Invalid type '{input_param['type']}' in required_inputs. Must be one of: {valid_types}")
        
        return errors

    def _create_toolkit_mapping(self, catalog_context: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Create a comprehensive mapping of available toolkits, triggers, and actions."""
        toolkit_mapping = {}
        
        # Handle the new structure with triggers, actions, and providers at top level
        if "triggers" in catalog_context or "actions" in catalog_context:
            # New structure: triggers, actions, providers at top level
            providers = catalog_context.get("providers", {})
            triggers = catalog_context.get("triggers", [])
            actions = catalog_context.get("actions", [])
            
            # Group triggers by toolkit
            for trigger in triggers:
                toolkit_slug = trigger.get('toolkit_slug')
                if toolkit_slug:
                    if toolkit_slug not in toolkit_mapping:
                        provider_data = providers.get(toolkit_slug, {})
                        toolkit_mapping[toolkit_slug] = {
                            "name": provider_data.get("name", toolkit_slug),
                            "description": provider_data.get("description", ""),
                            "triggers": {},
                            "actions": {}
                        }
                    
                    trigger_slug = trigger.get('slug') or trigger.get('name')
                    if trigger_slug:
                        toolkit_mapping[toolkit_slug]["triggers"][trigger_slug] = {
                            "name": trigger.get('name', trigger_slug),
                            "description": trigger.get('description', ''),
                            "parameters": trigger.get('parameters', [])
                        }
            
            # Group actions by toolkit
            for action in actions:
                toolkit_slug = action.get('toolkit_slug')
                if toolkit_slug:
                    if toolkit_slug not in toolkit_mapping:
                        provider_data = providers.get(toolkit_slug, {})
                        toolkit_mapping[toolkit_slug] = {
                            "name": provider_data.get("name", toolkit_slug),
                            "description": provider_data.get("description", ""),
                            "triggers": {},
                            "actions": {}
                        }
                    
                    action_slug = action.get('slug') or action.get('name')
                    if action_slug:
                        toolkit_mapping[toolkit_slug]["actions"][action_slug] = {
                            "name": action.get('name', action_slug),
                            "description": action.get('description', ''),
                            "parameters": action.get('parameters', [])
                        }
        
        else:
            # Legacy structure: toolkits at top level
            for slug, data in catalog_context.get("toolkits", {}).items():
                toolkit_mapping[slug] = {
                    "name": data.get("name", slug),
                    "description": data.get("description", ""),
                    "triggers": {},
                    "actions": {}
                }
                
                # Map triggers
                for trigger in data.get("triggers", []):
                    trigger_slug = trigger.get('slug') or trigger.get('name')
                    if trigger_slug:
                        toolkit_mapping[slug]["triggers"][trigger_slug] = {
                            "name": trigger.get('name', trigger_slug),
                            "description": trigger.get('description', ''),
                            "parameters": trigger.get('parameters', [])
                        }
                
                # Map actions
                for action in data.get("actions", []):
                    action_name = action.get('slug') or action.get('name')
                    if action_name:
                        toolkit_mapping[slug]["actions"][action_name] = {
                            "name": action.get('name', action_name),
                            "description": action.get('description', ''),
                            "parameters": action.get('parameters', [])
                        }
        
        return toolkit_mapping

    def _generate_dynamic_example(self, catalog_context: Dict[str, Any]) -> str:
        """Generate dynamic examples based on the available tools in the catalog context."""
        
        # Find the first available toolkit with both triggers and actions
        example_toolkit = None
        example_trigger = None
        example_action = None
        
        for slug, data in catalog_context.get("toolkits", {}).items():
            if data.get("triggers") and data.get("actions"):
                example_toolkit = slug
                example_trigger = data["triggers"][0] if data["triggers"] else None
                example_action = data["actions"][0] if data["actions"] else None
                break
        
        if not example_toolkit or not example_trigger or not example_action:
            # Fallback to a generic example
            return self._get_fallback_example()
        
        # Extract the actual slugs/names
        trigger_slug = example_trigger.get('slug') or example_trigger.get('name') or "EXAMPLE_TRIGGER"
        action_name = example_action.get('slug') or example_action.get('name') or "EXAMPLE_ACTION"
        
        # Generate both event-based and schedule-based examples
        examples = f"""**Example 1 (Event-Based):**
{{
"schema_type": "template",
"workflow": {{
"name": "Event-Based Workflow using {example_toolkit.title()}",
"description": "Example event-based workflow using {example_toolkit} toolkit",
"triggers": [{{
"id": "example_trigger",
"type": "event_based",
"toolkit_slug": "{example_toolkit}",
"composio_trigger_slug": "{trigger_slug}"
}}],
"actions": [{{
"id": "example_action",
"toolkit_slug": "{example_toolkit}",
"action_name": "{action_name}",
"required_inputs": [
{{ "name": "example_param", "source": "{{{{inputs.example_input}}}}", "type": "string" }}
],
"depends_on": ["example_trigger"]
}}]
}},
"missing_information": [{{
"field": "inputs.example_input",
"prompt": "What value should be used for the example parameter?",
"type": "string",
"required": true
}}]
}}

**Example 2 (Schedule-Based):**
{{
"schema_type": "template",
"workflow": {{
"name": "Schedule-Based Workflow",
"description": "Example schedule-based workflow that runs daily",
"triggers": [{{
"id": "schedule_trigger",
"type": "schedule_based",
"toolkit_slug": "system",
"composio_trigger_slug": "SCHEDULE_BASED"
}}],
"actions": [{{
"id": "example_action",
"toolkit_slug": "{example_toolkit}",
"action_name": "{action_name}",
"required_inputs": [
{{ "name": "example_param", "source": "{{{{inputs.example_input}}}}", "type": "string" }}
],
"depends_on": ["schedule_trigger"]
}}]
}},
"missing_information": [{{
"field": "inputs.example_input",
"prompt": "What value should be used for the example parameter?",
"type": "string",
"required": true
}}]
}}"""
        
        return examples
    
    def _get_fallback_example(self) -> str:
        """Return fallback examples when no suitable tools are available."""
        return """**Example 1 (Event-Based):**
{
"schema_type": "template",
"workflow": {
"name": "Example Event-Based Workflow",
"description": "Example event-based workflow structure",
"triggers": [{
"id": "example_trigger",
"type": "event_based",
"toolkit_slug": "example_toolkit",
"composio_trigger_slug": "EXAMPLE_TRIGGER"
}],
"actions": [{
"id": "example_action",
"toolkit_slug": "example_toolkit",
"action_name": "EXAMPLE_ACTION",
"required_inputs": [
{ "name": "example_param", "source": "{{inputs.example_input}}", "type": "string" }
],
"depends_on": ["example_trigger"]
}]
},
"missing_information": [{
"field": "inputs.example_input",
"prompt": "What value should be used for the example parameter?",
"type": "string",
"required": true
}]
}

**Example 2 (Schedule-Based):**
{
"schema_type": "template",
"workflow": {
"name": "Example Schedule-Based Workflow",
"description": "Example schedule-based workflow structure",
"triggers": [{
"id": "schedule_trigger",
"type": "schedule_based",
"toolkit_slug": "system",
"composio_trigger_slug": "SCHEDULE_BASED"
}],
"actions": [{
"id": "example_action",
"toolkit_slug": "example_toolkit",
"action_name": "EXAMPLE_ACTION",
"required_inputs": [
{ "name": "example_param", "source": "{{inputs.example_input}}", "type": "string" }
],
"depends_on": ["schedule_trigger"]
}]
},
"missing_information": [{
"field": "inputs.example_input",
"prompt": "What value should be used for the example parameter?",
"type": "string",
"required": true
}]
}}"""

    def _check_tool_hallucinations(self, dsl: Dict[str, Any], catalog_context: Dict[str, Any]) -> List[str]:
        """
        A simple, fast check to see if the LLM used tools that weren't in its context.
        Returns a list of error strings for feedback.
        """
        errors = []
        
        # Build sets of available tools from catalog context
        # The catalog context has triggers and actions as separate lists
        available_triggers = set()
        available_actions = set()

        # Check the triggers and actions lists directly (for the new format)
        for trigger in catalog_context.get("triggers", []):
            toolkit_slug = trigger.get("toolkit_slug", "")
            trigger_slug = trigger.get("trigger_slug", "") or trigger.get("slug", "")
            if toolkit_slug and trigger_slug:
                # Store both the individual trigger slug and the toolkit.trigger combination
                available_triggers.add(trigger_slug)
                available_triggers.add(f"{toolkit_slug}.{trigger_slug}")

        for action in catalog_context.get("actions", []):
            toolkit_slug = action.get("toolkit_slug", "")
            action_slug = action.get("action_slug", "") or action.get("slug", "") or action.get("action_name", "")
            if toolkit_slug and action_slug:
                # Store both the individual action slug and the toolkit.action combination
                available_actions.add(action_slug)
                available_actions.add(f"{toolkit_slug}.{action_slug}")

        workflow = dsl.get("workflow", {})
        
        # Check triggers
        for trigger in workflow.get("triggers", []):
            toolkit_slug = trigger.get("toolkit_slug", "")
            trigger_slug = trigger.get("composio_trigger_slug", "")
            if toolkit_slug and trigger_slug:
                # Check if the trigger exists in the available triggers
                # We check both the individual trigger slug and the toolkit.trigger combination
                trigger_exists = (
                    trigger_slug in available_triggers or 
                    f"{toolkit_slug}.{trigger_slug}" in available_triggers or
                    # Also check if the individual components exist in the catalog
                    any(
                        t.get("toolkit_slug") == toolkit_slug and 
                        (t.get("slug") == trigger_slug or t.get("name") == trigger_slug or t.get("trigger_slug") == trigger_slug)
                        for t in catalog_context.get("triggers", [])
                    )
                )
                if not trigger_exists:
                    errors.append(f"Invalid trigger: '{toolkit_slug}.{trigger_slug}'. It is not in the available triggers list.")
            
        # Check actions
        for action in workflow.get("actions", []):
            toolkit_slug = action.get("toolkit_slug", "")
            action_name = action.get("action_name", "")
            if toolkit_slug and action_name:
                # Check if the action exists in the available actions
                # We check both the individual action name and the toolkit.action combination
                action_exists = (
                    action_name in available_actions or 
                    f"{toolkit_slug}.{action_name}" in available_actions or
                    # Also check if the individual components exist in the catalog
                    any(
                        a.get("toolkit_slug") == toolkit_slug and 
                        (a.get("slug") == action_name or a.get("name") == action_name or a.get("action_name") == action_name)
                        for a in catalog_context.get("actions", [])
                    )
                )
                if not action_exists:
                    errors.append(f"Invalid action: '{toolkit_slug}.{action_name}'. It is not in the available actions list.")
            
        return errors

    def _build_robust_claude_prompt(self, request: GenerationRequest, catalog_context: Dict[str, Any], previous_errors: List[str]) -> str:
        """Builds an aggressive, explicit prompt for Claude with clear tool context and strict validation rules."""
        
        # Create comprehensive toolkit mapping
        toolkit_mapping = self._create_toolkit_mapping(catalog_context)
        
        # --- IMPROVEMENT 1: Simplify the tool context ---
        tool_list_str = ""
        has_triggers = False
        for slug, data in toolkit_mapping.items():
            tool_list_str += f"\n--- Toolkit: {slug} ---\n"
            if data.get("triggers"):
                has_triggers = True
                tool_list_str += "Triggers:\n"
                for trigger_slug, trigger_data in data["triggers"].items():
                    tool_list_str += f"  - composio_trigger_slug: {trigger_slug}\n"
                    if trigger_data.get("description"):
                        tool_list_str += f"    Description: {trigger_data['description']}\n"
            if data.get("actions"):
                tool_list_str += "Actions:\n"
                for action_name, action_data in data["actions"].items():
                    tool_list_str += f"  - action_name: {action_name}\n"
                    if action_data.get("description"):
                        tool_list_str += f"    Description: {action_data['description']}\n"
        
        # Add explicit warning if no triggers are available
        if not has_triggers:
            tool_list_str += "\n⚠️  WARNING: NO TRIGGERS AVAILABLE - Use manual trigger format: {\"triggers\": [{{\"id\": \"manual_trigger\", \"type\": \"manual\"}}]}"

        # Generate a dynamic example based on available tools
        dynamic_example = self._generate_dynamic_example(catalog_context)

        prompt = f"""<user_request>
{request.user_prompt}
</user_request>

<available_tools>
{tool_list_str}
</available_tools>

**IMPORTANT: Understanding Trigger Types**
There are two kinds of trigger available:

1. **event_based**: These are triggers from the <available_tools> list (e.g.; "SALESFORCE_NEW_LEAD_TRIGGER"). Use one of these when the user wants to start a workflow based on an event in a specific application.
2. **schedule_based**: This is a generic trigger for time-based workflows. You MUST use the exact slug "SCHEDULE_BASED" for the `composio_trigger_slug` if the user's request mentions a schedule, like "every morning", "at 8 PM", "on Fridays", "weekly", or any other time-based interval.

<instructions>
1. **Analyze the Request:** Read the <user_request> carefully.

2. **Create a Step-by-Step Plan:** Before writing any JSON, think through the sequence of operations needed. For example: "First, the workflow needs to start when a new payment is made in Stripe. Second, I need to add that customer's details to a Google Sheet. Third, I need to send a message to Slack."

3. **Select Tools for Each Step:** Based on your plan, find the best trigger and action from the <available_tools> for each step.

4. **Construct the Final JSON:** Now, build the complete workflow in the specified JSON format, making sure to include an action for every step in your plan.

5. **Trigger Type Analysis:** Analyze the <user_request> to determine the trigger type. Is it **event_based** (starts when something happens in an app) or **schedule_based** (starts at a specific time or interval like "every day")?

6. Design a logical, multi-step workflow.
7. Your output MUST conform to the `template` schema.
8. Every object in `required_inputs` MUST have a "name", "source", and "type" key.
9. Populate the `missing_information` array for any user inputs needed.
10. Your response MUST be a single, valid JSON object and nothing else.
11. NEVER invent or modify toolkit_slug, composio_trigger_slug, or action_name values.
12. ONLY use the exact values from the <available_tools> section above.
13. ⚠️  CRITICAL: Use triggers ONLY in the "triggers" array and actions ONLY in the "actions" array. NEVER use a trigger as an action or vice versa.
14. If you're unsure about a value, use the first available option from the list.
15. Every parameter MUST have a "type" field - this is CRITICAL for validation.
16. Use "string", "number", "boolean", or "array" as type values.
17. COPY AND PASTE the exact slug/name values - do not modify them.
18. Your JSON MUST be parseable by Python's json.loads().
19. ⚠️  CRITICAL: If no triggers are listed in <available_tools>, use this exact format: "triggers": [{{"id": "manual_trigger", "type": "manual"}}]
20. ⚠️  CRITICAL: NEVER use "trigger_type" - always use "triggers" array format as shown above.

**Rules for Trigger Selection:**
- ⚠️  **GOLDEN RULE:** If the user's request contains ANY time-based words (e.g., "every morning", "at 8 PM", "daily", "weekly", "on Fridays", "monthly", "hourly", "at 9 AM", "every day", "every week", "every month"), you MUST use "SCHEDULE_BASED" as the `composio_trigger_slug`. This rule overrides all other keywords or application names mentioned in the prompt.
- ⚠️  **CRITICAL:** If your analysis in Step 1 identifies a schedule, you MUST use "SCHEDULE_BASED" as the `composio_trigger_slug`. No exceptions.
- If the request is time-based, you MUST use "SCHEDULE_BASED" as the `composio_trigger_slug`.
- For `event_based` triggers, the `composio_trigger_slug` in your response MUST be an EXACT match to a slug from the **Triggers** section of `<available_tools>`.
- Action names in your response MUST be an EXACT match to a slug from the **Actions** section of `<available_tools>`.
- ⚠️  CRITICAL: NEVER use a trigger slug as an action name or vice versa. Triggers and actions are completely separate.
- ⚠️  CRITICAL: You MUST use the EXACT slug names as they appear in the <available_tools> section. Do not modify, abbreviate, or guess action names.
</instructions>

<dynamic_example>
{dynamic_example}
</dynamic_example>

<validation_rules>
CRITICAL: Your JSON MUST pass these validation rules:
- All required_inputs objects MUST have: name, source, type
- All toolkit_slug values MUST exist in the available_tools
- All composio_trigger_slug values MUST exist in the available_tools  
- All action_name values MUST exist in the available_tools
- ⚠️  If no triggers are available, use: "triggers": [{{"id": "manual_trigger", "type": "manual"}}]
- ⚠️  NEVER use "trigger_type" - always use "triggers" array format
- ⚠️  **SCHEDULE DETECTION:** If the user request contains time-based words, you MUST use "SCHEDULE_BASED" as composio_trigger_slug
- ⚠️  **SCHEDULE DETECTION:** Time-based words include: "every morning", "at 8 PM", "daily", "weekly", "on Fridays", "monthly", "hourly", "at 9 AM", "every day", "every week", "every month"
- No markdown formatting or code blocks
- Pure JSON only
- Every field must be properly quoted
- No trailing commas
</validation_rules>

<error_prevention>
COMMON MISTAKES TO AVOID:
- Do NOT add markdown formatting like ```json
- Do NOT add explanatory text before or after the JSON
- Do NOT use placeholder values like "UNKNOWN_ACTION_NAME"
- Do NOT invent new toolkit slugs or action names
- Do NOT forget the "type" field in required_inputs
- Do NOT use unquoted strings in JSON
- ⚠️  **CRITICAL:** Do NOT miss time-based words in the user request - if you see "every", "daily", "weekly", "at [time]", "on [day]", you MUST use "SCHEDULE_BASED"
- ⚠️  **CRITICAL:** Do NOT use event-based triggers when the user clearly wants a scheduled workflow
</error_prevention>
"""
        if previous_errors:
            errors_str = "\n".join(f"- {e}" for e in previous_errors)
            prompt += f"""
<feedback>
Your previous attempt failed. You MUST fix these errors:
{errors_str}

IMPORTANT: Read the error messages carefully and fix each one before generating your response.
</feedback>
"""
        # --- IMPROVEMENT 2: The Golden Rule at the end ---
        prompt += """

**CRITICAL FINAL INSTRUCTION:** 
1. You MUST only use the exact `composio_trigger_slug` and `action_name` values from the `<available_tools>` list.
2. Do not invent or modify them.
3. Copy the values exactly as they appear.
4. Generate ONLY the JSON response - no other text.
5. Ensure your JSON is valid and parseable.

Now, generate the complete JSON for the user's request."""
        
        return prompt
    
    async def _generate_with_validation_loop(self, request: GenerationRequest, catalog_context: Dict[str, Any]) -> GenerationResponse:
        """Manages the generation, validation, and retry loop."""
        previous_errors = []
        for attempt in range(self.max_regeneration_attempts):
            logger.info(f"Generation attempt {attempt + 1}/{self.max_regeneration_attempts}...")
            
            prompt = self._build_robust_claude_prompt(request, catalog_context, previous_errors)
            
            try:
                raw_response = await self.ai_client.generate_workflow(prompt)
                
                # Load schema definition for GenerationContext
                schema_definition = self.context_builder._load_schema_definition()
                
                # Convert dictionary catalog_context to CatalogContext object
                # Add system toolkit to the context for response parsing as well
                providers_list_for_parsing = list(catalog_context.get('providers', {}).values())
                triggers_list_for_parsing = catalog_context.get('triggers', []).copy()
                
                # Add system provider if not already present
                system_provider_for_parsing = {
                    'slug': 'system',
                    'name': 'System',
                    'description': 'System-level tools for scheduling and core logic.',
                    'triggers': [{
                        'slug': 'SCHEDULE_BASED',
                        'name': 'Schedule Based Trigger',
                        'description': 'A trigger that runs on a schedule.'
                    }],
                    'actions': []
                }
                if not any(p.get('slug') == 'system' for p in providers_list_for_parsing):
                    providers_list_for_parsing.append(system_provider_for_parsing)
                
                # Add system trigger if not already present
                system_trigger_for_parsing = {
                    'slug': 'SCHEDULE_BASED',
                    'name': 'Schedule Based Trigger',
                    'description': 'A trigger that runs on a schedule.',
                    'toolkit_slug': 'system'
                }
                if not any(t.get('slug') == 'SCHEDULE_BASED' for t in triggers_list_for_parsing):
                    triggers_list_for_parsing.append(system_trigger_for_parsing)
                
                catalog_context_obj = CatalogContext(
                    available_providers=providers_list_for_parsing,
                    available_triggers=triggers_list_for_parsing,
                    available_actions=catalog_context.get('actions', []),
                    provider_categories=[]  # Not used in this context
                )
                
                parsed_response = await self.response_parser.parse_response(
                    raw_response, 
                    GenerationContext(
                        request=request,
                        catalog=catalog_context_obj, 
                        schema_definition=schema_definition
                    )
                )

                if not parsed_response.success or not parsed_response.dsl_template:
                    error_msg = parsed_response.error_message or "Failed to parse valid JSON from LLM response."
                    previous_errors.append(error_msg)
                    logger.warning(f"Attempt {attempt + 1} failed during parsing: {error_msg}")
                    continue

                # --- NEW: AGGRESSIVE PRE-VALIDATION CHECK ---
                if parsed_response.dsl_template:
                    # Convert DSL template to dict for checking
                    dsl_dict = parsed_response.dsl_template
                    if hasattr(dsl_dict, 'dict'):
                        dsl_dict = dsl_dict.dict()
                    elif hasattr(dsl_dict, 'workflow'):
                        dsl_dict = {'workflow': dsl_dict.workflow}
                        if hasattr(dsl_dict['workflow'], 'dict'):
                            dsl_dict['workflow'] = dsl_dict['workflow'].dict()
                    
                    tool_errors = self._check_tool_hallucinations(dsl_dict, catalog_context)
                    if tool_errors:
                        logger.warning(f"Tool Hallucination Detected: {tool_errors}")
                        previous_errors.extend(tool_errors)
                        continue  # Force a retry with this specific feedback
                # ---------------------------------------------

                # Perform custom validation against available tools
                if parsed_response.dsl_template and hasattr(parsed_response.dsl_template, 'workflow'):
                    workflow_data = parsed_response.dsl_template.workflow
                    if isinstance(workflow_data, dict):
                        # Convert to dict if it's a Pydantic model
                        if hasattr(workflow_data, 'dict'):
                            workflow_dict = workflow_data.dict()
                        else:
                            workflow_dict = workflow_data
                        
                        # Validate against available tools
                        validation_errors = self._validate_generated_workflow(workflow_dict, catalog_context)
                        
                        if validation_errors:
                            logger.warning(f"Custom validation failed with {len(validation_errors)} errors: {validation_errors}")
                            previous_errors.extend(validation_errors)
                            continue
                        else:
                            logger.info("Custom validation passed - workflow uses valid tools")
                    else:
                        logger.warning("Generated workflow is not in expected format")
                        previous_errors.append("Generated workflow format is invalid")
                        continue

                # --- THIS IS THE FIX ---
                # ALWAYS validate the generated DSL against the catalog context
                logger.info("Validating generated workflow against catalog context...")
                
                # Convert DSL template to dict for validation
                dsl_dict = parsed_response.dsl_template
                if hasattr(dsl_dict, 'dict'):
                    dsl_dict = dsl_dict.dict()
                elif hasattr(dsl_dict, 'workflow'):
                    dsl_dict = {'workflow': dsl_dict.workflow}
                    if hasattr(dsl_dict['workflow'], 'dict'):
                        dsl_dict['workflow'] = dsl_dict['workflow'].dict()
                
                # Check for tool hallucinations first (fast check)
                tool_errors = self._check_tool_hallucinations(dsl_dict, catalog_context)
                
                # Perform comprehensive validation using WorkflowValidator
                try:
                    # --- THIS IS THE FIX ---
                    # Create the validation context from the LOCAL catalog_context
                    # that was passed into this function, NOT the global catalog.
                    # This ensures both Claude and the validator use the same pruned context.
                    
                    schema_definition = self.context_builder._load_schema_definition()
                    
                    # --- THIS IS THE FIX ---
                    # The Pydantic model expects a LIST of provider objects, not a dictionary.
                    # We must convert the dictionary's values into a list, but we need to preserve the slug.
                    # The validator also expects actions and triggers to be embedded within each provider.
                    
                    providers_dict_for_validation = catalog_context.get('providers', {})
                    triggers_list = catalog_context.get('triggers', [])
                    actions_list = catalog_context.get('actions', [])
                    
                    # --- ADD THIS BLOCK ---
                    # Create a definition for the virtual "system" toolkit
                    system_provider = {
                        'slug': 'system',
                        'name': 'System',
                        'description': 'System-level tools for scheduling and core logic.',
                        'triggers': [{
                            'slug': 'SCHEDULE_BASED',
                            'name': 'Schedule Based Trigger',
                            'description': 'A trigger that runs on a schedule.'
                        }],
                        'actions': []  # System provider has no actions
                    }
                    # --- END OF BLOCK ---
                    
                    providers_list_for_validation = []
                    for slug, provider_data in providers_dict_for_validation.items():
                        # Ensure each provider object has a 'slug' field for the validator
                        provider_with_slug = provider_data.copy()
                        provider_with_slug['slug'] = slug
                        
                        # Embed the triggers and actions for this provider
                        provider_triggers = [t for t in triggers_list if t.get('toolkit_slug') == slug]
                        provider_actions = [a for a in actions_list if a.get('toolkit_slug') == slug]
                        
                        provider_with_slug['triggers'] = provider_triggers
                        provider_with_slug['actions'] = provider_actions
                        
                        providers_list_for_validation.append(provider_with_slug)
                    
                    # Add the system provider to the list of providers for the validator
                    if not any(p['slug'] == 'system' for p in providers_list_for_validation):
                        providers_list_for_validation.append(system_provider)

                    # Add system trigger to the triggers list for validation
                    triggers_list_for_validation = catalog_context.get('triggers', []).copy()
                    system_trigger = {
                        'slug': 'SCHEDULE_BASED',
                        'name': 'Schedule Based Trigger',
                        'description': 'A trigger that runs on a schedule.',
                        'toolkit_slug': 'system'
                    }
                    if not any(t.get('slug') == 'SCHEDULE_BASED' for t in triggers_list_for_validation):
                        triggers_list_for_validation.append(system_trigger)

                    catalog_context_for_validation = CatalogContext(
                        available_providers=providers_list_for_validation,  # Pass the list here
                        available_triggers=triggers_list_for_validation,
                        available_actions=catalog_context.get('actions', []),
                        provider_categories=[]
                    )
                    
                    generation_context_for_validation = GenerationContext(
                        request=request,
                        catalog=catalog_context_for_validation,
                        schema_definition=schema_definition
                    )
                    
                    # Use this new, correct context for validation.
                    validation_result = await self.workflow_validator.validate_generated_workflow(
                        dsl_dict, 
                        generation_context_for_validation, 
                        "template"  # Assuming template workflow type
                    )
                    
                    # Extract validation errors from the result
                    validation_errors = validation_result.get('validation_errors', [])
                    lint_errors = validation_result.get('lint_errors', [])
                    
                    # Combine all validation errors
                    all_errors = tool_errors + validation_errors + lint_errors
                    
                    if not all_errors:
                        logger.info("Generated workflow passed comprehensive validation successfully!")
                        return parsed_response
                    else:
                        logger.warning(f"Validation failed with {len(all_errors)} errors: {all_errors}")
                        previous_errors.extend(all_errors)
                        # The loop will continue to the next attempt with specific feedback
                        
                except Exception as validation_exception:
                    logger.error(f"Error during comprehensive validation: {validation_exception}")
                    # Fall back to basic validation if WorkflowValidator fails
                    basic_validation_errors = self._validate_generated_workflow(dsl_dict, catalog_context)
                    all_errors = tool_errors + basic_validation_errors
                    
                    if not all_errors:
                        logger.info("Generated workflow passed basic validation successfully!")
                        return parsed_response
                    else:
                        logger.warning(f"Basic validation failed with {len(all_errors)} errors: {all_errors}")
                        previous_errors.extend(all_errors)
                        # The loop will continue to the next attempt with specific feedback

            except Exception as e:
                logger.exception(f"An unexpected exception occurred on attempt {attempt + 1}.")
                previous_errors.append(f"An unexpected error occurred: {str(e)}")

        logger.error("Failed to generate a valid workflow after all attempts.")
        return GenerationResponse(
            success=False,
            error_message=f"Failed to generate a valid workflow after {self.max_regeneration_attempts} attempts. Last errors: {previous_errors}"
        )
    
    # Configuration and utility methods
    def update_groq_api_key(self, new_api_key: str):
        """Update the Groq API key for tool retrieval"""
        self.groq_api_key = new_api_key
        logger.info("Groq API key updated")
    
    def get_groq_config(self) -> Dict[str, Any]:
        """Get information about the Groq configuration"""
        return {
            "api_key_configured": bool(self.groq_api_key),
            "base_url": self.groq_base_url,
            "model": self.groq_model,
            "status": "configured" if self.groq_api_key else "not_configured"
        }
    
    def update_tool_limits(self, max_triggers: Optional[int] = None, max_actions: Optional[int] = None, max_providers: Optional[int] = None):
        """Update the tool limits for context management"""
        if max_triggers is not None:
            self.max_triggers = max_triggers
        if max_actions is not None:
            self.max_actions = max_actions
        if max_providers is not None:
            self.max_providers = max_providers
        
        logger.info(f"Tool limits updated: triggers={self.max_triggers}, actions={self.max_actions}, providers={self.max_providers}")
    
    def get_tool_limits(self) -> Dict[str, Any]:
        """Get current tool limits configuration"""
        return {
            "max_triggers": self.max_triggers,
            "max_actions": self.max_actions,
            "max_providers": self.max_providers,
            "estimated_context_size": f"~{self.max_triggers * 2 + self.max_actions * 3 + self.max_providers * 2}KB"
        }
    
    def update_rate_limiting(self, base_delay: Optional[float] = None, max_delay: Optional[float] = None):
        """Update Claude API rate limiting configuration"""
        if base_delay is not None:
            self.claude_rate_limit_delay = base_delay
        if max_delay is not None:
            self.max_rate_limit_delay = max_delay
        
        logger.info(f"Rate limiting updated: base_delay={self.claude_rate_limit_delay}s, max_delay={self.max_rate_limit_delay}s")
    
    def get_rate_limiting_config(self) -> Dict[str, Any]:
        """Get current rate limiting configuration"""
        return {
            "base_delay": self.claude_rate_limit_delay,
            "max_delay": self.max_rate_limit_delay,
            "retry_strategy": "exponential_backoff"
        }
    

    
    # Delegate catalog management methods to catalog manager
    def get_cache_status(self) -> Dict[str, Any]:
        """Get the current cache status"""
        return self.catalog_manager.get_cache_status()
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status of the DSL Generator service"""
        return self.catalog_manager.get_health_status()
    
    def get_catalog_summary(self) -> Dict[str, Any]:
        """Get a summary of available catalog data"""
        return self.catalog_manager.get_catalog_summary()
    
    def get_catalog_health(self) -> Dict[str, Any]:
        """Get catalog health status for monitoring"""
        return self.catalog_manager.get_catalog_health()
    
    def get_catalog_stats(self) -> Dict[str, Any]:
        """Get detailed catalog statistics for debugging and monitoring"""
        return self.catalog_manager.get_catalog_stats()
    
    def get_catalog_validation_summary(self) -> Dict[str, Any]:
        """Get a summary of catalog validation for generation context"""
        return self.catalog_manager.get_catalog_validation_summary()
    
    def get_catalog_for_generation(self) -> Dict[str, Any]:
        """Get catalog data specifically formatted for generation prompts"""
        return self.context_builder.get_catalog_for_generation()
    
    def get_catalog_health_check(self) -> Dict[str, Any]:
        """Get a comprehensive catalog health check for monitoring"""
        return self.catalog_manager.get_catalog_health_check()
    
    def get_sample_workflow_data(self) -> Dict[str, Any]:
        """Get sample workflow data for generation prompts"""
        return self.catalog_manager.get_sample_workflow_data()
    
    def get_catalog_overview(self) -> Dict[str, Any]:
        """Get a high-level overview of the catalog for generation context"""
        return self.catalog_manager.get_catalog_overview()
    
    def get_available_providers(self) -> List[str]:
        """Get list of available provider slugs for validation"""
        return self.catalog_manager.get_available_providers()
    
    def get_provider_actions(self, provider_slug: str) -> List[str]:
        """Get list of available actions for a specific provider"""
        return self.catalog_manager.get_provider_actions(provider_slug)
    
    def get_provider_triggers(self, provider_slug: str) -> List[str]:
        """Get list of available triggers for a specific provider"""
        return self.catalog_manager.get_provider_triggers(provider_slug)
    
    def validate_catalog_references(self, providers: List[str], actions: List[str], triggers: List[str]) -> Dict[str, Any]:
        """Validate if the provided references exist in the catalog"""
        return self.catalog_manager.validate_catalog_references(providers, actions, triggers)
    
    def validate_workflow_components(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate specific workflow components against the catalog"""
        return self.response_parser.validate_workflow_components(workflow_data, self.catalog_manager._processed_catalog)
    
    def clear_processed_catalog(self):
        """Clear the in-memory catalog cache"""
        self.catalog_manager.clear_catalog_cache()
    
    async def preload_processed_catalog(self):
        """Preload catalog cache during initialization for immediate use"""
        await self.catalog_manager.preload_catalog_cache()
    
    async def refresh_processed_catalog(self, force: bool = False):
        """Refresh the catalog cache data"""
        await self.catalog_manager.refresh_catalog_cache(force)
    
    def get_ai_client_info(self) -> Dict[str, Any]:
        """Get information about the AI client configuration"""
        return self.ai_client.get_model_info()
    
    def update_ai_api_key(self, new_api_key: str):
        """Update the AI client API key"""
        self.ai_client.update_api_key(new_api_key)
    
    def update_ai_model(self, new_model: str):
        """Update the AI client model"""
        self.ai_client.update_model(new_model)
    
    async def _detect_vagueness(self, user_prompt: str) -> Optional[Dict[str, str]]:
        """
        Detect if a user prompt is too vague and return the reason.
        
        Args:
            user_prompt: The user's natural language prompt
            
        Returns:
            Dict with 'reason' key if vague, None if specific enough
        """
        prompt_lower = user_prompt.lower().strip()
        
        # Check for extremely short prompts
        if len(prompt_lower.split()) < 3:
            return {'reason': 'too_short'}
        
        # Check for generic requests without specific actions
        vague_phrases = [
            'help me', 'what can you do', 'show me', 'give me', 'i need',
            'create something', 'make a workflow', 'build something',
            'automate', 'workflow', 'integration', 'connect'
        ]
        
        # Check if prompt is just generic phrases without specifics
        words = prompt_lower.split()
        if len(words) <= 5 and any(phrase in prompt_lower for phrase in vague_phrases):
            return {'reason': 'too_generic'}
        
        # Check for prompts that don't mention specific apps or actions
        specific_indicators = [
            'gmail', 'slack', 'stripe', 'notion', 'google', 'microsoft',
            'send', 'receive', 'create', 'update', 'delete', 'schedule',
            'email', 'message', 'notification', 'alert', 'report'
        ]
        
        has_specific_indicator = any(indicator in prompt_lower for indicator in specific_indicators)
        if not has_specific_indicator and len(words) < 8:
            return {'reason': 'no_specific_apps_or_actions'}
        
        return None
    
    def _get_exemplar_workflows(self, reason: str) -> GenerationResponse:
        """
        Return pre-defined, high-quality DSL templates for vague prompts.
        
        Args:
            reason: The reason why the prompt was considered vague
            
        Returns:
            GenerationResponse with exemplar workflows
        """
        exemplar_workflows = {
            'too_short': {
                "triggers": [{"id": "manual_trigger", "type": "manual"}],
                "actions": [
                    {
                        "id": "gmail_send_email",
                        "action_name": "gmail_send_email",
                        "toolkit_slug": "gmail",
                        "parameters": {
                            "to": {"type": "string", "source": "user_input"},
                            "subject": {"type": "string", "source": "user_input"},
                            "body": {"type": "string", "source": "user_input"}
                        }
                    }
                ],
                "required_inputs": [
                    {"name": "to", "source": "user_input", "type": "string"},
                    {"name": "subject", "source": "user_input", "type": "string"},
                    {"name": "body", "source": "user_input", "type": "string"}
                ],
                "missing_information": []
            },
            'too_generic': {
                "triggers": [{"id": "schedule_trigger", "type": "schedule_based", "composio_trigger_slug": "SCHEDULE_BASED"}],
                "actions": [
                    {
                        "id": "slack_send_message",
                        "action_name": "slack_send_message",
                        "toolkit_slug": "slack",
                        "parameters": {
                            "channel": {"type": "string", "source": "user_input"},
                            "message": {"type": "string", "source": "user_input"}
                        }
                    }
                ],
                "required_inputs": [
                    {"name": "channel", "source": "user_input", "type": "string"},
                    {"name": "message", "source": "user_input", "type": "string"}
                ],
                "missing_information": []
            },
            'no_specific_apps_or_actions': {
                "triggers": [{"id": "gmail_new_email", "type": "event_based", "composio_trigger_slug": "GMAIL_NEW_EMAIL_TRIGGER"}],
                "actions": [
                    {
                        "id": "slack_send_message",
                        "action_name": "slack_send_message",
                        "toolkit_slug": "slack",
                        "parameters": {
                            "channel": {"type": "string", "source": "user_input"},
                            "message": {"type": "string", "source": "template", "value": "New email received: {{trigger.subject}}"}
                        }
                    }
                ],
                "required_inputs": [
                    {"name": "channel", "source": "user_input", "type": "string"}
                ],
                "missing_information": []
            }
        }
        
        workflow = exemplar_workflows.get(reason, exemplar_workflows['too_short'])
        
        return GenerationResponse(
            success=True,
            dsl_template=workflow,
            missing_fields=workflow.get('missing_information', []),
            confidence=0.8,  # High confidence for exemplar workflows
            is_exemplar=True,
            exemplar_reason=reason
        )