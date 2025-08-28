"""
Base prompt templates for DSL Generator.

These templates define the structure and content of prompts for different
workflow types. They use Python string formatting placeholders that will
be filled in by the PromptBuilder.
"""

  

# Template for generating executable workflows
EXECUTABLE_PROMPT = """You are an expert workflow automation engineer. Generate an executable workflow based on the user's request.

USER REQUEST: {user_prompt}

WORKFLOW TYPE: Executable (concrete workflow with connections)
COMPLEXITY: {complexity}

AVAILABLE TOOLKITS:
{available_toolkits}

AVAILABLE TRIGGERS:
{available_triggers}

AVAILABLE ACTIONS:
{available_actions}

SCHEMA DEFINITION:
{schema_definition}

CRITICAL INSTRUCTIONS:
1. Generate a valid JSON executable that follows the schema EXACTLY
2. Use ONLY the toolkits, triggers, and actions listed above - NEVER invent or make up new ones
3. Every toolkit_slug, composio_trigger_slug, and action_name must exist in the available lists above
4. Include required connections array
5. Make the workflow realistic and useful
6. Follow the ExecutableSchema structure exactly

REQUIRED STRUCTURE FOR EXECUTABLE:
{{
  "schema_type": "executable",
  "workflow": {{
    "name": "Workflow Name",
    "description": "Workflow Description",
    "triggers": [
      {{
        "toolkit_slug": "available_toolkit_slug",
        "composio_trigger_slug": "available_trigger_slug"
      }}
    ],
    "actions": [
      {{
        "toolkit_slug": "available_toolkit_slug",
        "action_name": "available_action_name"
      }}
    ]
  }},
  "connections": [
    {{
      "toolkit_slug": "available_toolkit_slug",
      "connection_id": "connection_id_here"
    }}
  ]
}}

IMPORTANT: If you cannot create a valid workflow using only the available tools above, generate a minimal valid executable with the most relevant available tools.

OUTPUT FORMAT:
Return ONLY valid JSON that matches the ExecutableSchema. No explanations or markdown formatting.

{complexity_guidance}"""

# Template for generating DAG workflows
DAG_PROMPT = """You are an expert workflow automation engineer. Generate a DAG workflow based on the user's request.

USER REQUEST: {user_prompt}

WORKFLOW TYPE: DAG (directed acyclic graph with nodes and edges)
COMPLEXITY: {complexity}

AVAILABLE TOOLKITS:
{available_toolkits}

AVAILABLE TRIGGERS:
{available_triggers}

AVAILABLE ACTIONS:
{available_actions}

SCHEMA DEFINITION:
{schema_definition}

CRITICAL INSTRUCTIONS:
1. Generate a valid JSON DAG that follows the schema EXACTLY
2. Use ONLY the toolkits, triggers, and actions listed above - NEVER invent or make up new ones
3. Every toolkit_slug, composio_trigger_slug, and action_name must exist in the available lists above
4. Create meaningful nodes and edges
5. Make the workflow realistic and useful
6. Follow the DAGSchema structure exactly

REQUIRED STRUCTURE FOR DAG:
{{
  "schema_type": "dag",
  "nodes": [
    {{
      "id": "node_1",
      "type": "trigger",
      "data": {{
        "toolkit_slug": "available_toolkit_slug",
        "composio_trigger_slug": "available_trigger_slug"
      }}
    }},
    {{
      "id": "node_2",
      "type": "action",
      "data": {{
        "toolkit_slug": "available_toolkit_slug",
        "action_name": "available_action_name"
      }}
    }}
  ],
  "edges": [
    {{
      "id": "edge_1",
      "source": "node_1",
      "target": "node_2"
    }}
  ]
}}

IMPORTANT: If you cannot create a valid workflow using only the available tools above, generate a minimal valid DAG with the most relevant available tools.

OUTPUT FORMAT:
Return ONLY valid JSON that matches the DAGSchema. No explanations or markdown formatting.

{complexity_guidance}"""

