import logging
import os
import socket
from pathlib import Path
import paramiko

import dotenv

from src.media_lens.common import get_project_root
from src.media_lens.storage_adapter import StorageAdapter


def upload_file(local_file: Path, remote_path: str):
    """
    Uploads a file to a remote server using SFTP or cloud storage.
    :param local_file: full path to the local file
    :param remote_path: relative path to the remote directory
    :return:
    """
    # Check if we're using cloud storage
    use_cloud = os.getenv('USE_CLOUD_STORAGE', 'false').lower() == 'true'
    
    if use_cloud:
        # When using cloud storage, we can make the file public via a web URL
        # or set up a Google Cloud CDN in front of the bucket
        storage = StorageAdapter()
        
        # If local_file is a Path object, convert to string to get the file name
        file_name = local_file.name if hasattr(local_file, 'name') else os.path.basename(str(local_file))
        
        # First, we need to read the file content
        if storage.file_exists(file_name):
            # File already exists in storage, nothing to do
            logging.info(f"File {file_name} already exists in cloud storage")
            return True
        else:
            # File doesn't exist in storage, need to read from local and upload
            with open(local_file, 'r') as f:
                content = f.read()
            
            # Upload to cloud storage
            storage.write_text(file_name, content)
            logging.info(f"File {file_name} uploaded to cloud storage")
            return True
    else:
        # Use traditional SFTP for non-cloud deployments
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
        remote_file = f'{remote_path}/{Path(local_file).name}'

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
