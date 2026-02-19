import os
import subprocess
import paramiko
from pathlib import Path

class SSHKeyManager:
    def __init__(self, user="pinky", ip="192.168.4.1"):
        self.user = user
        self.ip = ip
        self.key_path = Path.home() / ".ssh" / "id_rsa"
        self.pub_key_path = self.key_path.with_suffix(".pub")

    def check_local_key(self):
        """Checks if the local SSH key exists."""
        return self.key_path.exists() and self.pub_key_path.exists()

    def generate_local_key(self):
        """Generates a new SSH key pair if it doesn't exist."""
        if self.check_local_key():
            return True, "Key already exists."

        try:
            # Ensure .ssh directory exists
            self.key_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Generate key without passphrase
            subprocess.run(
                ["ssh-keygen", "-t", "rsa", "-b", "4096", "-f", str(self.key_path), "-N", ""],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            return True, "Key generated successfully."
        except subprocess.CalledProcessError as e:
            return False, f"Failed to generate key: {e.stderr.decode()}"
        except Exception as e:
            return False, f"Error generating key: {str(e)}"

    def transfer_key(self, password):
        """Transfers the public key to the remote robot using paramiko."""
        if not self.check_local_key():
            return False, "Local key not found. Please generate one first."

        try:
            # Read public key
            with open(self.pub_key_path, "r") as f:
                pub_key = f.read().strip()

            # Connect with password
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(self.ip, username=self.user, password=password, timeout=5)

            # Create .ssh directory and append key
            cmd = f"mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo '{pub_key}' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
            stdin, stdout, stderr = ssh.exec_command(cmd)
            
            exit_status = stdout.channel.recv_exit_status()
            ssh.close()

            if exit_status == 0:
                return True, "Key transferred successfully."
            else:
                return False, f"Remote command failed: {stderr.read().decode()}"

        except paramiko.AuthenticationException:
            return False, "Authentication failed. Wrong password?"
        except paramiko.SSHException as e:
            return False, f"SSH error: {str(e)}"
        except Exception as e:
            return False, f"Error transferring key: {str(e)}"

    def test_connection_without_password(self):
        """Tests if passwordless connection works."""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            # Attempt to connect without password (uses keys by default)
            ssh.connect(self.ip, username=self.user, timeout=5, look_for_keys=True)
            ssh.close()
            return True, "Connection successful."
        except paramiko.AuthenticationException:
            return False, "Authentication failed (Key not accepted?)."
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    def execute_remote_command(self, command, timeout=5):
        """Executes a command remotely and returns (success, output)."""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(self.ip, username=self.user, timeout=timeout, look_for_keys=True)
            
            stdin, stdout, stderr = ssh.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            ssh.close()
            
            if exit_status == 0:
                return True, output
            else:
                return False, error
        except Exception as e:
            return False, str(e)
