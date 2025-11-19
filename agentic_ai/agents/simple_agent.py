"""
Simple agent implementation for basic conversational AI.
"""

from langgraph.graph import StateGraph, START, END
from agentic_ai.agents.base import BaseAgent, State


class SimpleAgent(BaseAgent):
    """
    A simple conversational agent that responds to messages without tools.
    
    This is the most basic type of agent, suitable for teaching the fundamentals
    of LangGraph and agent interactions.
    """
    
    def __init__(
        self,
        llm,
        name,
        system_prompt=None,
        checkpointer=None
    ):
        super().__init__(
            llm=llm,
            name=name,
            system_prompt=system_prompt,
            checkpointer=checkpointer)

    def _build_graph(self):
        workflow = StateGraph(state_schema=State)

        workflow.add_node("llm_node", self.llm_node)
        workflow.add_edge(START, "llm_node")
        workflow.add_edge("llm_node", END)
        
        self.compile_graph(workflow)

    def llm_node(self, state: State):
        # Get current messages from state
        # System message should already be first (added in run() for new threads)
        current_messages = state["messages"]
        
        # Ensure system message is present (fallback safety check)
        # This handles edge cases where system message might not be in state
        messages_for_llm = self.add_system_message(current_messages)
        
        # Get response from LLM
        response = self.llm.invoke(messages_for_llm)
        
        # Return only the response - system message is already in state
        # MessagesState reducer will append the response to existing messages
        return {"messages": [response]}


# Example usage and testing
if __name__ == "__main__":
    from langchain.chat_models import init_chat_model
    from langgraph.checkpoint.memory import InMemorySaver
    from dotenv import load_dotenv

    load_dotenv()

    llm = init_chat_model("gemini-2.5-flash-lite", model_provider="google_genai")
    system_prompt = "You are a helpful assistant called TestBot."
    memory = InMemorySaver()
    
    agent = SimpleAgent(llm, name="TestBot", system_prompt=system_prompt, checkpointer=memory)
    
    agent.run("Hello, I am called Testuser. what is your name?")['messages'][-1].pretty_print()
    agent.run("Do you remember my name?")['messages'][-1].pretty_print()
    
    # Check conversation history
    history = agent.get_conversation_history(thread_id="default")
    for i, msg in enumerate(history):
        print(f"  {i+1}. {msg.__class__.__name__}: {msg.content}")

    print("\n" + "="*50 + "\n")
