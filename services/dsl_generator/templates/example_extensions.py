"""
Example: Extending and Customizing Prompt Templates

This file demonstrates how to create custom prompt variations
and extend the base templates for specific use cases.
"""

from .base_templates import (
    TEMPLATE_PROMPT,
    EXECUTABLE_PROMPT,
    DAG_PROMPT,
    COMPLEXITY_GUIDANCE
)

# Example 1: Add business-specific instructions
BUSINESS_TEMPLATE_PROMPT = TEMPLATE_PROMPT.replace(
    "CRITICAL INSTRUCTIONS:",
    """CRITICAL INSTRUCTIONS:
1. Generate a valid JSON template that follows the schema EXACTLY
2. Use ONLY the toolkits, triggers, and actions listed above - NEVER invent or make up new ones
3. Every toolkit_slug, trigger_id, and action_name must exist in the available lists above
4. Include meaningful missing_information fields for user input
5. Set appropriate confidence score (1-100)
6. Make the workflow realistic and useful
7. Follow the TemplateSchema structure exactly
8. BUSINESS RULE: Ensure workflows comply with company data retention policies
9. BUSINESS RULE: Include audit logging for compliance purposes
10. BUSINESS RULE: Prioritize security and privacy considerations"""
)

# Example 2: Create a simplified template for beginners
SIMPLE_TEMPLATE_PROMPT = """You are a helpful workflow automation assistant. Create a simple workflow template.

USER REQUEST: {user_prompt}

WORKFLOW TYPE: Simple Template
COMPLEXITY: Basic

AVAILABLE TOOLKITS:
{available_toolkits}

AVAILABLE ACTIONS:
{available_actions}

INSTRUCTIONS:
1. Create a very simple workflow with just 1-2 actions
2. Use only the tools listed above
3. Make it easy to understand and implement
4. Include clear missing_information fields

REQUIRED STRUCTURE:
{{
  "schema_type": "template",
  "workflow": {{
    "name": "Simple Workflow",
    "description": "A basic workflow for beginners",
    "triggers": [],
    "actions": [
      {{
        "toolkit_slug": "available_toolkit",
        "action_name": "available_action"
      }}
    ]
  }},
  "missing_information": [
    {{
      "field": "example_field",
      "prompt": "What would you like to configure?",
      "type": "string",
      "required": true
    }}
  ],
  "confidence": 90
}}

OUTPUT: Return only valid JSON, no explanations."""

# Example 3: Add industry-specific guidance
INDUSTRY_GUIDANCE = {
    "healthcare": "Ensure HIPAA compliance and patient data privacy",
    "finance": "Include audit trails and compliance reporting",
    "education": "Focus on student data protection and accessibility",
    "retail": "Prioritize customer experience and inventory management"
}

def get_industry_specific_prompt(industry: str, base_prompt: str) -> str:
    """Add industry-specific guidance to any base prompt"""
    if industry in INDUSTRY_GUIDANCE:
        industry_rule = f"\nINDUSTRY RULE: {INDUSTRY_GUIDANCE[industry]}"
        return base_prompt.replace(
            "CRITICAL INSTRUCTIONS:",
            f"CRITICAL INSTRUCTIONS:{industry_rule}"
        )
    return base_prompt

# Example 4: Create a template with conditional complexity
def get_adaptive_complexity_prompt(context, base_prompt: str) -> str:
    """Adapt prompt complexity based on available tools"""
    available_tools = len(context.catalog.available_providers)
    
    if available_tools < 3:
        complexity_note = "\nNOTE: Limited tools available - keep workflow simple"
    elif available_tools < 10:
        complexity_note = "\nNOTE: Moderate tool selection - balanced complexity recommended"
    else:
        complexity_note = "\nNOTE: Rich tool selection - can create sophisticated workflows"
    
    return base_prompt.replace(
        "CRITICAL INSTRUCTIONS:",
        f"CRITICAL INSTRUCTIONS:{complexity_note}"
    )

# Example 5: Add user experience guidance
USER_EXPERIENCE_TEMPLATE = TEMPLATE_PROMPT.replace(
    "CRITICAL INSTRUCTIONS:",
    """CRITICAL INSTRUCTIONS:
1. Generate a valid JSON template that follows the schema EXACTLY
2. Use ONLY the toolkits, triggers, and actions listed above - NEVER invent or make up new ones
3. Every toolkit_slug, trigger_id, and action_name must exist in the available lists above
4. Include meaningful missing_information fields for user input
5. Set appropriate confidence score (1-100)
6. Make the workflow realistic and useful
7. Follow the TemplateSchema structure exactly
8. UX RULE: Make missing_information prompts user-friendly and clear
9. UX RULE: Use descriptive field names that are self-explanatory
10. UX RULE: Provide helpful examples in prompts when possible"""
)

