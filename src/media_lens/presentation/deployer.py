import datetime
import logging
import os
import socket
import tempfile
from pathlib import Path
from typing import List, Optional

import dotenv
import paramiko

from src.media_lens.common import LOGGER_NAME, get_project_root
from src.media_lens.storage import shared_storage

logger = logging.getLogger(LOGGER_NAME)


def get_deploy_cursor() -> Optional[datetime.datetime]:
    """
    Get the last deploy cursor timestamp from storage.

    Returns:
        Last deployed timestamp or None if no cursor exists
    """
    cursor_path = "deploy_cursor.txt"
    storage = shared_storage

    if storage.file_exists(cursor_path):
        try:
            cursor_str = storage.read_text(cursor_path).strip()
            return datetime.datetime.fromisoformat(cursor_str)
        except (ValueError, OSError) as e:
            logger.warning(f"Could not read deploy cursor: {e}")
            return None
    return None


def update_deploy_cursor(timestamp: datetime.datetime) -> None:
    """
    Update the deploy cursor with the latest deployed timestamp.

    Args:
        timestamp: The timestamp to set as the new cursor
    """
    cursor_path = "deploy_cursor.txt"
    storage = shared_storage

    try:
        storage.write_text(cursor_path, timestamp.isoformat())
        logger.info(f"Updated deploy cursor to {timestamp.isoformat()}")
    except Exception as e:
        logger.error(f"Failed to update deploy cursor: {e}")


def rewind_deploy_cursor(days: int) -> None:
    """
    Rewind the deploy cursor by a specified number of days.

    Args:
        days: Number of days to rewind the cursor
    """
    current_cursor = get_deploy_cursor()
    if current_cursor:
        new_cursor = current_cursor - datetime.timedelta(days=days)
        update_deploy_cursor(new_cursor)
        logger.info(
            f"Deploy cursor rewound by {days} days: {current_cursor.isoformat()} → {new_cursor.isoformat()}"
        )
    else:
        logger.warning("No deploy cursor found - cannot rewind")


def reset_deploy_cursor() -> None:
    """
    Reset the deploy cursor to force full deployment on next run.
    """
    cursor_path = "deploy_cursor.txt"
    storage = shared_storage

    try:
        if storage.file_exists(cursor_path):
            storage.delete_file(cursor_path)
            logger.info("Deploy cursor reset - next deploy will upload all files")
    except Exception as e:
        logger.error(f"Failed to reset deploy cursor: {e}")


def get_files_to_deploy(cursor: Optional[datetime.datetime] = None) -> List[str]:
    """
    Get list of files that need to be deployed since cursor timestamp.

    Args:
        cursor: Cursor timestamp (None means deploy all files)

    Returns:
        List of file paths that need deployment
    """
    storage = shared_storage
    staging_dir = storage.get_staging_directory()

    # Get all HTML files in staging directory
    all_files = storage.get_files_by_pattern(staging_dir, "*.html")

    if cursor is None:
        logger.info("No deploy cursor found - deploying all files")
        return all_files

    # Filter files by modification time
    files_to_deploy = []
    for file_path in all_files:
        try:
            file_mtime = storage.get_file_modified_time(file_path)
            if file_mtime is None:
                # If we can't get mtime, include the file to be safe
                logger.debug(
                    f"Could not get modification time for {file_path}, including to be safe"
                )
                files_to_deploy.append(file_path)
            elif file_mtime > cursor:
                files_to_deploy.append(file_path)
        except Exception as e:
            logger.debug(f"Could not get modification time for {file_path}: {e}")
            # If we can't get mtime, include the file to be safe
            files_to_deploy.append(file_path)

    logger.info(f"Found {len(files_to_deploy)} files to deploy since cursor")
    return files_to_deploy


def upload_html_content_from_storage(storage_path: str) -> bool:
    """
    Helper function to read HTML content from storage, create temp file, and upload it.

    Args:
        storage_path: Path to the file in storage

    Returns:
        bool: True if upload succeeded, False otherwise
    """
    # Get content from storage
    content = shared_storage.read_text(storage_path)

    # Extract the original filename from storage_path
    original_filename = Path(storage_path).name

    # Create temporary file and upload
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
        f.write(content)
        local_temp_path = f.name

    success = upload_file(local_file=Path(local_temp_path), target_filename=original_filename)

    # Clean up temp file
    os.unlink(local_temp_path)

    return success


