import pytest
from unittest.mock import patch, MagicMock
import os
# Import AgentType for assertion
from langchain.agents import AgentType

# Import the class to be tested
from src.core.orchestrator import Orchestrator

# Mock the LLM and tools before importing the orchestrator
# Mock LLM Loader and LLM
mock_llm = MagicMock()
mock_llm.invoke.return_value = "Mock LLM Response"

mock_llm_loader_instance = MagicMock()
mock_llm_loader_instance.load.return_value = mock_llm

# Mock Skills (Tools)
mock_open_app = MagicMock(name="open_app_tool", description="Opens applications")
mock_open_app.run.return_value = "Mock App Opened"

mock_copy_file = MagicMock(name="copy_file_tool", description="Copies files")
mock_copy_file.run.return_value = "Mock File Copied"

mock_delete_file = MagicMock(name="delete_file_tool", description="Deletes files")
mock_delete_file.run.return_value = "Mock File Deleted"

mock_clipboard_write = MagicMock(name="clipboard_write_tool", description="Writes to clipboard")
mock_clipboard_write.run.return_value = "Mock Clipboard Written"

mock_clipboard_read = MagicMock(name="clipboard_read_tool", description="Reads from clipboard")
mock_clipboard_read.run.return_value = "Mock Clipboard Content"

# Mock Agent Executor instance (returned by initialize_agent)
mock_agent_executor_instance = MagicMock()
mock_agent_executor_instance.invoke.return_value = {"output": "Mock Agent Output"}

# Patch the dependencies where they are looked up (in orchestrator.py)
@patch("src.core.orchestrator.LLMLoader", return_value=mock_llm_loader_instance) # Patched LLMLoader class
@patch("src.core.orchestrator.Orchestrator._load_tools", return_value=[
    mock_open_app,
    mock_copy_file,
    mock_delete_file,
    mock_clipboard_write,
    mock_clipboard_read
]) # Patched the instance method _load_tools
@patch("src.core.orchestrator.initialize_agent", return_value=mock_agent_executor_instance) # Patched initialize_agent function
@patch("src.core.orchestrator.ConversationBufferMemory") # Mock memory
def test_orchestrator_initialization(
    mock_memory, mock_initialize_agent, mock_load_tools_method, mock_llm_loader_class
):
    """Test if the Orchestrator initializes correctly."""
    orchestrator = Orchestrator()

    # Assertions
    mock_llm_loader_class.assert_called_once()
    mock_llm_loader_instance.load.assert_called_once()
    mock_load_tools_method.assert_called_once()
    mock_memory.assert_called_once_with(memory_key="chat_history", return_messages=True)
    # Use the actual AgentType enum in the assertion
    mock_initialize_agent.assert_called_once_with(
        mock_load_tools_method.return_value, # tools
        mock_llm, # llm
        agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION, # Use Enum
        memory=mock_memory.return_value,
        verbose=True,
        handle_parsing_errors=True
    )
    assert orchestrator.agent == mock_agent_executor_instance
    assert orchestrator.llm == mock_llm
    assert orchestrator.tools == mock_load_tools_method.return_value
    assert orchestrator.memory == mock_memory.return_value

@patch("src.core.orchestrator.LLMLoader", return_value=mock_llm_loader_instance)
@patch("src.core.orchestrator.Orchestrator._load_tools", return_value=[
    mock_open_app,
    mock_copy_file,
    mock_delete_file,
    mock_clipboard_write,
    mock_clipboard_read
])
@patch("src.core.orchestrator.initialize_agent", return_value=mock_agent_executor_instance)
@patch("src.core.orchestrator.ConversationBufferMemory")
def test_orchestrator_process_input(
    mock_memory, mock_initialize_agent, mock_load_tools_method, mock_llm_loader_class
):
    """Test if the Orchestrator processes input correctly."""
    # Reset invoke mock for this specific test
    mock_agent_executor_instance.invoke.reset_mock()
    mock_agent_executor_instance.invoke.return_value = {"output": "Mock Agent Output for Process"}

    orchestrator = Orchestrator()

    # Test processing input
    user_input = "Open notepad"
    # Use route_command as per the implementation
    response = orchestrator.route_command(user_input)

    # Assertions
    mock_agent_executor_instance.invoke.assert_called_once_with({"input": user_input})
    assert response == "Mock Agent Output for Process"

@patch("src.core.orchestrator.LLMLoader") # Mock the class
@patch("src.core.orchestrator.Orchestrator._load_tools")
@patch("src.core.orchestrator.initialize_agent")
@patch("src.core.orchestrator.ConversationBufferMemory")
def test_orchestrator_init_llm_failure(
    mock_memory, mock_initialize_agent, mock_load_tools_method, mock_llm_loader_class
):
    """Test Orchestrator initialization when LLM loading fails."""
    # Configure the mock LLMLoader instance to return None for load()
    mock_loader_instance_fail = MagicMock()
    mock_loader_instance_fail.load.return_value = None
    mock_llm_loader_class.return_value = mock_loader_instance_fail

    orchestrator = Orchestrator()

    # Assertions
    mock_llm_loader_class.assert_called_once()
    mock_loader_instance_fail.load.assert_called_once()
    # Ensure other parts were not called because LLM failed
    mock_load_tools_method.assert_not_called()
    mock_memory.assert_not_called()
    mock_initialize_agent.assert_not_called()
    assert orchestrator.llm is None
    assert orchestrator.agent is None # Agent should be None if LLM fails

@patch("src.core.orchestrator.LLMLoader", return_value=mock_llm_loader_instance)
@patch("src.core.orchestrator.Orchestrator._load_tools", return_value=[
    mock_open_app
])
@patch("src.core.orchestrator.initialize_agent") # Mock initialize_agent
@patch("src.core.orchestrator.ConversationBufferMemory")
def test_orchestrator_process_input_agent_failure(
    mock_memory, mock_initialize_agent, mock_load_tools_method, mock_llm_loader_class
):
    """Test processing input when the agent executor fails."""
    # Configure initialize_agent to return a mock that raises an exception on invoke
    mock_failing_agent_executor = MagicMock()
    mock_failing_agent_executor.invoke.side_effect = Exception("Agent execution error")
    mock_initialize_agent.return_value = mock_failing_agent_executor

    orchestrator = Orchestrator()

    user_input = "Do something complex"
    response = orchestrator.route_command(user_input)

    # Assertions
    mock_failing_agent_executor.invoke.assert_called_once_with({"input": user_input})
    assert "Sorry, I encountered an error" in response