# Complexity guidance templates
COMPLEXITY_GUIDANCE = {
    "simple": "Keep the workflow simple with 1-2 actions and basic flow control.",
    "medium": "Create a moderate workflow with 3-5 actions and some conditional logic.",
    "complex": "Build a sophisticated workflow with multiple actions, conditions, and parallel execution."
}

  

  

  

  


# ===============================
# XML-styled prompts and Weave DSL v2 schema (template-focused)
# ===============================

# Weave DSL v2 JSON Schema (exact text provided)
DSL_SCHEMA_V2 = r"""{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://weave.services/dsl-schema-v2.json",
  "title": "Weave Workflow DSL Schema v2",
  "description": "Comprehensive schema supporting template, executable, and DAG workflow formats with advanced flow control",
  "type": "object",
  "oneOf": [
    { "$ref": "#/$defs/TemplateSchema" },
    { "$ref": "#/$defs/ExecutableSchema" },
    { "$ref": "#/$defs/DAGSchema" }
  ],
  "$defs": {
    "TemplateSchema": {
      "type": "object",
      "required": ["schema_type", "workflow"],
      "properties": {
        "schema_type": {
          "type": "string",
          "enum": ["template"],
          "description": "Schema type identifier"
        },
        "workflow": { "$ref": "#/$defs/WorkflowTemplate" },
        "missing_information": {
          "type": "array",
          "description": "List of required information the user must provide",
          "items": { "$ref": "#/$defs/MissingInformation" }
        },
        "confidence": {
          "type": "integer",
          "minimum": 1,
          "maximum": 100,
          "description": "Confidence score (1-100)"
        }
      }
    },
    "ExecutableSchema": {
      "type": "object",
      "required": ["schema_type", "workflow", "connections"],
      "properties": {
        "schema_type": {
          "type": "string",
          "enum": ["executable"],
          "description": "Schema type identifier"
        },
        "workflow": { "$ref": "#/$defs/WorkflowTemplate" },
        "connections": {
          "type": "array",
          "description": "Required connections for this workflow",
          "items": { "$ref": "#/$defs/ConnectionRef" }
        }
      }
    },
    "DAGSchema": {
      "type": "object",
      "required": ["schema_type", "nodes", "edges"],
      "properties": {
        "schema_type": {
          "type": "string",
          "enum": ["dag"],
          "description": "Schema type identifier"
        },
        "nodes": {
          "type": "array",
          "items": { "$ref": "#/$defs/DAGNode" }
        },
        "edges": {
          "type": "array",
          "items": { "$ref": "#/$defs/DAGEdge" }
        },
        "metadata": { "$ref": "#/$defs/WorkflowMetadata" }
      }
    },
    "WorkflowTemplate": {
      "type": "object",
      "required": ["name", "description", "triggers", "actions"],
      "properties": {
        "name": { "type": "string" },
        "description": { "type": "string" },
        "triggers": {
          "type": "array",
          "items": { "$ref": "#/$defs/TriggerTemplate" }
        },
        "actions": {
          "type": "array",
          "items": { "$ref": "#/$defs/ActionTemplate" }
        },
        "flow_control": { "$ref": "#/$defs/FlowControl" }
      }
    },
    "WorkflowExecutable": {
      "type": "object",
      "required": ["name", "description", "triggers", "actions"],
      "properties": {
        "name": { "type": "string" },
        "description": { "type": "string" },
        "triggers": {
          "type": "array",
          "items": { "$ref": "#/$defs/TriggerTemplate" }
        },
        "actions": {
          "type": "array",
          "items": { "$ref": "#/$defs/ActionTemplate" }
        },
        "flow_control": { "$ref": "#/$defs/FlowControl" }
      }
    },
    "TriggerTemplate": {
      "type": "object",
      "required": ["id", "type", "toolkit_slug"],
      "properties": {
        "id": { "type": "string" },
        "type": {
          "type": "string",
          "enum": ["event_based", "schedule_based"]
        },
        "toolkit_slug": { "type": "string" },
        "composio_trigger_slug": { "type": "string" },
        "configuration": { "type": "object" },
        "filters": { "type": "object" },
        "depends_on": {
          "type": "array",
          "items": { "type": "string" }
        },
        "requires_auth": { "type": "boolean", "default": true },
        "schedule": {
          "type": "object",
          "description": "Required for schedule_based triggers",
          "properties": {
            "cron_expr": {
              "type": "string",
              "description": "Cron expression (5 or 6 field format like '0 */3 * * *' for every 3 hours)"
            },
            "timezone": {
              "type": "string",
              "description": "Timezone for the schedule (e.g., 'UTC', 'America/New_York')",
              "default": "UTC"
            }
          },
          "required": ["cron_expr"],
          "if": {
            "properties": { "type": { "const": "schedule_based" } }
          },
          "then": { "required": ["cron_expr"] }
        }
      }
    },
    "TriggerExecutable": {
      "allOf": [
        { "$ref": "#/$defs/TriggerTemplate" },
        {
          "required": ["composio_trigger_slug", "configuration"],
          "properties": {
            "connection_id": { "type": "string" }
          }
        }
      ]
    },
    "ActionTemplate": {
      "type": "object",
      "required": ["id", "toolkit_slug", "action_name"],
      "properties": {
        "id": { "type": "string" },
        "toolkit_slug": { "type": "string" },
        "action_name": { "type": "string" },
        "required_inputs": {
          "type": "array",
          "items": { "$ref": "#/$defs/InputParameter" }
        },
        "depends_on": {
          "type": "array",
          "items": { "type": "string" }
        },
        "requires_auth": { "type": "boolean", "default": true },
        "conditional": { "$ref": "#/$defs/ConditionalLogic" }
      }
    },
    "ActionExecutable": {
      "allOf": [
        { "$ref": "#/$defs/ActionTemplate" },
        {
          "required": ["required_inputs"],
          "properties": {
            "connection_id": { "type": "string" }
          }
        }
      ]
    },
    "InputParameter": {
      "type": "object",
      "required": ["name", "source"],
      "properties": {
        "name": { "type": "string" },
        "source": {
          "oneOf": [
            { "type": "string" },
            { "$ref": "#/$defs/DataReference" }
          ]
        },
        "type": { "type": "string" },
        "required": { "type": "boolean", "default": true }
      }
    },
    "DataReference": {
      "type": "object",
      "required": ["trigger_id", "field_path"],
      "properties": {
        "trigger_id": { "type": "string" },
        "field_path": { "type": "string" },
        "default_value": { "type": "string" }
      }
    },
    "FlowControl": {
      "type": "object",
      "properties": {
        "conditions": {
          "type": "array",
          "items": { "$ref": "#/$defs/ConditionalLogic" }
        },
        "parallel_execution": {
          "type": "array",
          "items": {
            "type": "array",
            "items": { "type": "string" }
          }
        },
        "retry_policy": { "$ref": "#/$defs/RetryPolicy" }
      }
    },
    "ConditionalLogic": {
      "type": "object",
      "required": ["condition", "if_true", "if_false"],
      "properties": {
        "condition": {
          "oneOf": [
            { "$ref": "#/$defs/ComparisonCondition" },
            { "$ref": "#/$defs/LogicalCondition" }
          ]
        },
        "if_true": {
          "oneOf": [
            { "type": "string" },
            { "type": "array", "items": { "type": "string" } }
          ]
        },
        "if_false": {
          "oneOf": [
            { "type": "string" },
            { "type": "array", "items": { "type": "string" } }
          ]
        }
      }
    },
    "ComparisonCondition": {
      "type": "object",
      "required": ["operator", "left", "right"],
      "properties": {
        "operator": {
          "type": "string",
          "enum": ["==", "!=", ">", "<", ">=", "<=", "contains", "starts_with", "ends_with"]
        },
        "left": { "$ref": "#/$defs/DataReference" },
        "right": {
          "oneOf": [
            { "type": "string" },
            { "type": "number" },
            { "type": "boolean" }
          ]
        }
      }
    },
    "LogicalCondition": {
      "type": "object",
      "required": ["operator", "conditions"],
      "properties": {
        "operator": {
          "type": "string",
          "enum": ["AND", "OR", "NOT"]
        },
        "conditions": {
          "type": "array",
          "items": { "$ref": "#/$defs/ConditionalLogic" }
        }
      }
    },
    "RetryPolicy": {
      "type": "object",
      "properties": {
        "max_retries": { "type": "integer", "minimum": 0 },
        "retry_delay": { "type": "integer", "minimum": 1000 },
        "backoff_multiplier": { "type": "number", "minimum": 1.0 }
      }
    },

    "ConnectionRef": {
      "type": "object",
      "required": ["toolkit_slug", "connection_id"],
      "properties": {
        "toolkit_slug": { "type": "string" },
        "connection_id": { "type": "string" }
      }
    },
    "MissingInformation": {
      "type": "object",
      "required": ["field", "prompt", "type"],
      "properties": {
        "field": { "type": "string" },
        "prompt": { "type": "string" },
        "type": { "type": "string" },
        "required": { "type": "boolean", "default": true }
      }
    },
    "WorkflowMetadata": {
      "type": "object",
      "properties": {
        "name": { "type": "string" },
        "description": { "type": "string" },
        "version": { "type": "string" },
        "author": { "type": "string" },
        "created_at": { "type": "string", "format": "date-time" },
        "updated_at": { "type": "string", "format": "date-time" }
      }
    },
    "DAGNode": {
      "type": "object",
      "required": ["id", "type", "data"],
      "properties": {
        "id": { "type": "string" },
        "type": {
          "type": "string",
          "enum": ["trigger", "action", "gateway_if", "gateway_parallel", "end"]
        },
        "position": {
          "type": "object",
          "properties": {
            "x": { "type": "number" },
            "y": { "type": "number" }
          }
        },
        "data": {
          "oneOf": [
            { "$ref": "#/$defs/TriggerNodeData" },
            { "$ref": "#/$defs/ActionNodeData" },
            { "$ref": "#/$defs/GatewayNodeData" }
          ]
        }
      }
    },
    "DAGEdge": {
      "type": "object",
      "required": ["source", "target"],
      "properties": {
        "source": { "type": "string" },
        "target": { "type": "string" },
        "sourceHandle": { "type": "string" },
        "targetHandle": { "type": "string" },
        "condition": {
          "type": "string",
          "description": "Simple condition string like 'talisha@alcemi.dev in inputs.sender' or 'else'"
        }
      }
    },
    "TriggerNodeData": {
      "type": "object",
      "required": ["trigger_type", "toolkit_slug", "composio_trigger_slug"],
      "properties": {
        "trigger_type": { 
          "type": "string",
          "description": "Human-readable trigger type like 'gmail_message_received'"
        },
        "toolkit_slug": { 
          "type": "string",
          "description": "Toolkit identifier like 'gmail'"
        },
        "composio_trigger_slug": { 
          "type": "string",
          "description": "Composio trigger slug like 'GMAIL_MESSAGE_RECEIVED'"
        },
        "filters": { 
          "type": "object",
          "description": "Trigger filters for conditional activation"
        },
        "configuration": { 
          "type": "object",
          "description": "Trigger configuration parameters"
        },
        "requires_auth": { 
          "type": "boolean",
          "default": true,
          "description": "Whether authentication is required"
        }
      }
    },
    "ActionNodeData": {
      "type": "object",
      "required": ["tool", "action", "connection_id", "requires_auth", "input_template"],
      "properties": {
        "tool": { 
          "type": "string",
          "description": "Tool category like 'gmail', 'slack', 'notion'"
        },
        "action": { 
          "type": "string",
          "description": "Specific action slug like 'GMAIL_SEND_EMAIL'"
        },
        "connection_id": { 
          "type": "string",
          "description": "Composio connection ID like 'ca_xxx'"
        },
        "requires_auth": { 
          "type": "boolean",
          "description": "Whether authentication is required"
        },
        "input_template": { 
          "$ref": "#/$defs/InputTemplate",
          "description": "Input parameters for the action"
        },
        "output_vars": { 
          "type": "object",
          "description": "Output variable mapping like {'message_id': 'id'}"
        },
        "retry": { 
          "$ref": "#/$defs/RetryPolicy",
          "description": "Retry configuration for the action"
        },
        "timeout_ms": { 
          "type": "integer",
          "minimum": 1000,
          "description": "Timeout in milliseconds"
        }
      }
    },
    "GatewayNodeData": {
      "type": "object",
      "required": ["gateway_type"],
      "properties": {
        "gateway_type": {
          "type": "string",
          "enum": ["if", "parallel", "join"],
          "description": "Type of gateway node"
        },
        "description": {
          "type": "string",
          "description": "Human-readable description of the gateway"
        },
        "branches": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Available branches for this gateway"
        },
        "else_to": {
          "type": "string",
          "description": "Default branch when no conditions match"
        }
      }
    },
    "InputTemplate": {
      "type": "object",
      "description": "Input template supporting both static and dynamic values",
      "additionalProperties": {
        "oneOf": [
          { "type": "string" },
          { "type": "number" },
          { "type": "boolean" },
          { "type": "array" },
          { "type": "null" },
          { "$ref": "#/$defs/Jinja2Template" }
        ]
      }
    },
    "Jinja2Template": {
      "type": "string",
      "pattern": ".*\\\\{\\\\{.*\\\\}\\\\}.*",
      "description": "Jinja2 template string containing {{ }} placeholders"
    },
    "RetryPolicy": {
      "type": "object",
      "properties": {
        "retries": { 
          "type": "integer", 
          "minimum": 0,
          "description": "Number of retry attempts"
        },
        "backoff": { 
          "type": "string",
          "enum": ["linear", "exponential"],
          "description": "Backoff strategy"
        },
        "delay_ms": { 
          "type": "integer", 
          "minimum": 100,
          "description": "Delay between retries in milliseconds"
        }
      }
    }
  }
}"""

