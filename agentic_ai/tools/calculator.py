"""
Calculator tool for basic mathematical operations.
"""

import ast
import operator
from typing import Union
from langchain_core.tools import Tool
from langchain_core.tools import BaseTool


class CalculatorTool(BaseTool):
    """
    A safe calculator tool that can evaluate basic mathematical expressions.
    
    This tool provides a safe way to perform calculations by using Python's
    ast module to parse and evaluate mathematical expressions.
    """
    
    # Supported operations
    _operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
    }
    
    def __init__(self):
        super().__init__(
            name="calculator",
            description="""
            Perform basic mathematical calculations. Supports +, -, *, /, ** (power), and parentheses. Example: '2 + 3 * 4'
            
            Args:
                expression: Mathematical expression as a string
                
            Returns:
                Result of the calculation or error message
            """
        )
    
    def _run(self, expression: str) -> Union[float, int, str]:
        """
        Evaluate a mathematical expression safely.
        
        Args:
            expression: Mathematical expression as a string
            
        Returns:
            Result of the calculation or error message
        """
        try:
            # Parse the expression into an AST
            node = ast.parse(expression, mode='eval')
            return self._eval_node(node.body)
        except Exception as e:
            return f"Error: {str(e)}"
    
    def _eval_node(self, node):
        """Recursively evaluate AST nodes."""
        if isinstance(node, ast.Constant):  # Numbers
            return node.value
        elif isinstance(node, ast.BinOp):  # Binary operations
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op = self._operators.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operation: {type(node.op).__name__}")
            return op(left, right)
        elif isinstance(node, ast.UnaryOp):  # Unary operations (like negative numbers)
            operand = self._eval_node(node.operand)
            op = self._operators.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operation: {type(node.op).__name__}")
            return op(operand)
        else:
            raise ValueError(f"Unsupported node type: {type(node).__name__}")
    
    def to_langchain_tool(self) -> Tool:
        """Convert to LangChain tool."""
        return Tool(
            name=self.name,
            description=self.description,
            func=self.run
        )


# Example usage and testing
if __name__ == "__main__":
    calc = CalculatorTool()
    
    # Test cases
    test_expressions = [
        "2 + 3",
        "10 - 4",
        "5 * 6",
        "15 / 3",
        "2 ** 3",
        "(2 + 3) * 4",
        "10 + 5 * 2",
        "-5 + 3",
        "invalid expression"
    ]

    for expr in test_expressions:
        result = calc._run(expr)
        print(f"{expr} = {result}")
