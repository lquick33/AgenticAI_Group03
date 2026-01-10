"""
Setup utilities for agentic AI agents.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict
from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel

from agentic_ai.utils.paths import ENV


def setup_logging(
    level: str = "INFO", 
    log_file: Optional[str] = None,
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    Set up logging for the application.
    
    Args:
        level: Logging level ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        log_file: Optional file to write logs to
        format_string: Custom format string for log messages
        
    Returns:
        Configured logger instance
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Default format
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Configure logging
    logging.basicConfig(
        level=numeric_level,
        format=format_string,
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Create logger
    logger = logging.getLogger("agentic_ai")
    
    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)
        file_formatter = logging.Formatter(format_string)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def load_env_vars(env_file: Path = ENV) -> Dict[str, str]:
    """
    Load environment variables from a .env file.
    
    Args:
        env_file: Path to the .env file
        
    Returns:
        Dictionary of loaded environment variables
    """
    env_path = Path(env_file)
    
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded environment variables from {env_path}")
    else:
        print(f"Warning: Environment file {env_path} not found")
    
    # Return relevant environment variables
    env_vars = []
    relevant_keys = [
        "GOOGLE_API_KEY",
        "OPENAI_API_KEY", 
        "TAVILY_API_KEY",
        "OPENWEATHER_API_KEY",
        "OLLAMA_BASE_URL"
    ]
    
    for key in relevant_keys:
        value = os.getenv(key)
        if value:
            env_vars.append(key)
    
    print(f"Loaded {len(env_vars)} environment variables")


def setup_llm(
    provider: str = "gemini",
    model: str = "gemini-2.5-flash-lite",
    temperature: float = 0.7,
    **kwargs
) -> BaseChatModel:
    """
    Set up a language model for use with agents.
    
    Args:
        provider: LLM provider ("gemini", "openai", "ollama")
        model: Specific model name
        temperature: Temperature for response generation
        **kwargs: Additional arguments for the LLM
        
    Returns:
        Configured language model instance
    """
    load_env_vars()
    if provider.lower() == "gemini":
        return setup_gemini_llm(model, temperature, **kwargs)
    elif provider.lower() == "openai":
        return setup_openai_llm(model, temperature, **kwargs)
    elif provider.lower() == "ollama":
        return setup_ollama_llm(model, temperature, **kwargs)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


def setup_gemini_llm(
    model: str = None,
    temperature: float = 0.7,
    **kwargs
) -> BaseChatModel:
    """Set up Google Gemini LLM."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")
        
        default_model = model or "gemini-2.5-flash"
        
        return ChatGoogleGenerativeAI(
            model=default_model,
            temperature=temperature,
            google_api_key=api_key,
            **kwargs
        )
        
    except ImportError:
        raise ImportError("langchain-google-genai not installed. Run: pip install langchain-google-genai")


def setup_openai_llm(
    model: str = None,
    temperature: float = 0.7,
    **kwargs
) -> BaseChatModel:
    """Set up OpenAI LLM."""
    try:
        from langchain_openai import ChatOpenAI
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        default_model = model or "gpt-3.5-turbo"
        
        return ChatOpenAI(
            model=default_model,
            temperature=temperature,
            openai_api_key=api_key,
            **kwargs
        )
        
    except ImportError:
        raise ImportError("langchain-openai not installed. Run: pip install langchain-openai")


def setup_ollama_llm(
    model: str = None,
    temperature: float = 0.7,
    base_url: str = None,
    **kwargs
) -> BaseChatModel:
    """Set up Ollama LLM."""
    try:
        from langchain_community.llms import Ollama
        from langchain_community.chat_models import ChatOllama
        
        default_model = model or "llama3"
        default_base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        
        # Use ChatOllama for chat interface
        return ChatOllama(
            model=default_model,
            temperature=temperature,
            base_url=default_base_url,
            **kwargs
        )
        
    except ImportError:
        raise ImportError("langchain-community not installed. Run: pip install langchain-community")


def create_project_structure(base_path: str = ".") -> None:
    """
    Create the recommended project structure for agentic AI projects.
    
    Args:
        base_path: Base path where to create the structure
    """
    base = Path(base_path)
    
    # Create directories
    directories = [
        "agents",
        "tools", 
        "memory",
        "configs",
        "data",
        "notebooks",
        "tests",
        "logs"
    ]
    
    for directory in directories:
        dir_path = base / directory
        dir_path.mkdir(exist_ok=True)
        
        # Create __init__.py for Python packages
        if directory in ["agents", "tools", "memory"]:
            init_file = dir_path / "__init__.py"
            if not init_file.exists():
                init_file.write_text("# Package initialization\n")
    
    # Create basic files
    files = {
        ".env.example": """# Example environment variables
GOOGLE_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
OPENWEATHER_API_KEY=your_openweather_api_key_here
OLLAMA_BASE_URL=http://localhost:11434
""",
        "requirements.txt": """langchain
langchain-community
langchain-google-genai
langgraph
google-generativeai
ollama
jupyter
python-dotenv
requests
""",
        "README.md": """# Agentic AI Project

This project uses the agentic_ai package to build and experiment with AI agents.

## Setup

1. Copy `.env.example` to `.env` and fill in your API keys
2. Install dependencies: `pip install -r requirements.txt`
3. Start building your agents!

## Structure

- `agents/` - Custom agent implementations
- `tools/` - Custom tools for agents
- `memory/` - Memory systems and configurations
- `configs/` - Configuration files
- `notebooks/` - Jupyter notebooks for experimentation
- `data/` - Data files
- `tests/` - Test files
- `logs/` - Log files
"""
    }
    
    for filename, content in files.items():
        file_path = base / filename
        if not file_path.exists():
            file_path.write_text(content)
    
    print(f"Project structure created at {base.absolute()}")


# Example usage
if __name__ == "__main__":
    # Set up logging
    logger = setup_logging(level="INFO")
    logger.info("Logging setup complete")
    
    # Load environment variables
    env_vars = load_env_vars()
    logger.info(f"Loaded {len(env_vars)} environment variables")
    
    # Try to set up an LLM (will fail without API keys)
    try:
        llm = setup_llm("gemini")
        logger.info("LLM setup successful")
    except Exception as e:
        logger.warning(f"LLM setup failed: {e}")
    
    print("Setup utilities test completed")
