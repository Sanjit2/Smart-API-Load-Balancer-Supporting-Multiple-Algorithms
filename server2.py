import socket
import threading
import time
import random
import requests
import json
from cachetools import TTLCache
from datetime import datetime

SEARCH_API_KEY = "Your Gemini Api Key"

active_connections = 0
connections_lock = threading.Lock()

request_count = 0
total_latency = 0.0
metrics_lock = threading.Lock()

search_cache = TTLCache(maxsize=100, ttl=600)

def perform_search(query):

    if query in search_cache:
        print(f"Cache hit for search: {query}")
        return search_cache[query]
    
    try:
        search_engine_id = "YOUR_SEARCH_ENGINE_ID"
        url = f"https://www.googleapis.com/customsearch/v1"
        params = {
            "key": SEARCH_API_KEY,
            "cx": search_engine_id,
            "q": query
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            results = []
            if "items" in data:
                for item in data["items"][:5]:  
                    results.append(f"Title: {item['title']}\nLink: {item['link']}\nSnippet: {item.get('snippet', 'No snippet')}\n")
            
            formatted_results = "\n".join(results) if results else "No results found."
            search_cache[query] = formatted_results
            return formatted_results
        else:
            return f"Search error: {response.status_code}"
    except Exception as e:
        print(f"Search error: {e}")
        return f"Search error: {str(e)}"

def handle_client(client_socket, address, port):
    """Handle a single client connection with added search functionality"""
    global active_connections, request_count, total_latency

    with connections_lock:
        active_connections += 1
        current_connections = active_connections

    try:
        print(f"Backend {port}: Handling connection from {address}")
        print(f"Backend {port}: Active connections: {current_connections}")

        while True:
            try:
                data = client_socket.recv(1024)
                if not data:
                    break

                message = data.decode().strip()
                print(f"Backend {port} received: {message}")
                
                start_time = time.time()
                response = ""

                if message.upper() == "STATUS":
                    with metrics_lock:
                        avg_latency = total_latency / request_count if request_count > 0 else 0
                        status_response = (
                            f"[Backend {port} Status] "
                            f"Active Connections: {current_connections}, "
                            f"Total Requests: {request_count}, "
                            f"Average Latency: {avg_latency:.4f}s"
                        )
                        client_socket.send(status_response.encode())
                        print(f"Backend {port} sent status: {status_response}")
                        continue

                elif message.lower().startswith("search "):
                    query = message[len("search "):].strip()
                    search_results = perform_search(query)
                    response = f"[From Backend {port}] Search results for '{query}':\n{search_results}"

                elif message.upper() == "GET TIME":
                    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
                    response = f"[From Backend {port}] The current time is: {current_time}"

                elif message.upper().startswith("UPPERCASE "):
                    text_to_upper = message[len("UPPERCASE "):]
                    response = f"[From Backend {port}] {text_to_upper.upper()}"

                elif message.lower().startswith("take me to "):
                    website_name = message[len("take me to "):].strip()
                    if website_name:
                        redirect_url = f"https://www.{website_name}.com"
                        response = f"HTTP/1.1 302 Found\r\nLocation: {redirect_url}\r\n\r\nYou will be redirected to {website_name}."
                        client_socket.send(response.encode())
                        print(f"Backend {port} sent redirect to: {redirect_url}")
                        continue
                    else:
                        response = f"[From Backend {port}] Please specify a website after 'take me to'."

                elif message.lower().startswith("open "):
                    url_to_open = message[len("open "):].strip()
                    if url_to_open.startswith("http://") or url_to_open.startswith("https://"):
                        response = f"HTTP/1.1 302 Found\r\nLocation: {url_to_open}\r\n\r\nRedirecting to {url_to_open}"
                        client_socket.send(response.encode())
                        print(f"Backend {port} sent redirect to: {url_to_open}")
                        continue
                    else:
                        response = f"[From Backend {port}] Invalid URL. Please include http:// or https://."

                else:
                    response = f"[From Backend {port}] You sent: {message}"

                if not message.lower().startswith("search "):
                    delay = 0.2 * current_connections + random.uniform(0, 0.05)
                    time.sleep(delay)
                    print(f"Added delay: {delay:.3f}s")

                client_socket.send(response.encode())
                end_time = time.time()
                latency = end_time - start_time

                with metrics_lock:
                    request_count += 1
                    total_latency += latency

                print(f"Backend {port} sent response (latency: {latency:.4f}s)")

            except Exception as e:
                print(f"Backend {port} error: {e}")
                break
    finally:
        with connections_lock:
            active_connections -= 1
            print(f"Backend {port}: Connection closed. Active connections: {active_connections}")

        client_socket.close()
        print(f"Backend {port}: Connection from {address} closed")

def handle_ping(client_socket, address, port):
    """Handle a health check ping"""
    try:
        data = client_socket.recv(4)
        if data == b"PING":
            with connections_lock:
                delay = 0.001 * active_connections
            time.sleep(delay)
            client_socket.send(b"PONG")
    finally:
        client_socket.close()

def start_backend_server(port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', port))
    server.listen(5)
    print(f"Enhanced backend server {port} listening on port {port}")
    print(f"Available commands:")
    print(f"  - search [query]: Search the web")
    print(f"  - STATUS: Get server status")
    print(f"  - GET TIME: Get current time")
    print(f"  - UPPERCASE [text]: Convert text to uppercase")
    print(f"  - take me to [site]: Redirect to website")

    try:
        while True:
            client_socket, address = server.accept()
            print(f"Backend {port}: New connection from {address}")

            client_thread = threading.Thread(
                target=handle_client,
                args=(client_socket, address, port)
            )
            client_thread.daemon = True
            client_thread.start()
    except KeyboardInterrupt:
        print(f"Backend {port}: Shutting down")
    finally:
        server.close()

if __name__ == "__main__":
    start_backend_server(8002)