# Main TEMPLATE prompt (XML-styled)
TEMPLATE_PROMPT_XML = """
<prompt id="weave.dsl.template" role="system">

  <meta>
    <purpose>
    Generate a parametric workflow template using ONLY the available toolkits, triggers, and actions.
    If toolkits are provided as selected apps, you must use ALL provided toolkits in your final workflow.
    Be sure to analyze the user's request and understand how the toolkits, triggers, and actions can be best utilized to achieve the user's goals.
    Identify required data flow between apps.
    </purpose>
    
    <audience>Workflow automation engineer</audience>
    <mode>JSON-only output (no prose, no markdown)</mode>
  </meta>

  <inputs>
    <user_request>{user_prompt}</user_request>
    <workflow_type>Template</workflow_type>

    <catalog>
      <available_toolkits>{available_toolkits}</available_toolkits>
      <available_triggers>{available_triggers}</available_triggers>
      <available_actions>{available_actions}</available_actions>
    </catalog>

    <schema_definition><![CDATA[{schema_definition}]]></schema_definition>
    <selected_plan><![CDATA[{selected_plan}]]></selected_plan>
  </inputs>

  <rules>
    <rule>Return ONLY valid JSON that matches the TemplateSchema. No markdown, no comments. NO ADDITIONAL TEXT OF ANY KIND</rule>
    <rule>Use ONLY toolkits/triggers/actions from the provided catalog. Never invent new ones.</rule>
    <rule>Every <code>toolkit_slug</code>, <code>composio_trigger_slug</code>, and <code>action_name</code> MUST exist in the catalog lists.</rule>
    <rule>If <code>selected_plan</code> is provided, you MUST use ONLY the tools and actions listed in that plan.</rule>
    <rule>MUST include at least one action in the workflow. A workflow with only triggers is incomplete.</rule>
    <rule>Build <code>missing_information</code> STRICTLY from unresolved required inputs in the workflow (actions and triggers). DO NOT add follow-up questions or preferences.</rule>
    <rule>For each action, inspect <code>required_inputs</code>. If any required input has no concrete value (empty, null, or a template referencing unknown data), add an entry to <code>missing_information</code>.</rule>
    <rule>For triggers, include required configuration fields (e.g., schedule cron) that are unset.</rule>
    <rule>Each missing item must use: <code>field</code> = a dot-path to the unresolved input (e.g., <code>actions.<action_id>.required_inputs.<param_name&gt;</code> or <code>triggers.<trigger_id>.configuration.<field></code>), <code>prompt</code> = short description of that specific input, <code>type</code> = expected type, <code>required</code> = true/false.</rule>
    <rule>If all required inputs are satisfied, output an empty <code>missing_information</code> array.</rule>
    <rule>Do NOT include planning rationale or a <code>plan</code> object in the output. Output ONLY the DSL JSON.</rule>
    <rule>Output MUST include a top-level <code>schema_type</code> field (template/executable/dag).</rule>
    <rule>Set a reasonable integer <code>confidence</code> (1–100).</rule>
    <rule>If the request cannot be satisfied with the catalog, output the simplest valid template using the most relevant available tools.</rule>
  </rules>

  <missing_information_policy>
    <source_of_truth>Unresolved required inputs defined by the selected triggers/actions only.</source_of_truth>
    <field_format>actions.&lt;action_id&gt;.required_inputs.&lt;param_name&gt; OR triggers.&lt;trigger_id&gt;.configuration.&lt;field&gt;</field_format>
    <prompt_text>Use the parameter's own description; do not ask follow-up product questions.</prompt_text>
    <type_source>Use the parameter's declared type (string, number, boolean, array, object, email, url, enum).</type_source>
    <when_empty>Leave array empty if nothing is missing.</when_empty>
  </missing_information_policy>

  <output_contract>
    <![CDATA[
    {{
      "schema_type": "template",
      "workflow": {{
        "name": "Workflow Name",
        "description": "Workflow Description",
        "triggers": [
          {{
            "id": "user-defined identifier",
            "type": "event_based or schedule_based",
            "toolkit_slug": "available_toolkit_slug",
            "composio_trigger_slug": "available_trigger_slug",
            "requires_auth": true
          }}
        ],
        "actions": [
          {{
            "id": "user-defined identifier",
            "toolkit_slug": "available_toolkit_slug",
            "action_name": "available_action_name",
            "required_inputs": [
              {{
                "name": "param_name",
                "source": "static string or {{{{ jinja }}}}",
                "type": "string|number|boolean|email|url|enum|object|array",
                "required": true
              }}
            ],
            "depends_on": ["trigger_or_action_ids"],
            "requires_auth": true
          }}
        ],
        "flow_control": {{
          "conditions": [],
          "parallel_execution": [],
          "retry_policy": null
        }}
      }},
      "missing_information": [
        {{
          "field": "actions.find_deals.required_inputs.deal_id",
          "prompt": "Deal identifier from the trigger payload (e.g., HubSpot deal id)",
          "type": "string",
          "required": true
        }}
      ],
      "confidence": 85
    }}
    ]]>
  </output_contract>

  <catalog_validation>
    <must>Use exact <code>toolkit_slug</code> values from &lt;available_toolkits&gt;.</must>
    <must>Use exact <code>composio_trigger_slug</code> values from &lt;available_triggers&gt;.</must>
    <must>Use exact <code>action_name</code> values from &lt;available_actions&gt;.</must>
    <never>Do not create or assume any tool that is not explicitly listed.</never>
  </catalog_validation>

</prompt>
"""

