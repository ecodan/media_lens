import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, BinaryIO

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
    """
    def __init__(self):
        self.bucket_name = os.getenv("GCP_STORAGE_BUCKET", "media-lens-storage")
        self.use_cloud = os.getenv('USE_CLOUD_STORAGE', 'false').lower() == 'true'
        self.local_root = Path(os.getenv('LOCAL_STORAGE_PATH', str(Path.cwd() / "working/out")))
        
        if self.use_cloud:
            try:
                # Determine authentication method
                creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
                use_workload_identity = os.getenv('USE_WORKLOAD_IDENTITY', 'false').lower() == 'true'
                
                if use_workload_identity:
                    # Using workload identity (VM's service account)
                    logger.info("Using workload identity (VM's service account)")
                    self.client = storage.Client()
                elif creds_path and os.path.isfile(creds_path):
                    # Using explicit credentials file
                    logger.info(f"Using credentials from {creds_path}")
                    self.client = storage.Client()
                else:
                    # Try default credentials
                    logger.info(f"Using default credentials (no explicit config found)")
                    try:
                        self.client = storage.Client()
                    except Exception as e:
                        logger.warning(f"Failed to get default credentials: {str(e)}")
                        # Fall back to anonymous/unauthenticated client as last resort
                        logger.warning("Falling back to anonymous client - limited functionality")
                        self.client = storage.Client(project="anonymous")
                
                # Create bucket if it doesn't exist (for emulator)
                try:
                    self.bucket = self.client.get_bucket(self.bucket_name)
                except Exception as e:
                    logger.info(f"Bucket {self.bucket_name} doesn't exist, creating: {str(e)}")
                    self.bucket = self.client.create_bucket(self.bucket_name)
                    logger.info(f"Created bucket: {self.bucket_name}")
            except Exception as e:
                logger.error(f"Error initializing storage client: {str(e)}")
                # Fall back to local storage if cloud fails
                self.use_cloud = False
                logger.info("Falling back to local storage due to error")
        
        logger.info(f"Storage adapter initialized. Using cloud: {self.use_cloud}")
    
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
    
    def get_directory_path(self, timestamp: str) -> str:
        """
        Get a timestamped directory path.
        
        Args:
            timestamp: Timestamp string to use in the directory name
            
        Returns:
            Path to the directory
        """
        return timestamp