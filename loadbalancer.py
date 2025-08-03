import socket
import threading
import sys
import time
import uuid
import ssl

    
LB_HOST = '127.0.0.1'  
LB_PORT = 9000         

SSL_CERT = 'ssl_certs/cert.pem'
SSL_KEY = 'ssl_certs/key.pem'

USE_SSL = True
BACKEND_SERVERS = [   
    ('127.0.0.1', 8001),
    ('127.0.0.1', 8002)
]


current_server = 0

server_lock = threading.Lock()

active_connections_per_backend = {}
connections_lock = threading.Lock()

LOAD_BALANCING_ALGORITHM = "ROUND_ROBIN"  
connections = {}  
backend_response_times = {}
response_times_lock = threading.Lock()
HEALTH_CHECK_INTERVAL = 5
health_check_running = False

def initialize_connection_counter():
    """Initialize connection counters for all backend servers"""
    global active_connections_per_backend
    with connections_lock:
        for server in BACKEND_SERVERS:
            active_connections_per_backend[server] = 0
    print("Initialized connection counters for all backend servers")

def initialize_response_times():
    """Initialize response times for all backend servers"""
    global backend_response_times
    with response_times_lock:
        for server in BACKEND_SERVERS:
            backend_response_times[server] = float('inf') 
    print("Initialized response times for all backend servers")
    
def increment_connection_count(backend):
    """Increment the connection count for a backend server"""
    with connections_lock:
        active_connections_per_backend[backend] = active_connections_per_backend.get(backend, 0) + 1
        print(f"Incremented connection count for {backend} to {active_connections_per_backend[backend]}")

def decrement_connection_count(backend):
    """Decrement the connection count for a backend server"""
    with connections_lock:
        if backend in active_connections_per_backend and active_connections_per_backend[backend] > 0:
            active_connections_per_backend[backend] -= 1
            print(f"Decremented connection count for {backend} to {active_connections_per_backend[backend]}")

def get_next_server():

    if LOAD_BALANCING_ALGORITHM == "ROUND_ROBIN":
        return get_next_server_round_robin()
    elif LOAD_BALANCING_ALGORITHM == "LEAST_CONNECTIONS":
        return get_next_server_least_connections()
    elif LOAD_BALANCING_ALGORITHM == "LEAST_RESPONSE":
        return get_next_server_least_response()
    else:
      
        return get_next_server_round_robin()

def get_next_server_round_robin():
    global current_server
    with server_lock:  # Lock to ensure thread safety
        server = BACKEND_SERVERS[current_server]
        current_server = (current_server + 1) % len(BACKEND_SERVERS)
        print(f"Round robin selected server: {server}")
        return server

def get_next_server_least_connections():
    with connections_lock:
        connections = {server: active_connections_per_backend.get(server, 0) for server in BACKEND_SERVERS}
        
        min_connections = float('inf')
        selected_server = None
        
        for server, count in connections.items():
            if count < min_connections:
                min_connections = count
                selected_server = server
        
        print(f"Least connections selected server: {selected_server} (connections: {min_connections})")
        return selected_server if selected_server else BACKEND_SERVERS[0]

def get_next_server_least_response():

    with response_times_lock:
        min_response_time = float('inf')
        selected_server = None
        
        for server in BACKEND_SERVERS:
            if server in backend_response_times:
                response_time = backend_response_times[server]
                if response_time < min_response_time:
                    min_response_time = response_time
                    selected_server = server
        
        if selected_server:
            print(f"Least response time selected server: {selected_server} (response time: {min_response_time:.4f}s)")
            return selected_server
        else:
            return BACKEND_SERVERS[0]

def health_check_ping(server):
    host, port = server
    
    try:

        start_time = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2.0)

        sock.connect((host, port))

        sock.send(b"PING")

        response = sock.recv(4)

        if response:
            end_time = time.time()
            response_time = end_time - start_time

            with response_times_lock:
                old_time = backend_response_times.get(server, float('inf'))
                if old_time == float('inf'):

                    backend_response_times[server] = response_time
                else:
                    alpha = 0.3  
                    backend_response_times[server] = alpha * response_time + (0.7) * old_time
                
            print(f"Health check: {server} response time {response_time:.4f}s, avg: {backend_response_times[server]:.4f}s")
        else:
            print(f"Health check: {server} no response")
            with response_times_lock:
                backend_response_times[server] = backend_response_times.get(server, float('inf')) * 1.5
    
    except (socket.timeout, ConnectionRefusedError) as e:
        print(f"Health check: {server} failed - {str(e)}")
        with response_times_lock:
            backend_response_times[server] = float('inf')
    
    except Exception as e:
        print(f"Health check error for {server}: {e}")
    
    finally:
        try:
            sock.close()
        except:
            pass

def health_check_thread():
    global health_check_running
    
    while health_check_running:
        for server in BACKEND_SERVERS:
            health_check_ping(server)
        time.sleep(HEALTH_CHECK_INTERVAL)

def start_health_check():
    """Start the health check thread"""
    global health_check_running
    
    if not health_check_running:

        initialize_response_times()
        
        health_check_running = True
    
        health_thread = threading.Thread(target=health_check_thread)
        health_thread.daemon = True
        health_thread.start()
        
        print(f"Started health check thread (interval: {HEALTH_CHECK_INTERVAL}s)")

def stop_health_check():
    """Stop the health check thread"""
    global health_check_running
    health_check_running = False
    print("Stopped health check thread")

