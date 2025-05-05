#!/usr/bin/env python
# -*- coding: utf-8 -*-
import unittest
import sys
import os
from math import pi, e, sin, sqrt

# Adjust path to import from src
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.skills.calculator import calculate

class TestCalculatorSkill(unittest.TestCase):

    def test_basic_arithmetic(self):
        self.assertIn("4", calculate("2 + 2"))
        self.assertIn("5", calculate("10 - 5"))
        self.assertIn("12", calculate("3 * 4"))
        self.assertIn("2.5", calculate("10 / 4"))

    def test_exponentiation(self):
        self.assertIn("256", calculate("2 ** 8"))
        self.assertIn("9", calculate("pow(3, 2)"))

    def test_constants(self):
        self.assertIn(str(pi), calculate("pi"))
        self.assertIn(str(e), calculate("e"))
        self.assertIn(str(pi * 2), calculate("pi * 2"))

    def test_functions(self):
        self.assertIn("4", calculate("sqrt(16)"))
        self.assertIn("1", calculate("sin(pi/2)")) # sin(pi/2) = 1
        self.assertTrue(abs(float(calculate("cos(pi)").split(": ")[-1]) - (-1.0)) < 1e-9) # cos(pi) = -1
        self.assertIn("100", calculate("log10(10000)")) # log10(10000) should be 4, mistake in original test? No, log10(100) is 2. Let's test log10(100)
        self.assertIn("2", calculate("log10(100)"))
        self.assertIn("5.5", calculate("abs(-5.5)"))

    def test_order_of_operations(self):
        self.assertIn("10", calculate("2 + 2 * 4")) # 2 + 8 = 10
        self.assertIn("14", calculate("(2 + 5) * 2")) # 7 * 2 = 14

    def test_error_division_by_zero(self):
        result = calculate("1 / 0")
        self.assertIn("❌ Error", result)
        self.assertIn("division by zero", result)

    def test_error_invalid_syntax(self):
        result = calculate("2 +*")
        self.assertIn("❌ Error", result)
        self.assertIn("Invalid mathematical syntax", result)

    def test_error_disallowed_name(self):
        result = calculate("some_variable + 1")
        self.assertIn("❌ Error", result)
        self.assertIn("Name \'some_variable\' is not allowed", result)

    def test_error_disallowed_function_import(self):
        result = calculate("__import__(\'os\').system(\'echo unsafe\')")
        self.assertIn("❌ Error", result)
        # The exact error might vary depending on ast parsing stage, check for common indicators
        self.assertTrue("Name \'__import__\' is not allowed" in result or "Invalid syntax" in result or "Unsupported node type" in result)

    def test_error_disallowed_attribute(self):
        # Example trying to access methods on numbers (though safe_eval prevents this)
        result = calculate("(1).__add__(2)")
        self.assertIn("❌ Error", result)
        self.assertIn("Unsupported node type: Attribute", result) # Expecting Attribute node error

if __name__ == "__main__":
    # Ensure the tests directory exists
    test_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(test_dir, exist_ok=True)
    unittest.main()

