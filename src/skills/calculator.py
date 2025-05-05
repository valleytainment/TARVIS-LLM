#!/usr/bin/env python
# -*- coding: utf-8 -*-
import math
import logging
from langchain.tools import tool
import operator
import ast

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- Safe Evaluation Setup ---
# Define allowed operators
allowed_operators = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos
}

# Define allowed names (constants and functions)
allowed_names = {
    'pi': math.pi,
    'e': math.e,
    'sqrt': math.sqrt,
    'sin': math.sin,
    'cos': math.cos,
    'tan': math.tan,
    'log': math.log,
    'log10': math.log10,
    'abs': abs,
    'pow': pow,
    # Add more safe functions/constants as needed
}

def safe_eval_math(expr):
    """Safely evaluates a mathematical expression string."""
    try:
        node = ast.parse(expr, mode='eval').body
    except SyntaxError as e:
        raise ValueError(f"Invalid mathematical syntax: {e}")

    def _eval(node):
        if isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.Constant): # Handles numbers and potentially strings/booleans if allowed
             if isinstance(node.value, (int, float)):
                 return node.value
             else:
                 raise TypeError(f"Unsupported constant type: {type(node.value)}")
        elif isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            op = type(node.op)
            if op in allowed_operators:
                return allowed_operators[op](left, right)
            else:
                raise ValueError(f"Unsupported binary operator: {op.__name__}")
        elif isinstance(node, ast.UnaryOp):
            operand = _eval(node.operand)
            op = type(node.op)
            if op in allowed_operators:
                return allowed_operators[op](operand)
            else:
                raise ValueError(f"Unsupported unary operator: {op.__name__}")
        elif isinstance(node, ast.Name):
            if node.id in allowed_names:
                return allowed_names[node.id]
            else:
                raise NameError(f"Name 	'{node.id}	' is not allowed")
        elif isinstance(node, ast.Call):
            func_name = node.func.id
            if func_name in allowed_names and callable(allowed_names[func_name]):
                args = [_eval(arg) for arg in node.args]
                return allowed_names[func_name](*args)
            else:
                raise NameError(f"Function 	'{func_name}	' is not allowed or not callable")
        else:
            raise TypeError(f"Unsupported node type: {type(node).__name__}")

    return _eval(node)
# --- End Safe Evaluation Setup ---

@tool
def calculate(expression: str) -> str:
    """Evaluates a mathematical expression and returns the result.
    Supports basic arithmetic (+, -, *, /, **), constants (pi, e), and common functions (sqrt, sin, cos, tan, log, log10, abs, pow).
    Args:
        expression: The mathematical expression string (e.g., "2 + 2", "sqrt(16) * pi").

    Returns:
        The result of the calculation as a string, or an error message.
    """
    logging.info(f"Executing calculator skill with expression: {expression}")
    try:
        result = safe_eval_math(expression)
        result_str = f"✅ Result: {result}"
        logging.info(f"Calculation successful: {expression} = {result}")
        return result_str
    except (ValueError, TypeError, NameError, ZeroDivisionError) as e:
        error_msg = f"❌ Error calculating 	'{expression}	': {e}"
        logging.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"❌ Unexpected error calculating 	'{expression}	': {e}"
        logging.error(error_msg, exc_info=True)
        return error_msg

# Example usage (for testing purposes)
if __name__ == "__main__":
    print("Testing calculator skill...")
    expressions = [
        "2 + 2",
        "10 / 4",
        "sqrt(16) * pi",
        "2 ** 8",
        "sin(pi/2)",
        "log10(100)",
        "abs(-5.5)",
        "1 / 0", # Error case
        "import os", # Error case
        "some_variable + 1" # Error case
    ]
    for expr in expressions:
        result = calculate(expr)
        print(f"Calculation for 	'{expr}	': {result}")
    print("calculator test finished.")