# Planning prompt (step 1): choose tools/actions and rationale
PLANNING_PROMPT_XML = """
<prompt id="weave.dsl.planning" role="system">

  <meta>
    <purpose>Plan which toolkits, triggers, and actions to use and why.</purpose>
    <audience>Workflow automation engineer</audience>
    <mode>JSON-only output (no prose, no markdown)</mode>
  </meta>

  <inputs>
    <user_request>{user_prompt}</user_request>
    <catalog>
      <available_toolkits>{available_toolkits}</available_toolkits>
      <available_triggers>{available_triggers}</available_triggers>
      <available_actions>{available_actions}</available_actions>
    </catalog>
  </inputs>

  <rules>
    <rule>Return ONLY valid JSON with a top-level object named "plan". No markdown.</rule>
    <rule>Use ONLY toolkits/triggers/actions from the provided catalog. Never invent new ones.</rule>
    <rule>Every <code>toolkit_slug</code>, <code>trigger_id</code>, and <code>action_name</code> MUST exist in the catalog lists.</rule>
    <rule>Prefer the most relevant tools for the user goal; avoid unrelated providers.</rule>
  </rules>

  <output_contract>
    <![CDATA[
    {
      "plan": {
        "toolkits": [
          { "toolkit_slug": "gmail", "why": "Receive and send emails" }
        ],
        "triggers": [
          { "toolkit_slug": "gmail", "composio_trigger_slug": "GMAIL_NEW_GMAIL_MESSAGE", "why": "Detect incoming messages" }
        ],
        "actions": [
          { "toolkit_slug": "gmail", "action_name": "GMAIL_SEND_EMAIL", "why": "Send a reply" }
        ],
        "notes": "Short reasoning explaining tool choices"
      }
    }
    ]]>
  </output_contract>

  <catalog_validation>
    <must>Use exact slugs/ids from the catalog lists.</must>
    <never>Do not include providers/actions unrelated to the user request.</never>
  </catalog_validation>

</prompt>
"""

