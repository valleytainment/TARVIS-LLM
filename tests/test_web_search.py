#!/usr/bin/env python
# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch, MagicMock

# Import the function to be tested
from src.skills.web_search import web_search

class TestWebSearchSkill(unittest.TestCase):

    @patch("src.skills.web_search.info_search_web") # Mock the search tool
    @patch("src.skills.web_search.browser_navigate") # Mock the browser navigate tool
    @patch("src.skills.web_search.browser_scroll_down") # Mock the browser scroll tool
    @patch("src.skills.web_search.browser_view") # Mock the browser view tool
    def test_web_search_success(self, mock_browser_view, mock_browser_scroll, mock_browser_navigate, mock_info_search):
        """Test the web_search function with mocked successful search and browse."""
        query = "test query about AI"
        
        # Configure mock search results
        mock_search_results = {
            "search_results": [
                {"url": "http://example.com/ai1", "title": "AI Page 1", "snippet": "Snippet 1..."},
                {"url": "http://example.com/ai2", "title": "AI Page 2", "snippet": "Snippet 2..."}
            ]
        }
        mock_info_search.return_value = mock_search_results
        
        # Configure mock browser view results (after navigate and scroll)
        # Simulate finding content after scrolling
        mock_browser_view.side_effect = [
            {"markdown": "Initial view..."}, # After navigate
            {"markdown": "Scrolled view with AI content..."} # After scroll
        ]

        # Call the function
        result = web_search(query)

        # Assertions
        mock_info_search.assert_called_once_with(query=query)
        # Check if browser was navigated to the first URL
        mock_browser_navigate.assert_called_once_with(url="http://example.com/ai1")
        # Check if scrolling occurred (at least once)
        mock_browser_scroll.assert_called()
        # Check if browser_view was called (at least twice: after nav, after scroll)
        self.assertGreaterEqual(mock_browser_view.call_count, 2)
        
        # Check the returned result (should contain content from the scrolled view)
        self.assertIsInstance(result, str)
        self.assertIn("Scrolled view with AI content...", result)
        self.assertIn("http://example.com/ai1", result) # Ensure source URL is included

    @patch("src.skills.web_search.info_search_web")
    def test_web_search_no_results(self, mock_info_search):
        """Test web_search when the search yields no results."""
        query = "unfindable query xyz"
        mock_info_search.return_value = {"search_results": []}

        result = web_search(query)

        mock_info_search.assert_called_once_with(query=query)
        self.assertIn("No relevant web pages found", result)

    @patch("src.skills.web_search.info_search_web")
    @patch("src.skills.web_search.browser_navigate", side_effect=Exception("Browser navigation failed"))
    def test_web_search_browse_fail(self, mock_browser_navigate, mock_info_search):
        """Test web_search when browsing the first result fails."""
        query = "query leading to browse failure"
        mock_search_results = {
            "search_results": [
                {"url": "http://fail.com", "title": "Fail Page", "snippet": "Snippet..."}
            ]
        }
        mock_info_search.return_value = mock_search_results

        result = web_search(query)

        mock_info_search.assert_called_once_with(query=query)
        mock_browser_navigate.assert_called_once_with(url="http://fail.com")
        self.assertIn("Error accessing URL http://fail.com: Browser navigation failed", result)

if __name__ == "__main__":
    unittest.main()

