#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import logging
from pathlib import Path
import importlib
import inspect # Added for dynamic loading
from langchain.agents import Tool, initialize_agent, AgentType
from langchain.tools.base import BaseTool # Added for type checking
from langchain.memory import ConversationBufferWindowMemory
from langchain.schema import SystemMessage
from dotenv import load_dotenv

from .llm_manager import LLMLoader
from .storage_manager import load_settings

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class Orchestrator:
    """Manages the interaction flow, loading the LLM and routing commands to appropriate skills."""

    def __init__(self):
        """Initializes the Orchestrator, loading the LLM, tools, memory, and custom prompt."""
        logging.info("Initializing Orchestrator...")
        self.settings = load_settings()
        self.llm_loader = LLMLoader()
        self.llm = self.llm_loader.load()

        if self.llm is None:
            logging.error("LLM failed to load. Orchestrator cannot function without an LLM.")
            self.agent = None
            return

        self.tools = self._load_tools()

        try:
            self.max_context_turns = int(os.getenv("MAX_CONTEXT_TURNS", 5))
            if self.max_context_turns <= 0:
                self.max_context_turns = 5
        except ValueError:
            self.max_context_turns = 5
        logging.info(f"Using conversation memory window size (k): {self.max_context_turns * 2}")
        self.memory = ConversationBufferWindowMemory(
            memory_key="chat_history",
            return_messages=True,
            k=self.max_context_turns * 2
        )

        system_prompt_content = self._load_system_prompt()
        system_message = SystemMessage(content=system_prompt_content)
        agent_kwargs = {"system_message": system_message}

        try:
            if not self.tools:
                 logging.warning("No tools were loaded. Agent will only use LLM knowledge.")
                 # Decide if agent should still initialize without tools
                 # For now, let it initialize but it won't be very useful

            self.agent = initialize_agent(
                self.tools if self.tools else [], # Pass empty list if no tools
                self.llm,
                agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
                memory=self.memory,
                agent_kwargs=agent_kwargs,
                verbose=True,
                handle_parsing_errors=True
            )
            logging.info("Orchestrator initialized successfully with agent.")
        except Exception as e:
            logging.error(f"Failed to initialize agent: {e}", exc_info=True)
            self.agent = None

    def _load_system_prompt(self) -> str:
        """Loads the system prompt from the path specified in settings or default."""
        custom_prompt_path_str = self.settings.get("system_prompt_path")
        # Corrected default path finding relative to this file
        default_prompt_path = Path(__file__).resolve().parent.parent / "config" / "prompts" / "system_prompt.txt"
        prompt_path = default_prompt_path

        if custom_prompt_path_str:
            try:
                custom_prompt_path = Path(custom_prompt_path_str).resolve()
                if custom_prompt_path.is_file():
                    prompt_path = custom_prompt_path
                    logging.info(f"Using custom system prompt from: {prompt_path}")
                else:
                    logging.warning(f"Custom system prompt path \"{custom_prompt_path_str}\" not found. Using default prompt.")
            except Exception as e:
                logging.error(f"Error resolving custom prompt path \"{custom_prompt_path_str}\": {e}. Using default prompt.")
        else:
            logging.info(f"Using default system prompt from: {prompt_path}")

        try:
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            if not prompt_path.exists():
                 logging.warning(f"Prompt file {prompt_path} not found. Creating with default content.")
                 with open(prompt_path, "w", encoding="utf-8") as f:
                     f.write("You are Jarvis, a helpful AI assistant. Respond concisely and accurately.")

            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logging.error(f"Failed to read or create system prompt file {prompt_path}: {e}. Using fallback prompt.")
            return "You are a helpful AI assistant."

    def _load_tools(self):
        """Dynamically loads tools decorated with @tool from the skills directory."""
        logging.info("Dynamically loading tools from skills directory...")
        tools_list = []
        # Corrected path finding relative to this file
        skills_dir = Path(__file__).resolve().parent.parent / "skills"
        
        if not skills_dir.is_dir():
            logging.error(f"Skills directory not found at {skills_dir}. Cannot load tools.")
            return []

        for filepath in skills_dir.glob("*.py"):
            if filepath.name == "__init__.py":
                continue

            module_name = filepath.stem
            # Construct the full module path relative to the 'src' directory
            module_path = f"src.skills.{module_name}"
            
            try:
                logging.debug(f"Attempting to import module: {module_path}")
                module = importlib.import_module(module_path)
                logging.debug(f"Successfully imported module: {module_path}")

                # Inspect the module for functions decorated with @tool
                # LangChain's @tool typically replaces the function with a Tool instance
                for name, obj in inspect.getmembers(module):
                    # Check if the object is an instance of BaseTool (which Tool inherits from)
                    if isinstance(obj, BaseTool):
                        logging.info(f"Found tool: {obj.name} in module {module_name}")
                        tools_list.append(obj)
                    # Alternative check (less robust): Check if it's a function with specific metadata
                    # elif inspect.isfunction(obj) and hasattr(obj, '__is_tool') and obj.__is_tool:
                    #     logging.info(f"Found decorated function: {name} in module {module_name}")
                    #     tools_list.append(obj) # Assuming @tool adds metadata

            except ImportError as e:
                logging.error(f"Failed to import skill module {module_path}: {e}", exc_info=True)
            except Exception as e:
                logging.error(f"An unexpected error occurred while loading tools from {module_path}: {e}", exc_info=True)

        if not tools_list:
            logging.warning("No tools were discovered or loaded from the skills directory.")
        else:
            logging.info(f"Successfully discovered and loaded {len(tools_list)} tools: {[t.name for t in tools_list]}")
            
        return tools_list

    def route_command(self, user_input: str):
        """Routes the user's command to the appropriate skill via the LangChain agent."""
        logging.info(f"Routing command: {user_input}")
        if not self.agent:
            error_msg = "Agent is not initialized (likely due to LLM or tool loading failure). Cannot process command."
            logging.error(error_msg)
            return error_msg

        try:
            response = self.agent.invoke({"input": user_input})
            output = response.get('output', "Agent did not return a standard output.")
            logging.info(f"Agent response: {output}")
            return output
        except Exception as e:
            error_msg = f"Error during agent execution: {e}"
            logging.error(error_msg, exc_info=True)
            return "Sorry, I encountered an error while processing your request. Please check the logs for details."

# Example usage (for testing purposes)
if __name__ == "__main__":
    print("Testing Orchestrator with dynamic tool loading...")
    try:
        orchestrator = Orchestrator()
        if orchestrator.agent:
            print("Orchestrator initialized.")
            print(f"Loaded tools: {[tool.name for tool in orchestrator.tools]}")
            # Example command (requires LLM model)
            # command = "Copy my_notes.txt to backups/notes_backup.txt"
            # print(f"Sending command: {command}")
            # result = orchestrator.route_command(command)
            # print(f"Result: {result}")
        else:
            print("Orchestrator initialization failed. Check logs.")
    except Exception as e:
        print(f"Error during Orchestrator test: {e}")
    print("Orchestrator test script finished.")

