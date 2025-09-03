"""
Prompt Builder for DSL Generator

Handles construction of Claude prompts for different workflow types,
complexity levels, and includes catalog validation instructions.
"""

import json
import logging
from typing import Dict, Any, List
from .models import GenerationContext
from .templates.base_templates import (
    EXECUTABLE_PROMPT,
    DAG_PROMPT,
    COMPLEXITY_GUIDANCE,
    # XML prompt system and helpers
    render_template_prompt,
    CATALOG_VALIDATION_STRICT_XML,
    render_feedback_retry,
    render_final_attempt,
    COMPLEXITY_GUIDANCE_TEXT,
    render_planning_prompt,
)

logger = logging.getLogger(__name__)


class PromptBuilder:
    """
    Builds Claude prompts for workflow generation.
    
    Responsibilities:
    - Constructing prompts for different workflow types
    - Including catalog validation instructions
    - Formatting catalog data for prompts
    - Adding complexity-specific guidance
    """
    
    def __init__(self):
        """Initialize the prompt builder"""
        # Generation templates for different workflow types
        self.generation_templates = {
            "template": self._build_template_prompt,
            "executable": self._build_executable_prompt,
            "dag": self._build_dag_prompt
        }
    
    def build_prompt(self, context: GenerationContext, attempt: int = 1, previous_errors: List[str] = None, selected_plan: str = "{}") -> str:
        """Build the Claude prompt for workflow generation"""
        logger.info(f"[LINE 45] build_prompt called with attempt: {attempt}, previous_errors count: {len(previous_errors) if previous_errors else 0}")
        logger.info(f"[LINE 46] Context request workflow_type: {context.request.workflow_type}")
        logger.info(f"[LINE 47] Context request complexity: {context.request.complexity}")
        logger.info(f"[LINE 48] Selected plan: {selected_plan}")
        
        if previous_errors is None:
            previous_errors = []
            logger.info(f"[LINE 50] Initialized empty previous_errors list")
            
        workflow_type = context.request.workflow_type
        complexity = context.request.complexity
        
        logger.info(f"[LINE 54] Building prompt for workflow_type: {workflow_type}, complexity: {complexity}")
        
        # Build prompt depending on workflow type; template supports selected_plan injection
        if workflow_type == "template":
            logger.info(f"[LINE 57] Using template prompt builder with selected_plan")
            base_prompt = self._build_template_prompt(context, complexity, selected_plan)
        else:
            logger.info(f"[LINE 59] Using {workflow_type} prompt template")
            prompt_template = self.generation_templates.get(workflow_type, self._build_template_prompt)
            base_prompt = prompt_template(context, complexity)
        
        logger.info(f"[LINE 62] Base prompt length: {len(base_prompt)} chars")
        logger.debug(f"[LINE 63] Base prompt preview: {base_prompt[:500]}...")
        
        # Add additional validation instructions if we have catalog data
        catalog_providers = getattr(context.catalog, 'available_providers', None)
        logger.info(f"[LINE 66] Catalog available_providers type: {type(catalog_providers)}")
        logger.info(f"[LINE 67] Catalog available_providers count: {len(catalog_providers) if isinstance(catalog_providers, (list, dict)) else 'N/A'}")
        
        if catalog_providers:
            logger.info(f"[LINE 69] Adding catalog validation instructions...")
            # Append strict XML guardrails for catalog validation
            base_prompt += f"\n\n{CATALOG_VALIDATION_STRICT_XML}"
            logger.info(f"[LINE 71] Added CATALOG_VALIDATION_STRICT_XML (length: {len(CATALOG_VALIDATION_STRICT_XML)} chars)")
        else:
            logger.warning(f"[LINE 73] No catalog providers available, skipping validation instructions")
        
        # Add feedback from previous failures if this is a retry
        if attempt > 1 and previous_errors:
            logger.info(f"[LINE 76] Adding feedback section for retry attempt {attempt}...")
            feedback_section = self._get_feedback_section(attempt, previous_errors)
            base_prompt += f"\n\n{feedback_section}"
            logger.info(f"[LINE 78] Added feedback section (length: {len(feedback_section)} chars)")
            logger.debug(f"[LINE 79] Feedback section: {feedback_section}")
        else:
            logger.info(f"[LINE 81] No feedback section needed (attempt: {attempt}, previous_errors: {len(previous_errors) if previous_errors else 0})")
        
        final_prompt_length = len(base_prompt)
        logger.info(f"[LINE 83] Final prompt length: {final_prompt_length} chars")
        logger.debug(f"[LINE 84] Final prompt preview: {base_prompt[:1000]}...")
        
        return base_prompt

    def build_planning_prompt(self, context: GenerationContext) -> str:
        """Build the planning prompt to select relevant toolkits/triggers/actions"""
        logger.info(f"[LINE 87] build_planning_prompt called")
        logger.info(f"[LINE 88] Context request user_prompt: '{context.request.user_prompt}'")
        
        # Get catalog data from the correct structure
        available_toolkits = getattr(context.catalog, 'available_providers', [])
        available_triggers = getattr(context.catalog, 'available_triggers', [])
        available_actions = getattr(context.catalog, 'available_actions', [])
        
        logger.info(f"[LINE 93] Available toolkits count: {len(available_toolkits) if isinstance(available_toolkits, list) else 'N/A'}")
        logger.info(f"[LINE 94] Available triggers count: {len(available_triggers) if isinstance(available_triggers, list) else 'N/A'}")
        logger.info(f"[LINE 95] Available actions count: {len(available_actions) if isinstance(available_actions, list) else 'N/A'}")
        
        logger.debug(f"[LINE 97] Available toolkits: {available_toolkits[:5] if isinstance(available_toolkits, list) and len(available_toolkits) > 5 else available_toolkits}")
        logger.debug(f"[LINE 98] Available triggers: {available_triggers[:5] if isinstance(available_triggers, list) and len(available_triggers) > 5 else available_triggers}")
        logger.debug(f"[LINE 99] Available actions: {available_actions[:5] if isinstance(available_actions, list) and len(available_actions) > 5 else available_actions}")
        
        planning_prompt = render_planning_prompt(
            user_prompt=context.request.user_prompt,
            available_toolkits=self._format_toolkits_for_prompt(available_toolkits),
            available_triggers=self._format_triggers_for_prompt(available_triggers),
            available_actions=self._format_actions_for_prompt(available_actions),
        )
        
        logger.info(f"[LINE 107] Planning prompt generated (length: {len(planning_prompt)} chars)")
        logger.debug(f"[LINE 108] Planning prompt preview: {planning_prompt[:500]}...")
        
        return planning_prompt
    
    def _build_template_prompt(self, context: GenerationContext, complexity: str, selected_plan: str = "{}") -> str:
        """Build prompt for template workflow type using XML-styled prompt"""
        logger.info(f"[LINE 111] _build_template_prompt called")
        logger.info(f"[LINE 112] Complexity: '{complexity}'")
        logger.info(f"[LINE 113] Selected plan: '{selected_plan}'")
        
        # Get catalog data from the correct structure
        available_toolkits = getattr(context.catalog, 'available_providers', [])
        available_triggers = getattr(context.catalog, 'available_triggers', [])
        available_actions = getattr(context.catalog, 'available_actions', [])
        
        logger.info(f"[LINE 119] Formatted toolkits count: {len(available_toolkits) if isinstance(available_toolkits, list) else 'N/A'}")
        logger.info(f"[LINE 120] Formatted triggers count: {len(available_triggers) if isinstance(available_triggers, list) else 'N/A'}")
        logger.info(f"[LINE 121] Formatted actions count: {len(available_actions) if isinstance(available_actions, list) else 'N/A'}")
        
        logger.debug(f"[LINE 123] Formatted toolkits preview: {available_toolkits[:3] if isinstance(available_toolkits, list) and len(available_toolkits) > 3 else available_toolkits}")
        logger.debug(f"[LINE 124] Formatted triggers preview: {available_triggers[:3] if isinstance(available_triggers, list) and len(available_triggers) > 3 else available_triggers}")
        logger.debug(f"[LINE 125] Formatted actions preview: {available_actions[:3] if isinstance(available_actions, list) and len(available_actions) > 3 else available_actions}")
        
        template_prompt = render_template_prompt(
            user_prompt=context.request.user_prompt,
            complexity="",  # deprecated; not used by XML template
            available_toolkits=self._format_toolkits_for_prompt(available_toolkits),
            available_triggers=self._format_triggers_for_prompt(available_triggers),
            available_actions=self._format_actions_for_prompt(available_actions),
            # Prefer the embedded DSL v2 schema default; optionally could pass context schema
            # schema_definition=json.dumps(context.schema_definition, indent=2),
            complexity_guidance="",  # deprecated; not used by XML template
            selected_plan=selected_plan,
        )
        
        logger.info(f"[LINE 135] Template prompt generated (length: {len(template_prompt)} chars)")
        logger.debug(f"[LINE 136] Template prompt preview: {template_prompt[:500]}...")
        
        return template_prompt
    
    def _build_executable_prompt(self, context: GenerationContext, complexity: str) -> str:
        """Build prompt for executable workflow type using external template"""
        return EXECUTABLE_PROMPT.format(
            user_prompt=context.request.user_prompt,
            complexity=complexity.title(),
            available_toolkits=self._format_toolkits_for_prompt(context.catalog.available_providers),
            available_triggers=self._format_triggers_for_prompt(context.catalog.available_triggers),
            available_actions=self._format_actions_for_prompt(context.catalog.available_actions),
            schema_definition=json.dumps(context.schema_definition, indent=2),
            complexity_guidance=COMPLEXITY_GUIDANCE.get(complexity, COMPLEXITY_GUIDANCE["medium"])
        )
    
    def _build_dag_prompt(self, context: GenerationContext, complexity: str) -> str:
        """Build prompt for DAG workflow type using external template"""
        return DAG_PROMPT.format(
            user_prompt=context.request.user_prompt,
            complexity=complexity.title(),
            available_toolkits=self._format_toolkits_for_prompt(context.catalog.available_providers),
            available_triggers=self._format_triggers_for_prompt(context.catalog.available_triggers),
            available_actions=self._format_actions_for_prompt(context.catalog.available_actions),
            schema_definition=json.dumps(context.schema_definition, indent=2),
            complexity_guidance=COMPLEXITY_GUIDANCE.get(complexity, COMPLEXITY_GUIDANCE["medium"])
        )
    
    def _format_toolkits_for_prompt(self, toolkits: List[Dict[str, Any]]) -> str:
        """Format toolkits for Claude prompt"""
        if not toolkits:
            return "No toolkits available"
        
        import logging
        logger = logging.getLogger(__name__)
        
        # Debug: log first few toolkits to see structure
        logger.debug(f"Formatting {len(toolkits)} toolkits")
        if toolkits:
            logger.debug(f"First toolkit data: {toolkits[0]}")
            for i, toolkit in enumerate(toolkits[:3]):
                logger.debug(f"Toolkit {i}: keys={list(toolkit.keys())}, name={toolkit.get('name')}, slug={toolkit.get('slug')}")
        
        formatted = []
        meaningful_slugs = 0
        total_toolkits = len(toolkits[:20])  # Limit to first 20
        
        for toolkit in toolkits[:20]:  # Limit to first 20
            name = toolkit.get('name', 'Unknown')
            slug = toolkit.get('slug', 'unknown')
            
            # Only include toolkits that have a valid slug
            if slug and slug != 'unknown':
                meaningful_slugs += 1
                formatted.append(f"- {name} (slug: {slug})")
                if toolkit.get('description'):
                    formatted.append(f"  Description: {toolkit['description']}")
        
        logger.info(f"Toolkits with meaningful slugs: {meaningful_slugs}/{total_toolkits}")
        
        if not formatted:
            # Fallback: show some basic toolkit examples
            fallback_toolkits = [
                "- Gmail (slug: gmail)",
                "- Slack (slug: slack)",
                "- GitHub (slug: github)",
                "- Linear (slug: linear)",
                "- Notion (slug: notion)"
            ]
            logger.warning(f"No valid toolkits found in catalog, using fallback examples")
            return "\n".join(fallback_toolkits)
        
        logger.debug(f"Formatted {len(formatted)} valid toolkits")
        return "\n".join(formatted)
    
    def _format_triggers_for_prompt(self, triggers: List[Dict[str, Any]]) -> str:
        """Format triggers for Claude prompt"""
        if not triggers:
            return "No triggers available"
        
        import logging
        logger = logging.getLogger(__name__)
        
        # Debug: log first few triggers to see structure
        logger.debug(f"Formatting {len(triggers)} triggers")
        if triggers:
            logger.debug(f"First trigger data: {triggers[0]}")
            for i, trigger in enumerate(triggers[:3]):
                logger.debug(f"Trigger {i}: keys={list(trigger.keys())}, id={trigger.get('id')}, name={trigger.get('name')}, slug={trigger.get('slug')}")
        
        formatted = []
        meaningful_slugs = 0
        total_triggers = len(triggers[:15])  # Limit to first 15
        
        for trigger in triggers[:15]:  # Limit to first 15
            # Use slug as the primary identifier (matches database structure)
            trigger_slug = trigger.get('slug', 'unknown_trigger')
            toolkit_slug = trigger.get('toolkit_slug', 'unknown_toolkit')
            name = trigger.get('name', 'Unknown')
            
            # Only include triggers that have a valid slug
            if trigger_slug and trigger_slug != 'unknown_trigger':
                meaningful_slugs += 1
                formatted.append(f"- trigger_slug: {trigger_slug} (toolkit_slug: {toolkit_slug}) — {name}")
                if trigger.get('description'):
                    formatted.append(f"  Description: {trigger['description']}")
        
        logger.info(f"Triggers with meaningful slugs: {meaningful_slugs}/{total_triggers}")
        
        if not formatted:
            # Fallback: show some basic trigger examples from popular toolkits
            fallback_triggers = [
                "- trigger_slug: NEW_EMAIL (toolkit_slug: gmail) — New Email Received",
                "- trigger_slug: NEW_MESSAGE (toolkit_slug: slack) — New Message",
                "- trigger_slug: NEW_ISSUE (toolkit_slug: github) — New Issue Created",
                "- trigger_slug: NEW_TASK (toolkit_slug: linear) — New Task Created",
                "- trigger_slug: NEW_PAGE (toolkit_slug: notion) — New Page Created"
            ]
            logger.warning(f"No valid triggers found in catalog, using fallback examples")
            return "\n".join(fallback_triggers)
        
        logger.debug(f"Formatted {len(formatted)} valid triggers")
        return "\n".join(formatted)
    
    def _format_actions_for_prompt(self, actions: List[Dict[str, Any]]) -> str:
        """Format actions for Claude prompt"""
        if not actions:
            return "No actions available"
        
        import logging
        logger = logging.getLogger(__name__)
        
        # Debug: log first few actions to see structure
        logger.debug(f"Formatting {len(actions)} actions")
        if actions:
            logger.debug(f"First action data: {actions[0]}")
            for i, action in enumerate(actions[:3]):
                logger.debug(f"Action {i}: keys={list(action.keys())}, action_name={action.get('action_name')}, name={action.get('name')}, id={action.get('id')}, slug={action.get('slug')}")
        
        formatted = []
        meaningful_slugs = 0
        total_actions = len(actions[:100])  # Limit to first 100
        
        for action in actions[:100]:  # Limit to first 100
            # Use slug as the primary identifier (matches database structure)
            action_slug = action.get('slug', 'unknown_action')
            toolkit_slug = action.get('toolkit_slug', 'unknown_toolkit')
            name = action.get('name', 'Unknown')
            
            # Only include actions that have a valid slug
            if action_slug and action_slug != 'unknown_action':
                meaningful_slugs += 1
                formatted.append(f"- action_slug: {action_slug} (toolkit_slug: {toolkit_slug}) — {name}")
                if action.get('description'):
                    formatted.append(f"  Description: {action['description']}")
                if action.get('parameters'):
                    # Include a short list of required parameter names to guide correctness
                    required_params = [p.get('name') for p in action['parameters'] if p.get('required')]
                    if required_params:
                        formatted.append(f"  Required inputs: {', '.join(required_params)}")
        
        logger.info(f"Actions with meaningful slugs: {meaningful_slugs}/{total_actions}")
        
        if not formatted:
            # Fallback: show some basic action examples from popular toolkits
            fallback_actions = [
                "- action_slug: GMAIL_SEND_EMAIL (toolkit_slug: gmail) — Send Email",
                "- action_slug: SLACK_SEND_MESSAGE (toolkit_slug: slack) — Send Message",
                "- action_slug: GITHUB_CREATE_ISSUE (toolkit_slug: github) — Create Issue",
                "- action_slug: LINEAR_CREATE_ISSUE (toolkit_slug: linear) — Create Issue",
                "- action_slug: NOTION_CREATE_PAGE (toolkit_slug: notion) — Create Page"
            ]
            logger.warning(f"No valid actions found in catalog, using fallback examples")
            return "\n".join(fallback_actions)
        
        logger.debug(f"Formatted {len(formatted)} valid actions")
        return "\n".join(formatted)
    
    def _get_catalog_validation_instructions(self, context: GenerationContext) -> str:
        """Deprecated: replaced by strict XML guardrails appended in build_prompt"""
        return CATALOG_VALIDATION_STRICT_XML
    
    def _get_catalog_examples(self, context: GenerationContext) -> str:
        """Get specific examples from the available catalog to guide generation"""
        if not context.catalog.available_providers:
            return ""
        
        # Prepare examples for the template
        toolkit_examples = []
        for provider in list(context.catalog.available_providers)[:5]:  # Limit to 5
            if 'slug' in provider and 'name' in provider:
                toolkit_examples.append(f"- {provider['name']} (slug: {provider['slug']})")
        
        trigger_examples = []
        for trigger in list(context.catalog.available_triggers)[:5]:  # Limit to 5
            if 'name' in trigger and 'toolkit_name' in trigger:
                trigger_examples.append(f"- {trigger['name']} from {trigger['toolkit_name']}")
        
        action_examples = []
        for action in list(context.catalog.available_actions)[:5]:  # Limit to 5
            if 'name' in action and 'toolkit_name' in action:
                action_examples.append(f"- {action['name']} from {action['toolkit_name']}")
        
        # Precompute joined strings to avoid backslashes in f-string expressions
        toolkits_text = "\n".join(toolkit_examples) if toolkit_examples else "No toolkits available"
        triggers_text = "\n".join(trigger_examples) if trigger_examples else "No triggers available"
        actions_text = "\n".join(action_examples) if action_examples else "No actions available"

        # Return a lightweight XML-styled examples block
        return (
            "<catalog_examples>\n"
            f"  <toolkits>\n{toolkits_text}\n  </toolkits>\n"
            f"  <triggers>\n{triggers_text}\n  </triggers>\n"
            f"  <actions>\n{actions_text}\n  </actions>\n"
            "</catalog_examples>"
        )
    
    def _get_feedback_section(self, attempt: int, previous_errors: List[str]) -> str:
        """Generate feedback section for retry attempts using XML helper"""
        # Summarize errors succinctly; keep a few examples
        summarized = []
        for error in previous_errors[:6]:
            summarized.append(f"- {error}")
        return render_feedback_retry(attempt=attempt, error_summary="\n".join(summarized))
    
    def build_final_attempt_prompt(self, context: GenerationContext, previous_errors: List[str]) -> str:
        """Build a minimal, guaranteed-valid workflow prompt for the final attempt (XML)"""
        # Get catalog data from the correct structure
        available_toolkits = getattr(context.catalog, 'available_providers', [])
        available_triggers = getattr(context.catalog, 'available_triggers', [])
        available_actions = getattr(context.catalog, 'available_actions', [])
        
        return render_final_attempt(
            user_prompt=context.request.user_prompt,
            available_toolkits=self._format_toolkits_for_prompt(available_toolkits),
            available_actions=self._format_actions_for_prompt(available_actions),
            available_triggers=self._format_triggers_for_prompt(available_triggers),
            previous_errors="\n".join(previous_errors[:6]),
        )
