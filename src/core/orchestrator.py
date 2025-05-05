#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import logging
from pathlib import Path
import importlib
import inspect # Added for dynamic loading
from typing import Iterator, Dict, Any, Optional # Added for streaming and settings

# Langchain imports
from langchain.agents import Tool, initialize_agent, AgentType # Keep for potential fallback or future use
from langchain.tools.base import BaseTool # Added for type checking
from langchain.memory import ConversationBufferWindowMemory
from langchain.schema import SystemMessage, StrOutputParser
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema.runnable import RunnablePassthrough

# Attempt RAG imports, handle gracefully if packages not installed
try:
    from langchain_community.vectorstores import Chroma
    from langchain_community.embeddings import SentenceTransformerEmbeddings
    RAG_ENABLED = True
except ImportError:
    logging.warning("RAG dependencies (chromadb, sentence-transformers) not found. RAG features will be disabled.")
    Chroma = None
    SentenceTransformerEmbeddings = None
    RAG_ENABLED = False

from dotenv import load_dotenv

from .llm_manager import LLMLoader
from .storage_manager import load_settings # Keep for default if settings not passed

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Define paths relative to the script location or project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
VECTOR_STORE_DIR = PROJECT_ROOT / "vector_store"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

class Orchestrator:
    """Manages the interaction flow, loading the LLM, tools, memory, and integrating RAG."""

    # Modified __init__ to accept optional settings
    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        """Initializes the Orchestrator, loading LLM, tools, memory, and setting up RAG chain or fallback agent.
        
        Args:
            settings (Optional[Dict[str, Any]]): Application settings dictionary. If None, loads from file.
        """
        logging.info("Initializing Orchestrator...")
        # Use provided settings or load from file
        self.settings = settings if settings is not None else load_settings()
        
        # TODO: Add logic here to select LLM based on self.settings["active_llm_provider"]
        # For now, it still uses the LLMLoader which relies on .env or defaults
        self.llm_loader = LLMLoader() 
        self.llm = self.llm_loader.load()

        if self.llm is None:
            logging.error("LLM failed to load. Orchestrator cannot function without an LLM.")
            self.agent = None
            self.rag_chain = None
            return

        self.tools = self._load_tools()
        self.retriever = None
        self.rag_chain = None
        self.agent = None # Initialize agent as None

        # --- RAG Setup --- 
        if RAG_ENABLED:
            try:
                logging.info("Attempting to initialize RAG components...")
                if not VECTOR_STORE_DIR.exists():
                    logging.warning(f"Vector store directory 	'{VECTOR_STORE_DIR}' not found. RAG will not function until the store is built.")
                else:
                    # Initialize embeddings (ensure this matches the builder)
                    embeddings = SentenceTransformerEmbeddings(model_name=EMBEDDING_MODEL_NAME)
                    # Load the persistent vector store
                    vector_store = Chroma(
                        persist_directory=str(VECTOR_STORE_DIR),
                        embedding_function=embeddings
                    )
                    self.retriever = vector_store.as_retriever(
                        search_type="similarity",
                        search_kwargs={"k": 3} # Retrieve top 3 relevant chunks
                    )
                    logging.info(f"Successfully loaded vector store from {VECTOR_STORE_DIR} and created retriever.")

                    # Define RAG Prompt Template
                    rag_prompt_template = """
                    You are an assistant for question-answering tasks. 
                    Use the following pieces of retrieved context to answer the question. 
                    If you don't know the answer, just say that you don't know. 
                    Use three sentences maximum and keep the answer concise.
                    
                    Context: {context}
                    
                    Question: {question}
                    
                    Answer:"""
                    rag_prompt = ChatPromptTemplate.from_template(rag_prompt_template)

                    # Define RAG Chain using LCEL
                    self.rag_chain = (
                        {"context": self.retriever, "question": RunnablePassthrough()}
                        | rag_prompt
                        | self.llm
                        | StrOutputParser()
                    )
                    logging.info("RAG chain initialized successfully.")

            except Exception as e:
                logging.error(f"Failed to initialize RAG components: {e}. RAG will be disabled.", exc_info=True)
                self.retriever = None
                self.rag_chain = None
        # --- End RAG Setup ---

        # --- Fallback Agent Setup (If RAG is disabled or failed) ---
        if self.rag_chain is None:
            logging.info("RAG is disabled or failed to initialize. Setting up standard conversational agent.")
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
            agent_kwargs = {
                "system_message": system_message,
                "extra_prompt_messages": [MessagesPlaceholder(variable_name="chat_history")] # Required for CONVERSATIONAL_REACT_DESCRIPTION
            }

            try:
                if not self.tools:
                    logging.warning("No tools were loaded. Agent will only use LLM knowledge.")
                
                self.agent = initialize_agent(
                    self.tools if self.tools else [],
                    self.llm,
                    agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
                    memory=self.memory,
                    agent_kwargs=agent_kwargs,
                    verbose=True,
                    handle_parsing_errors=True,
                    max_iterations=5 # Add max iterations to prevent loops
                )
                logging.info("Fallback conversational agent initialized successfully.")
            except Exception as e:
                logging.error(f"Failed to initialize fallback agent: {e}", exc_info=True)
                self.agent = None
        # --- End Fallback Agent Setup ---

        if self.rag_chain is None and self.agent is None:
            logging.error("CRITICAL: Failed to initialize both RAG chain and fallback agent. Orchestrator cannot process commands.")
        else:
             logging.info("Orchestrator initialized.")

    def _load_system_prompt(self) -> str:
        """Loads the system prompt from the path specified in settings or default."""
        custom_prompt_path_str = self.settings.get("system_prompt_path")
        default_prompt_path = PROJECT_ROOT / "config" / "prompts" / "system_prompt.txt"
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
                 # More generic default prompt
                 default_content = "You are a helpful AI assistant. Use the tools provided when necessary."
                 with open(prompt_path, "w", encoding="utf-8") as f:
                     f.write(default_content)
                 return default_content

            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logging.error(f"Failed to read or create system prompt file {prompt_path}: {e}. Using fallback prompt.")
            return "You are a helpful AI assistant."

    def _load_tools(self):
        """Dynamically loads tools decorated with @tool from the skills directory."""
        logging.info("Dynamically loading tools from skills directory...")
        tools_list = []
        skills_dir = PROJECT_ROOT / "src" / "skills"
        
        if not skills_dir.is_dir():
            logging.error(f"Skills directory not found at {skills_dir}. Cannot load tools.")
            return []

        for filepath in skills_dir.glob("*.py"):
            if filepath.name == "__init__.py":
                continue

            module_name = filepath.stem
            module_path = f"src.skills.{module_name}"
            
            try:
                logging.debug(f"Attempting to import module: {module_path}")
                module = importlib.import_module(module_path)
                logging.debug(f"Successfully imported module: {module_path}")

                for name, obj in inspect.getmembers(module):
                    if isinstance(obj, BaseTool):
                        logging.info(f"Found tool: {obj.name} in module {module_name}")
                        tools_list.append(obj)

            except ImportError as e:
                logging.error(f"Failed to import skill module {module_path}: {e}", exc_info=True)
            except Exception as e:
                logging.error(f"An unexpected error occurred while loading tools from {module_path}: {e}", exc_info=True)

        if not tools_list:
            logging.warning("No tools were discovered or loaded from the skills directory.")
        else:
            logging.info(f"Successfully discovered and loaded {len(tools_list)} tools: {[t.name for t in tools_list]}")
            
        return tools_list

    def route_command_stream(self, user_input: str) -> Iterator[str]:
        """Routes the user's command, yielding response chunks via streaming."""
        logging.info(f"Routing command (streaming): {user_input}")
        
        # Prioritize RAG chain if available and seems relevant
        if self.rag_chain and self.retriever: 
             is_question = "?" in user_input or user_input.lower().startswith(("what", "who", "where", "when", "why", "how", "explain", "tell me about"))
             if is_question:
                 logging.info("Input looks like a question, attempting RAG stream...")
                 try:
                     # Stream directly from the RAG chain
                     for chunk in self.rag_chain.stream(user_input):
                         yield chunk
                     return # Stop processing if RAG stream succeeded
                 except Exception as e:
                     error_msg = f"Error during RAG chain streaming: {e}"
                     logging.error(error_msg, exc_info=True)
                     yield f"\n[Error during RAG: {e}]\n" # Yield error chunk
                     # Fall through to agent if RAG fails
             else:
                 logging.info("Input does not look like a question, using standard agent stream.")

        # Fallback to standard agent stream if RAG is not used or fails
        if self.agent:
            logging.info("Using standard conversational agent stream...")
            try:
                # Agent stream yields dictionaries with steps and final response
                # We need to extract the actual response chunk
                for chunk in self.agent.stream({"input": user_input}):
                    # Check for final answer chunk (structure might vary by agent type)
                    if "output" in chunk:
                        yield chunk["output"]
                    # Optionally, yield intermediate steps if needed for debugging/UI
                    # elif "actions" in chunk:
                    #     yield f"\n[Action: {chunk['actions']}]\n"
                    # elif "intermediate_step" in chunk:
                    #     yield f"\n[Step: {chunk['intermediate_step']}]\n"
            except Exception as e:
                error_msg = f"Error during agent streaming: {e}"
                logging.error(error_msg, exc_info=True)
                yield f"\n[Sorry, I encountered an error while processing your request: {e}]\n"
        else:
            error_msg = "Neither RAG chain nor fallback agent is initialized. Cannot process command."
            logging.error(error_msg)
            yield f"\n[{error_msg}]\n"

# Example usage (for testing purposes)
if __name__ == "__main__":
    print("Testing Orchestrator with RAG integration and streaming (if available)...")
    try:
        # Test initialization with settings passed
        test_settings = load_settings()
        orchestrator = Orchestrator(settings=test_settings)
        
        if orchestrator.rag_chain or orchestrator.agent:
            print("Orchestrator initialized.")
            if orchestrator.rag_chain:
                print("RAG chain is active.")
            if orchestrator.agent:
                 print(f"Fallback agent is active with tools: {[tool.name for tool in orchestrator.tools]}")
            
            # Example command (requires LLM model and potentially vector store)
            command = "What is TARVIS?" # Should trigger RAG if store exists
            # command = "Calculate 5 * 12" # Should trigger agent tool
            print(f"\nSending command: {command}")
            print("Streaming response:")
            full_response = ""
            for chunk in orchestrator.route_command_stream(command):
                print(chunk, end="", flush=True) # Print chunk without newline
                full_response += chunk
            print("\n--- End of Stream ---")
            # print(f"\nFull reconstructed response: {full_response}")

        else:
            print("Orchestrator initialization failed. Check logs.")
    except Exception as e:
        print(f"\nError during Orchestrator test: {e}")
    print("\nOrchestrator test script finished.")

