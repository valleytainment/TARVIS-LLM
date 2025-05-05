#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import logging
from pathlib import Path

# Langchain imports
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Define paths relative to the script location or project root
# Assuming this script is run from the project root (tarvis-audit)
PROJECT_ROOT = Path(__file__).parent.parent.parent
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "knowledge_base"
VECTOR_STORE_DIR = PROJECT_ROOT / "vector_store"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2" # A good default, downloads automatically

def build_vector_store():
    """Loads documents, splits them, creates embeddings, and indexes them in ChromaDB."""
    logging.info(f"Starting RAG build process...")
    logging.info(f"Knowledge base directory: {KNOWLEDGE_BASE_DIR}")
    logging.info(f"Vector store directory: {VECTOR_STORE_DIR}")

    if not KNOWLEDGE_BASE_DIR.exists() or not any(KNOWLEDGE_BASE_DIR.iterdir()):
        logging.warning(f"Knowledge base directory 	'{KNOWLEDGE_BASE_DIR}	' is empty or does not exist. No documents to index.")
        return

    try:
        # 1. Load Documents
        # Using DirectoryLoader with TextLoader for .txt files
        loader = DirectoryLoader(
            str(KNOWLEDGE_BASE_DIR),
            glob="**/*.txt", # Load only .txt files for now
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"},
            show_progress=True,
            use_multithreading=True # Can speed up loading if many files
        )
        documents = loader.load()
        if not documents:
            logging.warning("No documents loaded from the knowledge base directory.")
            return
        logging.info(f"Loaded {len(documents)} document(s).")

        # 2. Split Documents
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, # Adjust chunk size as needed
            chunk_overlap=200  # Adjust overlap as needed
        )
        texts = text_splitter.split_documents(documents)
        logging.info(f"Split documents into {len(texts)} chunks.")

        # 3. Create Embeddings
        logging.info(f"Initializing embedding model: {EMBEDDING_MODEL_NAME}")
        # This will download the model on first use if not cached
        embeddings = SentenceTransformerEmbeddings(model_name=EMBEDDING_MODEL_NAME)
        logging.info("Embedding model initialized.")

        # 4. Initialize ChromaDB and Index Documents
        logging.info(f"Initializing ChromaDB vector store at: {VECTOR_STORE_DIR}")
        # Ensure the directory exists
        VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)

        # Create or load the persistent vector store
        # Chroma.from_documents will create embeddings and index
        vector_store = Chroma.from_documents(
            documents=texts,
            embedding=embeddings,
            persist_directory=str(VECTOR_STORE_DIR)
        )
        logging.info(f"Vector store created/updated and persisted at {VECTOR_STORE_DIR}")
        logging.info("RAG build process completed successfully.")

    except Exception as e:
        logging.error(f"Error during RAG build process: {e}", exc_info=True)

if __name__ == "__main__":
    build_vector_store()