def render_planning_prompt(
    user_prompt: str,
    available_toolkits: str,
    available_triggers: str,
    available_actions: str,
) -> str:
    import logging
    logger = logging.getLogger(__name__)
    
    logger.debug(f"render_planning_prompt called with:")
    logger.debug(f"  user_prompt: {user_prompt}")
    logger.debug(f"  available_toolkits type: {type(available_toolkits)}")
    logger.debug(f"  available_triggers type: {type(available_triggers)}")
    logger.debug(f"  available_actions type: {type(available_actions)}")
    
    try:
        result = PLANNING_PROMPT_XML.format(
            user_prompt=user_prompt,
            available_toolkits=available_toolkits,
            available_triggers=available_triggers,
            available_actions=available_actions,
        )
        logger.debug(f"Planning prompt rendered successfully (length: {len(result)})")
        return result
    except Exception as e:
        logger.error(f"Error rendering planning prompt: {e}")
        logger.error(f"Parameters: user_prompt='{user_prompt}', toolkits='{available_toolkits}', triggers='{available_triggers}', actions='{available_actions}'")
        raise

# Strict catalog guardrails (reusable block)
CATALOG_VALIDATION_STRICT_XML = """
<catalog_validation_strict id="weave.dsl.catalog.validation">
  <rules>
    <rule>You MUST use ONLY the exact <code>toolkit_slug</code> values from &lt;available_toolkits&gt;.</rule>
    <rule>You MUST use ONLY the exact <code>composio_trigger_slug</code> values from &lt;available_triggers&gt;.</rule>
    <rule>You MUST use ONLY the exact <code>action_name</code> values from &lt;available_actions&gt;.</rule>
    <rule>If a toolkit/trigger/action is not listed, it DOES NOT EXIST and CANNOT be used.</rule>
    <rule>When in doubt, choose the most relevant available tool from the catalog.</rule>
  </rules>
  <anti_examples>
    <never>email_service (unless present in catalog)</never>
    <never>send_email (unless present in actions)</never>
    <never>analytics (unless present in catalog)</never>
    <never>log_event (unless present in actions)</never>
  </anti_examples>
  <positive_examples>
    <do>Use only exact slugs/ids/names from the provided lists.</do>
  </positive_examples>
</catalog_validation_strict>
"""

