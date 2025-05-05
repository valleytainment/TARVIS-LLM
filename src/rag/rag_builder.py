#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import logging
from pathlib import Path
import shutil # For removing old store

# Langchain imports - handle potential import errors
try:
    from langchain_community.document_loaders import DirectoryLoader, TextLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_community.vectorstores import Chroma
    IMPORT_SUCCESS = True
except ImportError as e:
    logging.error(f"Failed to import necessary LangChain components for RAG building: {e}")
    IMPORT_SUCCESS = False

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - RAG Builder - %(message)s")

# Define paths relative to the script location (assuming src/rag/rag_builder.py)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent # Should point to tarvis-audit/
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "knowledge_base"
VECTOR_STORE_DIR = PROJECT_ROOT / "vector_store"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

def build_vector_store():
    """Loads documents, splits them, generates embeddings, and saves to ChromaDB."""
    if not IMPORT_SUCCESS:
        logging.error("Cannot build vector store due to missing dependencies.")
        return False

    logging.info("Starting vector store build process...")

    # --- 1. Check and Create Knowledge Base Directory ---
    if not KNOWLEDGE_BASE_DIR.exists():
        logging.warning(f"Knowledge base directory 	'{KNOWLEDGE_BASE_DIR}' not found. Creating it.")
        try:
            KNOWLEDGE_BASE_DIR.mkdir(parents=True, exist_ok=True)
            # Add a placeholder file if the directory was just created and is empty
            placeholder_file = KNOWLEDGE_BASE_DIR / "placeholder.txt"
            if not any(KNOWLEDGE_BASE_DIR.iterdir()): # Check if directory is empty
                 with open(placeholder_file, "w") as f:
                     f.write("Please add your knowledge base documents (e.g., .txt, .md) to this directory.")
                 logging.info(f"Created placeholder file in empty knowledge base directory: {placeholder_file}")
        except Exception as e:
            logging.error(f"Failed to create knowledge base directory: {e}")
            return False
    elif not any(KNOWLEDGE_BASE_DIR.iterdir()):
         logging.warning(f"Knowledge base directory 	'{KNOWLEDGE_BASE_DIR}' is empty. Vector store will be empty.")
         # Optionally, create placeholder if it doesn't exist even if dir exists
         placeholder_file = KNOWLEDGE_BASE_DIR / "placeholder.txt"
         if not placeholder_file.exists():
              with open(placeholder_file, "w") as f:
                  f.write("Please add your knowledge base documents (e.g., .txt, .md) to this directory.")
              logging.info(f"Created placeholder file in empty knowledge base directory: {placeholder_file}")

    # --- 2. Load Documents ---
    logging.info(f"Loading documents from: {KNOWLEDGE_BASE_DIR}")
    try:
        # Use DirectoryLoader with glob to support multiple types, ensure recursive
        # Using TextLoader explicitly for .txt as a fallback example if needed
        loader = DirectoryLoader(
            str(KNOWLEDGE_BASE_DIR),
            glob="**/*[.txt|.md]", # Load .txt and .md files recursively
            loader_cls=TextLoader, # Specify loader for matched files
            use_multithreading=True, # Speed up loading
            show_progress=True,
            silent_errors=True # Log errors but don't stop
        )
        documents = loader.load()
        if not documents:
            logging.warning("No documents loaded from the knowledge base directory. Vector store will be empty or may fail.")
            # Decide if we should proceed with an empty store or stop
            # Proceeding for now, Chroma might handle empty input gracefully

    except Exception as e:
        logging.error(f"Failed to load documents: {e}", exc_info=True)
        return False

    # --- 3. Split Documents ---
    logging.info(f"Splitting {len(documents)} documents into chunks...")
    try:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, 
            chunk_overlap=150, # Increased overlap slightly
            length_function=len
        )
        chunks = text_splitter.split_documents(documents)
        if not chunks:
             logging.warning("No text chunks generated after splitting. Vector store will be empty.")
        logging.info(f"Split documents into {len(chunks)} chunks.")
    except Exception as e:
        logging.error(f"Failed to split documents: {e}", exc_info=True)
        return False

    # --- 4. Initialize Embeddings ---
    logging.info(f"Initializing embedding model: {EMBEDDING_MODEL_NAME}")
    try:
        # This step might download the model if not cached
        embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
    except Exception as e:
        logging.error(f"Failed to initialize embedding model: {e}. Ensure sentence-transformers is installed and model is accessible.", exc_info=True)
        return False

    # --- 5. Create/Update Vector Store ---
    logging.info(f"Building Chroma vector store at: {VECTOR_STORE_DIR}")
    try:
        # Remove old store directory if it exists to ensure a fresh build
        if VECTOR_STORE_DIR.exists():
            logging.info(f"Removing existing vector store at {VECTOR_STORE_DIR}...")
            shutil.rmtree(VECTOR_STORE_DIR)
        
        # Create the vector store from documents
        # Chroma.from_documents handles the embedding process internally
        if chunks: # Only build if there are chunks
            vector_store = Chroma.from_documents(
                documents=chunks,
                embedding=embeddings,
                persist_directory=str(VECTOR_STORE_DIR)
            )
            vector_store.persist() # Ensure data is saved
            logging.info("Successfully built and persisted vector store.")
        else:
            # Create the directory anyway so the app doesn't complain about it missing
            VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
            logging.info("Vector store directory created, but it is empty as no document chunks were processed.")
            
    except Exception as e:
        logging.error(f"Failed to build or persist vector store: {e}", exc_info=True)
        return False

    logging.info("Vector store build process completed successfully.")
    return True

if __name__ == "__main__":
    # Make the script runnable directly for testing or manual builds
    if build_vector_store():
        print("\nVector store build process finished successfully.")
    else:
        print("\nVector store build process failed. Check logs for details.")

