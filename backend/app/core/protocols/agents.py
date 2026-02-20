"""
Agent Protocol definitions.

Defines the contract that all study agents must satisfy,
enabling the AgentFactory / Registry pattern (OCP compliance).
"""

from typing import Protocol, List, Dict, Any, AsyncGenerator, runtime_checkable


@runtime_checkable
class StudyAgent(Protocol):
    """
    Contract: any agent that can participate in a study session.

    Implementors: TutorAgent, QuickChatAgent, FlashcardGeneratorAgent, QuizGeneratorAgent

    This Protocol enables the Open/Closed Principle:
    new agents can be added by implementing this interface
    without modifying ChatService or endpoints.
    """

    name: str

    async def astream(
        self,
        state: Dict[str, Any],
        config: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream agent responses asynchronously.

        Preconditions:
            - state contains 'messages' key with list of BaseMessage
            - config contains 'configurable' with session metadata

        Postconditions:
            - Yields dicts containing agent output chunks
            - Stream always terminates (no infinite loops)
        """
        ...

    def get_tools(self) -> List[Any]:
        """
        Return the list of tools available to this agent.

        Postconditions:
            - Returns a list of LangChain Tool-compatible objects
        """
        ...
