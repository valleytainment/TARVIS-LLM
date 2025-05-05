import os
import logging
from pathlib import Path
from langchain.agents import Tool, initialize_agent, AgentType
from langchain.chains.conversation.memory import ConversationBufferMemory
from langchain.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate
from langchain.schema import SystemMessage # Import SystemMessage
from dotenv import load_dotenv

# Assuming llm_manager is in the same directory or PYTHONPATH is set correctly
from .llm_manager import LLMLoader
from .storage_manager import load_settings # Import load_settings

# Import skill functions - these files will be created in the next steps
# We will define placeholder functions for now if needed for testing, 
# or structure the code to load them dynamically later.
# from ..skills import open_app, file_ops, clipboard # Corrected relative import

# Load environment variables
load_dotenv()

# Configure logginglogging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
class Orchestrator:
    """Manages the interaction flow, loading the LLM and routing commands to appropriate skills."""

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
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logging.error(f"Failed to read system prompt file {prompt_path}: {e}. Using fallback prompt.")
            return "You are a helpful AI assistant." # Basic fallback prompt

    def _load_tools(self):
        """Loads the available skills as tools for the LangChain agent."""
        logging.info("Loading tools...")
        tools_list = []
        try:
            # Dynamically import skills to avoid errors if files don't exist yet
            # These imports assume the skill modules are in ../skills/
            from ..skills import open_app, file_ops, clipboard

            # Define tools based on the blueprint
            tools_list = [
                Tool(
                    name="open_application",
                    func=open_app.execute, # Assumes an execute function in open_app.py
                    description="Opens or launches a specified application on the computer (e.g., Firefox, Notepad, VS Code). Input should be the name of the application."
                ),
                Tool(
                    name="copy_file",
                    func=file_ops.copy_file, # Assumes copy_file function in file_ops.py
                    description="Copies a file from a source path to a destination path. Input should be the source and destination paths."
                ),
                Tool(
                    name="delete_file",
                    func=file_ops.delete_file, # Assumes delete_file function in file_ops.py
                    description="Deletes a file at the specified path. Input should be the path to the file."
                ),
                Tool(
                    name="write_to_clipboard",
                    func=clipboard.write, # Assumes write function in clipboard.py
                    description="Writes the given text content to the system clipboard. Input should be the text to write."
                ),
                Tool(
                    name="read_from_clipboard",
                    func=clipboard.read, # Assumes read function in clipboard.py
                    description="Reads the current text content from the system clipboard. Takes no input."
                )
                # Add more tools here as skills are developed
            ]
            logging.info(f"Successfully loaded {len(tools_list)} tools.")
        except ImportError as e:
            logging.warning(f"Could not import one or more skill modules: {e}. Agent will have limited tools.")
        except AttributeError as e:
            logging.warning(f"A skill module is missing an expected function: {e}. Check skill implementations.")
        except Exception as e:
            logging.error(f"An unexpected error occurred while loading tools: {e}", exc_info=True)

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

