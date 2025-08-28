"""
Workflow DSL Compilers Package

This package contains the two main compilers for the workflow automation engine:

1. Template Materializer (T→E): Converts high-level Template JSON with placeholders 
   into fully-resolved Executable JSON.

2. Graph Lowerer (E→D): Lowers concrete Executable JSON into executor/UI-ready 
   DAG JSON (nodes + edges + routing).
"""

from .template_materializer import TemplateMaterializer
from .graph_lowerer import GraphLowerer

__all__ = [
    "TemplateMaterializer",
    "GraphLowerer"
]