# Retry feedback helper (for regenerations)
FEEDBACK_RETRY_XML = """
<prompt id="weave.dsl.feedback.retry" role="system">
  <attempt>{attempt}</attempt>
  <previous_errors><![CDATA[
{error_summary}
  ]]></previous_errors>
  <directive>
    Fix ALL above errors. Re-emit output using ONLY the provided catalog. Do NOT repeat mistakes.
  </directive>
</prompt>
"""

# Final minimal attempt (last-chance fallback)
FINAL_ATTEMPT_XML = """
<prompt id="weave.dsl.final.attempt" role="system">

  <meta>
    <severity>CRITICAL</severity>
    <instruction>Emit the simplest valid TEMPLATE that passes catalog validation.</instruction>
  </meta>

  <inputs>
    <user_request>{user_prompt}</user_request>
    <workflow_type>Template</workflow_type>
    <catalog>
      <available_toolkits>{available_toolkits}</available_toolkits>
      <available_actions>{available_actions}</available_actions>
      <available_triggers>{available_triggers}</available_triggers>
    </catalog>
    <previous_errors><![CDATA[{previous_errors}]]></previous_errors>
  </inputs>

  <rules>
    <rule>Use ONLY exact catalog values.</rule>
    <rule>Prefer the first relevant toolkit/action/trigger if uncertain.</rule>
    <rule>Validity over complexity. Simpler is better.</rule>
    <rule>Return ONLY JSON for the TemplateSchema. No prose.</rule>
    <rule>MUST include schema_type: "template" field.</rule>
    <rule>MUST include workflow object with at least one trigger and one action.</rule>
  </rules>

  <output_format>
    <![CDATA[
    {
      "schema_type": "template",
      "workflow": {
        "name": "Simple Workflow",
        "description": "Basic workflow for the user request",
        "triggers": [
          {
            "id": "trigger_1",
            "type": "event_based",
            "toolkit_slug": "github",
            "composio_trigger_slug": "GITHUB_ISSUE_ADDED_EVENT"
          }
        ],
        "actions": [
          {
            "id": "action_1",
            "type": "action",
            "toolkit_slug": "linear",
            "action_name": "LINEAR_CREATE_ISSUE"
          }
        ]
      },
      "missing_information": [],
      "confidence": 50
    }
    ]]>
  </output_format>

</prompt>
"""

