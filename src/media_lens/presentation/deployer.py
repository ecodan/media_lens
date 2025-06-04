import logging
import os
import socket
import tempfile
from pathlib import Path
import paramiko

import dotenv

from src.media_lens.common import get_project_root
from src.media_lens.storage import shared_storage


def upload_html_content_from_storage(storage_path: str, remote_path: str) -> None:
    """
    Helper function to read HTML content from storage, create temp file, and upload it.
    
    Args:
        storage_path: Path to the file in storage
        remote_path: Remote path for deployment
    """
    # Get content from storage
    content = shared_storage.read_text(storage_path)
    
    # Extract the original filename from storage_path
    original_filename = Path(storage_path).name
    
    # Create temporary file and upload
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
        f.write(content)
        local_temp_path = f.name
    
    upload_file(Path(local_temp_path), remote_path, original_filename)
    
    # Clean up temp file
    os.unlink(local_temp_path)


def upload_file(local_file: Path, remote_path: str, target_filename: str = None):
    """
    Uploads a file to a remote server using SFTP.
    :param local_file: full path to the local file
    :param remote_path: relative path to the remote directory
    :param target_filename: optional filename to use for the uploaded file (defaults to local file name)
    :return:
    """

    # Get FTP credentials
    hostname = os.getenv("FTP_HOSTNAME")
    # Check for IP fallback if hostname is set
    ip_fallback = os.getenv("FTP_IP_FALLBACK")
    username = os.getenv("FTP_USERNAME")
    key_path = os.getenv("FTP_KEY_PATH")
    port_str = os.getenv("FTP_PORT")
    port: int = int(port_str) if port_str else 22

    try:
        connect_hostname = hostname
        print(f"Attempting to connect to {connect_hostname} on port {port}")

        # Create SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Load Ed25519 key
        try:
            print("Loading Ed25519 key...")
            private_key = paramiko.Ed25519Key.from_private_key_file(key_path)
        except paramiko.ssh_exception.PasswordRequiredException:
            # passphrase = getpass("Enter private key passphrase: ")
            passphrase = os.getenv("FTP_PASSPHRASE")
            private_key = paramiko.Ed25519Key.from_private_key_file(key_path, password=passphrase)
        except Exception as e:
            print(f"Error loading key: {str(e)}")
            raise

        print("Key loaded successfully")
        print("Establishing connection...")

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
                look_for_keys=False
            )
        except socket.gaierror as e:
            connection_error = e
            # If we have an IP fallback and DNS resolution failed, try with the IP
            if ip_fallback and "nodename nor servname provided, or not known" in str(e):
                print(f"DNS resolution failed for {connect_hostname}. Trying IP fallback: {ip_fallback}")
                try:
                    ssh.connect(
                        hostname=ip_fallback,
                        username=username,
                        pkey=private_key,
                        port=port,
                        timeout=30,
                        allow_agent=False,
                        look_for_keys=False
                    )
                    # If we successfully connected with IP, update connection_error to None
                    connection_error = None
                except Exception as ip_e:
                    print(f"Failed to connect using IP fallback: {str(ip_e)}")
                    # Keep the original error
        
        # If we still have an error, raise it
        if connection_error:
            raise connection_error

        print("Opening SFTP session...")
        sftp = ssh.open_sftp()
        print(f"Connected to {hostname}")

        # Create remote directory if it doesn't exist
        try:
            sftp.stat(remote_path)
            print("Reports directory exists")
        except FileNotFoundError:
            print("Creating reports directory...")
            sftp.mkdir(remote_path)
            print("Created reports directory")

        # Construct remote file path
        filename = target_filename if target_filename else Path(local_file).name
        remote_file = f'{remote_path}/{filename}'

        # Upload the file
        print(f"Uploading {local_file} to {remote_file}...")
        sftp.put(local_file, remote_file)
        print(f"Successfully uploaded {local_file} to {remote_file}")

        # Close connections
        sftp.close()
        ssh.close()
        return True

    except paramiko.SSHException as e:
        print(f"SSH/SFTP error: {e}")
        print(f"Full error details: {str(e)}")
        return False
    except Exception as e:
        print(f"Error: {str(e)}")
        print(f"Error type: {type(e)}")
        return False



##################
# Test
def main():
    local: Path = get_project_root() / "working/out/medialens.html"
    remote: str = os.getenv("FTP_REMOTE_PATH")
    upload_file(local, remote)

if __name__ == '__main__':
    dotenv.load_dotenv()
    logging.basicConfig(level=logging.DEBUG)
    main()
