import socket
import threading
import time
import logging
import queue

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 全局变量
client_socket = None
is_connected = False
socket_lock = threading.Lock()
send_queue = queue.Queue()
receive_queue = queue.Queue()

def connect_server(host='127.0.0.1', port=8888):
    """
    连接到服务器
    
    Args:
        host: 服务器主机地址
        port: 服务器端口
    
    Returns:
        bool: 连接是否成功
    """
    global client_socket, is_connected
    
    try:
        # 创建TCP套接字
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((host, port))
        is_connected = True
        
        # 启动发送线程
        heartbeat_thread = threading.Thread(target=send_thread)
        heartbeat_thread.daemon = True
        heartbeat_thread.start()

        # 启动接收线程
        heartbeat_thread = threading.Thread(target=receive_thread)
        heartbeat_thread.daemon = True
        heartbeat_thread.start()
        
        logger.info(f"成功连接到服务器 {host}:{port}")
        return True
    except Exception as e:
        logger.error(f"连接服务器失败: {e}")
        if client_socket:
            client_socket.close()
        client_socket = None
        is_connected = False
        return False

def disconnect():
    """
    断开与服务器的连接
    """
    global client_socket, is_connected
    
    if client_socket:
        try:
            client_socket.close()
        except Exception as e:
            logger.error(f"关闭连接错误: {e}")
        finally:
            client_socket = None
            is_connected = False
            logger.info("已断开与服务器的连接")

def is_server_connected():
    """
    检查是否已连接到服务器
    
    Returns:
        bool: 是否已连接
    """
    return is_connected and client_socket is not None

def get_modbus(data):
    """
    将前端json请求转换为modbus帧
    """
    res = data
    return res

def send_data(data):
    """
    将前端json请求发送到服务器
    """
    res = get_modbus(data)
    client_socket.sendall(res.encode('utf-8'))

def send_thread():
    """
    发送线程
    """
    global client_socket, is_connected
    while is_connected:
        try:
            data = send_queue.get(timeout=1)
            client_socket.sendall(data.encode('utf-8'))
            time.sleep(1)
        except queue.Empty:
            # 队列为空，继续循环
            continue
        except Exception as e:
            logger.error(f"发送失败: {e}")
            disconnect()
            break
        
def receive_thread():
    """
    接收线程
    """
    global client_socket, is_connected
    while is_connected:
        try:
            data = client_socket.recv(1024)
            if not data:
                break
            receive_queue.put(data.decode('utf-8'))
        except Exception as e:
            logger.error(f"接收失败: {e}")
            disconnect()
            break

# 使用示例
if __name__ == "__main__":
    # 连接服务器
    if connect_server():
        try:
            # 保持程序运行
            while is_server_connected():
                cmd = input("请输入命令(0发送, 1接收): ")
                if cmd == '0':
                    data = input("请输入要发送的数据: ")
                    send_queue.put(data)
                elif cmd == '1':
                    if not receive_queue.empty():
                        res = receive_queue.get()
                        print(f"接收到数据: {res}")
                    else:
                        print("没有接收到数据")
                else:
                    print("无效命令")
        finally:
            # 断开连接
            disconnect()
    else:
        print("连接服务器失败，程序退出")