# Complexity guidance (shared text)
COMPLEXITY_GUIDANCE_TEXT = """
<complexity_guidance id="weave.dsl.complexity">
  <simple>Keep the workflow simple with 1–2 actions and basic flow control.</simple>
  <medium>Create a moderate workflow with 3–5 actions and some conditional logic.</medium>
  <complex>Build a sophisticated workflow with multiple actions, conditions, and parallel execution.</complex>
</complexity_guidance>
"""

# Convenience: renderers for PromptBuilder
def render_template_prompt(
    user_prompt: str,
    complexity: str,
    available_toolkits: str,
    available_triggers: str,
    available_actions: str,
    schema_definition: str = DSL_SCHEMA_V2,
    complexity_guidance: str = COMPLEXITY_GUIDANCE_TEXT,
    selected_plan: str = "{}",
) -> str:
    """
    Produce the filled XML system prompt for TEMPLATE generation.
    All catalog inputs should be preformatted strings (lists or tables of items).
    """
    return TEMPLATE_PROMPT_XML.format(
        user_prompt=user_prompt,
        complexity=complexity,
        available_toolkits=available_toolkits,
        available_triggers=available_triggers,
        available_actions=available_actions,
        schema_definition=schema_definition,
        complexity_guidance=complexity_guidance,
        selected_plan=selected_plan,
    )


def render_feedback_retry(attempt: int, error_summary: str) -> str:
    """Produce the retry feedback XML block."""
    return FEEDBACK_RETRY_XML.format(attempt=attempt, error_summary=error_summary)


def render_final_attempt(
    user_prompt: str,
    available_toolkits: str,
    available_actions: str,
    available_triggers: str,
    previous_errors: str,
) -> str:
    """Produce the final-attempt fallback XML block (template-only)."""
    return FINAL_ATTEMPT_XML.format(
        user_prompt=user_prompt,
        available_toolkits=available_toolkits,
        available_actions=available_actions,
        available_triggers=available_triggers,
        previous_errors=previous_errors,
    )
