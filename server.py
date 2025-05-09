import socket
import threading
import time

def handle_client(client_socket, client_address):
    print(f"连接到客户端: {client_address}")
    while True:
        try:
            data = client_socket.recv(1024).decode('utf-8')
            if not data:
                break
            res = conpress_data(data)
            client_socket.sendall(res.encode('utf-8'))
        except Exception as e:
            print(f"Error: {e}")
            break
    client_socket.close()
    print(f"{client_address} 已断开连接")

def start_serve():
    # 创建TCP套接字
    _server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    _server_socket.bind(('0.0.0.0', 8888))
    _server_socket.listen(5)
    _server_socket.settimeout(1.0)

    print("服务器已启动，监听端口 8888...")
    
    while True:
        try:
            client_socket, client_address = _server_socket.accept()
            client_thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
            client_thread.daemon = True
            client_thread.start()
        except socket.timeout:
            continue
        except Exception as e:
            print(f"Error: {e}")
            break

def conpress_data(message):
    """
    处理接收到的数据
    """
    return f"处理完成: {message}"

if __name__ == "__main__":
    start_serve()