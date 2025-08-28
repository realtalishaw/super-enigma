# Prompt Templates for DSL Generator

This directory contains the prompt templates used by the DSL Generator service to communicate with Claude AI for workflow generation.

## 📁 File Structure

- **`__init__.py`** - Package initialization and exports
- **`base_templates.py`** - Core prompt templates for different workflow types
- **`README.md`** - This documentation file

## 🎯 Available Templates

### 1. **Template Workflows** (`TEMPLATE_PROMPT`)
Generates parametric workflows with missing fields that users need to fill in.

**Use Case**: When you want to create a workflow template that users can customize.

### 2. **Executable Workflows** (`EXECUTABLE_PROMPT`)
Generates concrete workflows with all necessary connections and parameters.

**Use Case**: When you want to create a ready-to-run workflow.

### 3. **DAG Workflows** (`DAG_PROMPT`)
Generates directed acyclic graph workflows with nodes and edges.

**Use Case**: When you need complex workflow logic with multiple execution paths.

## 🔧 Template Variables

All templates use Python string formatting with these placeholders:

```python
{
    "user_prompt": "The user's natural language request",
    "complexity": "simple|medium|complex",
    "available_toolkits": "Formatted list of available toolkits",
    "available_triggers": "Formatted list of available triggers", 
    "available_actions": "Formatted list of available actions",
    "schema_definition": "JSON schema definition",
    "complexity_guidance": "Complexity-specific instructions"
}
```

## 📝 How to Modify Prompts

### **Adding New Instructions**

1. **Edit the template** in `base_templates.py`:
   ```python
   TEMPLATE_PROMPT = """You are an expert workflow automation engineer...
   
   NEW INSTRUCTION: Add your custom instruction here
   
   USER REQUEST: {user_prompt}
   ...
   """
   ```

2. **Add new template variables** if needed:
   ```python
   # In base_templates.py
   NEW_TEMPLATE_VARIABLE = "Your new template content"
   
   # In prompt_builder.py, update the format call:
   return TEMPLATE_PROMPT.format(
       # ... existing variables
       new_variable=NEW_TEMPLATE_VARIABLE
   )
   ```

### **Creating New Workflow Types**

1. **Add the template** to `base_templates.py`:
   ```python
   NEW_WORKFLOW_TYPE_PROMPT = """Your new prompt template here..."""
   ```

2. **Update the exports** in `__init__.py`:
   ```python
   from .base_templates import (
       TEMPLATE_PROMPT,
       EXECUTABLE_PROMPT,
       DAG_PROMPT,
       NEW_WORKFLOW_TYPE_PROMPT  # Add this
   )
   
   __all__ = [
       'TEMPLATE_PROMPT',
       'EXECUTABLE_PROMPT', 
       'DAG_PROMPT',
       'NEW_WORKFLOW_TYPE_PROMPT'  # Add this
   ]
   ```

3. **Update PromptBuilder** in `prompt_builder.py`:
   ```python
   from .templates.base_templates import (
       # ... existing imports
       NEW_WORKFLOW_TYPE_PROMPT
   )
   
   class PromptBuilder:
       def __init__(self):
           self.generation_templates = {
               "template": self._build_template_prompt,
               "executable": self._build_executable_prompt,
               "dag": self._build_dag_prompt,
               "new_type": self._build_new_type_prompt  # Add this
           }
       
       def _build_new_type_prompt(self, context: GenerationContext, complexity: str) -> str:
           return NEW_WORKFLOW_TYPE_PROMPT.format(
               # ... format with your variables
           )
   ```

## 🎨 Customizing Prompt Content

### **Modifying Instructions**

You can customize any part of the prompts:

- **Role Definition**: Change "You are an expert workflow automation engineer" to something else
- **Instructions**: Modify the critical instructions list
- **Examples**: Update the required structure examples
- **Validation Rules**: Customize catalog validation instructions

### **Adding New Sections**

```python
TEMPLATE_PROMPT = """You are an expert workflow automation engineer...

USER REQUEST: {user_prompt}

NEW SECTION: Add your custom section here
{new_section_content}

AVAILABLE TOOLKITS:
{available_toolkits}
...
"""
```

### **Conditional Content**

You can add conditional logic in the PromptBuilder:

```python
def _build_template_prompt(self, context: GenerationContext, complexity: str) -> str:
    # Add conditional content based on context
    extra_instructions = ""
    if context.request.user_id:
        extra_instructions = "\nUSER CONTEXT: This is for user {context.request.user_id}"
    
    return TEMPLATE_PROMPT.format(
        # ... existing variables
        extra_instructions=extra_instructions
    )
```

## 🔍 Testing Template Changes

1. **Run the debug script** to test your changes:
   ```bash
   cd services/dsl_generator
   python debug_generation.py
   ```

2. **Check prompt output** in the logs to see how your template renders

3. **Test with real generation** to ensure Claude understands the new instructions

## 📚 Best Practices

### **Template Design**
- **Be Specific**: Give clear, unambiguous instructions
- **Use Examples**: Include concrete examples of expected output
- **Validate Input**: Ensure all placeholders are properly filled
- **Keep Consistent**: Maintain similar structure across workflow types

### **Content Organization**
- **Logical Flow**: Organize content in a logical sequence
- **Clear Sections**: Use clear section headers and separators
- **Consistent Formatting**: Use consistent formatting for lists and examples
- **Error Prevention**: Include instructions that prevent common mistakes

### **Maintenance**
- **Version Control**: Track changes to templates
- **Documentation**: Document any new template variables or sections
- **Testing**: Test templates with different inputs and contexts
- **Review**: Regularly review and improve template effectiveness

## 🚀 Advanced Customization

### **Dynamic Templates**

You can create dynamic templates that change based on context:

```python
def get_dynamic_template(context: GenerationContext) -> str:
    if context.catalog.available_providers < 5:
        return SIMPLE_TEMPLATE_PROMPT
    else:
        return ADVANCED_TEMPLATE_PROMPT
```

### **Template Inheritance**

Create base templates and extend them:

```python
BASE_INSTRUCTIONS = """CRITICAL INSTRUCTIONS:
1. Generate valid JSON
2. Follow the schema exactly
3. Use only available tools"""

TEMPLATE_PROMPT = f"""{BASE_INSTRUCTIONS}

SPECIFIC TEMPLATE INSTRUCTIONS:
4. Include missing_information fields
5. Set confidence score

USER REQUEST: {{user_prompt}}
..."""
```

### **Localization**

Support multiple languages:

```python
TEMPLATES = {
    "en": TEMPLATE_PROMPT_EN,
    "es": TEMPLATE_PROMPT_ES,
    "fr": TEMPLATE_PROMPT_FR
}

def get_localized_template(language: str, workflow_type: str) -> str:
    return TEMPLATES[language][workflow_type]
```

## 🔧 Troubleshooting

### **Common Issues**

1. **Missing Variables**: Ensure all placeholders in templates are provided in format calls
2. **Format Errors**: Check that template strings use valid Python string formatting syntax
3. **Import Errors**: Verify that templates are properly exported from `__init__.py`

### **Debug Tips**

- Use the debug script to test individual components
- Check logs for template rendering errors
- Validate that all required context data is available
- Test templates with minimal context to isolate issues

---

**Note**: When modifying templates, always test thoroughly as they directly affect the quality of generated workflows. Small changes can have significant impacts on Claude's understanding and output quality.
