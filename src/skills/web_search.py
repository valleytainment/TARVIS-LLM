# src/skills/web_search.py

import logging
from langchain.agents import Tool

# Note: This skill relies on the agent having access to 
# the 'info_search_web' and 'browser_navigate' tools provided by the environment.
# We define functions here that the agent can call, which *internally* would trigger
# the necessary tool calls via the agent's execution loop.
# The functions themselves don't directly call the tools, but describe what the agent should do.

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def search_web(query: str) -> str:
    """Performs a web search for the given query.
    
    This function is intended to be used as a LangChain tool. 
    The agent executing this tool is expected to use the 'info_search_web' 
    environment tool to perform the actual search.
    
    Args:
        query: The search query string.
        
    Returns:
        A string indicating the search action has been initiated or results summary.
        The actual results are expected to be processed by the agent from the 
        'info_search_web' tool's observation.
    """
    logging.info(f"Initiating web search for query: {query}")
    # The agent framework will handle calling the actual 'info_search_web' tool.
    # This function's return value is primarily for the agent's internal reasoning.
    return f"Web search initiated for '{query}'. Results will be provided by the search tool."

def browse_url(url: str) -> str:
    """Navigates the browser to the specified URL.
    
    This function is intended to be used as a LangChain tool.
    The agent executing this tool is expected to use the 'browser_navigate' 
    environment tool to perform the actual navigation.
    
    Args:
        url: The URL to navigate to.
        
    Returns:
        A string indicating the navigation action has been initiated.
    """
    logging.info(f"Initiating browser navigation to URL: {url}")
    # The agent framework will handle calling the actual 'browser_navigate' tool.
    return f"Browser navigation initiated for '{url}'. Page content will be provided by the browser tool."

# --- Tool Definition --- 
def get_tools() -> list[Tool]:
    """Returns a list of LangChain Tool objects for this skill module."""
    return [
        Tool(
            name="search_web",
            func=search_web, # The function the agent calls
            description="Performs a web search using a search engine for a given query. Returns search results including titles, links, and snippets. Use this to find information online, get current events, or find specific websites."
        ),
        # Tool(
        #     name="browse_url",
        #     func=browse_url,
        #     description="Opens a specific URL in a web browser to view its content. Use this after a web search provides a relevant link, or when a URL is explicitly mentioned. Input must be a valid URL."
        # )
        # Decided against adding browse_url as a separate tool for now.
        # The agent can decide to use the browser_navigate tool directly based on 
        # the context or search results, which might be more flexible than forcing 
        # it through this specific tool wrapper.
    ]

# Example usage (for testing purposes - cannot actually perform search here)
if __name__ == "__main__":
    print("Testing web_search skill definition...")
    tools = get_tools()
    print(f"Loaded tools: {[tool.name for tool in tools]}")
    
    search_tool = next((t for t in tools if t.name == "search_web"), None)
    if search_tool:
        print(f"\nSearch Tool Name: {search_tool.name}")
        print(f"Search Tool Description: {search_tool.description}")
        # Simulate calling the function (won't actually search)
        result = search_tool.func("latest AI news")
        print(f"Simulated search call result: {result}")
    
    # browse_tool = next((t for t in tools if t.name == "browse_url"), None)
    # if browse_tool:
    #     print(f"\nBrowse Tool Name: {browse_tool.name}")
    #     print(f"Browse Tool Description: {browse_tool.description}")
    #     # Simulate calling the function (won't actually browse)
    #     result = browse_tool.func("https://example.com")
    #     print(f"Simulated browse call result: {result}")
        
    print("\nweb_search test finished.")

