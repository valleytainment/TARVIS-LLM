import os
import logging
import importlib
import inspect
from pathlib import Path
from langchain.agents import Tool, initialize_agent, AgentType
from langchain.chains.conversation.memory import ConversationBufferMemory
from langchain.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate
from langchain.schema import SystemMessage # Import SystemMessage
from dotenv import load_dotenv

# Assuming llm_manager is in the same directory or PYTHONPATH is set correctly
from .llm_manager import LLMLoader
from .storage_manager import load_settings # Import load_settings

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class Orchestrator:
    """Manages the interaction flow, loading the LLM and routing commands to dynamically loaded skills."""

    def __init__(self):
        """Initializes the Orchestrator, loading the LLM, tools, memory, and custom prompt."""
        logging.info("Initializing Orchestrator...")
        self.settings = load_settings()
        self.llm_loader = LLMLoader() # LLMLoader now uses settings internally
        self.llm = self.llm_loader.load()
        
        if self.llm is None:
            logging.error("LLM failed to load. Orchestrator cannot function without an LLM.")
            self.agent = None
            return

        self.tools = self._load_tools()
        self.memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
        
        # Load and prepare the system prompt
        system_prompt_content = self._load_system_prompt()
        system_message = SystemMessage(content=system_prompt_content)
        agent_kwargs = {"system_message": system_message}

        # Initialize the agent
        try:
            self.agent = initialize_agent(
                self.tools,
                self.llm,
                agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
                memory=self.memory,
                agent_kwargs=agent_kwargs, # Pass the custom system prompt
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
        # Use resource_path utility if available, otherwise fallback
        try:
            from ..utils.resource_path import get_resource_path
            default_prompt_path = get_resource_path(Path("config") / "prompts" / "system_prompt.txt")
        except ImportError:
            logging.warning("resource_path utility not found, using relative path for default prompt.")
            default_prompt_path = Path(__file__).resolve().parent.parent / "config" / "prompts" / "system_prompt.txt"
            
        prompt_path = default_prompt_path

        if custom_prompt_path_str:
            try:
                # Resolve custom path relative to project root if not absolute
                custom_prompt_path = Path(custom_prompt_path_str)
                if not custom_prompt_path.is_absolute():
                     project_root = Path(__file__).resolve().parent.parent.parent
                     custom_prompt_path = project_root / custom_prompt_path
                
                if custom_prompt_path.is_file():
                    prompt_path = custom_prompt_path.resolve()
                    logging.info(f"Using custom system prompt from: {prompt_path}")
                else:
                    logging.warning(f"Custom system prompt path \"{custom_prompt_path_str}\" (resolved to {custom_prompt_path}) not found. Using default prompt.")
            except Exception as e:
                logging.error(f"Error resolving custom prompt path \"{custom_prompt_path_str}\": {e}. Using default prompt.")
        else:
            logging.info(f"Using default system prompt from: {prompt_path}")

        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logging.error(f"Failed to read system prompt file {prompt_path}: {e}. Using fallback prompt.")
            return "You are a helpful AI assistant." # Basic fallback prompt

    def _load_tools(self):
        """Dynamically loads tools from skill modules in the src/skills directory."""
        logging.info("Dynamically loading tools from src/skills...")
        tools_list = []
        skills_dir = Path(__file__).resolve().parent.parent / "skills"
        
        if not skills_dir.is_dir():
            logging.warning(f"Skills directory not found at {skills_dir}. No tools will be loaded.")
            return []

        for filepath in skills_dir.glob("*.py"):
            if filepath.name == "__init__.py":
                continue

            module_name = filepath.stem
            try:
                # Construct the full module path relative to the project structure (e.g., src.skills.open_app)
                module_spec = f"src.skills.{module_name}"
                skill_module = importlib.import_module(module_spec)
                logging.debug(f"Imported skill module: {module_spec}")

                # Look for a function named 'get_tool' or 'get_tools'
                get_tool_func = None
                if hasattr(skill_module, "get_tool") and callable(skill_module.get_tool):
                    get_tool_func = skill_module.get_tool
                elif hasattr(skill_module, "get_tools") and callable(skill_module.get_tools):
                     # Handle case where a module might provide multiple tools
                     get_tool_func = skill_module.get_tools 
                
                if get_tool_func:
                    tools_or_tool = get_tool_func()
                    if isinstance(tools_or_tool, list):
                        tools_list.extend(tools_or_tool)
                        logging.info(f"Loaded {len(tools_or_tool)} tools from {module_name}.py")
                    elif isinstance(tools_or_tool, Tool):
                        tools_list.append(tools_or_tool)
                        logging.info(f"Loaded tool from {module_name}.py")
                    else:
                        logging.warning(f"Function 'get_tool(s)' in {module_name}.py did not return a Tool or list of Tools.")
                else:
                    logging.warning(f"No 'get_tool' or 'get_tools' function found in {module_name}.py. Skipping.")

            except ImportError as e:
                logging.error(f"Failed to import skill module {module_name}: {e}", exc_info=True)
            except Exception as e:
                logging.error(f"Error loading tools from {module_name}.py: {e}", exc_info=True)

        if not tools_list:
            logging.warning("No tools were loaded. The agent might not be able to perform specific actions.")
        else:
            logging.info(f"Successfully loaded {len(tools_list)} tools in total.")
            
        return tools_list

    def route_command(self, user_input: str):
        """Routes the user's command to the appropriate skill via the LangChain agent."""
        logging.info(f"Routing command: {user_input}")
        if not self.agent:
            error_msg = "Agent is not initialized (likely due to LLM or tool loading failure). Cannot process command."
            logging.error(error_msg)
            return error_msg

        try:
            # Use agent.invoke for newer LangChain versions, includes input structure
            response = self.agent.invoke({"input": user_input})
            # The actual response is usually in the 'output' key
            output = response.get('output', "Agent did not return a standard output.")
            logging.info(f"Agent response: {output}")
            return output
        except Exception as e:
            error_msg = f"Error during agent execution: {e}"
            logging.error(error_msg, exc_info=True)
            # Provide a user-friendly error message
            return "Sorry, I encountered an error while processing your request. Please check the logs for details."

# Example usage (for testing purposes - requires LLM and potentially skills)
if __name__ == "__main__":
    print("Testing Orchestrator...")
    # This test assumes the LLM model exists and skill modules are available
    # It might fail if the LLM isn't loaded or skills are missing
    try:
        orchestrator = Orchestrator()
        if orchestrator.agent:
            print("Orchestrator initialized.")
            print(f"Loaded tools: {[tool.name for tool in orchestrator.tools]}")
            # Example command (will likely fail if LLM/skills not fully set up)
            # command = "Open notepad"
            # print(f"Sending command: {command}")
            # result = orchestrator.route_command(command)
            # print(f"Result: {result}")
        else:
            print("Orchestrator initialization failed. Check logs.")
    except Exception as e:
        print(f"Error during Orchestrator test: {e}")
    print("Orchestrator test script finished.")

