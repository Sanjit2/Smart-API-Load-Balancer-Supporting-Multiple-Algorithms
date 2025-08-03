import socket
import os
import platform
import subprocess
import ssl
import time

SERVER_HOST = '127.0.0.1'
SERVER_PORT = 9000  
USE_SSL = True
SSL_CERT = 'ssl_certs/cert.pem'  
VERIFY_CERT = False

def open_url_in_browser(url):
    if platform.system() == "Linux":
        try:

            is_wsl = False
            try:
                with open('/proc/version', 'r') as f:
                    if 'microsoft' in f.read().lower():
                        is_wsl = True
            except:
                pass

            if is_wsl:
                try:
                    subprocess.run(['powershell.exe', '-Command', f'Start-Process "{url}"'], check=True)
                    print(f"Opened '{url}' using PowerShell (via WSL).")
                    return True
                except (subprocess.SubprocessError, FileNotFoundError):
                    try:
                        subprocess.run(['wslview', url], check=True)
                        print(f"Opened '{url}' using wslview.")
                        return True
                    except (subprocess.SubprocessError, FileNotFoundError):
                        print(f"Could not open browser in WSL. Please open '{url}' manually.")
                        return False
            else:
                subprocess.run(['xdg-open', url], check=True)
                print(f"Opened '{url}' using xdg-open.")
                return True
        except Exception as e:
            print(f"Error opening browser: {e}")
            print(f"Please open '{url}' manually in your browser.")
            return False
    elif platform.system() == "Windows":
        import webbrowser
        try:
            webbrowser.open_new_tab(url)
            print(f"Opened '{url}' in a new browser tab.")
            return True
        except webbrowser.Error:
            print(f"Could not open a web browser automatically on Windows.")
            return False
    else:
        print(f"Unsupported operating system for automatic browser opening. Please open '{url}' manually.")
        return False

def run_client():

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:

        if USE_SSL:

            ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            
            if VERIFY_CERT and os.path.exists(SSL_CERT):
                ssl_context.load_verify_locations(SSL_CERT)
                print(f"Using certificate for SSL verification: {SSL_CERT}")
            else:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                print("SSL certificate verification disabled")
            
 
            client_socket = ssl_context.wrap_socket(client_socket, server_hostname=SERVER_HOST)
            print("SSL enabled for connection")
        
        client_socket.connect((SERVER_HOST, SERVER_PORT))
        print(f"Connected to load balancer at {SERVER_HOST}:{SERVER_PORT}")

        client_socket.settimeout(5.0)

        while True:
            message = input("Enter message to send (or 'quit' to exit): ")
            if message.lower() == 'quit':
                break

            try:
                client_socket.setblocking(0) 
                while True:
                    try:
                        leftover = client_socket.recv(4096)
                        if not leftover or len(leftover) == 0:
                            break
                        print(f"Cleared leftover data: {leftover.decode()}")
                    except (socket.error, BlockingIOError):
                        break
            except Exception as e:
                print(f"Error clearing buffer: {e}")
            finally:
                client_socket.setblocking(1)  
                

            client_socket.sendall(message.encode())
            print(f"Sent message: {message}")
            
            time.sleep(0.2)

            try:
                client_socket.settimeout(5.0)  
                response = client_socket.recv(4096).decode()
                print(f"Received from server: {response}")

                if response.lower().startswith("http/1.1 302 found"):
                    lines = response.splitlines()
                    location_header = next((line for line in lines if line.lower().startswith("location:")), None)
                    if location_header:
                        url_to_open = location_header.split(":", 1)[1].strip()
                        print(f"Server requested redirection to: {url_to_open}")
                        open_url_in_browser(url_to_open)
                    else:
                        print("Received a redirect response but no Location header found.")
            except socket.timeout:
                print("Timeout waiting for server response.")
            
            time.sleep(0.5)

    except ConnectionRefusedError:
        print(f"Connection refused. Make sure the load balancer is running at {SERVER_HOST}:{SERVER_PORT}")
    except ssl.SSLError as e:
        print(f"SSL error: {e}")
        print("This could be due to certificate verification issues.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        client_socket.close()
        print("Connection closed.")

if __name__ == "__main__":
    run_client()