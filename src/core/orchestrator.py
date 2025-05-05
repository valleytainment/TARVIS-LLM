#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import logging
from pathlib import Path
import importlib
import inspect # Used for dynamically finding @tool decorated functions
from typing import Iterator, Dict, Any, Optional # Type hinting

# Langchain imports
from langchain import hub # For pulling standard prompt templates (e.g., react-chat)
from langchain.agents import AgentExecutor, create_react_agent # Core agent execution logic
from langchain.tools.base import BaseTool # Base class for tool type checking
from langchain.memory import ConversationBufferWindowMemory # For agent memory
from langchain.schema import SystemMessage, StrOutputParser # For RAG chain output
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder # For prompt templating
from langchain.schema.runnable import RunnablePassthrough # For RAG chain construction

# LLM Provider Imports (handle potential errors if libraries not installed)
try:
    from langchain_openai import ChatOpenAI
except ImportError:
    logging.warning("langchain-openai not installed. OpenAI provider will be unavailable.")
    ChatOpenAI = None
try:
    from langchain_deepseek import ChatDeepseek
except ImportError:
    logging.warning("langchain-deepseek not installed. Deepseek provider will be unavailable.")
    ChatDeepseek = None

# Attempt RAG imports, handle gracefully if packages not installed
try:
    from langchain_community.vectorstores import Chroma # Vector store implementation
    from langchain_huggingface import HuggingFaceEmbeddings # Embedding model
    RAG_ENABLED = True
except ImportError:
    logging.warning("RAG dependencies (chromadb, sentence-transformers/langchain-huggingface) not found. RAG features will be disabled.")
    Chroma = None
    HuggingFaceEmbeddings = None
    RAG_ENABLED = False

# Secure Storage Import for API keys
try:
    from src.utils.security import SecureStorage
except ImportError:
    logging.error("Could not import SecureStorage. API key functionality will be limited.")
    SecureStorage = None

from dotenv import load_dotenv # For loading environment variables from .env file

from .llm_manager import LLMLoader # For loading local LLMs
from .storage_manager import load_settings # To load settings if not provided

# Load environment variables from .env file in the project root
load_dotenv()

# Configure logging for the orchestrator module
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - Orchestrator - %(message)s")

# Define paths relative to the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent 
VECTOR_STORE_DIR = PROJECT_ROOT / "vector_store" # Directory for ChromaDB
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2" # Default embedding model for RAG

