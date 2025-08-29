"""
Frontend suggestions routes.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
import uuid
import logging
import time

from api.models import (
    PlanRequest, MissingField, DSLParametric, 
    Suggestion, PlanResponse
)

# Try to import DSL generator service, but don't fail hard at module import time
try:
    from services.dsl_generator.generator import DSLGeneratorService
    from services.dsl_generator.models import GenerationRequest
    DSL_GENERATOR_AVAILABLE = True
except Exception as e:
    logging.warning(f"DSL Generator service not available at import time: {e}")
    DSL_GENERATOR_AVAILABLE = False
    DSLGeneratorService = None
    GenerationRequest = None

# Import database service for getting integration names
try:
    from core.catalog.database_service import DatabaseCatalogService
    from core.catalog.cache import RedisCacheStore
    from core.catalog.redis_client import RedisClientFactory
    from core.config import settings
    DATABASE_SERVICE_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Database service not available: {e}")
    DATABASE_SERVICE_AVAILABLE = False
    DatabaseCatalogService = None
    RedisCacheStore = None
    RedisClientFactory = None

# Import suggestions service
try:
    from api.user_services.suggestions_service import get_suggestions_service
    SUGGESTIONS_SERVICE_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Suggestions service not available: {e}")
    SUGGESTIONS_SERVICE_AVAILABLE = False

router = APIRouter(prefix="/suggestions", tags=["Suggestions"])


async def get_dsl_generator():
    """Get DSL generator service instance or None if not available"""
    # Lazy import fallback in case initial import failed
    global DSL_GENERATOR_AVAILABLE, DSLGeneratorService, GenerationRequest
    if not DSL_GENERATOR_AVAILABLE or DSLGeneratorService is None or GenerationRequest is None:
        try:
            from services.dsl_generator.generator import DSLGeneratorService as _DSLGenSvc
            from services.dsl_generator.models import GenerationRequest as _GenReq
            DSLGeneratorService = _DSLGenSvc
            GenerationRequest = _GenReq
            DSL_GENERATOR_AVAILABLE = True
            logging.info("DSL Generator service imported lazily at request time")
        except Exception as e:
            logging.warning(f"DSL Generator import failed at request time: {e}")
            return None
    
    try:
        # Get the global cache service
        from api.cache_service import get_global_cache_service
        cache_service = await get_global_cache_service()
        
        if not cache_service.is_initialized():
            logging.warning("Global cache service not initialized; attempting on-demand initialization")
            try:
                await cache_service.initialize()
            except Exception as e:
                logging.warning(f"On-demand cache initialization failed: {e}")
        
        # Create DSL generator and load it with global cache
        generator = DSLGeneratorService()
        await generator.initialize()
        
        # Load the catalog cache from global service
        try:
            catalog_cache = cache_service.get_catalog_cache()
        except Exception as e:
            logging.warning(f"Failed to retrieve catalog cache: {e}")
            catalog_cache = {}
        generator.set_global_cache(catalog_cache)
        
        return generator
    except Exception as e:
        logging.warning(f"Failed to initialize DSL generator: {e}")
        return None


async def get_database_service():
    """Get database service instance or None if not available"""
    if not DATABASE_SERVICE_AVAILABLE:
        return None
    
    try:
        # Get the global cache service
        from api.cache_service import get_global_cache_service
        cache_service = await get_global_cache_service()
        
        if not cache_service.is_initialized():
            logging.warning("Global cache service not initialized")
            return None
        
        # Use the catalog service from the global cache service
        return cache_service.get_catalog_service()
    except Exception as e:
        logging.warning(f"Failed to get database service: {e}")
        return None


async def get_suggestions_db_service():
    """Get suggestions database service instance or None if not available"""
    if not SUGGESTIONS_SERVICE_AVAILABLE:
        return None
    
    try:
        return await get_suggestions_service()
    except Exception as e:
        logging.warning(f"Failed to get suggestions service: {e}")
        return None


async def get_integration_names(integration_ids: List[str], database_service) -> Dict[str, str]:
    """Get human-readable names for integration IDs"""
    if not database_service or not integration_ids:
        return {}
    
    integration_names = {}
    for integration_id in integration_ids:
        try:
            provider = await database_service._get_provider_from_database(integration_id)
            if provider:
                integration_names[integration_id] = provider.get("name", integration_id)
            else:
                integration_names[integration_id] = integration_id
        except Exception as e:
            logging.warning(f"Failed to get integration name for {integration_id}: {e}")
            integration_names[integration_id] = integration_id
    
    return integration_names


@router.post(":generate")
async def generate_suggestions(
    request: PlanRequest,
    generator = Depends(get_dsl_generator),
    database_service = Depends(get_database_service),
    suggestions_service = Depends(get_suggestions_db_service)
):
    """Generate multiple workflow suggestions using DSL generator (validation disabled)"""
    logging.info(f"[LINE 152] generate_suggestions called with request: {request}")
    logging.info(f"[LINE 153] Request user_request: '{request.user_request}'")
    logging.info(f"[LINE 154] Request selected_apps: {request.selected_apps}")
    logging.info(f"[LINE 155] Request user_id: {request.user_id}")
    logging.info(f"[LINE 156] Request num_suggestions: {request.num_suggestions}")
    
    try:
        logging.info(f"[LINE 158] Checking if generator is available...")
        if not generator:
            logging.error(f"[LINE 159] Generator is not available")
            raise HTTPException(
                status_code=503, 
                detail="DSL Generator service is not available. Please ensure the service is properly configured."
            )
        logging.info(f"[LINE 165] Generator is available, proceeding with generation")
        
        # Use real DSL generator service
        try:
            logging.info(f"[LINE 169] Ensuring GenerationRequest is available...")
            # Ensure GenerationRequest is available (lazy import fallback) without rebinding global
            GenReq = GenerationRequest
            if GenReq is None:
                logging.warning(f"[LINE 173] GenerationRequest is None, attempting lazy import...")
                try:
                    from services.dsl_generator.models import GenerationRequest as _GenReq
                    GenReq = _GenReq
                    logging.info(f"[LINE 176] Successfully imported GenerationRequest")
                except Exception as e:
                    logging.error(f"[LINE 178] Failed to import GenerationRequest: {e}")
                    raise Exception(f"Generator models unavailable: {e}")
            else:
                logging.info(f"[LINE 181] GenerationRequest is already available")

            logging.info(f"[LINE 184] Converting PlanRequest to GenerationRequest...")
            # Convert PlanRequest to GenerationRequest
            generation_request = GenReq(
                user_prompt=request.user_request,
                selected_apps=request.selected_apps,
                user_id=request.user_id,
                workflow_type="template",  # Default to template for suggestions
                complexity="medium"        # Default to medium complexity
            )
            logging.info(f"[LINE 192] Created GenerationRequest: {generation_request}")
            logging.info(f"[LINE 193] GenerationRequest.user_prompt: '{generation_request.user_prompt}'")
            logging.info(f"[LINE 194] GenerationRequest.selected_apps: {generation_request.selected_apps}")
            logging.info(f"[LINE 195] GenerationRequest.workflow_type: {generation_request.workflow_type}")
            logging.info(f"[LINE 196] GenerationRequest.complexity: {generation_request.complexity}")
            
            # Generate multiple workflows in parallel
            num_suggestions = request.num_suggestions or 1
            logging.info(f"[LINE 199] Starting parallel workflow generation for {num_suggestions} suggestions...")
            start_time = time.time()
            logging.info(f"[LINE 200] Calling generator.generate_multiple_workflows()...")
            responses = await generator.generate_multiple_workflows(generation_request, num_suggestions)
            generation_time = time.time() - start_time
            logging.info(f"[LINE 203] generator.generate_multiple_workflows() completed in {generation_time:.3f}s")
            logging.info(f"[LINE 204] Generated {len(responses)} responses")
            
            # Process all responses and create suggestions
            suggestions = []
            for i, response in enumerate(responses):
                logging.info(f"[LINE 207] Processing response {i+1}: success={response.success}, error={getattr(response, 'error_message', 'N/A')}")
                
                if not response.success:
                    logging.warning(f"[LINE 209] Response {i+1} failed: {response.error_message}")
                    # Create a fallback suggestion for failed generations
                    fallback_suggestion = Suggestion(
                        suggestion_id=str(uuid.uuid4()),
                        title=f"Failed Generation {i+1}",
                        description=f"Workflow generation failed: {response.error_message}",
                        dsl_parametric=DSLParametric(
                            version=1,
                            name=f"failed_workflow_{i+1}",
                            connections={},
                            trigger={"type": "manual"},
                            actions=[{"type": "notification"}]
                        ),
                        missing_fields=[],
                        confidence=0.0,
                        apps=request.selected_apps or [],
                        source="generator",
                        full_workflow_json={}
                    )
                    suggestions.append(fallback_suggestion)
                    continue
                
                logging.info(f"[LINE 225] Response {i+1} successful, processing dsl_template...")
                
                # Convert GenerationResponse to Suggestion
                if response.dsl_template:
                    logging.info(f"[LINE 228] Processing dsl_template for response {i+1}...")
                    # Extract workflow information from the DSL template
                    workflow = response.dsl_template.get("workflow", {})
                    toolkit = response.dsl_template.get("toolkit", {})
                    logging.info(f"[LINE 231] Extracted workflow: {workflow}")
                    logging.info(f"[LINE 232] Extracted toolkit: {toolkit}")
                    
                    # Get workflow name and description (prefer AI-written description from DSL)
                    workflow_name = workflow.get("name", f"generated_workflow_{i+1}")
                    workflow_description = workflow.get("description") or response.reasoning or f"Automated workflow for: {request.user_request}"
                    logging.info(f"[LINE 236] Workflow name: {workflow_name}")
                    logging.info(f"[LINE 237] Workflow description: {workflow_description}")
                    
                    # Extract triggers and actions
                    triggers = workflow.get("triggers", [])
                    actions = workflow.get("actions", [])
                    logging.info(f"[LINE 240] Extracted triggers: {triggers}")
                    logging.info(f"[LINE 241] Extracted actions: {actions}")
                    
                    # Create DSL parametric structure
                    dsl_parametric = DSLParametric(
                        version=1,
                        name=workflow_name,
                        connections=response.dsl_template.get("connections", {}),
                        trigger=triggers[0] if triggers else {"type": "manual"},
                        actions=actions if actions else [{"type": "notification"}]
                    )
                    logging.info(f"[LINE 248] Created DSLParametric for response {i+1}: {dsl_parametric}")
                else:
                    logging.warning(f"[LINE 250] No dsl_template found for response {i+1}, using fallback...")
                    # Fallback if no DSL template
                    workflow_name = f"generated_workflow_{i+1}"
                    workflow_description = response.reasoning or f"Automated workflow for: {request.user_request}"
                    dsl_parametric = DSLParametric(
                        version=1,
                        name=workflow_name,
                        connections={},
                        trigger={"type": "manual"},
                        actions=[{"type": "notification"}]
                    )
                    logging.info(f"[LINE 259] Created fallback DSLParametric for response {i+1}: {dsl_parametric}")
                
                # Convert DSL generator MissingField objects to API MissingField format
                api_missing_fields = []
                if response.missing_fields:
                    logging.info(f"[LINE 263] Processing missing_fields for response {i+1}: {response.missing_fields}")
                    for missing_field in response.missing_fields:
                        api_missing_field = {
                            "path": missing_field.field,
                            "prompt": missing_field.prompt,
                            "type_hint": missing_field.type
                        }
                        api_missing_fields.append(api_missing_field)
                        logging.info(f"[LINE 269] Converted missing field: {api_missing_field}")
                else:
                    logging.info(f"[LINE 271] No missing fields found for response {i+1}")
                
                logging.info(f"[LINE 273] Getting integration names for response {i+1}...")
                # Get integration names for better display
                integration_names = await get_integration_names(
                    response.suggested_apps or request.selected_apps or [], 
                    database_service
                )
                logging.info(f"[LINE 277] Integration names for response {i+1}: {integration_names}")
                
                # Use integration names instead of IDs for display
                display_apps = [
                    integration_names.get(app_id, app_id) 
                    for app_id in (response.suggested_apps or request.selected_apps or [])
                ]
                logging.info(f"[LINE 282] Display apps for response {i+1}: {display_apps}")
                
                # Generate unique suggestion ID
                suggestion_id = str(uuid.uuid4())
                logging.info(f"[LINE 285] Generated suggestion ID for response {i+1}: {suggestion_id}")
                
                # Create generation metadata for benchmarking
                generation_metadata = {
                    "generation_time_seconds": round(generation_time, 3),
                    "model_version": getattr(response, 'model_version', 'unknown'),
                    "prompt_tokens": getattr(response, 'prompt_tokens', 0),
                    "completion_tokens": getattr(response, 'completion_tokens', 0),
                    "total_tokens": getattr(response, 'total_tokens', 0),
                    "generation_timestamp": time.time(),
                    "dsl_generator_version": "1.0.0",  # You can make this dynamic
                    "suggestion_number": i + 1,
                    "total_suggestions": num_suggestions
                }
                logging.info(f"[LINE 297] Created generation metadata for response {i+1}: {generation_metadata}")
                
                suggestion = Suggestion(
                    suggestion_id=suggestion_id,
                    title=workflow_name,
                    description=workflow_description,
                    dsl_parametric=dsl_parametric,
                    missing_fields=api_missing_fields,
                    confidence=response.confidence,
                    apps=display_apps,
                    source="generator",
                    # Store the full workflow JSON for preview
                    full_workflow_json=response.dsl_template or response.workflow_json or {}
                )
                logging.info(f"[LINE 309] Created Suggestion object for response {i+1}: {suggestion}")
                
                # Save suggestion to database if service is available
                if suggestions_service:
                    logging.info(f"[LINE 312] Suggestions service available, saving response {i+1} to database...")
                    try:
                        save_success = await suggestions_service.save_suggestion(
                            user_id=request.user_id,
                            user_request=request.user_request or "",
                            selected_apps=request.selected_apps or [],
                            suggestion_id=suggestion_id,
                            title=workflow_name,
                            description=workflow_description,
                            dsl_parametric=dsl_parametric.dict(),
                            missing_fields=api_missing_fields,
                            confidence=response.confidence,
                            apps=display_apps,
                            source="generator",
                            full_workflow_json=response.dsl_template or response.workflow_json or {},
                            generation_metadata=generation_metadata
                        )
                        
                        if save_success:
                            logging.info(f"[LINE 329] Successfully saved suggestion {suggestion_id} to database")
                        else:
                            logging.warning(f"[LINE 331] Failed to save suggestion {suggestion_id} to database")
                            
                    except Exception as e:
                        logging.error(f"[LINE 334] Error saving suggestion {i+1} to database: {e}")
                        # Don't fail the request if saving fails
                else:
                    logging.warning(f"[LINE 337] Suggestions service not available - suggestion {i+1} not saved to database")
                
                suggestions.append(suggestion)
            
            logging.info(f"[LINE 340] Returning PlanResponse with {len(suggestions)} suggestions...")
            # Return all generated suggestions
            return PlanResponse(suggestions=suggestions)
            
        except Exception as e:
            logging.error(f"[LINE 343] DSL generator failed: {e}")
            logging.error(f"[LINE 344] Exception type: {type(e).__name__}")
            logging.error(f"[LINE 345] Exception details: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to generate workflow suggestions: {str(e)}"
            )
        
    except HTTPException:
        logging.error(f"[LINE 352] Re-raising HTTPException")
        raise
    except Exception as e:
        logging.error(f"[LINE 354] Unexpected error in suggestions generation: {e}")
        logging.error(f"[LINE 355] Exception type: {type(e).__name__}")
        logging.error(f"[LINE 356] Exception details: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Unexpected error: {str(e)}"
        )


@router.get("/{suggestion_id}/preview")
async def preview_workflow(
    suggestion_id: str,
    suggestions_service = Depends(get_suggestions_db_service)
):
    """Get the full workflow JSON for preview from stored suggestion"""
    try:
        if not suggestions_service:
            raise HTTPException(
                status_code=503,
                detail="Suggestions service not available"
            )
        
        # Try to get the suggestion from the database
        suggestion = await suggestions_service.get_suggestion(suggestion_id)
        
        if not suggestion:
            raise HTTPException(
                status_code=404,
                detail="Suggestion not found"
            )
        
        # Return the full workflow JSON for preview
        return {
            "suggestion_id": suggestion_id,
            "title": suggestion.get("title"),
            "description": suggestion.get("description"),
            "full_workflow_json": suggestion.get("full_workflow_json", {}),
            "dsl_parametric": suggestion.get("dsl_parametric", {}),
            "missing_fields": suggestion.get("missing_fields", []),
            "confidence": suggestion.get("confidence_score"),
            "apps": suggestion.get("apps", []),
            "source": suggestion.get("source"),
            "created_at": suggestion.get("created_at")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error previewing workflow: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error previewing workflow: {str(e)}"
        )


@router.post("/{suggestion_id}/actions")
async def update_suggestion_actions(
    suggestion_id: str,
    actions: Dict[str, Any],
    suggestions_service = Depends(get_suggestions_db_service)
):
    """Update user actions for a suggestion (e.g., accepted, rejected, workflow created)"""
    try:
        if not suggestions_service:
            raise HTTPException(
                status_code=503,
                detail="Suggestions service not available"
            )
        
        # Add timestamp to actions
        actions["timestamp"] = time.time()
        actions["action_type"] = actions.get("action_type", "unknown")
        
        # Update the suggestion with user actions
        success = await suggestions_service.update_user_actions(suggestion_id, actions)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to update suggestion actions"
            )
        
        return {"status": "success", "message": "Actions updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error updating suggestion actions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error updating suggestion actions: {str(e)}"
        )


@router.get("/analytics")
async def get_suggestions_analytics(
    days: int = 30,
    suggestions_service = Depends(get_suggestions_db_service)
):
    """Get analytics on suggestions for the last N days"""
    try:
        if not suggestions_service:
            raise HTTPException(
                status_code=503,
                detail="Suggestions service not available"
            )
        
        analytics = await suggestions_service.get_suggestions_analytics(days)
        return analytics
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error getting suggestions analytics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting suggestions analytics: {str(e)}"
        )
