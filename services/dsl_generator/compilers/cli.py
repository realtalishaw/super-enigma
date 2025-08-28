"""
CLI interface for the workflow DSL compilers.

Usage:
    weave compile template --in t.json --out exec.json
    weave compile dag --in exec.json --out dag.json --layout dagre
"""

import argparse
import json
import sys
import logging
from pathlib import Path
from typing import Dict, Any

from template_materializer import TemplateMaterializer
from graph_lowerer import GraphLowerer

logger = logging.getLogger(__name__)


def load_json_file(file_path: str) -> Dict[str, Any]:
    """Load and parse a JSON file"""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {file_path}: {e}")
        sys.exit(1)


def save_json_file(data: Dict[str, Any], file_path: str):
    """Save data to a JSON file"""
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Output saved to: {file_path}")
    except Exception as e:
        logger.error(f"Failed to save output to {file_path}: {e}")
        sys.exit(1)


def compile_template(args):
    """Compile template to executable"""
    logger.info("Compiling template to executable...")
    
    # Load template
    template_doc = load_json_file(args.input)
    
    # Load context (catalog, user, connections, etc.)
    ctx = {}
    
    if args.catalog:
        ctx["catalog"] = load_json_file(args.catalog)
    
    if args.user:
        ctx["user"] = load_json_file(args.user)
    
    if args.connections:
        ctx["connections"] = load_json_file(args.connections)
    
    if args.answers:
        ctx["answers"] = load_json_file(args.answers)
    
    if args.defaults:
        ctx["defaults"] = load_json_file(args.defaults)
    
    # Compile
    materializer = TemplateMaterializer()
    result = materializer.compile(template_doc, ctx)
    
    if result["executable_doc"] is None:
        logger.error("Template compilation failed:")
        for error in result["report"].errors:
            logger.error(f"  {error['path']}: {error['message']}")
        sys.exit(1)
    
    # Save output
    save_json_file(result["executable_doc"], args.output)
    
    # Show report
    if result["report"].warnings:
        logger.warning("Warnings:")
        for warning in result["report"].warnings:
            logger.warning(f"  {warning['path']}: {warning['message']}")
    
    if result["report"].repairs:
        logger.info("Auto-repairs applied:")
        for repair in result["report"].repairs:
            logger.info(f"  {repair['path']}: {repair['reason']}")
    
    logger.info("Template compilation completed successfully!")


def compile_dag(args):
    """Compile executable to DAG"""
    logger.info("Compiling executable to DAG...")
    
    # Load executable
    executable_doc = load_json_file(args.input)
    
    # Load context
    ctx = {}
    
    if args.catalog:
        ctx["catalog"] = load_json_file(args.catalog)
    
    ctx["layout"] = args.layout
    ctx["uiDefaults"] = {}
    
    if args.ui_defaults:
        ctx["uiDefaults"] = load_json_file(args.ui_defaults)
    
    # Compile
    lowerer = GraphLowerer()
    result = lowerer.compile(executable_doc, ctx)
    
    if result["dag_doc"] is None:
        logger.error("DAG compilation failed:")
        for error in result["report"].errors:
            logger.error(f"  {error['path']}: {error['message']}")
        sys.exit(1)
    
    # Save output
    save_json_file(result["dag_doc"], args.output)
    
    # Show report
    if result["report"].warnings:
        logger.warning("Warnings:")
        for warning in result["report"].warnings:
            logger.warning(f"  {warning['path']}: {warning['message']}")
    
    if result["report"].hints:
        logger.info("Hints:")
        for hint in result["report"].hints:
            logger.info(f"  {hint}")
    
    logger.info("DAG compilation completed successfully!")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Workflow DSL Compiler CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compile template to executable
  weave compile template --in template.json --out executable.json --catalog catalog.json
  
  # Compile executable to DAG
  weave compile dag --in executable.json --out dag.json --layout dagre
  
  # Full compilation pipeline
  weave compile template --in template.json --out executable.json --catalog catalog.json
  weave compile dag --in executable.json --out dag.json --layout dagre
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Compilation command")
    
    # Template materializer command
    template_parser = subparsers.add_parser(
        "template",
        help="Compile Template JSON to Executable JSON (T→E)"
    )
    template_parser.add_argument("--in", dest="input", required=True, help="Input template file")
    template_parser.add_argument("--out", dest="output", required=True, help="Output executable file")
    template_parser.add_argument("--catalog", help="Catalog file (providers, actions, triggers)")
    template_parser.add_argument("--user", help="User context file")
    template_parser.add_argument("--connections", help="Connections file")
    template_parser.add_argument("--answers", help="User answers file")
    template_parser.add_argument("--defaults", help="Default policies file")
    template_parser.set_defaults(func=compile_template)
    
    # Graph lowerer command
    dag_parser = subparsers.add_parser(
        "dag",
        help="Compile Executable JSON to DAG JSON (E→D)"
    )
    dag_parser.add_argument("--in", dest="input", required=True, help="Input executable file")
    dag_parser.add_argument("--out", dest="output", required=True, help="Output DAG file")
    dag_parser.add_argument("--catalog", help="Catalog file (for type hints)")
    dag_parser.add_argument("--layout", choices=["dagre", "elk", "manual"], default="dagre", help="Layout algorithm")
    dag_parser.add_argument("--ui-defaults", help="UI defaults file")
    dag_parser.set_defaults(func=compile_dag)
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Execute command
    try:
        args.func(args)
    except KeyboardInterrupt:
        logger.info("Compilation interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
