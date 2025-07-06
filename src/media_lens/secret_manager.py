"""Google Secret Manager integration for the Media Lens application.

This module provides a centralized way to retrieve secrets from Google Cloud Secret Manager
with proper error handling and fallback mechanisms.
"""

import os
import logging
from typing import Optional, Dict, Any

try:
    from google.cloud import secretmanager
    from google.api_core import exceptions as gcp_exceptions
    SECRET_MANAGER_AVAILABLE = True
except ImportError:
    SECRET_MANAGER_AVAILABLE = False
    secretmanager = None
    gcp_exceptions = None


class SecretManagerClient:
    """Client for retrieving secrets from Google Cloud Secret Manager."""
    
    def __init__(self, project_id: Optional[str] = None):
        """Initialize the Secret Manager client.
        
        Args:
            project_id: Google Cloud project ID. If None, will use GOOGLE_CLOUD_PROJECT
                       or SECRET_MANAGER_PROJECT_ID environment variables.
        """
        self.project_id = project_id or os.getenv('SECRET_MANAGER_PROJECT_ID') or os.getenv('GOOGLE_CLOUD_PROJECT')
        self.client = None
        self.logger = logging.getLogger(__name__)
        
        # Check if Secret Manager should be used
        self.use_secret_manager = os.getenv('USE_SECRET_MANAGER', 'true').lower() == 'true'
        
        if not self.use_secret_manager:
            self.logger.info("Secret Manager disabled via USE_SECRET_MANAGER environment variable")
            return
            
        if not SECRET_MANAGER_AVAILABLE:
            self.logger.warning("google-cloud-secret-manager not available, falling back to environment variables")
            return
            
        if not self.project_id:
            self.logger.warning("No project ID configured for Secret Manager")
            return
            
        try:
            self.client = secretmanager.SecretManagerServiceClient()
            self.logger.info(f"Secret Manager client initialized for project: {self.project_id}")
        except Exception as e:
            self.logger.error(f"Failed to initialize Secret Manager client: {e}")
            self.client = None
    
    def is_available(self) -> bool:
        """Check if Secret Manager is available and configured."""
        return self.client is not None and self.use_secret_manager
    
    def get_secret(self, secret_name: str, version: str = "latest") -> Optional[str]:
        """Retrieve a secret from Google Secret Manager.
        
        Args:
            secret_name: Name of the secret to retrieve
            version: Version of the secret to retrieve (default: "latest")
            
        Returns:
            Secret value as string, or None if not found or error occurred
        """
        if not self.is_available():
            self.logger.debug(f"Secret Manager not available, skipping secret: {secret_name}")
            return None
            
        try:
            name = f"projects/{self.project_id}/secrets/{secret_name}/versions/{version}"
            response = self.client.access_secret_version(request={"name": name})
            secret_value = response.payload.data.decode("UTF-8")
            self.logger.debug(f"Successfully retrieved secret: {secret_name}")
            return secret_value
            
        except gcp_exceptions.NotFound:
            self.logger.warning(f"Secret not found: {secret_name}")
            return None
        except gcp_exceptions.PermissionDenied:
            self.logger.error(f"Permission denied accessing secret: {secret_name}")
            return None
        except Exception as e:
            self.logger.error(f"Error retrieving secret {secret_name}: {e}")
            return None
    
    def get_secrets_batch(self, secret_names: Dict[str, str]) -> Dict[str, Optional[str]]:
        """Retrieve multiple secrets in batch.
        
        Args:
            secret_names: Dictionary mapping environment variable names to secret names
                         e.g., {"ANTHROPIC_API_KEY": "anthropic-api-key"}
            
        Returns:
            Dictionary mapping environment variable names to secret values
        """
        results = {}
        
        if not self.is_available():
            self.logger.debug("Secret Manager not available, returning empty results")
            return {key: None for key in secret_names.keys()}
        
        for env_var, secret_name in secret_names.items():
            results[env_var] = self.get_secret(secret_name)
            
        return results


# Global variable to track if secrets have been loaded
_secrets_loaded = False
_loaded_secrets_cache = {}

def load_secrets_from_gcp() -> Dict[str, Optional[str]]:
    """Load secrets from Google Cloud Secret Manager and set environment variables.
    
    This function retrieves commonly used secrets and sets them as environment variables
    if they're not already set. It's idempotent - subsequent calls will return cached results.
    
    Returns:
        Dictionary of loaded secrets
    """
    global _secrets_loaded, _loaded_secrets_cache
    
    # Return cached results if already loaded
    if _secrets_loaded:
        return _loaded_secrets_cache.copy()
    
    logger = logging.getLogger(__name__)
    
    # Define the secrets we need to load
    secrets_config = {
        "ANTHROPIC_API_KEY": "anthropic-api-key",
        "GOOGLE_API_KEY": "google-api-key",
        "FTP_HOSTNAME": "ftp-hostname",
        "FTP_USERNAME": "ftp-username",
        "FTP_PASSPHRASE": "ftp-passphrase",
        "FTP_PORT": "ftp-port",
        "FTP_IP_FALLBACK": "ftp-ip-fallback",
        "FTP_REMOTE_PATH": "ftp-remote-path",
    }
    
    # Initialize the Secret Manager client
    client = SecretManagerClient()
    
    # Load secrets
    loaded_secrets = {}
    
    if client.is_available():
        logger.info("Loading secrets from Google Cloud Secret Manager")
        secrets = client.get_secrets_batch(secrets_config)
        
        # Set environment variables for secrets that were successfully retrieved
        for env_var, secret_value in secrets.items():
            if secret_value is not None:
                # Only set if not already in environment (allows local override)
                if env_var not in os.environ:
                    os.environ[env_var] = secret_value
                    logger.debug(f"Set environment variable: {env_var}")
                else:
                    logger.debug(f"Environment variable already set: {env_var}")
                loaded_secrets[env_var] = secret_value
            else:
                logger.warning(f"Failed to load secret for: {env_var}")
                loaded_secrets[env_var] = None
    else:
        logger.info("Secret Manager not available, using environment variables only")
        # Return current environment values
        for env_var in secrets_config.keys():
            loaded_secrets[env_var] = os.getenv(env_var)
    
    # Cache the results and mark as loaded
    _loaded_secrets_cache = loaded_secrets.copy()
    _secrets_loaded = True
    
    return loaded_secrets


# Initialize secrets when module is imported (for web application)
if __name__ != "__main__":
    # Only auto-load in production/cloud environments
    if os.getenv('USE_SECRET_MANAGER', 'true').lower() == 'true':
        try:
            load_secrets_from_gcp()
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to auto-load secrets: {e}")