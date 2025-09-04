#!/usr/bin/env python3

# Script to fix the generator.py file with proper SCHEDULE_BASED trigger handling

# Read the current file
with open('/Users/talishawhite/workflow-automation-engine/services/dsl_generator/generator.py', 'r') as f:
    lines = f.readlines()

# Find the line with the problematic condition and fix it
for i, line in enumerate(lines):
    if "if trigger_slug and trigger_slug != 'SCHEDULE_BASED':" in line:
        # Replace the problematic line with proper handling
        lines[i] = "        if trigger_slug:\n"
        
        # Insert the new SCHEDULE_BASED handling
        insert_lines = [
            "            if trigger_slug == 'SCHEDULE_BASED':\n",
            "                # Add a schedule-based trigger\n",
            "                catalog_context['triggers'].append({\n",
            "                    'slug': 'SCHEDULE_BASED',\n",
            "                    'name': 'Schedule Based Trigger',\n",
            "                    'description': 'Trigger that runs on a schedule',\n",
            "                    'toolkit_slug': 'system',\n",
            "                    'toolkit_name': 'System',\n",
            "                    'trigger_slug': 'SCHEDULE_BASED',\n",
            "                    'metadata': {'type': 'schedule_based'}\n",
            "                })\n",
            "            else:\n"
        ]
        
        # Insert the new lines
        for j, new_line in enumerate(insert_lines):
            lines.insert(i + 1 + j, new_line)
        
        # Fix the indentation for the rest of the code block
        # Find the next lines and fix their indentation
        current_index = i + len(insert_lines) + 1
        while current_index < len(lines):
            line = lines[current_index]
            if line.strip().startswith('# Find and add the selected actions'):
                break
            if line.startswith('            # Find the trigger in the catalog'):
                lines[current_index] = line.replace('            # Find the trigger in the catalog', '                # Find the trigger in the catalog')
            elif line.startswith('            for provider_slug, provider_data in catalog_data.items():'):
                lines[current_index] = line.replace('            for provider_slug, provider_data in catalog_data.items():', '                for provider_slug, provider_data in catalog_data.items():')
            elif line.startswith('                triggers = provider_data.get(\'triggers\', []):'):
                lines[current_index] = line.replace('                triggers = provider_data.get(\'triggers\', []):', '                    triggers = provider_data.get(\'triggers\', []):')
            elif line.startswith('                for trigger in triggers:'):
                lines[current_index] = line.replace('                for trigger in triggers:', '                    for trigger in triggers:')
            elif line.startswith('                    if trigger.get(\'slug\') == trigger_slug:'):
                lines[current_index] = line.replace('                    if trigger.get(\'slug\') == trigger_slug:', '                        if trigger.get(\'slug\') == trigger_slug:')
            elif line.startswith('                        catalog_context[\'triggers\'].append({'):
                lines[current_index] = line.replace('                        catalog_context[\'triggers\'].append({', '                            catalog_context[\'triggers\'].append({')
            elif line.startswith('                        # Add provider info'):
                lines[current_index] = line.replace('                        # Add provider info', '                            # Add provider info')
            elif line.startswith('                        catalog_context[\'providers\'][provider_slug] = {'):
                lines[current_index] = line.replace('                        catalog_context[\'providers\'][provider_slug] = {', '                            catalog_context[\'providers\'][provider_slug] = {')
            elif line.startswith('                        break'):
                lines[current_index] = line.replace('                        break', '                            break')
            current_index += 1
        break

# Write the fixed content back to the file
with open('/Users/talishawhite/workflow-automation-engine/services/dsl_generator/generator.py', 'w') as f:
    f.writelines(lines)

print("Fixed the generator.py file with proper SCHEDULE_BASED trigger handling")