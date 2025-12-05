# Agentic Artificial Intelligence

This repository contains the course materials and a comprehensive Python package for teaching LangGraph-based AI agents. The project is designed for bachelor's/master's students learning to implement AI agents with proper software architecture.

This project is inspired by the phenomenal [Hugging Face's Agent Course](https://huggingface.co/learn/agents-course) and examples from the LangChain/LangGraph documentation.

## 🚀 Installation

### IDE - Integrated Development Environment

You are free to use any IDE that is suitable for Python development. However, we recommend using either [Cursor](https://cursor.com/) which is based on Visual Studio Code (VS Code) or [VS Code](https://code.visualstudio.com/) itself.

#### Extensions

When using VS Code or Cursor make sure to install the following extensions:

- Python (ms-python.python)
- Jupyter (ms-toolsai.jupyter)

### Environment Setup with `uv`

This project uses `uv` as the package manager, which provides fast and reliable dependency management. The project includes a `pyproject.toml` file with all required dependencies pre-configured.

#### 1. Clone and Setup

Make sure that you do have git installed by following this [install git guide](https://github.com/git-guides/install-git).

```bash
git clone https://github.com/WIMUniCologne/agentic_artificial_intelligence
```

#### 2. Install Dependencies with uv

Make sure to have `uv` installed by following this [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/).
Then open a new terminal and navigate to the project directory.

```bash
# Navigate to the project directory
cd <PATH_TO_PROJECT_DIRECTORY> # for example: /Users/user/Projects/agentic_artificial_intelligence

# Install all dependencies and create virtual environment
uv sync
```

This command will:

- Create a virtual environment in `.venv/`
- Install all dependencies specified in `pyproject.toml`
- Set up the project for development

#### 3. Activate the Environment (Optional)

We most likely won't need this as we try to always work with the `uv`command.

```bash
# Activate the virtual environment
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate     # On Windows
```

**Note**: You can run commands directly with `uv run` without activating the environment.

#### 4. Setting Up / Register the Jupyter Kernel

To ensure your Jupyter notebooks use the project's virtual environment and can access the `agentic_ai` package, you need to register it as a kernel.

```bash
# Register the project environment as a Jupyter kernel
uv run python -m ipykernel install --user --name agentic_ai --display-name "python_agentic_ai"
```

Now, when you open a notebook, you can select **"python_agentic_ai"** from the "Kernel" > "Change kernel" menu in Jupyter.

#### Environment Configuration (AI APIs)

**Get API Keys:**

- **Gemini**: [Google AI Studio](https://aistudio.google.com/app/apikey) (Recommended)
<!-- - **OpenAI**: [OpenAI Platform](https://platform.openai.com/api-keys)
- **Tavily**: [Tavily API](https://tavily.com/) (for web search)
- **OpenWeather**: [OpenWeatherMap](https://openweathermap.org/api) -->

Create a `.env` file in the project root. You can also use the `env.example` and rename it to `.env`
**Important!** For security reasons, make sure to add the `.env` file to:

1. `.gitignore` or
2. `.cursorignore` or similar if not using cursor

```env
# Required: Choose your preferred LLM provider
GOOGLE_API_KEY=your_gemini_api_key_here
# OR
OPENAI_API_KEY=your_openai_api_key_here
# OR
OLLAMA_BASE_URL=http://localhost:11434

# Optional: For enhanced tools
TAVILY_API_KEY=your_tavily_search_key
OPENWEATHER_API_KEY=your_weather_api_key
```

### Test Your Setup

Go to `exercises/unit_01` and open the notebook `unit_01.ipynb` choose the kernel as explained in `4. Setting Up the Jupyter Kernel` and try to run the tests.
Alternatively, create a notebook choose the kernel and run the following code examples:

## 📚 Usage Examples

### Simple Conversational Agent

```python
from agentic_ai.utils import setup_llm
from agentic_ai.agents import SimpleAgent

llm = setup_llm("gemini")

agent = SimpleAgent(
    llm=llm,
    name="FriendlyBot",
    system_prompt="You are a helpful and friendly assistant."
)

response = agent.run("What can you help me with?")
print(response)
```

### Agent with Tools

```python
from agentic_ai.utils import setup_llm
from agentic_ai.agents import ToolAgent
from agentic_ai.tools import CalculatorTool

llm = setup_llm("gemini")

# Create tools
calculator = CalculatorTool()
tools = [calculator.to_langchain_tool()]

# Create tool agent
agent = ToolAgent(llm=llm, tools=tools, name="ToolBot")

response = agent.run("What is 15 * 24?")
print(response)
```

### Memory-Enabled Agent

```python
from agentic_ai.utils import setup_llm
from agentic_ai.agents import SimpleAgent
from langgraph.checkpoint.memory import InMemorySaver

llm = setup_llm("gemini")
memory = InMemorySaver()

memory_agent = SimpleAgent(
    llm=llm,
    name="FriendlyBot",
    system_prompt="You are a helpful and friendly assistant.",
    checkpointer=memory
)

memory_agent.run("Hi my name is John Doe")['messages'][-1].pretty_print()

memory_agent.run("What is my name?")['messages'][-1].pretty_print()
```

## 🎓 Educational Structure

This package is designed for teaching AI agents with proper software architecture:

### **Modular Design**

- **Tools**: Each tool is a separate module (calculator, web search, etc.)
- **Agents**: Different agent types for various use cases
- **Memory**: Multiple memory systems for different needs
- **Utils**: Helper functions for setup and configuration

### **Progressive Learning**

1. **Simple Agents**: Basic conversational AI
2. **Tool Integration**: Adding capabilities with tools
3. **Memory Systems**: Maintaining context and history
4. **Advanced Patterns**: Multi-agent systems and complex workflows

### **Best Practices**

- Clean separation of concerns
- Configurable components
- Comprehensive error handling
- Extensive documentation and examples

## 📓 Course Exercises

The `exercises/` directory contains Jupyter notebooks for each course unit:

- **Unit 0**: Project Setup & Python Basics
- **Unit 1**: Verifying the Setup & Introduction
- **Unit 2**: First LLM Calls
  ...

Further units are pushed throughout the course.

### Running the Exercises

Option 1 (preferred)
Having the Jupyter extension installed, just open the `.ipynb` file of the specific exercise and use the jupyter kernel we registered for this project.

Option 2 (alternative)
Having Jupyter installed on your machine, start Jupyter to work on exercises using uv:

```bash
uv run jupyter notebook exercises
```

## 🛠️ Development

### Running Examples

```bash
# Simple agent example
uv run python examples/simple_agent_example.py

# Tool agent example
uv run python examples/tool_agent_example.py

# Memory system example
uv run python examples/memory_example.py
```

### Running with uv

Since the project uses `uv`, you can run any Python command with:

```bash
# Run any Python script
uv run python your_script.py

# Install additional dependencies (if needed)
uv add package_name

# Start Jupyter notebook (we usually do not need this)
uv run jupyter notebook
```

### Testing

```bash
# Run tests (when available)
uv run pytest

# Run examples as tests
uv run python -m examples.simple_agent_example
```

## 📖 Documentation

- **API Documentation**: See docstrings in each module
- **Examples**: Check the `examples/` directory
- **Course Materials**: Jupyter notebooks in `exercises/`

## 🤝 Contributing

This is an educational project. Students can:

- Add new tools to the `tools/` directory
- Implement custom agents in `agents/`
- Create new memory systems in `memory/`
- Add utilities and helpers in `utils/`

## 📄 License

MIT License - see LICENSE file for details.

## 🆘 Troubleshooting

**Common Issues:**

1. **API Key Errors**: Make sure your `.env` file is properly configured
2. **Import Errors**: Ensure the package is installed and the import path is correct
3. **LLM Timeouts**: Check your internet connection and API quotas
4. **Tool Failures**: Verify that optional dependencies are installed

**Getting Help:**

- Check the example files in `examples/`
- Review the course notebooks in `exercises`
- Look at the docstrings in the source code
