import datetime
import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, BinaryIO
from google.auth import default

# Import cloud storage conditionally
if os.getenv('USE_CLOUD_STORAGE', 'false').lower() == 'true':
    from google.cloud import storage

from src.media_lens.common import LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)

class StorageAdapter:
    """
    Storage adapter that abstracts file operations to work with either
    local file system or cloud storage.
    
    This adapter maintains the same directory structure and file naming
    conventions as the original application, but allows for switching
    between local and cloud storage backends.
    
    This class implements the singleton pattern to prevent multiple instances
    from being created, which can cause issues in cloud deployments.
    """
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Prevent multiple initializations
        if self._initialized:
            import traceback
            logger.warning(f"StorageAdapter.__init__() called on already initialized singleton. "
                         f"This is harmless but inefficient. Consider using StorageAdapter.get_instance() "
                         f"or the shared_storage from storage.py instead. Call stack:\n{traceback.format_stack()}")
            return
        
        self.bucket_name = os.getenv("GCP_STORAGE_BUCKET")
        self.use_cloud = os.getenv('USE_CLOUD_STORAGE', 'false').lower() == 'true'
        local_path = os.getenv('LOCAL_STORAGE_PATH', './working')
        self.local_root = Path(local_path)
        
        # Initialize directory manager
        from src.media_lens.directory_manager import DirectoryManager
        self.directory_manager = DirectoryManager(base_path="")

        logger.info(f"Using cloud storage: {self.use_cloud}")
        if self.use_cloud:
            logger.info(f"Cloud storage bucket: {self.bucket_name}")
        else:
            logger.info(f"Local storage path: {self.local_root}")

        # Initialize cloud storage client if needed
        if self.use_cloud:
            try:
                # Determine authentication method
                creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
                use_workload_identity = os.getenv('USE_WORKLOAD_IDENTITY', 'false').lower() == 'true'
                project_id = os.getenv('GOOGLE_CLOUD_PROJECT')

                # First try to use explicit service account file from the keys directory
                try:
                    # Check if credential file exists at the path provided by GOOGLE_APPLICATION_CREDENTIALS
                    if creds_path and os.path.isfile(creds_path):
                        logger.info(f"Using explicit credentials from {creds_path}")
                        from google.oauth2 import service_account
                        credentials = service_account.Credentials.from_service_account_file(creds_path)
                        self.client = storage.Client(credentials=credentials, project=project_id)
                    # If workload identity is enabled and no explicit credential file
                    elif use_workload_identity:
                        logger.info("Using workload identity (VM's service account)")
                        logger.info(f"Creating storage client with default credentials and project ID: {project_id}")
                        
                        # Add explicit environment variable for Google Application Default Credentials discovery
                        if 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ:
                            logger.info("GOOGLE_APPLICATION_CREDENTIALS not set, checking VM credential paths")
                            # Check common VM credential paths
                            for cred_path in [
                                "/var/run/secrets/cloud.google.com/service-account.json",
                                "/var/run/secrets/cloud.google.com/key.json",
                                "/var/google-cloud/auth/application_default_credentials.json",
                                "/etc/google/auth/application_default_credentials.json"
                            ]:
                                if os.path.exists(cred_path):
                                    logger.info(f"Found credentials at {cred_path}, setting GOOGLE_APPLICATION_CREDENTIALS")
                                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path
                                    break
                        
                        credentials, _ = default()
                        self.client = storage.Client(credentials=credentials, project=project_id)
                    else:
                        # If no explicit credentials and not using workload identity, try default client
                        logger.info("No explicit credentials found, trying default client")
                        self.client = storage.Client()
                except Exception as e:
                    logger.warning(f"Failed to create storage client: {str(e)}")
                    logger.warning("Searching for credential files in /app/keys directory")
                    
                    # Search for any JSON credential files in the keys directory
                    found_key = False
                    keys_dir = '/app/keys'
                    if os.path.isdir(keys_dir):
                        for filename in os.listdir(keys_dir):
                            if filename.endswith('.json'):
                                key_file = os.path.join(keys_dir, filename)
                                logger.info(f"Trying service account key file: {key_file}")
                                try:
                                    from google.oauth2 import service_account
                                    credentials = service_account.Credentials.from_service_account_file(key_file)
                                    self.client = storage.Client(credentials=credentials, project=project_id)
                                    found_key = True
                                    logger.info(f"Successfully authenticated with {key_file}")
                                    break
                                except Exception as key_error:
                                    logger.warning(f"Failed to use {key_file}: {str(key_error)}")
                    
                    if not found_key:
                        # Fall back to anonymous client as last resort
                        logger.warning("No valid service account keys found, falling back to anonymous client")
                        self.client = storage.Client(project="anonymous")

                # Create bucket if it doesn't exist (for emulator)
                try:
                    self.bucket = self.client.get_bucket(self.bucket_name)
                    logger.info(f"Using existing bucket: {self.bucket_name}")
                except Exception as e:
                    logger.error(f"Unable to access bucket {self.bucket_name}: {str(e)}")
                    self.bucket = self.client.create_bucket(self.bucket_name)
                    logger.info(f"Created bucket: {self.bucket_name}")
            except Exception as e:
                logger.error(f"Error initializing storage client: {str(e)}")
                # Fall back to local storage if cloud fails
                self.use_cloud = False
                logger.info("Falling back to local storage due to error")
        
        logger.info(f"Storage adapter initialized. Using cloud: {self.use_cloud}")
        self._initialized = True
    
    @classmethod
    def get_instance(cls):
        """
        Get the singleton instance of StorageAdapter.
        
        This is the preferred way to get a StorageAdapter instance.
        Direct instantiation using StorageAdapter() is deprecated but still works.
        """
        if cls._instance is None:
            cls._instance = cls.__new__(cls)
            cls._instance.__init__()
        return cls._instance
    
    @classmethod
    def reset_instance(cls):
        """
        Reset the singleton instance. This is primarily for testing purposes.
        
        Warning: This should only be used in tests as it can cause issues
        if multiple parts of the application hold references to the old instance.
        """
        cls._instance = None
        cls._initialized = False
    
    def write_text(self, path: Union[str, Path], content: str, encoding: str = "utf-8") -> str:
        """
        Write text content to a file.
        
        Args:
            path: Path to the file (relative to storage root)
            content: Text content to write
            encoding: Text encoding to use
            
        Returns:
            Full path to the created file
        """
        path_str = str(path)
        
        if self.use_cloud:
            blob = self.bucket.blob(path_str)
            blob.upload_from_string(content, content_type="text/plain")
            return f"gs://{self.bucket_name}/{path_str}"
        else:
            # Local file system
            local_path = self.local_root / path_str
            os.makedirs(local_path.parent, exist_ok=True)
            with open(local_path, 'w', encoding=encoding) as f:
                f.write(content)
            return str(local_path)
    
    def read_text(self, path: Union[str, Path], encoding: str = "utf-8") -> str:
        """
        Read text content from a file.
        
        Args:
            path: Path to the file (relative to storage root)
            encoding: Text encoding to use
            
        Returns:
            Text content of the file
        """
        path_str = str(path)
        
        if self.use_cloud:
            blob = self.bucket.blob(path_str)
            return blob.download_as_text(encoding=encoding)
        else:
            # Local file system
            local_path = self.local_root / path_str
            with open(local_path, 'r', encoding=encoding) as f:
                return f.read()
    
    def write_json(self, path: Union[str, Path], data: Any, indent: int = 2) -> str:
        """
        Write JSON data to a file.
        
        Args:
            path: Path to the file (relative to storage root)
            data: Data to serialize to JSON
            indent: Indentation level for pretty-printing
            
        Returns:
            Full path to the created file
        """
        json_str = json.dumps(data, indent=indent)
        return self.write_text(path, json_str)
    
    def read_json(self, path: Union[str, Path]) -> Any:
        """
        Read JSON data from a file.
        
        Args:
            path: Path to the file (relative to storage root)
            
        Returns:
            Parsed JSON data
        """
        content = self.read_text(path)
        return json.loads(content)
    
    def write_binary(self, path: Union[str, Path], content: bytes) -> str:
        """
        Write binary content to a file.
        
        Args:
            path: Path to the file (relative to storage root)
            content: Binary content to write
            
        Returns:
            Full path to the created file
        """
        path_str = str(path)
        
        if self.use_cloud:
            blob = self.bucket.blob(path_str)
            blob.upload_from_string(content)
            return f"gs://{self.bucket_name}/{path_str}"
        else:
            # Local file system
            local_path = self.local_root / path_str
            os.makedirs(local_path.parent, exist_ok=True)
            with open(local_path, 'wb') as f:
                f.write(content)
            return str(local_path)
    
    def read_binary(self, path: Union[str, Path]) -> bytes:
        """
        Read binary content from a file.
        
        Args:
            path: Path to the file (relative to storage root)
            
        Returns:
            Binary content of the file
        """
        path_str = str(path)
        
        if self.use_cloud:
            blob = self.bucket.blob(path_str)
            return blob.download_as_bytes()
        else:
            # Local file system
            local_path = self.local_root / path_str
            with open(local_path, 'rb') as f:
                return f.read()
    
    # Maintain backward compatibility with original methods
    def upload_file(self, local_path, remote_path):
        """Upload a file to storage (legacy method for compatibility)"""
        if self.use_cloud:
            blob = self.bucket.blob(remote_path)
            blob.upload_from_filename(local_path)
            return f"gs://{self.bucket_name}/{remote_path}"
        else:
            # For local testing, just copy the file to the destination
            dest_path = self.local_root / remote_path
            os.makedirs(dest_path.parent, exist_ok=True)
            with open(local_path, 'rb') as src_file, open(dest_path, 'wb') as dest_file:
                dest_file.write(src_file.read())
            return str(dest_path)
    
    def download_file(self, remote_path, local_path):
        """Download a file from storage (legacy method for compatibility)"""
        if self.use_cloud:
            blob = self.bucket.blob(remote_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            blob.download_to_filename(local_path)
        else:
            # For local testing, just copy from the source location
            src_path = self.local_root / remote_path
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(src_path, 'rb') as src_file, open(local_path, 'wb') as dest_file:
                dest_file.write(src_file.read())
    
    def list_files(self, prefix: str = "") -> List[str]:
        """List files in storage with the given prefix"""
        if self.use_cloud:
            return [blob.name for blob in self.bucket.list_blobs(prefix=prefix)]
        else:
            # For local testing, list files in the local directory
            path = self.local_root / prefix
            if not path.exists():
                return []
            
            files = []
            for p in Path(path).rglob('*'):
                if p.is_file():
                    rel_path = p.relative_to(self.local_root)
                    files.append(str(rel_path))
            return files

    def list_directories(self, prefix: str = "") -> List[str]:
        """List directories in storage with the given prefix"""
        if self.use_cloud:
            # For cloud storage, directories are implicit from file paths
            blobs = self.bucket.list_blobs(prefix=prefix)
            dirs = set()
            for blob in blobs:
                parts = blob.name.split('/')
                for i in range(1, len(parts)):
                    dir_path = '/'.join(parts[:i])
                    if dir_path.startswith(prefix):
                        dirs.add(dir_path)
            return sorted(list(dirs))
        else:
            # For local storage
            path = self.local_root / prefix
            if not path.exists():
                return []
            
            dirs = []
            for p in Path(path).rglob('*'):
                if p.is_dir():
                    rel_path = p.relative_to(self.local_root)
                    dirs.append(str(rel_path))
            return dirs
    
    def file_exists(self, path: Union[str, Path]) -> bool:
        """Check if a file exists in storage"""
        path_str = str(path)
        
        if self.use_cloud:
            blob = self.bucket.blob(path_str)
            return blob.exists()
        else:
            # Local file system
            local_path = self.local_root / path_str
            return local_path.exists()
    
    def get_file_modified_time(self, path: Union[str, Path]) -> Optional[datetime.datetime]:
        """
        Get the modification time of a file.
        
        Args:
            path: Path to the file (relative to storage root)
            
        Returns:
            Modification time as datetime object or None if file doesn't exist
        """
        path_str = str(path)
        
        try:
            if self.use_cloud:
                blob = self.bucket.blob(path_str)
                if blob.exists():
                    blob.reload()  # Refresh metadata
                    return blob.time_created  # Use creation time for cloud storage
                else:
                    return None
            else:
                # Local file system
                local_path = self.local_root / path_str
                if local_path.exists():
                    mtime = os.path.getmtime(local_path)
                    return datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc)
                else:
                    return None
        except Exception as e:
            logger.warning(f"Could not get modification time for {path_str}: {e}")
            return None
    
    def delete_file(self, path: Union[str, Path]) -> bool:
        """
        Delete a file from storage.
        
        Args:
            path: Path to the file (relative to storage root)
            
        Returns:
            True if file was deleted successfully, False otherwise
        """
        path_str = str(path)
        
        try:
            if self.use_cloud:
                blob = self.bucket.blob(path_str)
                if blob.exists():
                    blob.delete()
                    logger.debug(f"Deleted cloud file: {path_str}")
                    return True
                else:
                    logger.warning(f"Cloud file does not exist: {path_str}")
                    return False
            else:
                # Local file system
                local_path = self.local_root / path_str
                if local_path.exists() and local_path.is_file():
                    local_path.unlink()
                    logger.debug(f"Deleted local file: {local_path}")
                    return True
                else:
                    logger.warning(f"Local file does not exist: {local_path}")
                    return False
        except Exception as e:
            logger.error(f"Failed to delete file {path_str}: {e}")
            return False
    
    def delete_directory(self, path: Union[str, Path], recursive: bool = False) -> bool:
        """
        Delete a directory from storage.
        
        Args:
            path: Path to the directory (relative to storage root)
            recursive: If True, delete directory and all contents
            
        Returns:
            True if directory was deleted successfully, False otherwise
        """
        path_str = str(path)
        
        try:
            if self.use_cloud:
                # For cloud storage, delete all files with this prefix
                if recursive:
                    prefix = path_str.rstrip('/') + '/'
                    blobs = list(self.bucket.list_blobs(prefix=prefix))
                    if blobs:
                        for blob in blobs:
                            blob.delete()
                        logger.debug(f"Deleted cloud directory: {path_str} ({len(blobs)} files)")
                        return True
                    else:
                        logger.warning(f"Cloud directory is empty or does not exist: {path_str}")
                        return False
                else:
                    # Non-recursive - just delete the placeholder if it exists
                    placeholder = f"{path_str.rstrip('/')}/.placeholder"
                    blob = self.bucket.blob(placeholder)
                    if blob.exists():
                        blob.delete()
                        logger.debug(f"Deleted cloud directory placeholder: {path_str}")
                        return True
                    else:
                        logger.warning(f"Cloud directory placeholder does not exist: {path_str}")
                        return False
            else:
                # Local file system
                local_path = self.local_root / path_str
                if local_path.exists() and local_path.is_dir():
                    if recursive:
                        import shutil
                        shutil.rmtree(local_path)
                        logger.debug(f"Deleted local directory recursively: {local_path}")
                    else:
                        # Only delete if empty
                        local_path.rmdir()
                        logger.debug(f"Deleted empty local directory: {local_path}")
                    return True
                else:
                    logger.warning(f"Local directory does not exist: {local_path}")
                    return False
        except Exception as e:
            logger.error(f"Failed to delete directory {path_str}: {e}")
            return False
    
    def create_directory(self, path: Union[str, Path]) -> str:
        """
        Create a directory in storage.
        For cloud storage, this is a no-op as directories are implicit.
        For local storage, creates the directory.
        
        Args:
            path: Path to the directory (relative to storage root)
            
        Returns:
            Full path to the created directory
        """
        path_str = str(path)
        
        if self.use_cloud:
            # Directories don't exist in cloud storage, but we can create an
            # empty placeholder file to simulate directory creation
            placeholder = f"{path_str.rstrip('/')}/.placeholder"
            blob = self.bucket.blob(placeholder)
            blob.upload_from_string("")
            return f"gs://{self.bucket_name}/{path_str}"
        else:
            # Local file system
            local_path = self.local_root / path_str
            os.makedirs(local_path, exist_ok=True)
            return str(local_path)
    
    def get_files_by_pattern(self, path: Union[str, Path], pattern: str) -> List[str]:
        """
        Find files matching a glob pattern.
        
        Args:
            path: Base path to search in (relative to storage root)
            pattern: Glob pattern to match against
            
        Returns:
            List of matching file paths
        """
        path_str = str(path)
        
        if self.use_cloud:
            # Cloud storage doesn't have glob support, so we'll list all files
            # in the path and filter them manually
            all_files = self.list_files(path_str)
            
            # Convert glob pattern to regex pattern for matching
            import fnmatch
            regex_pattern = fnmatch.translate(pattern)
            import re
            matcher = re.compile(regex_pattern)
            
            # Filter files that match the pattern
            return [f for f in all_files if matcher.match(os.path.basename(f))]
        else:
            # Local file system has glob support
            local_path = self.local_root / path_str
            glob_files = list(local_path.glob(pattern))
            
            # Convert to relative paths
            return [str(f.relative_to(self.local_root)) for f in glob_files]
    
    def get_absolute_path(self, path: Union[str, Path]) -> str:
        """
        Get the absolute path or URI for a file in storage.
        
        Args:
            path: Path to the file (relative to storage root)
            
        Returns:
            Absolute path or URI to the file
        """
        path_str = str(path)
        
        if self.use_cloud:
            return f"gs://{self.bucket_name}/{path_str}"
        else:
            return str(self.local_root / path_str)
    
    def get_job_directory(self, timestamp: Optional[str] = None) -> str:
        """
        Get a job directory path in YYYY/MM/DD/HHmmss format.
        
        Args:
            timestamp: Optional timestamp string. If None, uses current time.
            
        Returns:
            Job directory path
        """
        return self.directory_manager.get_job_dir(timestamp)
    
    def get_intermediate_directory(self, subdir: str = "") -> str:
        """
        Get intermediate data directory path.
        
        Args:
            subdir: Optional subdirectory within intermediate
            
        Returns:
            Intermediate directory path
        """
        return self.directory_manager.get_intermediate_dir(subdir)
    
    def get_staging_directory(self, subdir: str = "") -> str:
        """
        Get staging directory path for website-ready files.
        
        Args:
            subdir: Optional subdirectory within staging
            
        Returns:
            Staging directory path
        """
        return self.directory_manager.get_staging_dir(subdir)
    
    def get_jobs_in_date_range(self, start_date: str, end_date: str) -> List[str]:
        """
        Get all job directories within a date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            List of job directory paths within the date range
        """
        return self.directory_manager.get_jobs_in_date_range(start_date, end_date, self)
    
    def get_directory_path(self, timestamp: str) -> str:
        """
        Get a timestamped directory path (deprecated - use get_job_directory).
        
        Args:
            timestamp: Timestamp string to use in the directory name
            
        Returns:
            Path to the directory
        """
        logger.warning("get_directory_path is deprecated, use get_job_directory instead")
        return self.get_job_directory(timestamp)