def forward_data(connection_id, source_socket, dest_socket, direction):

    try:

        if connection_id not in connections:
            print(f"{direction}: Connection {connection_id} no longer exists")
            return
            
        while True:
            try:
                source_socket.settimeout(0.5)
                
                data = source_socket.recv(1024)
                if not data:  
                    print(f"{direction}: Connection closed")
                    break
                
                if connection_id not in connections:
                    print(f"{direction}: Connection {connection_id} was closed while receiving")
                    break
                
                dest_socket.send(data)
                print(f"{direction}: {len(data)} bytes")
                
            except socket.timeout:
                if connection_id not in connections:
                    print(f"{direction}: Connection {connection_id} no longer exists (timeout check)")
                    break
                continue
                
            except Exception as e:
                print(f"Error in {direction}: {e}")
                break
                
    except Exception as e:
        print(f"Outer error in {direction}: {e}")
    finally:
        close_connection(connection_id)
            
def close_connection(connection_id):
    """Safely close a connection and clean up resources"""
    global connections
    
    conn_info = connections.pop(connection_id, None)
    if not conn_info:
        return  
        
    client_socket, backend_socket, backend_server = conn_info
    
    print(f"Closing connection {connection_id}")

    if LOAD_BALANCING_ALGORITHM == "LEAST_CONNECTIONS" and backend_server:
        decrement_connection_count(backend_server)
    
 
    try:
        if client_socket:
            client_socket.close()
    except Exception as e:
        print(f"Error closing client socket: {e}")
        
    try:
        if backend_socket:
            backend_socket.close()
    except Exception as e:
        print(f"Error closing backend socket: {e}")
        
    print(f"Connection {connection_id} closed")

def handle_client(client_socket, client_address):
    """
    Handle a new client connection
    client_socket: socket connected to the client
    client_address: client's address (IP, port)
    """
    global connections

    connection_id = str(uuid.uuid4())
    
    backend_socket = None
    backend_server = None
    
    try:
        backend_server = get_next_server()
        backend_host, backend_port = backend_server
        print(f"Connection {connection_id}: Forwarding from {client_address} to {backend_host}:{backend_port}")

        if LOAD_BALANCING_ALGORITHM == "LEAST_CONNECTIONS":
            increment_connection_count(backend_server)

        backend_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        backend_socket.connect((backend_host, backend_port))

        connections[connection_id] = (client_socket, backend_socket, backend_server)

        client_to_backend = threading.Thread(
            target=forward_data,
            args=(connection_id, client_socket, backend_socket, 
                  f"Connection {connection_id}: client {client_address} -> backend {backend_host}:{backend_port}")
        )
        client_to_backend.daemon = True
        
        backend_to_client = threading.Thread(
            target=forward_data,
            args=(connection_id, backend_socket, client_socket, 
                  f"Connection {connection_id}: backend {backend_host}:{backend_port} -> client {client_address}")
        )
        backend_to_client.daemon = True
        
        client_to_backend.start()
        backend_to_client.start()
        
    except Exception as e:
        print(f"Error setting up connection {connection_id}: {e}")
        
        if LOAD_BALANCING_ALGORITHM == "LEAST_CONNECTIONS" and backend_server:
            decrement_connection_count(backend_server)
        
        try:
            if client_socket:
                client_socket.close()
        except:
            pass
            
        try:
            if backend_socket:
                backend_socket.close()
        except:
            pass
        connections.pop(connection_id, None)

def start_load_balancer():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    ssl_context = None
    if USE_SSL:
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(certfile=SSL_CERT, keyfile=SSL_KEY)
        print(f"SSL enabled with certificate: {SSL_CERT}")
    
    try:
        server_socket.bind((LB_HOST, LB_PORT))
        server_socket.listen(5)
        print(f"Load balancer listening on {LB_HOST}:{LB_PORT}")
        print(f"Backend servers: {BACKEND_SERVERS}")
        print(f"Using {LOAD_BALANCING_ALGORITHM} algorithm")
        
        while True:

            client_socket, client_address = server_socket.accept()
            print(f"Accepted connection from {client_address}")
            
            if USE_SSL:
                try:
                    client_socket = ssl_context.wrap_socket(client_socket, server_side=True)
                    print(f"SSL handshake successful with {client_address}")
                except ssl.SSLError as e:
                    print(f"SSL handshake failed with {client_address}: {e}")
                    client_socket.close()
                    continue
            
            client_thread = threading.Thread(
                target=handle_client,
                args=(client_socket, client_address)
            )
            client_thread.daemon = True  
            client_thread.start()
            
    except KeyboardInterrupt:
        print("\nShutting down load balancer...")
        for connection_id in list(connections.keys()):
            close_connection(connection_id)
        if LOAD_BALANCING_ALGORITHM == "LEAST_RESPONSE":
            stop_health_check()
    finally:
        server_socket.close()

def show_algorithm_menu():
    """Show menu for algorithm selection"""
    print("\n=== TCP Load Balancer ===")
    print("Select load balancing algorithm:")
    print("1. Round Robin")
    print("2. Least Connections")
    print("3. Least Response Time")
    
    while True:
        choice = input("Enter your choice (1/2/3): ")
        if choice == "1":
            return "ROUND_ROBIN"
        elif choice == "2":
            return "LEAST_CONNECTIONS"
        elif choice == "3":
            return "LEAST_RESPONSE"
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")

if __name__ == "__main__":

    LOAD_BALANCING_ALGORITHM = show_algorithm_menu()

    if LOAD_BALANCING_ALGORITHM == "LEAST_CONNECTIONS":
        initialize_connection_counter()

    if LOAD_BALANCING_ALGORITHM == "LEAST_RESPONSE":
        start_health_check()

    start_load_balancer()