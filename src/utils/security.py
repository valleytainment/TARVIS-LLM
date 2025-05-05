#!/usr/bin/env python
# -*- coding: utf-8 -*-

import keyring
import logging
from typing import Optional

# Configure basic logging for security utilities
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - Security - %(message)s")

# Define a consistent service name for keyring
KEYRING_SERVICE_NAME = "tarvis_llm"

class SecureStorage:
    """Provides methods to securely store and retrieve API keys using the OS keyring."""

    @staticmethod
    def store_key(provider_name: str, api_key: str):
        """Stores an API key securely for a given provider.

        Args:
            provider_name: The name of the API provider (e.g., 'openai', 'deepseek').
            api_key: The API key string to store.
        """
        try:
            keyring.set_password(KEYRING_SERVICE_NAME, provider_name, api_key)
            # Corrected logging format
            logging.info(f"API key for provider '{provider_name}' stored successfully.")
        except Exception as e:
            # Corrected logging format
            logging.error(f"Failed to store API key for provider '{provider_name}': {e}", exc_info=True)
            # Re-raise or handle as appropriate for the application context
            raise RuntimeError(f"Could not store API key securely. Keyring backend might be missing or misconfigured. Error: {e}")

    @staticmethod
    def retrieve_key(provider_name: str) -> Optional[str]:
        """Retrieves an API key securely for a given provider.

        Args:
            provider_name: The name of the API provider (e.g., 'openai', 'deepseek').

        Returns:
            The retrieved API key string, or None if not found or an error occurs.
        """
        try:
            api_key = keyring.get_password(KEYRING_SERVICE_NAME, provider_name)
            if api_key:
                # Corrected logging format
                logging.debug(f"API key retrieved for provider '{provider_name}'")
                return api_key
            else:
                # Corrected logging format
                logging.info(f"No API key found stored for provider '{provider_name}'")
                return None
        except Exception as e:
            # Corrected logging format
            logging.error(f"Failed to retrieve API key for provider '{provider_name}': {e}", exc_info=True)
            # Depending on desired behavior, could return None or raise an error
            # Returning None might be safer for non-critical operations
            return None

    @staticmethod
    def delete_key(provider_name: str):
        """Deletes a stored API key for a given provider.

        Args:
            provider_name: The name of the API provider (e.g., 'openai', 'deepseek').
        """
        try:
            keyring.delete_password(KEYRING_SERVICE_NAME, provider_name)
            # Corrected logging format
            logging.info(f"API key for provider '{provider_name}' deleted successfully.")
        except keyring.errors.PasswordDeleteError:
            # Corrected logging format
            logging.warning(f"No API key found to delete for provider '{provider_name}'")
            # This is not necessarily an error, just means the key wasn't there
        except Exception as e:
            # Corrected logging format
            logging.error(f"Failed to delete API key for provider '{provider_name}': {e}", exc_info=True)
            raise RuntimeError(f"Could not delete API key securely. Keyring backend might be missing or misconfigured. Error: {e}")

# Example Usage (for testing purposes)
if __name__ == "__main__":
    try:
        print("Testing SecureStorage...")
        # Store a dummy key
        SecureStorage.store_key("test_provider", "dummy_api_key_12345")
        print("Stored key for test_provider.")

        # Retrieve the key
        retrieved_key = SecureStorage.retrieve_key("test_provider")
        print(f"Retrieved key for test_provider: {retrieved_key}")
        assert retrieved_key == "dummy_api_key_12345"

        # Retrieve a non-existent key
        non_existent_key = SecureStorage.retrieve_key("non_existent_provider")
        print(f"Retrieved key for non_existent_provider: {non_existent_key}")
        assert non_existent_key is None

        # Delete the key
        SecureStorage.delete_key("test_provider")
        print("Deleted key for test_provider.")

        # Verify deletion
        deleted_key = SecureStorage.retrieve_key("test_provider")
        print(f"Retrieved key for test_provider after deletion: {deleted_key}")
        assert deleted_key is None
        
        # Test deleting non-existent key (should not raise error)
        SecureStorage.delete_key("non_existent_provider")
        print("Attempted to delete non-existent key (should not error).")

        print("SecureStorage tests passed.")

    except Exception as main_exc:
        print(f"\nError during SecureStorage test: {main_exc}")
        print("Please ensure a keyring backend is installed and configured (e.g., SecretService, Windows Credential Manager, macOS Keychain).")
        print("You might need to install a backend like `keyrings.cryptfile` or `keyrings.osx` or configure `dbus`.")

