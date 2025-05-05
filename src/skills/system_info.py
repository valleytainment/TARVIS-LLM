#!/usr/bin/env python
# -*- coding: utf-8 -*-
import datetime
import logging
import psutil # For system load
from langchain.tools import tool

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

@tool
def get_current_datetime(dummy_input: str = "") -> str:
    """Returns the current date and time. Ignores any input provided."""
    # The dummy_input parameter is added to conform to the single-string input requirement of some agents.
    logging.info(f"Executing get_current_datetime skill. (Input ignored: {dummy_input[:50]}...)")
    try:
        now = datetime.datetime.now()
        datetime_str = now.isoformat()
        logging.info(f"Current datetime: {datetime_str}")
        return f"✅ Current date and time: {datetime_str}"
    except Exception as e:
        error_msg = f"❌ Error getting current date and time: {e}"
        logging.error(error_msg, exc_info=True)
        return error_msg

@tool
def get_system_load(dummy_input: str = "") -> str:
    """Returns basic system load information (CPU and Memory usage). Ignores any input provided."""
    # The dummy_input parameter is added to conform to the single-string input requirement of some agents.
    logging.info(f"Executing get_system_load skill. (Input ignored: {dummy_input[:50]}...)")
    try:
        cpu_percent = psutil.cpu_percent(interval=1) # Get CPU usage over 1 second
        memory_info = psutil.virtual_memory()
        memory_percent = memory_info.percent
        load_str = f"CPU Usage: {cpu_percent}%, Memory Usage: {memory_percent}%"
        logging.info(f"System load: {load_str}")
        return f"✅ Current system load: {load_str}"
    except Exception as e:
        error_msg = f"❌ Error getting system load: {e}"
        logging.error(error_msg, exc_info=True)
        return error_msg

# Example usage (for testing purposes)
if __name__ == "__main__":
    print("Testing system_info skill...")
    # Pass dummy input for consistency
    datetime_result = get_current_datetime("test")
    print(f"Get datetime result: {datetime_result}")
    load_result = get_system_load("test")
    print(f"Get system load result: {load_result}")
    print("system_info test finished.")