class Orchestrator:
    """Manages the interaction flow, loading the LLM, tools, memory, and integrating RAG.
    
    Acts as the central brain, deciding whether to use a RAG chain (if available and enabled)
    or a conversational agent (fallback) to respond to user input.
    Handles loading the appropriate LLM based on settings (local, OpenAI, Deepseek).
    Dynamically loads tools (skills) from the specified directory.
    Manages conversation history for the agent.
    """

    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        """Initializes the Orchestrator.

        Loads the LLM based on settings, dynamically loads tools, sets up conversation memory,
        and attempts to initialize either a RAG chain (if dependencies met and vector store exists)
        or a fallback conversational agent.
        
        Args:
            settings (Optional[Dict[str, Any]]): Application settings dictionary. 
                                                If None, loads settings from the default file.
        """
        logging.info("Initializing Orchestrator...")
        # Use provided settings or load from file using storage_manager
        self.settings = settings if settings is not None else load_settings()
        
        # --- LLM Loading based on Settings ---
        # This is the first critical step, as other components depend on the LLM.
        self.llm = self._load_llm_from_settings()

        # If LLM loading fails, the orchestrator cannot function.
        if self.llm is None:
            logging.error("LLM failed to load. Orchestrator cannot function without an LLM.")
            self.agent_executor = None 
            self.rag_chain = None
            return # Stop initialization
        # --- End LLM Loading ---

        # Load tools (skills) dynamically from the skills directory.
        self.tools = self._load_tools()
        
        # Initialize RAG and Agent components to None initially.
        self.retriever = None
        self.rag_chain = None
        self.agent_executor = None 

        # --- RAG Setup --- 
        # Attempt RAG setup only if dependencies were imported successfully (RAG_ENABLED is True)
        # and the LLM was loaded successfully.
        if RAG_ENABLED and self.llm:
            try:
                logging.info("Attempting to initialize RAG components...")
                vector_store_path = VECTOR_STORE_DIR # Use defined path
                
                # Check if the vector store directory exists.
                if not vector_store_path.exists():
                    logging.warning(f"Vector store directory \"{vector_store_path}\" not found. RAG will not function until the store is built.")
                else:
                    # Ensure HuggingFaceEmbeddings class is available (redundant check, but safe).
                    if HuggingFaceEmbeddings is None:
                        raise ImportError("HuggingFaceEmbeddings is required for RAG but not available.")
                        
                    # Initialize the embedding model.
                    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
                    
                    # Load the existing Chroma vector store.
                    vector_store = Chroma(
                        persist_directory=str(vector_store_path),
                        embedding_function=embeddings
                    )
                    # Create a retriever from the vector store.
                    self.retriever = vector_store.as_retriever(
                        search_type="similarity", # Use similarity search
                        search_kwargs={"k": 3} # Retrieve top 3 relevant chunks
                    )
                    logging.info(f"Successfully loaded vector store from {vector_store_path} and created retriever.")

                    # Define the prompt template for the RAG chain.
                    rag_prompt_template = """
                    You are an assistant for question-answering tasks. 
                    Use the following pieces of retrieved context to answer the question. 
                    If you don\\'t know the answer, just say that you don\\'t know. 
                    Use three sentences maximum and keep the answer concise.
                    
                    Context: {context}
                    
                    Question: {question}
                    
                    Answer:"""
                    rag_prompt = ChatPromptTemplate.from_template(rag_prompt_template)

                    # Construct the RAG chain using LangChain Expression Language (LCEL).
                    # 1. Retrieve context using the retriever.
                    # 2. Pass the original question through.
                    # 3. Format the prompt with context and question.
                    # 4. Pass the formatted prompt to the LLM.
                    # 5. Parse the LLM output as a string.
                    self.rag_chain = (
                        {"context": self.retriever, "question": RunnablePassthrough()}
                        | rag_prompt
                        | self.llm
                        | StrOutputParser()
                    )
                    logging.info("RAG chain initialized successfully.")

            except Exception as e:
                # If any part of RAG setup fails, log the error and disable RAG.
                logging.error(f"Failed to initialize RAG components: {e}. RAG will be disabled.", exc_info=True)
                self.retriever = None
                self.rag_chain = None
        # --- End RAG Setup ---

        # --- Fallback Agent Setup ---
        # If RAG is disabled (due to missing dependencies or setup failure) 
        # AND the LLM was loaded successfully, set up the conversational agent.
        if self.rag_chain is None and self.llm:
            logging.info("RAG is disabled or failed to initialize. Setting up standard conversational agent.")
            try:
                # Configure conversation memory window size.
                try:
                    self.max_context_turns = int(os.getenv("MAX_CONTEXT_TURNS", 5))
                    if self.max_context_turns <= 0:
                        self.max_context_turns = 5 # Ensure positive window size
                except ValueError:
                    self.max_context_turns = 5 # Default if env var is invalid
                # k represents total messages (user + AI), so multiply turns by 2.
                memory_window_size = self.max_context_turns * 2
                logging.info(f"Using conversation memory window size (k): {memory_window_size}")
                self.memory = ConversationBufferWindowMemory(
                    memory_key="chat_history", # Key used in the agent prompt
                    return_messages=True, # Return history as message objects
                    k=memory_window_size
                )

                # Load system prompt (content is loaded, but integration depends on agent type).
                system_prompt_content = self._load_system_prompt()
                # Note: For ReAct agents, the system message is often part of the main prompt template.

                # Create the conversational agent.
                if not self.tools:
                    logging.warning("No tools were loaded. Agent will only use LLM knowledge and conversation history.")
                
                # Use the standard ReAct chat prompt from Langchain Hub.
                # This prompt includes placeholders for chat_history, input, agent_scratchpad, and tools.
                prompt = hub.pull("hwchase17/react-chat") 
                logging.info(f"Using agent prompt template from hub: hwchase17/react-chat")
                
                # Create the ReAct agent runnable.
                agent = create_react_agent(self.llm, self.tools if self.tools else [], prompt)
                
                # Create the AgentExecutor, which runs the agent loop.
                self.agent_executor = AgentExecutor(
                    agent=agent,
                    tools=self.tools if self.tools else [], # Provide the loaded tools
                    memory=self.memory, # Provide the conversation memory
                    verbose=True, # Log agent actions and thoughts
                    handle_parsing_errors=True, # Attempt to recover from LLM output parsing errors
                    max_iterations=5 # Limit the number of steps the agent can take per turn
                )
                logging.info("Fallback conversational agent executor initialized successfully.")
                
            except Exception as e:
                # If agent setup fails, log the error.
                logging.error(f"Failed to initialize fallback agent executor: {e}", exc_info=True)
                self.agent_executor = None
        # --- End Fallback Agent Setup ---

        # Final check: Ensure at least one processing mechanism (RAG or Agent) is ready.
        if self.rag_chain is None and self.agent_executor is None:
            logging.error("CRITICAL: Failed to initialize both RAG chain and fallback agent executor. Orchestrator cannot process commands.")
        else:
             logging.info("Orchestrator initialized.")

    def _load_llm_from_settings(self) -> Optional[Any]: # Return type can be BaseLanguageModel but Any is safer for now
        """Loads the appropriate LLM (local, OpenAI, Deepseek) based on the active provider in settings.
        
        Retrieves API keys securely using SecureStorage if required.
        Returns the initialized LangChain LLM/ChatModel instance, or None if loading fails.
        """
        active_provider = self.settings.get("active_llm_provider", "local")
        provider_config = self.settings.get("api_providers", {}).get(active_provider, {})
        is_enabled = provider_config.get("enabled", False)
        model_name = provider_config.get("model")
        endpoint = provider_config.get("endpoint") # Optional base URL for API providers
        api_key = None
        llm_instance = None

        logging.info(f"Attempting to load LLM for active provider: \"{active_provider}\"")

        # --- Handle Local LLM --- 
        if active_provider == "local":
            logging.info("Loading local LLM using LLMLoader...")
            try:
                # LLMLoader handles reading .env vars (GPU, quant, mlock, model path) and settings
                loader = LLMLoader() 
                llm_instance = loader.load() # This performs the actual loading
                if llm_instance:
                    logging.info("Local LLM loaded successfully.")
                else:
                    logging.error("Failed to load local LLM (LLMLoader.load() returned None).")
            except Exception as e:
                logging.error(f"Error during local LLM loading: {e}", exc_info=True)
            return llm_instance # Return the instance (or None if failed)

        # --- Handle API-based Providers --- 
        # Check if the selected API provider is enabled in settings.
        if not is_enabled:
            logging.warning(f"Provider \"{active_provider}\" is not enabled in settings. Cannot load LLM.")
            return None

        # Check if SecureStorage is available for retrieving API keys.
        if not SecureStorage:
            logging.error(f"SecureStorage is unavailable. Cannot retrieve API key for \"{active_provider}\".")
            return None

        # Retrieve the API key securely.
        try:
            api_key = SecureStorage.retrieve_key(active_provider)
            if not api_key:
                logging.error(f"API key for \"{active_provider}\" not found in secure storage.")
                return None
            logging.info(f"Retrieved API key for \"{active_provider}\" from secure storage.")
        except Exception as e:
            logging.error(f"Error retrieving API key for \"{active_provider}\": {e}", exc_info=True)
            return None

        # Initialize the appropriate LangChain ChatModel based on the provider.
        try:
            if active_provider == "openai" and ChatOpenAI:
                logging.info(f"Initializing ChatOpenAI with model: {model_name}")
                llm_instance = ChatOpenAI(
                    model=model_name,
                    openai_api_key=api_key,
                    openai_api_base=endpoint or None, # Use custom endpoint if provided
                    streaming=True, # Enable streaming responses
                    # Consider adding temperature, max_tokens etc. if needed
                )
            elif active_provider == "deepseek" and ChatDeepseek:
                logging.info(f"Initializing ChatDeepseek with model: {model_name}")
                llm_instance = ChatDeepseek(
                    model=model_name,
                    deepseek_api_key=api_key,
                    base_url=endpoint or None, # Use custom endpoint if provided
                    streaming=True, # Enable streaming responses
                    # Consider adding temperature, max_tokens etc. if needed
                )
            # Add elif blocks here for other future API providers
            else:
                # If provider name is unknown or the corresponding library wasn\\'t imported.
                logging.error(f"Unsupported or unavailable provider type: \"{active_provider}\"")
                return None
            
            logging.info(f"Successfully initialized LLM for provider: \"{active_provider}\"")
            return llm_instance

        except Exception as e:
            # Catch errors during LLM client initialization (e.g., invalid model name, connection issues)
            logging.error(f"Failed to initialize LLM for provider \"{active_provider}\": {e}", exc_info=True)
            return None

    def _load_system_prompt(self) -> str:
        """Loads the system prompt string.
        
        Reads from the path specified in settings (system_prompt_path).
        If no path is set or the file doesn\\'t exist, it falls back to a default path 
        (src/config/prompts/system_prompt.txt).
        If the default file doesn\\'t exist, it creates it with basic content.
        Returns the loaded or default system prompt string.
        """
        custom_prompt_path_str = self.settings.get("system_prompt_path")
        default_prompt_path = PROJECT_ROOT / "src" / "config" / "prompts" / "system_prompt.txt"
        prompt_path = default_prompt_path # Start with default

        # Check if a custom path is provided in settings.
        if custom_prompt_path_str:
            try:
                custom_prompt_path = Path(custom_prompt_path_str).resolve()
                # Use the custom path only if it points to an existing file.
                if custom_prompt_path.is_file():
                    prompt_path = custom_prompt_path
                    logging.info(f"Using custom system prompt from: {prompt_path}")
                else:
                    logging.warning(f"Custom system prompt path \"{custom_prompt_path_str}\" not found. Using default prompt.")
            except Exception as e:
                # Handle potential errors resolving the custom path.
                logging.error(f"Error resolving custom prompt path \"{custom_prompt_path_str}\": {e}. Using default prompt.")
        else:
            # If no custom path is set, use the default.
            logging.info(f"Using default system prompt from: {prompt_path}")

        # Try to read the selected prompt file.
        try:
            # Ensure the directory exists.
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            # If the file doesn\\'t exist, create it with default content.
            if not prompt_path.exists():
                 logging.warning(f"Prompt file {prompt_path} not found. Creating with default content.")
                 default_content = "You are a helpful AI assistant. Answer the user\\'s questions and use the tools provided when necessary."
                 with open(prompt_path, "w", encoding="utf-8") as f:
                     f.write(default_content)
                 return default_content

            # Read the content from the existing file.
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            # Handle errors during file reading or creation.
            logging.error(f"Failed to read or create system prompt file {prompt_path}: {e}. Using fallback prompt.")
            return "You are a helpful AI assistant." # Basic fallback prompt

    def _load_tools(self) -> list:
        """Dynamically loads tools (functions decorated with @tool) from Python files 
        within the src/skills directory.
        
        Returns:
            list: A list of loaded LangChain tool objects (instances of BaseTool).
        """
        logging.info("Dynamically loading tools from skills directory...")
        tools_list = []
        skills_dir = PROJECT_ROOT / "src" / "skills"
        
        # Check if the skills directory exists.
        if not skills_dir.is_dir():
            logging.error(f"Skills directory not found at {skills_dir}. Cannot load tools.")
            return []

        # Iterate over Python files in the skills directory.
        for filepath in skills_dir.glob("*.py"):
            # Skip __init__.py files.
            if filepath.name == "__init__.py":
                continue

            module_name = filepath.stem # Get the filename without extension
            module_path = f"src.skills.{module_name}" # Construct the full module path
            
            try:
                # Import the module dynamically using importlib.
                logging.debug(f"Attempting to import module: {module_path}")
                module = importlib.import_module(module_path)
                logging.debug(f"Successfully imported module: {module_path}")

                # Inspect the imported module for objects that are instances of BaseTool.
                # The @tool decorator wraps functions into BaseTool instances.
                for name, obj in inspect.getmembers(module):
                    if isinstance(obj, BaseTool):
                        logging.info(f"Found tool: {obj.name} in module {module_name}")
                        tools_list.append(obj)

            except ImportError as e:
                # Handle errors if a skill module cannot be imported (e.g., missing dependencies).
                logging.error(f"Failed to import skill module {module_path}: {e}", exc_info=True)
            except Exception as e:
                # Handle any other unexpected errors during loading.
                logging.error(f"An unexpected error occurred while loading tools from {module_path}: {e}", exc_info=True)

        # Log the outcome of the tool loading process.
        if not tools_list:
            logging.warning("No tools were discovered or loaded from the skills directory.")
        else:
            logging.info(f"Successfully discovered and loaded {len(tools_list)} tools: {[t.name for t in tools_list]}")
            
        return tools_list

    def route_command_stream(self, user_input: str) -> Iterator[str]:
        """Processes the user input and yields the response chunks via streaming.

        Prioritizes using the RAG chain if it\\'s available. 
        Otherwise, falls back to using the conversational agent executor.
        Handles potential errors during invocation.

        Args:
            user_input (str): The user\\'s command or question.

        Yields:
            Iterator[str]: An iterator of response chunks (strings).
        """
        logging.info(f"Routing command. Input length: {len(user_input)}")
        
        # --- RAG Chain Execution (Priority) ---
        if self.rag_chain:
            logging.info("Using RAG chain to process input.")
            try:
                # Stream the response directly from the RAG chain.
                for chunk in self.rag_chain.stream(user_input):
                    yield chunk
                logging.info("RAG chain streaming finished.")
                return # Stop processing after RAG
            except Exception as e:
                error_msg = f"Error during RAG chain execution: {e}"
                logging.error(error_msg, exc_info=True)
                yield f"\n[Error processing request with RAG: {e}]\n" # Yield error message
                # Decide whether to fall back to agent or just return error.
                # For now, just return the error from RAG.
                return

        # --- Agent Executor Execution (Fallback) ---
        elif self.agent_executor:
            logging.info("Using fallback agent executor to process input.")
            try:
                # Use agent executor\\'s stream method for intermediate steps and final answer.
                # Note: The structure of the streamed output might vary.
                # We are primarily interested in the final output chunks.
                final_output_key = "output" # Default key for final answer in AgentExecutor stream
                
                # Stream the agent execution steps and final output.
                for chunk in self.agent_executor.stream({"input": user_input}):
                    # The streamed output is a dictionary. We need to check for the final answer key.
                    # Different agent types might use different keys. Inspect the output if needed.
                    if final_output_key in chunk:
                        yield chunk[final_output_key]
                        
                logging.info("Agent executor streaming finished.")
                return # Stop processing after agent
                
            except Exception as e:
                error_msg = f"Error during agent execution: {e}"
                logging.error(error_msg, exc_info=True)
                yield f"\n[Error processing request with Agent: {e}]\n" # Yield error message
                return

        # --- No Processing Mechanism Available --- 
        else:
            error_msg = "Orchestrator Error: No processing mechanism (RAG or Agent) is available."
            logging.error(error_msg)
            yield f"\n[{error_msg}]\n"
            return

# Example usage (for testing purposes - requires running from project root: python -m src.core.orchestrator)
if __name__ == "__main__":
    print("Testing Orchestrator initialization...")
    try:
        orchestrator = Orchestrator()
        if orchestrator.llm:
            print("Orchestrator initialized. LLM loaded.")
            if orchestrator.rag_chain:
                print("RAG chain is active.")
            elif orchestrator.agent_executor:
                print("Fallback agent executor is active.")
                print(f"Loaded tools: {[tool.name for tool in orchestrator.tools]}")
            else:
                print("WARNING: LLM loaded, but neither RAG nor Agent could be initialized.")
            
            # Example command execution (optional)
            # print("\nTesting command routing (stream):")
            # test_input = "What is the capital of France?"
            # print(f">>> {test_input}")
            # for response_chunk in orchestrator.route_command_stream(test_input):
            #     print(response_chunk, end="", flush=True)
            # print("\n--- Stream test finished ---")
            
        else:
            print("Orchestrator initialization failed: LLM did not load.")
            
    except Exception as main_e:
        print(f"An error occurred during Orchestrator testing: {main_e}")
        logging.error("Error in Orchestrator test execution", exc_info=True)

    print("\nOrchestrator test script finished.")

