#!/usr/bin/env python
# -*- coding: utf-8 -*-
import unittest
import datetime
import re # For regex matching in system load

# Import the functions to be tested
# Assuming the script is run from the project root (e.g., using python -m unittest discover)
from src.skills.system_info import get_current_datetime, get_system_load

class TestSystemInfoSkill(unittest.TestCase):

    def test_get_current_datetime(self):
        """Test the get_current_datetime function."""
        # Call the function (with dummy input)
        datetime_str = get_current_datetime("dummy")
        
        # Check if it returns a non-empty string
        self.assertIsInstance(datetime_str, str)
        self.assertTrue(len(datetime_str) > 0)
        
        # Attempt to parse the date part to check format validity (basic check)
        # Example format: "Current date and time is: YYYY-MM-DD HH:MM:SS"
        try:
            # Extract the date/time part after the prefix
            match = re.search(r": (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", datetime_str)
            self.assertIsNotNone(match, "Datetime string format is unexpected.")
            if match:
                datetime_part = match.group(1)
                datetime.datetime.strptime(datetime_part, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            self.fail("get_current_datetime returned a string that could not be parsed as YYYY-MM-DD HH:MM:SS")
        except Exception as e:
            self.fail(f"An unexpected error occurred during datetime parsing: {e}")

    def test_get_system_load(self):
        """Test the get_system_load function."""
        # Call the function (with dummy input)
        load_info = get_system_load("dummy")
        
        # Check if it returns a non-empty string
        self.assertIsInstance(load_info, str)
        self.assertTrue(len(load_info) > 0)
        
        # Check for expected keywords/patterns
        self.assertIn("CPU Usage:", load_info)
        self.assertIn("%", load_info) # Expect percentage sign
        self.assertIn("Memory Usage:", load_info)
        self.assertIn("Load Average:", load_info)
        
        # Check if load averages look like numbers (e.g., using regex)
        # Example: "Load Average: 0.12 (1 min), 0.15 (5 min), 0.10 (15 min)"
        load_avg_match = re.search(r"Load Average: (\d+\.\d+) \(1 min\), (\d+\.\d+) \(5 min\), (\d+\.\d+) \(15 min\)", load_info)
        self.assertIsNotNone(load_avg_match, "Load average format is unexpected.")

if __name__ == "__main__":
    unittest.main()

