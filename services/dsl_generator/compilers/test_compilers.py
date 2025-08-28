#!/usr/bin/env python3
"""
Test script to demonstrate the workflow DSL compilers.

This script shows the complete pipeline:
Template JSON → Template Materializer → Executable JSON → Graph Lowerer → DAG JSON
"""

import json
import sys
from pathlib import Path

# Add the compilers directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from template_materializer import TemplateMaterializer
from graph_lowerer import GraphLowerer


def load_example_data():
    """Load example data for testing"""
    examples_dir = Path(__file__).parent / "examples"
    
    with open(examples_dir / "simple_template.json") as f:
        template = json.load(f)
    
    with open(examples_dir / "sample_catalog.json") as f:
        catalog = json.load(f)
    
    with open(examples_dir / "sample_connections.json") as f:
        connections = json.load(f)
    
    with open(examples_dir / "sample_answers.json") as f:
        answers = json.load(f)
    
    with open(examples_dir / "sample_defaults.json") as f:
        defaults = json.load(f)
    
    return template, catalog, connections, answers, defaults


def test_template_materializer():
    """Test the Template Materializer (T→E)"""
    print("=" * 60)
    print("TESTING TEMPLATE MATERIALIZER (T→E)")
    print("=" * 60)
    
    template, catalog, connections, answers, defaults = load_example_data()
    
    # Create context
    ctx = {
        "catalog": catalog,
        "user": {"id": "user123", "tenant_id": "tenant456"},
        "connections": connections,
        "answers": answers,
        "defaults": defaults
    }
    
    # Compile template to executable
    materializer = TemplateMaterializer()
    result = materializer.compile(template, ctx)
    
    if result["executable_doc"] is None:
        print("❌ Template compilation failed!")
        for error in result["report"].errors:
            print(f"  Error: {error['path']} - {error['message']}")
        return None
    
    print("✅ Template compilation successful!")
    
    # Show report
    if result["report"].warnings:
        print("\n⚠️  Warnings:")
        for warning in result["report"].warnings:
            print(f"  {warning['path']}: {warning['message']}")
    
    if result["report"].repairs:
        print("\n🔧 Auto-repairs applied:")
        for repair in result["report"].repairs:
            print(f"  {repair['path']}: {repair['reason']}")
    
    # Show the executable document
    executable = result["executable_doc"]
    print(f"\n📋 Executable Document:")
    print(f"  Workflow ID: {executable['workflow_id']}")
    print(f"  Version: {executable['version']}")
    print(f"  Triggers: {len(executable['triggers'])}")
    print(f"  Actions: {len(executable['actions'])}")
    
    # Show trigger details
    for trigger in executable["triggers"]:
        print(f"\n  🔔 Trigger: {trigger['local_id']}")
        print(f"    Provider: {trigger['exec']['provider']}")
        print(f"    Slug: {trigger['exec']['trigger_slug']}")
        print(f"    Connection: {trigger['exec']['connection_id']}")
        if "trigger_instance_id" in trigger:
            print(f"    Instance ID: {trigger['trigger_instance_id'][:16]}...")
    
    # Show action details
    for action in executable["actions"]:
        print(f"\n  ⚡ Action: {action['local_id']}")
        print(f"    Provider: {action['exec']['provider']}")
        print(f"    Slug: {action['exec']['action_slug']}")
        print(f"    Connection: {action['exec']['connection_id']}")
        print(f"    Retry: {action['exec']['retry']['max_attempts']} attempts")
        print(f"    Timeout: {action['exec']['timeout_ms']}ms")
    
    return executable


def test_graph_lowerer(executable):
    """Test the Graph Lowerer (E→D)"""
    print("\n" + "=" * 60)
    print("TESTING GRAPH LOWERER (E→D)")
    print("=" * 60)
    
    # Create context
    ctx = {
        "catalog": {},  # Not needed for basic lowering
        "layout": "dagre",
        "uiDefaults": {}
    }
    
    # Compile executable to DAG
    lowerer = GraphLowerer()
    result = lowerer.compile(executable, ctx)
    
    if result["dag_doc"] is None:
        print("❌ DAG compilation failed!")
        for error in result["report"].errors:
            print(f"  Error: {error['path']} - {error['message']}")
        return None
    
    print("✅ DAG compilation successful!")
    
    # Show report
    if result["report"].warnings:
        print("\n⚠️  Warnings:")
        for warning in result["report"].warnings:
            print(f"  {warning['path']}: {warning['message']}")
    
    if result["report"].hints:
        print("\n💡 Hints:")
        for hint in result["report"].hints:
            print(f"  {hint}")
    
    # Show the DAG document
    dag = result["dag_doc"]
    print(f"\n📊 DAG Document:")
    print(f"  Workflow ID: {dag['workflow_id']}")
    print(f"  Version: {dag['version']}")
    print(f"  Nodes: {len(dag['nodes'])}")
    print(f"  Edges: {len(dag['edges'])}")
    
    # Show node details
    for node in dag["nodes"]:
        print(f"\n  🟢 Node: {node['id']} ({node['type']})")
        print(f"    Label: {node['label']}")
        if "position" in node:
            print(f"    Position: ({node['position']['x']}, {node['position']['y']})")
        
        # Show node-specific data
        if node["type"] == "trigger":
            data = node["data"]
            print(f"    Kind: {data['kind']}")
            print(f"    Tool: {data['tool']}")
            print(f"    Slug: {data['slug']}")
        elif node["type"] == "action":
            data = node["data"]
            print(f"    Tool: {data['tool']}")
            print(f"    Action: {data['action']}")
            print(f"    Retry: {data['retry']['max_attempts']} attempts")
    
    # Show edge details
    for edge in dag["edges"]:
        print(f"\n  🔗 Edge: {edge['id']}")
        print(f"    Source: {edge['source']} → Target: {edge['target']}")
        print(f"    When: {edge['when']}")
        if edge.get("label"):
            print(f"    Label: {edge['label']}")
    
    # Show globals
    if dag["globals"]:
        print(f"\n⚙️  Global Settings:")
        for key, value in dag["globals"].items():
            print(f"    {key}: {value}")
    
    return dag


def main():
    """Run the complete compiler test"""
    print("🚀 Workflow DSL Compiler Test Suite")
    print("Testing the complete pipeline: Template → Executable → DAG")
    
    # Step 1: Template Materializer
    executable = test_template_materializer()
    if not executable:
        print("\n❌ Pipeline failed at Template Materializer stage")
        return
    
    # Step 2: Graph Lowerer
    dag = test_graph_lowerer(executable)
    if not dag:
        print("\n❌ Pipeline failed at Graph Lowerer stage")
        return
    
    # Success!
    print("\n" + "=" * 60)
    print("🎉 COMPLETE PIPELINE SUCCESS!")
    print("=" * 60)
    print("✅ Template JSON → Template Materializer → Executable JSON")
    print("✅ Executable JSON → Graph Lowerer → DAG JSON")
    print("\nThe workflow is now ready for execution!")
    
    # Save outputs for inspection
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    with open(output_dir / "executable.json", "w") as f:
        json.dump(executable, f, indent=2)
    
    with open(output_dir / "dag.json", "w") as f:
        json.dump(dag, f, indent=2)
    
    print(f"\n📁 Output files saved to: {output_dir}")


if __name__ == "__main__":
    main()
