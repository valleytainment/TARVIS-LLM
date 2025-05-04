# src/skills/system_info.py

import logging
import datetime
import psutil
from langchain.agents import Tool

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def get_current_datetime() -> str:
    """Returns the current date and time.

    Returns:
        A string representing the current date and time.
    """
    now = datetime.datetime.now()
    formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"Providing current date and time: {formatted_time}")
    return f"The current date and time is {formatted_time}"

def get_system_load() -> str:
    """Returns basic system load information (CPU and Memory usage).

    Returns:
        A string summarizing the current CPU and memory usage.
    """
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1) # Short interval for quick check
        memory_info = psutil.virtual_memory()
        memory_percent = memory_info.percent
        load_info = f"Current system load: CPU {cpu_percent}%, Memory {memory_percent}% used."
        logging.info(load_info)
        return load_info
    except Exception as e:
        error_msg = f"❌ Error getting system load: {e}"
        logging.error(error_msg, exc_info=True)
        return error_msg

# --- Tool Definition --- 
def get_tools() -> list[Tool]:
    """Returns a list of LangChain Tool objects for this skill module."""
    return [
        Tool(
            name="get_current_datetime",
            func=lambda _: get_current_datetime(), # Lambda to ignore potential agent input
            description="Gets the current date and time."
        ),
        Tool(
            name="get_system_load",
            func=lambda _: get_system_load(), # Lambda to ignore potential agent input
            description="Gets basic system load information, including CPU and memory usage percentage."
        )
    ]

# Example usage (for testing purposes)
if __name__ == "__main__":
    print("Testing system_info skill...")
    tools = get_tools()
    print(f"Loaded tools: {[tool.name for tool in tools]}")

    datetime_tool = next((t for t in tools if t.name == "get_current_datetime"), None)
    if datetime_tool:
        print(f"\nDateTime Tool Name: {datetime_tool.name}")
        print(f"DateTime Tool Description: {datetime_tool.description}")
        result = datetime_tool.func(None) # Call with dummy input
        print(f"DateTime call result: {result}")

    load_tool = next((t for t in tools if t.name == "get_system_load"), None)
    if load_tool:
        print(f"\nLoad Tool Name: {load_tool.name}")
        print(f"Load Tool Description: {load_tool.description}")
        result = load_tool.func(None) # Call with dummy input
        print(f"Load call result: {result}")

    print("\nsystem_info test finished.")

