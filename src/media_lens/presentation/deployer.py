import logging
import os
from pathlib import Path
import paramiko

import dotenv

from src.media_lens.common import get_project_root


def upload_file(local_file: Path, remote_path: str):
    """
    Uploads a file to a remote server using SFTP.
    :param local_file: full path to the local file
    :param remote_path: relative path to the remote directory
    :return:
    """
    # Get FTP credentials
    hostname = os.getenv("FTP_HOSTNAME")
    username = os.getenv("FTP_USERNAME")
    key_path = os.getenv("FTP_KEY_PATH")
    port: int = int(os.getenv("FTP_PORT"))

    try:
        print(f"Attempting to connect to {hostname} on port {port}")

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

        ssh.connect(
            hostname=hostname,
            username=username,
            pkey=private_key,
            port=port,
            timeout=30,
            allow_agent=False,
            look_for_keys=False
        )

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
