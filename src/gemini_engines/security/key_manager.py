"""
Secure API Key Management with OS keyring integration
Provides secure storage and retrieval of sensitive API keys
"""
import os
import logging
from typing import Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import keyring for secure storage
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    logger.warning("keyring library not available - falling back to environment variables")


class SecureKeyManager:
    """
    Manages API keys with OS-level secure storage when available.
    Falls back to environment variables or .env file if keyring unavailable.
    """
    
    SERVICE_NAME = "gemini-mcp"
    PRIMARY_KEY_NAME = "GOOGLE_API_KEY"
    SECONDARY_KEY_NAME = "GOOGLE_API_KEY2"
    
    def __init__(self, use_keyring: bool = True):
        """
        Initialize key manager.
        
        Args:
            use_keyring: Whether to attempt using OS keyring (default True)
        """
        # Disable keyring if running in MCP mode to avoid logging issues
        import sys
        is_mcp_mode = not sys.stdin.isatty()
        self.use_keyring = use_keyring and KEYRING_AVAILABLE and not is_mcp_mode
        self._env_file_path = Path(".env")
        
        if self.use_keyring:
            logger.info("Using OS keyring for secure API key storage")
        else:
            logger.info("Using environment variables for API key storage")
    
    def get_api_key(self, key_name: str = PRIMARY_KEY_NAME) -> Optional[str]:
        """
        Retrieve API key from secure storage or environment.
        
        Args:
            key_name: Name of the key to retrieve
            
        Returns:
            API key string or None if not found
        """
        # Try keyring first if available
        if self.use_keyring:
            try:
                key = keyring.get_password(self.SERVICE_NAME, key_name)
                if key:
                    logger.debug(f"Retrieved {key_name} from keyring")
                    return key
            except Exception as e:
                logger.warning(f"Failed to retrieve from keyring: {e}")
        
        # Fall back to environment variable
        key = os.environ.get(key_name)
        if key:
            logger.debug(f"Retrieved {key_name} from environment")
            return key
        
        # Try .env file as last resort
        key = self._read_from_env_file(key_name)
        if key:
            logger.debug(f"Retrieved {key_name} from .env file")
            return key
        
        return None
    
    def get_all_api_keys(self) -> List[str]:
        """
        Get all available API keys (primary and secondary).
        
        Returns:
            List of available API keys
        """
        keys = []
        
        primary = self.get_api_key(self.PRIMARY_KEY_NAME)
        if primary:
            keys.append(primary)
        
        secondary = self.get_api_key(self.SECONDARY_KEY_NAME)
        if secondary:
            keys.append(secondary)
        
        if not keys:
            raise ValueError(
                f"No API keys found. Please set {self.PRIMARY_KEY_NAME} "
                f"in environment variables, .env file, or OS keyring"
            )
        
        return keys
    
    def store_api_key(self, key_value: str, key_name: str = PRIMARY_KEY_NAME) -> bool:
        """
        Store API key in secure storage (keyring if available).
        
        Args:
            key_value: The API key to store
            key_name: Name to store the key under
            
        Returns:
            True if stored successfully, False otherwise
        """
        if not key_value:
            logger.error("Cannot store empty API key")
            return False
        
        if self.use_keyring:
            try:
                keyring.set_password(self.SERVICE_NAME, key_name, key_value)
                logger.info(f"Stored {key_name} in OS keyring")
                
                # Remove from .env file if it exists (to avoid confusion)
                self._remove_from_env_file(key_name)
                return True
            except Exception as e:
                logger.error(f"Failed to store in keyring: {e}")
                return False
        else:
            logger.warning("Keyring not available - please set API key in environment variables")
            return False
    
    def delete_api_key(self, key_name: str = PRIMARY_KEY_NAME) -> bool:
        """
        Delete API key from secure storage.
        
        Args:
            key_name: Name of the key to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        if self.use_keyring:
            try:
                keyring.delete_password(self.SERVICE_NAME, key_name)
                logger.info(f"Deleted {key_name} from keyring")
                return True
            except Exception as e:
                logger.warning(f"Failed to delete from keyring: {e}")
                return False
        return False
    
    def _read_from_env_file(self, key_name: str) -> Optional[str]:
        """Read API key from .env file if it exists."""
        if not self._env_file_path.exists():
            return None
        
        try:
            with open(self._env_file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(f"{key_name}="):
                        # Extract value after the equals sign
                        value = line[len(key_name) + 1:].strip()
                        # Remove quotes if present
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        return value
        except Exception as e:
            logger.warning(f"Error reading .env file: {e}")
        
        return None
    
    def _remove_from_env_file(self, key_name: str):
        """Remove API key from .env file to avoid confusion."""
        if not self._env_file_path.exists():
            return
        
        try:
            with open(self._env_file_path, 'r') as f:
                lines = f.readlines()
            
            with open(self._env_file_path, 'w') as f:
                for line in lines:
                    if not line.strip().startswith(f"{key_name}="):
                        f.write(line)
            
            logger.info(f"Removed {key_name} from .env file (now using keyring)")
        except Exception as e:
            logger.warning(f"Error updating .env file: {e}")
    
    def migrate_to_keyring(self) -> bool:
        """
        Migrate API keys from environment/.env to OS keyring.
        
        Returns:
            True if migration successful, False otherwise
        """
        if not self.use_keyring:
            logger.error("Keyring not available for migration")
            return False
        
        success = True
        
        # Migrate primary key
        primary = os.environ.get(self.PRIMARY_KEY_NAME) or self._read_from_env_file(self.PRIMARY_KEY_NAME)
        if primary:
            if self.store_api_key(primary, self.PRIMARY_KEY_NAME):
                logger.info(f"Migrated {self.PRIMARY_KEY_NAME} to keyring")
            else:
                success = False
        
        # Migrate secondary key
        secondary = os.environ.get(self.SECONDARY_KEY_NAME) or self._read_from_env_file(self.SECONDARY_KEY_NAME)
        if secondary:
            if self.store_api_key(secondary, self.SECONDARY_KEY_NAME):
                logger.info(f"Migrated {self.SECONDARY_KEY_NAME} to keyring")
            else:
                success = False
        
        if success:
            logger.info("""
╔══════════════════════════════════════════════════════════════════╗
║                    API KEY MIGRATION COMPLETE                     ║
║                                                                    ║
║  Your API keys have been securely stored in the OS keyring.      ║
║  You can now remove them from your .env file and environment.    ║
║                                                                    ║
║  To retrieve: keyring get gemini-mcp GOOGLE_API_KEY              ║
║  To delete:   keyring del gemini-mcp GOOGLE_API_KEY              ║
╚══════════════════════════════════════════════════════════════════╝
            """)
        
        return success


# Global instance for easy access
_key_manager: Optional[SecureKeyManager] = None


def get_key_manager() -> SecureKeyManager:
    """Get or create the global key manager instance."""
    global _key_manager
    if _key_manager is None:
        _key_manager = SecureKeyManager()
    return _key_manager


def get_api_keys() -> List[str]:
    """Convenience function to get all API keys."""
    return get_key_manager().get_all_api_keys()