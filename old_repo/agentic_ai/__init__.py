"""
Agentic AI - A Python package for teaching LangGraph-based AI agents.

This package provides modular components for building and teaching AI agents
using LangGraph, including tools, agents, memory systems, and utilities.
"""

import warnings
import os

# Suppress transformers warning about missing PyTorch/TensorFlow/Flax
# We don't need these for our LangChain/LangGraph use case
os.environ['TRANSFORMERS_NO_ADVISORY_WARNINGS'] = 'true'
warnings.filterwarnings('ignore', message='.*PyTorch, TensorFlow.*')

__version__ = "0.1.0"
__author__ = "Tim Alvaro Ockenga"

# Import main components for easy access
from .agents import BaseAgent, SimpleAgent, ToolAgent
from .utils import setup_logging

__all__ = [
    "BaseAgent",
    "SimpleAgent", 
    "ToolAgent",
    "setup_logging",
    "load_env_vars"
]
