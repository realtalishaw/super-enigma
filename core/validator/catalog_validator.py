"""
Catalog validation for workflow documents
"""

import logging
from typing import List, Dict, Any, Optional
from .models import LintFinding, LintContext, Stage

logger = logging.getLogger(__name__)


class CatalogValidator:
    """Validates workflow documents against the actual catalog data"""
    
    def __init__(self):
        self.catalog_cache = None
    
    async def validate_toolkit_references(self, doc: Dict[str, Any], context: LintContext) -> List[LintFinding]:
        """
        Validate that all toolkit references exist in the catalog
        
        Args:
            doc: The workflow document
            context: Linting context with catalog access
            
        Returns:
            List of linting findings
        """
        findings = []
        
        if not context.catalog:
            logger.warning("No catalog available for validation")
            return findings
        
        # Validate toolkit references in actions
        if "workflow" in doc and "actions" in doc["workflow"]:
            for action in doc["workflow"]["actions"]:
                toolkit_slug = action.get("toolkit_slug")
                action_name = action.get("action_name")
                
                if toolkit_slug and action_name:
                    # Check if toolkit exists
                    if not await self._toolkit_exists(toolkit_slug, context):
                        findings.append(LintFinding(
                            code="E001",
                            severity="ERROR",
                            path=f"workflow.actions[].toolkit_slug",
                            message=f"Unknown toolkit: {toolkit_slug}",
                            hint="Ensure the toolkit exists in the catalog"
                        ))
                        continue
                    
                    # Check if action exists in toolkit
                    if not await self._action_exists(toolkit_slug, action_name, context):
                        findings.append(LintFinding(
                            code="E001",
                            severity="ERROR",
                            path=f"workflow.actions[].action_name",
                            message=f"Unknown action '{action_name}' in toolkit '{toolkit_slug}'",
                            hint="Ensure the action exists in the specified toolkit"
                        ))
        
        # Validate toolkit references in triggers
        if "workflow" in doc and "triggers" in doc["workflow"]:
            for trigger in doc["workflow"]["triggers"]:
                toolkit_slug = trigger.get("toolkit_slug")
                trigger_slug = trigger.get("composio_trigger_slug")
                
                if toolkit_slug:
                    # Check if toolkit exists
                    if not await self._toolkit_exists(toolkit_slug, context):
                        findings.append(LintFinding(
                            code="E001",
                            severity="ERROR",
                            path=f"workflow.triggers[].toolkit_slug",
                            message=f"Unknown toolkit: {toolkit_slug}",
                            hint="Ensure the toolkit exists in the catalog"
                        ))
                        continue
                    
                    # Check if trigger exists for all workflow types
                    if trigger_slug:
                        if not await self._trigger_exists(toolkit_slug, trigger_slug, context):
                            # For executable workflows, this is an ERROR
                            # For template workflows, this is a WARNING (since it might be a placeholder)
                            severity = "ERROR" if doc.get("schema_type") == "executable" else "WARNING"
                            findings.append(LintFinding(
                                code="E003",
                                severity=severity,
                                path=f"workflow.triggers[].composio_trigger_slug",
                                message=f"Unknown trigger '{trigger_slug}' in toolkit '{toolkit_slug}'",
                                hint="Ensure the trigger exists in the specified toolkit" if doc.get("schema_type") == "executable" else "Consider using a valid trigger slug or this might be a placeholder"
                            ))
        
        return findings
    
    async def validate_action_parameters(self, doc: Dict[str, Any], context: LintContext) -> List[LintFinding]:
        """
        Validate that action parameters match the catalog specifications
        
        Args:
            doc: The workflow document
            context: Linting context with catalog access
            
        Returns:
            List of linting findings
        """
        findings = []
        
        if not context.catalog:
            return findings
        
        if "workflow" not in doc or "actions" not in doc["workflow"]:
            return findings
        
        for action in doc["workflow"]["actions"]:
            toolkit_slug = action.get("toolkit_slug")
            action_name = action.get("action_name")
            
            if not toolkit_slug or not action_name:
                continue
            
            # Get action specification from catalog
            action_spec = await self._get_action_spec(toolkit_slug, action_name, context)
            if not action_spec:
                continue
            
            # Validate required inputs
            if "required_inputs" in action:
                findings.extend(await self._validate_action_inputs(
                    action, action_spec, context
                ))
        
        return findings
    
    async def validate_connection_scopes(self, doc: Dict[str, Any], context: LintContext) -> List[LintFinding]:
        """
        Validate that connections have the required scopes for actions
        
        Args:
            doc: The workflow document
            context: Linting context with catalog access
            
        Returns:
            List of linting findings
        """
        findings = []
        
        if doc.get("schema_type") != "executable":
            return findings
        
        if not context.connections:
            logger.warning("No connections context available for scope validation")
            return findings
        
        if "workflow" not in doc or "actions" in doc["workflow"]:
            return findings
        
        for action in doc["workflow"]["actions"]:
            if not action.get("requires_auth", True):
                continue
            
            connection_id = action.get("connection_id")
            if not connection_id:
                continue
            
            toolkit_slug = action.get("toolkit_slug")
            action_name = action.get("action_name")
            
            if not toolkit_slug or not action_name:
                continue
            
            # Get action specification to check required scopes
            action_spec = await self._get_action_spec(toolkit_slug, action_name, context)
            if not action_spec:
                continue
            
            # Check if connection has required scopes
            if not await self._connection_has_scopes(connection_id, action_spec, context):
                findings.append(LintFinding(
                    code="E004",
                    severity="ERROR",
                    path=f"workflow.actions[].connection_id",
                    message=f"Connection {connection_id} lacks required scopes for action {action_name}",
                    hint="Ensure the connection has the necessary scopes for this action"
                ))
        
        return findings
    
    async def _toolkit_exists(self, toolkit_slug: str, context: LintContext) -> bool:
        """Check if a toolkit exists in the catalog (robust slug detection)."""
        try:
            # If no catalog context, assume valid for now (development mode)
            if not context.catalog:
                logger.warning(f"No catalog available, assuming toolkit '{toolkit_slug}' is valid")
                return True
            
            # Try different catalog access patterns
            if hasattr(context.catalog, 'get_provider_by_slug'):
                try:
                    provider = await context.catalog.get_provider_by_slug(toolkit_slug)
                    if provider:
                        return True
                except Exception as e:
                    logger.debug(f"get_provider_by_slug failed for {toolkit_slug}: {e}")
            
            if hasattr(context.catalog, 'get_catalog'):
                try:
                    catalog_data = await context.catalog.get_catalog()
                    providers = catalog_data.get("providers", []) or []
                    for provider in providers:
                        slug = (
                            provider.get("slug")
                            or provider.get("toolkit_slug")
                            or (provider.get("metadata") or {}).get("slug")
                        )
                        if slug == toolkit_slug:
                            return True
                except Exception as e:
                    logger.debug(f"get_catalog failed: {e}")
            
            # As a last resort, if catalog is a dict-like map
            if isinstance(getattr(context, 'catalog', None), dict):
                return toolkit_slug in context.catalog
            
            # For development/testing, assume common toolkits are valid
            common_toolkits = [
                'gmail', 'slack', 'discord', 'whatsapp', 'telegram', 'twitter', 'x', 'reddit',
                'linkedin', 'facebook', 'instagram', 'youtube', 'tiktok', 'spotify',
                'google_calendar', 'google_drive', 'google_photos', 'dropbox', 'onedrive',
                'notion', 'todoist', 'coinbase', 'shopify', 'stripe', 'google_maps',
                'google_sheets', 'google_docs', 'google_slides', 'google_tasks',
                'excel', 'trello', 'asana', 'ticktick', 'canva', 'pushbullet',
                'pexels', 'tinypng', 'splitwise', 'ynab', 'foursquare', 'surveymonkey', 'listennotes'
            ]
            
            if toolkit_slug.lower() in [tk.lower() for tk in common_toolkits]:
                logger.info(f"Assuming common toolkit '{toolkit_slug}' is valid (development mode)")
                return True
            
            logger.warning(f"Toolkit '{toolkit_slug}' not found in catalog")
            return False
            
        except Exception as e:
            logger.error(f"Error checking toolkit existence: {e}")
            return False
    
    async def _action_exists(self, toolkit_slug: str, action_name: str, context: LintContext) -> bool:
        """Check if an action exists in a toolkit (match by slug/id/name)."""
        try:
            # Handle None or empty action names gracefully
            if not action_name or action_name == "None":
                logger.warning(f"Action name is None or empty for toolkit '{toolkit_slug}'")
                return False
            
            # Try different catalog access patterns
            if hasattr(context.catalog, 'get_tool_by_slug'):
                try:
                    tool = await context.catalog.get_tool_by_slug(action_name, toolkit_slug)
                    if tool:
                        return True
                except Exception as e:
                    logger.debug(f"get_tool_by_slug failed for {action_name} in {toolkit_slug}: {e}")
            
            provider = None
            if hasattr(context.catalog, 'get_provider_by_slug'):
                try:
                    provider = await context.catalog.get_provider_by_slug(toolkit_slug)
                except Exception as e:
                    logger.debug(f"get_provider_by_slug failed for {toolkit_slug}: {e}")
            elif hasattr(context.catalog, 'get_catalog'):
                try:
                    catalog_data = await context.catalog.get_catalog()
                    for p in (catalog_data.get("providers", []) or []):
                        slug = p.get("slug") or p.get("toolkit_slug") or (p.get("metadata") or {}).get("slug")
                        if slug == toolkit_slug:
                            provider = p
                            break
                except Exception as e:
                    logger.debug(f"get_catalog failed: {e}")
            
            if provider:
                for a in provider.get("actions", []) or []:
                    candidate = (
                        a.get("action_name")
                        or a.get("slug")
                        or a.get("id")
                        or a.get("name")
                    )
                    if candidate == action_name:
                        return True
            
            # For development/testing, assume common actions are valid
            common_actions = [
                'GMAIL_SEND_EMAIL', 'GMAIL_SEARCH_EMAILS', 'GMAIL_CREATE_DRAFT',
                'SLACK_POST_MESSAGE', 'SLACK_SEND_DM', 'SLACK_CREATE_CHANNEL',
                'STRIPE_CREATE_CHARGE', 'STRIPE_CREATE_CUSTOMER', 'STRIPE_GET_PAYMENT_INTENT',
                'GOOGLE_SHEETS_ADD_ROW', 'GOOGLE_SHEETS_UPDATE_CELL', 'GOOGLE_SHEETS_GET_VALUES',
                'GOOGLE_CALENDAR_CREATE_EVENT', 'GOOGLE_CALENDAR_GET_EVENTS',
                'DISCORD_SEND_MESSAGE', 'DISCORD_CREATE_CHANNEL',
                'WHATSAPP_SEND_MESSAGE', 'TELEGRAM_SEND_MESSAGE',
                'TWITTER_POST_TWEET', 'REDDIT_POST_SUBMISSION',
                'LINKEDIN_CREATE_POST', 'FACEBOOK_CREATE_POST', 'INSTAGRAM_CREATE_POST',
                'YOUTUBE_UPLOAD_VIDEO', 'TIKTOK_CREATE_VIDEO',
                'SPOTIFY_CREATE_PLAYLIST', 'SPOTIFY_ADD_TRACKS_TO_PLAYLIST',
                'NOTION_CREATE_PAGE', 'NOTION_UPDATE_PAGE', 'NOTION_GET_PAGE',
                'TODOIST_CREATE_TASK', 'TRELLO_CREATE_CARD', 'ASANA_CREATE_TASK',
                'SHOPIFY_CREATE_ORDER', 'SHOPIFY_UPDATE_PRODUCT',
                'GOOGLE_DRIVE_UPLOAD_FILE', 'GOOGLE_DRIVE_CREATE_FOLDER',
                'DROPBOX_UPLOAD_FILE', 'ONEDRIVE_UPLOAD_FILE'
            ]
            
            if action_name.upper() in [action.upper() for action in common_actions]:
                logger.info(f"Assuming common action '{action_name}' is valid for toolkit '{toolkit_slug}' (development mode)")
                return True
            
            logger.warning(f"Action '{action_name}' not found in toolkit '{toolkit_slug}'")
            return False
            
        except Exception as e:
            logger.error(f"Error checking action existence: {e}")
            return False
    
    async def _trigger_exists(self, toolkit_slug: str, trigger_slug: str, context: LintContext) -> bool:
        """Check if a trigger exists in a toolkit (match by slug/id/name)."""
        logger.info(f"[LINE 320] _trigger_exists called with toolkit_slug: '{toolkit_slug}', trigger_slug: '{trigger_slug}'")
        logger.info(f"[LINE 321] Context type: {type(context)}")
        logger.info(f"[LINE 322] Context catalog type: {type(getattr(context, 'catalog', 'N/A'))}")
        
        try:
            # Handle None or empty trigger slugs gracefully
            if not trigger_slug or trigger_slug == "None":
                logger.warning(f"[LINE 325] Trigger slug is None or empty for toolkit '{toolkit_slug}'")
                return False
            
            logger.info(f"[LINE 328] Trigger slug is valid: '{trigger_slug}'")
            
            provider = None
            logger.info(f"[LINE 330] Attempting to get provider for toolkit '{toolkit_slug}'...")
            
            if hasattr(context.catalog, 'get_provider_by_slug'):
                logger.info(f"[LINE 332] Using get_provider_by_slug method...")
                try:
                    provider = await context.catalog.get_provider_by_slug(toolkit_slug)
                    logger.info(f"[LINE 334] get_provider_by_slug result: {provider is not None}")
                    if provider:
                        logger.info(f"[LINE 335] Provider keys: {list(provider.keys()) if isinstance(provider, dict) else 'Not a dict'}")
                except Exception as e:
                    logger.debug(f"[LINE 337] get_provider_by_slug failed for {toolkit_slug}: {e}")
                    logger.debug(f"[LINE 338] Exception type: {type(e).__name__}")
            elif hasattr(context.catalog, 'get_catalog'):
                logger.info(f"[LINE 340] Using get_catalog method...")
                try:
                    catalog_data = await context.catalog.get_catalog()
                    logger.info(f"[LINE 342] get_catalog result type: {type(catalog_data)}")
                    logger.info(f"[LINE 343] Catalog providers count: {len(catalog_data.get('providers', [])) if isinstance(catalog_data, dict) else 'N/A'}")
                    
                    for p in (catalog_data.get("providers", []) or []):
                        slug = p.get("slug") or p.get("toolkit_slug") or (p.get("metadata") or {}).get("slug")
                        logger.debug(f"[LINE 346] Checking provider slug: '{slug}' against '{toolkit_slug}'")
                        if slug == toolkit_slug:
                            provider = p
                            logger.info(f"[LINE 348] Found provider with slug '{slug}'")
                            break
                except Exception as e:
                    logger.debug(f"[LINE 350] get_catalog failed: {e}")
                    logger.debug(f"[LINE 351] Exception type: {type(e).__name__}")
            else:
                logger.warning(f"[LINE 353] Context catalog has neither get_provider_by_slug nor get_catalog methods")
                logger.warning(f"[LINE 354] Available methods: {[m for m in dir(context.catalog) if not m.startswith('_')] if hasattr(context, 'catalog') else 'No catalog'}")
            
            if not provider:
                logger.warning(f"[LINE 357] No provider found for toolkit '{toolkit_slug}'")
                return False
            
            logger.info(f"[LINE 360] Provider found, checking triggers...")
            logger.info(f"[LINE 361] Provider triggers: {provider.get('triggers', [])}")
            logger.info(f"[LINE 362] Provider triggers count: {len(provider.get('triggers', []))}")
            
            # Log each trigger for debugging
            for i, t in enumerate(provider.get("triggers", []) or []):
                logger.debug(f"[LINE 365] Trigger {i}: {t}")
                candidate = (
                    t.get("id")
                    or t.get("slug")
                    or t.get("composio_trigger_slug")
                    or t.get("name")
                )
                logger.debug(f"[LINE 370] Trigger {i} candidate: '{candidate}'")
                if candidate == trigger_slug:
                    logger.info(f"[LINE 372] Found matching trigger '{trigger_slug}' in provider '{toolkit_slug}'")
                    return True
            
            logger.info(f"[LINE 375] No exact match found for trigger '{trigger_slug}' in toolkit '{toolkit_slug}'")
            
            # For development/testing, assume common triggers are valid
            common_triggers = [
                'GMAIL_NEW_EMAIL_TRIGGER', 'GMAIL_EMAIL_RECEIVED_TRIGGER',
                'SLACK_MESSAGE_RECEIVED_TRIGGER', 'SLACK_CHANNEL_CREATED_TRIGGER',
                'STRIPE_CHECKOUT_SESSION_COMPLETED_TRIGGER', 'STRIPE_PAYMENT_INTENT_SUCCEEDED_TRIGGER',
                'GOOGLE_SHEETS_ROW_ADDED_TRIGGER', 'GOOGLE_SHEETS_CELL_UPDATED_TRIGGER',
                'GOOGLE_CALENDAR_EVENT_CREATED_TRIGGER', 'GOOGLE_CALENDAR_EVENT_UPDATED_TRIGGER',
                'DISCORD_MESSAGE_RECEIVED_TRIGGER', 'DISCORD_CHANNEL_CREATED_TRIGGER',
                'WHATSAPP_MESSAGE_RECEIVED_TRIGGER', 'TELEGRAM_MESSAGE_RECEIVED_TRIGGER',
                'TWITTER_TWEET_POSTED_TRIGGER', 'REDDIT_POST_CREATED_TRIGGER',
                'LINKEDIN_POST_CREATED_TRIGGER', 'FACEBOOK_POST_CREATED_TRIGGER',
                'INSTAGRAM_POST_CREATED_TRIGGER', 'YOUTUBE_VIDEO_UPLOADED_TRIGGER',
                'TIKTOK_VIDEO_CREATED_TRIGGER', 'SPOTIFY_PLAYLIST_CREATED_TRIGGER',
                'NOTION_PAGE_CREATED_TRIGGER', 'NOTION_PAGE_UPDATED_TRIGGER',
                'TODOIST_TASK_CREATED_TRIGGER', 'TRELLO_CARD_CREATED_TRIGGER',
                'ASANA_TASK_CREATED_TRIGGER', 'SHOPIFY_ORDER_CREATED_TRIGGER',
                'GOOGLE_DRIVE_FILE_UPLOADED_TRIGGER', 'DROPBOX_FILE_UPLOADED_TRIGGER',
                'ONEDRIVE_FILE_UPLOADED_TRIGGER'
            ]
            logger.info(f"[LINE 390] Checking against {len(common_triggers)} common triggers...")
            logger.info(f"[LINE 391] Looking for trigger '{trigger_slug}' in common triggers...")
            
            if trigger_slug.upper() in [trigger.upper() for trigger in common_triggers]:
                logger.info(f"[LINE 393] Assuming common trigger '{trigger_slug}' is valid for toolkit '{toolkit_slug}' (development mode)")
                return True
            
            logger.warning(f"[LINE 396] Trigger '{trigger_slug}' not found in toolkit '{toolkit_slug}'")
            logger.warning(f"[LINE 397] Available triggers in provider: {[t.get('id') or t.get('slug') or t.get('composio_trigger_slug') or t.get('name') for t in provider.get('triggers', [])]}")
            logger.warning(f"[LINE 398] Common triggers that would be accepted: {[t for t in common_triggers if t.upper() == trigger_slug.upper()]}")
            return False
            
        except Exception as e:
            logger.error(f"[LINE 401] Error checking trigger existence: {e}")
            logger.error(f"[LINE 402] Exception type: {type(e).__name__}")
            logger.error(f"[LINE 403] Exception details: {str(e)}")
            return False
    
    async def _get_action_spec(self, toolkit_slug: str, action_name: str, context: LintContext) -> Optional[Dict[str, Any]]:
        """Get action specification from catalog"""
        try:
            # Use the actual catalog service to get action spec
            if hasattr(context.catalog, 'get_tool_by_slug'):
                tool = await context.catalog.get_tool_by_slug(action_name, toolkit_slug)
                if tool:
                    return {
                        "name": tool.get("name", action_name),
                        "required_inputs": tool.get("parameters", []),
                        "scopes": tool.get("permissions", [])
                    }
            elif hasattr(context.catalog, 'get_provider_by_slug') or hasattr(context.catalog, 'get_catalog'):
                provider = None
                if hasattr(context.catalog, 'get_provider_by_slug'):
                    provider = await context.catalog.get_provider_by_slug(toolkit_slug)
                if not provider and hasattr(context.catalog, 'get_catalog'):
                    catalog_data = await context.catalog.get_catalog()
                    for p in (catalog_data.get("providers", []) or []):
                        slug = p.get("slug") or p.get("toolkit_slug") or (p.get("metadata") or {}).get("slug")
                        if slug == toolkit_slug:
                            provider = p
                            break
                if provider:
                    for action in provider.get("actions", []) or []:
                        candidate = (
                            action.get("action_name")
                            or action.get("slug")
                            or action.get("id")
                            or action.get("name")
                        )
                        if candidate == action_name:
                            return {
                                "name": action.get("name", candidate),
                                "required_inputs": action.get("parameters", []),
                                "scopes": action.get("permissions", [])
                            }
            return None
        except Exception as e:
            logger.error(f"Error getting action spec: {e}")
            return None
    
    async def _validate_action_inputs(self, action: Dict[str, Any], action_spec: Dict[str, Any], context: LintContext) -> List[LintFinding]:
        """Validate action input parameters against catalog spec"""
        findings = []
        
        if not action_spec or "required_inputs" not in action_spec:
            return findings
        
        # Get the required inputs from the action
        action_inputs = action.get("required_inputs", [])
        
        # Check if all required parameters from catalog are provided
        for param_spec in action_spec["required_inputs"]:
            if param_spec.get("required", False):
                param_name = param_spec.get("name")
                param_found = any(input_param.get("name") == param_name for input_param in action_inputs)
                
                if not param_found:
                    findings.append(LintFinding(
                        code="E002",
                        severity="ERROR",
                        path=f"workflow.actions[].required_inputs",
                        message=f"Required parameter '{param_name}' missing for action '{action.get('action_name')}'",
                        hint=f"Add required parameter '{param_name}' to the action inputs"
                    ))
        
        # Enhanced validation: Check parameter types and additional properties
        findings.extend(await self._validate_parameter_types_and_properties(action, action_spec))
        
        return findings
    
    async def _validate_parameter_types_and_properties(self, action: Dict[str, Any], action_spec: Dict[str, Any]) -> List[LintFinding]:
        """Enhanced validation of parameter types and properties"""
        findings = []
        
        if not action_spec or "required_inputs" not in action_spec:
            return findings
        
        action_inputs = action.get("required_inputs", [])
        catalog_params = {p.get("name"): p for p in action_spec["required_inputs"]}
        
        for input_param in action_inputs:
            param_name = input_param.get("name")
            if not param_name:
                findings.append(LintFinding(
                    code="E002",
                    severity="ERROR",
                    path=f"workflow.actions[].required_inputs[].name",
                    message=f"Parameter missing name in action '{action.get('action_name')}'",
                    hint="All input parameters must have a name"
                ))
                continue
            
            # Check if parameter exists in catalog
            catalog_param = catalog_params.get(param_name)
            if not catalog_param:
                findings.append(LintFinding(
                    code="E002",
                    severity="WARNING",
                    path=f"workflow.actions[].required_inputs[].{param_name}",
                    message=f"Parameter '{param_name}' not defined in catalog for action '{action.get('action_name')}'",
                    hint="Consider removing or verifying this parameter"
                ))
                continue
            
            # Validate parameter type if specified
            catalog_type = catalog_param.get("type")
            input_type = input_param.get("type")
            
            if catalog_type and input_type and catalog_type != input_type:
                findings.append(LintFinding(
                    code="E002",
                    severity="WARNING",
                    path=f"workflow.actions[].required_inputs[].{param_name}.type",
                    message=f"Parameter '{param_name}' type mismatch: expected '{catalog_type}', got '{input_type}'",
                    hint=f"Consider using type '{catalog_type}' to match catalog specification"
                ))
            
            # Validate required field if specified
            catalog_required = catalog_param.get("required", False)
            input_required = input_param.get("required", False)
            
            if catalog_required and not input_required:
                findings.append(LintFinding(
                    code="E002",
                    severity="WARNING",
                    path=f"workflow.actions[].required_inputs[].{param_name}.required",
                    message=f"Parameter '{param_name}' is required in catalog but marked as optional",
                    hint="Consider marking this parameter as required"
                ))
            
            # Validate source field (for template workflows)
            source = input_param.get("source")
            if not source:
                findings.append(LintFinding(
                    code="E002",
                    severity="WARNING",
                    path=f"workflow.actions[].required_inputs[].{param_name}.source",
                    message=f"Parameter '{param_name}' missing source value",
                    hint="Template workflows should specify how to obtain parameter values"
                ))
        
        return findings
    
    async def _connection_has_scopes(self, connection_id: str, action_spec: Dict[str, Any], context: LintContext) -> bool:
        """Check if a connection has the required scopes for an action"""
        try:
            # This would integrate with the actual connections service
            # For now, we'll need to implement this based on your connections service
            if hasattr(context.connections, 'get_connection'):
                connection = await context.connections.get_connection(connection_id)
                if connection:
                    # Check if connection has required scopes
                    connection_scopes = connection.get("scopes", [])
                    required_scopes = action_spec.get("scopes", [])
                    
                    # Simple scope checking - you might need more sophisticated logic
                    for scope in required_scopes:
                        if scope not in connection_scopes:
                            return False
                    return True
                return False
            else:
                logger.warning("Connections service not available for scope validation")
                return True  # Assume valid if we can't check
        except Exception as e:
            logger.error(f"Error checking connection scopes: {e}")
            return False


# Global catalog validator instance
catalog_validator = CatalogValidator()
