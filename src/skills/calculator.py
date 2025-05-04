# src/skills/calculator.py

import logging
import ast
import operator as op
from langchain.agents import Tool

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Supported operators
allowed_operators = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.USub: op.neg
}

# Allowed node types (numbers and binary/unary operations)
allowed_node_types = {
    ast.Expression, 
    ast.Constant, # Handles numbers in Python 3.9+
    ast.Num,      # Handles numbers in Python < 3.8 (for broader compatibility)
    ast.BinOp,
    ast.UnaryOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.USub
}

def _eval_expr_node(node):
    """Recursively evaluates an AST node, ensuring only allowed operations are performed."""
    if not isinstance(node, tuple(allowed_node_types)):
        raise TypeError(f"Unsupported AST node type: {type(node).__name__}")

    if isinstance(node, ast.Expression):
        return _eval_expr_node(node.body)
    elif isinstance(node, (ast.Constant, ast.Num)): # Constant for Py 3.9+, Num for < 3.8
        if isinstance(node.value, (int, float)):
            return node.value
        else:
            raise TypeError(f"Unsupported constant type: {type(node.value).__name__}")
    elif isinstance(node, ast.BinOp):
        left_val = _eval_expr_node(node.left)
        right_val = _eval_expr_node(node.right)
        operator_func = allowed_operators.get(type(node.op))
        if operator_func:
            return operator_func(left_val, right_val)
        else:
            raise TypeError(f"Unsupported binary operator: {type(node.op).__name__}")
    elif isinstance(node, ast.UnaryOp):
        operand_val = _eval_expr_node(node.operand)
        operator_func = allowed_operators.get(type(node.op))
        if operator_func:
            return operator_func(operand_val)
        else:
            raise TypeError(f"Unsupported unary operator: {type(node.op).__name__}")
    else:
        # This case should not be reached if the initial type check is correct
        raise TypeError(f"Unhandled node type during evaluation: {type(node).__name__}")

def calculate(expression: str) -> str:
    """Safely evaluates a mathematical expression.

    Args:
        expression: The mathematical expression string (e.g., "2 + 2 * 5", "(10 - 4) / 2").

    Returns:
        The result of the calculation as a string, or an error message.
    """
    logging.info(f"Attempting to calculate expression: {expression}")
    try:
        # Parse the expression into an Abstract Syntax Tree (AST)
        node = ast.parse(expression, mode=\'eval\')
        
        # Validate all nodes in the tree before evaluation
        for sub_node in ast.walk(node):
            if not isinstance(sub_node, tuple(allowed_node_types)):
                 raise TypeError(f"Disallowed node type found: {type(sub_node).__name__}")
                 
        # Evaluate the expression using the safe recursive evaluator
        result = _eval_expr_node(node)
        logging.info(f"Calculation result for \"{expression}\" = {result}")
        return f"The result of {expression} is {result}"
    except (SyntaxError, TypeError, ValueError, ZeroDivisionError) as e:
        error_msg = f"❌ Error calculating \"{expression}\": {e}"
        logging.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"❌ Unexpected error calculating \"{expression}\": {e}"
        logging.error(error_msg, exc_info=True)
        return error_msg

# --- Tool Definition --- 
def get_tool() -> Tool:
    """Returns the LangChain Tool object for this skill module."""
    return Tool(
        name="calculator",
        func=calculate,
        description="Evaluates mathematical expressions. Use this for calculations involving numbers and basic arithmetic operations (+, -, *, /, **). Input should be the mathematical expression string (e.g., \"5 * (3 + 1)\")."
    )

# Example usage (for testing purposes)
if __name__ == "__main__":
    print("Testing calculator skill...")
    tool = get_tool()
    print(f"Tool Name: {tool.name}")
    print(f"Tool Description: {tool.description}")

    expressions = [
        "2 + 2",
        "10 * (5 - 3)",
        "100 / 4",
        "2 ** 8",
        "-5 + 10",
        "1 / 0", # Zero division
        "import os", # Unsafe
        "print(\'hello\')", # Unsafe
        "a + 5" # Undefined variable (should raise TypeError during eval)
    ]

    for expr in expressions:
        result = calculate(expr)
        print(f"Calculation for \"{expr}\": {result}")

    print("\ncalculator test finished.")

