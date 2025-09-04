#!/usr/bin/env python3

# Script to fix the remaining indentation issues in generator.py

# Read the current file
with open('/Users/talishawhite/workflow-automation-engine/services/dsl_generator/generator.py', 'r') as f:
    lines = f.readlines()

# Fix the specific indentation issues
for i, line in enumerate(lines):
    # Fix line 780 - triggers = provider_data.get('triggers', [])
    if line.strip() == "triggers = provider_data.get('triggers', [])" and line.startswith('                triggers'):
        lines[i] = "                    triggers = provider_data.get('triggers', [])\n"
        print(f"Fixed line {i+1}: indentation for triggers assignment")

# Write the fixed content back to the file
with open('/Users/talishawhite/workflow-automation-engine/services/dsl_generator/generator.py', 'w') as f:
    f.writelines(lines)

print("Fixed the remaining indentation issues in generator.py")