def upload_file(local_file: Path, target_filename: Optional[str] = None):
    """
    Uploads a file to a remote server using SFTP.
    :param local_file: full path to the local file
    :param remote_path: relative path to the remote directory
    :param target_filename: optional filename to use for the uploaded file (defaults to local file name)
    :return:
    """

    # Get FTP credentials from environment or loaded secrets
    from src.media_lens.secret_manager import load_secrets_from_gcp

    loaded_secrets = load_secrets_from_gcp()

    hostname = os.getenv("FTP_HOSTNAME") or loaded_secrets.get("FTP_HOSTNAME")
    ip_fallback = os.getenv("FTP_IP_FALLBACK") or loaded_secrets.get("FTP_IP_FALLBACK")
    username = os.getenv("FTP_USERNAME") or loaded_secrets.get("FTP_USERNAME")
    key_file_path = os.getenv("FTP_SSH_KEY_FILE")  # SSH key file path
    port_str = os.getenv("FTP_PORT") or loaded_secrets.get("FTP_PORT")
    port: int = int(port_str) if port_str else 22

    remote_path_from_secrets = os.getenv("FTP_REMOTE_PATH") or loaded_secrets.get("FTP_REMOTE_PATH")
    logger.info(
        f"FTP credentials loaded: hostname: {hostname} | ip_fallback: {ip_fallback} | username: {username} | port: {port} | key_file_path: {key_file_path} | remote path {remote_path_from_secrets}"
    )

    try:
        connect_hostname = hostname
        logger.info(f"Attempting to connect to {connect_hostname} on port {port}")

        # Create SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Load Ed25519 key from file
        try:
            logger.debug("Loading Ed25519 key...")
            if not key_file_path:
                raise ValueError("FTP_SSH_KEY_FILE environment variable is not set")

            # Get passphrase from loaded secrets
            passphrase = os.getenv("FTP_PASSPHRASE") or loaded_secrets.get("FTP_PASSPHRASE")

            if passphrase:
                private_key = paramiko.Ed25519Key.from_private_key_file(
                    key_file_path, password=passphrase
                )
            else:
                private_key = paramiko.Ed25519Key.from_private_key_file(key_file_path)
        except Exception as e:
            logger.error(f"Error loading key: {e!s}")
            raise

        logger.debug("Key loaded successfully; establishing connection...")

        connection_error = None
        # Try with hostname first
        try:
            ssh.connect(
                hostname=connect_hostname,
                username=username,
                pkey=private_key,
                port=port,
                timeout=30,
                allow_agent=False,
                look_for_keys=False,
            )
        except socket.gaierror as e:
            connection_error = e
            # If we have an IP fallback and DNS resolution failed, try with the IP
            if ip_fallback and "nodename nor servname provided, or not known" in str(e):
                logger.warning(
                    f"DNS resolution failed for {connect_hostname}. Trying IP fallback: {ip_fallback}"
                )
                try:
                    ssh.connect(
                        hostname=ip_fallback,
                        username=username,
                        pkey=private_key,
                        port=port,
                        timeout=30,
                        allow_agent=False,
                        look_for_keys=False,
                    )
                    # If we successfully connected with IP, update connection_error to None
                    connection_error = None
                except Exception as ip_e:
                    logger.error(f"Failed to connect using IP fallback: {ip_e!s}")
                    # Keep the original error

        # If we still have an error, raise it
        if connection_error:
            raise connection_error

        logger.debug("Opening SFTP session...")
        sftp = ssh.open_sftp()
        logger.info(f"Connected to {hostname}")

        # Create remote directory if it doesn't exist
        try:
            sftp.stat(remote_path_from_secrets)
            logger.debug("Remote directory exists")
        except FileNotFoundError:
            logger.info(f"Creating remote directory: {remote_path_from_secrets}")
            # Create parent directories if they don't exist
            remote_path_parts = remote_path_from_secrets.strip("/").split("/")
            current_path = ""
            for part in remote_path_parts:
                current_path += "/" + part
                try:
                    sftp.stat(current_path)
                    logger.debug(f"Directory exists: {current_path}")
                except FileNotFoundError:
                    logger.info(f"Creating directory: {current_path}")
                    sftp.mkdir(current_path)
            logger.info("Created remote directory structure")

        # Construct remote file path
        filename = target_filename if target_filename else Path(local_file).name
        remote_file = f"{remote_path_from_secrets}/{filename}"

        # Upload the file
        logger.info(f"Uploading {local_file} to {remote_file}...")
        sftp.put(local_file, remote_file)
        logger.info(f"Successfully uploaded {local_file} to {remote_file}")

        # Close connections
        sftp.close()
        ssh.close()
        return True

    except paramiko.SSHException as e:
        logger.error(f"SSH/SFTP error: {e}")
        logger.error(f"Full error details: {e!s}")
        return False
    except Exception as e:
        logger.error(f"Error: {e!s}")
        logger.error(f"Error type: {type(e)}")
        return False


##################
# Test
def main():
    local: Path = get_project_root() / "working/out/medialens.html"
    upload_file(local_file=local)


if __name__ == "__main__":
    dotenv.load_dotenv()
    logging.basicConfig(level=logging.DEBUG)
    main()