# Example 6: Create a template for specific use cases
def get_use_case_specific_prompt(use_case: str, base_prompt: str) -> str:
    """Customize prompt for specific use cases"""
    use_case_instructions = {
        "automation": "\nAUTOMATION FOCUS: Emphasize efficiency and time-saving",
        "integration": "\nINTEGRATION FOCUS: Highlight data flow between systems",
        "monitoring": "\nMONITORING FOCUS: Include alerting and notification features",
        "compliance": "\nCOMPLIANCE FOCUS: Ensure audit trails and documentation"
    }
    
    if use_case in use_case_instructions:
        return base_prompt.replace(
            "CRITICAL INSTRUCTIONS:",
            f"CRITICAL INSTRUCTIONS:{use_case_instructions[use_case]}"
        )
    return base_prompt

# Example 7: Add seasonal or time-based prompts
def get_seasonal_prompt(base_prompt: str, season: str = None) -> str:
    """Add seasonal context to prompts"""
    seasonal_context = {
        "holiday": "\nSEASONAL CONTEXT: Consider holiday-specific workflows and timing",
        "quarter_end": "\nSEASONAL CONTEXT: Focus on reporting and deadline-driven workflows",
        "year_end": "\nSEASONAL CONTEXT: Include year-end processes and new year planning",
        "tax_season": "\nSEASONAL CONTEXT: Emphasize financial and tax-related workflows"
    }
    
    if season in seasonal_context:
        return base_prompt.replace(
            "CRITICAL INSTRUCTIONS:",
            f"CRITICAL INSTRUCTIONS:{seasonal_context[season]}"
        )
    return base_prompt

# Example 8: Create a template with learning objectives
LEARNING_TEMPLATE_PROMPT = """You are an expert workflow automation engineer and educator. Generate a workflow template that teaches users about automation.

USER REQUEST: {user_prompt}

WORKFLOW TYPE: Educational Template
COMPLEXITY: {complexity}

AVAILABLE TOOLKITS:
{available_toolkits}

AVAILABLE TRIGGERS:
{available_triggers}

AVAILABLE ACTIONS:
{available_actions}

SCHEMA DEFINITION:
{schema_definition}

EDUCATIONAL OBJECTIVES:
1. Generate a valid JSON template that follows the schema EXACTLY
2. Use ONLY the toolkits, triggers, and actions listed above
3. Include clear missing_information fields with educational value
4. Add comments in the missing_information to explain concepts
5. Make the workflow demonstrate best practices
6. Include learning opportunities in the workflow design
7. Follow the TemplateSchema structure exactly

REQUIRED STRUCTURE:
{{
  "schema_type": "template",
  "workflow": {{
    "name": "Educational Workflow",
    "description": "A workflow that teaches automation concepts",
    "triggers": [...],
    "actions": [...]
  }},
  "missing_information": [
    {{
      "field": "example_field",
      "prompt": "What would you like to configure? (This field demonstrates how to collect user input)",
      "type": "string",
      "required": true,
      "learning_note": "This field shows how to make workflows configurable"
    }}
  ],
  "confidence": 85
}}

OUTPUT FORMAT:
Return ONLY valid JSON that matches the TemplateSchema. No explanations or markdown formatting.

{complexity_guidance}"""

# Example 9: Create a template for different user skill levels
SKILL_LEVEL_TEMPLATES = {
    "beginner": SIMPLE_TEMPLATE_PROMPT,
    "intermediate": TEMPLATE_PROMPT,
    "advanced": TEMPLATE_PROMPT.replace(
        "CRITICAL INSTRUCTIONS:",
        """CRITICAL INSTRUCTIONS:
1. Generate a valid JSON template that follows the schema EXACTLY
2. Use ONLY the toolkits, triggers, and actions listed above
3. Every toolkit_slug, trigger_id, and action_name must exist in the available lists above
4. Include meaningful missing_information fields for user input
5. Set appropriate confidence score (1-100)
6. Make the workflow realistic and useful
7. Follow the TemplateSchema structure exactly
8. ADVANCED: Include conditional logic and error handling
9. ADVANCED: Consider edge cases and failure scenarios
10. ADVANCED: Optimize for performance and scalability"""
    )
}

def get_skill_level_prompt(skill_level: str) -> str:
    """Get prompt template for specific skill level"""
    return SKILL_LEVEL_TEMPLATES.get(skill_level, TEMPLATE_PROMPT)

# Example 10: Create a template with company branding
def get_branded_prompt(company_name: str, base_prompt: str) -> str:
    """Add company branding to prompts"""
    branded_intro = f"""You are an expert workflow automation engineer at {company_name}. 
Generate a workflow template that aligns with {company_name}'s automation standards and best practices.

"""
    
    return base_prompt.replace(
        "You are an expert workflow automation engineer. Generate a workflow template based on the user's request.",
        branded_intro
    )
