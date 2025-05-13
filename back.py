import socket
import threading
import time
import logging
import queue
import os
import sys
import yaml
import json

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 全局变量
client_socket = None
is_connected = False
socket_lock = threading.Lock()
send_queue = queue.Queue()
receive_queue = queue.Queue()

db_socket = None
db_connected = False

def load_config():
    # 首先尝试读取外部配置文件
    external_config = 'config.yaml'  # 与可执行文件同目录的配置文件
    if os.path.exists(external_config):
        with open(external_config, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)
    
    # 如果外部配置不存在，则使用打包的配置
    if getattr(sys, 'frozen', False):
        # 运行在打包环境
        base_path = sys._MEIPASS
    else:
        # 运行在开发环境
        base_path = os.path.dirname(__file__)
    
    config_path = os.path.join(base_path, 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def conpress_database(host='127.0.0.1', port=8889):
    """
    连接到数据库
    """
    global db_socket, db_connected
    try:
        # 创建TCP套接字
        db_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        db_socket.connect((host, port))
        db_connected = True
        
        # 启动发送线程

        # 启动接收线程
        
        logger.info(f"成功连接到服务器 {host}:{port}")
        return True
    except Exception as e:
        logger.error(f"连接服务器失败: {e}")
        if db_socket:
            db_socket.close()
        db_socket = None
        db_connected = False
        return False

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

def calculate_crc(data):
    """
    crc初始为0xFFFF，遍历data的每个字节，与crc异或运算作为新的crc
    - 如果crc的最低位为1，则将crc右移1位，并异或0xA001
    - 否则，将crc右移1位
    - 最后返回低字节在前，高字节在后的CRC
    """
    crc = 0xffff
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc = crc >> 1
    return crc.to_bytes(2, byteorder='little')

def send_data(data):
    """
    解析所有modbus帧发送到服务器
    """
    serial, slave_adress, function_code, start_address, quantity = data
    request = f'{int(slave_adress):02x} {int(function_code):02x} {int(start_address):04x} {int(quantity):04x}'
    request = bytes.fromhex(request)
    crc = calculate_crc(request)
    request += crc
    data = f"{serial}:{request.hex()}"
    send_queue.put(data)
    return data

def send_thread():
    """
    发送线程
    """
    global client_socket, is_connected
    while is_connected:
        try:
            data = send_queue.get(timeout=1)
            client_socket.sendall(data.encode('utf-8'))
            time.sleep(0.1)
        except queue.Empty:
            # 队列为空，继续循环
            continue
        except Exception as e:
            logger.error(f"发送失败: {e}")
            disconnect()
            break
        
def receive_thread():
    """
    接收线程，将接收的数据帧按字节存储到队列中
    """
    global client_socket, is_connected
    while is_connected:
        try:
            data = client_socket.recv(1024)
            if not data:
                logger.warning("服务器已断开连接")
                break
            
            # 记录接收到的数据
            logger.info(f"接收到数据: {data.hex(' ').upper()}")
            
            # 按字节依次存储到队列中
            for byte in data:
                # 直接存储整数值，而不是十六进制字符串
                receive_queue.put(byte)
        except Exception as e:
            logger.error(f"接收失败: {e}")
            disconnect()
            break

def init_serial():
    """
    初始化串口
    """
    global client_socket, is_connected
    config = load_config()
    serial_ports = config.get('serial_ports', [])
    if not serial_ports:
        logger.error("未找到串口配置信息")
        return False
    if not is_connected:
        logger.error("未连接到服务器")
        return False
    # 将列表序列化为JSON字符串
    serial_ports_json = json.dumps(serial_ports)
    # 发送JSON字符串
    client_socket.sendall(serial_ports_json.encode('utf-8'))
    
    return True

def get_complete_frames(receive_queue, number_of_frames=1):
    """获取完整的Modbus帧
    Args:
        receive_queue: 接收队列
        number_of_frames: 需要读取的帧数
    Returns:
        list: 完整帧的列表，每个元素为十六进制字符串
    """
    frames = []
    temp_bytes = []
    frame_size = 0
    collecting = False
    retry = 0

    if receive_queue.qsize() < 3:
        logger.warning(f"数据不足，当前队列长度: {receive_queue.qsize()} 字节")
        return None

    while len(frames) < number_of_frames:
        try:
            if not collecting:
                # 读取前3个字节
                if receive_queue.qsize() < 3:
                    break
                    
                for _ in range(3):
                    # 直接获取整数值
                    byte_val = receive_queue.get()
                    temp_bytes.append(byte_val)
                    
                # 计算完整帧大小
                data_length = temp_bytes[2]
                frame_size = 2 + 1 + data_length + 2  # 地址(1) + 功能码(1) + 长度(1) + 数据(n) + CRC(2)
                logger.info(f"帧大小: {frame_size} 字节 (数据长度: {data_length})")
                collecting = True
                
            # 继续收集剩余字节
            remaining_bytes = frame_size - len(temp_bytes)
            if receive_queue.qsize() < remaining_bytes:
                logger.info(f"等待更多数据，还需 {remaining_bytes} 字节")
                break
            
            for _ in range(remaining_bytes):
                # 直接获取整数值
                byte_val = receive_queue.get()
                temp_bytes.append(byte_val)
            
            # 组合完整帧
            if len(temp_bytes) == frame_size:
                # 将整数列表转换为字节
                frame_data = bytes(temp_bytes)
                # 获取格式化的十六进制字符串
                formatted_hex = ' '.join(f'{b:02X}' for b in frame_data)
                frames.append(formatted_hex)
                logger.info(f"获取到完整帧: {formatted_hex}")
                temp_bytes = []
                frame_size = 0
                collecting = False
                
        except Exception as e:
            logger.error(f"获取完整帧时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            retry += 1
            if retry >= 3:
                logger.error("重试次数过多，停止读取")
                break
            temp_bytes = []
            frame_size = 0
            collecting = False

    return frames

def get_front_json():
    """获取前端json数据"""
    data = 'COM 50', '1', '3', '2', '4'
    send_data(data)

# 使用示例
if __name__ == "__main__":
    # 连接服务器
    if connect_server():
        try:
            # 保持程序运行
            init_serial()
            while is_server_connected():
                time.sleep(1)
                get_front_json()

                # 获取完整帧
                frames = get_complete_frames(receive_queue, number_of_frames=1)
                print(f"获取到的完整帧: {frames}")

        finally:
            # 断开连接
            disconnect()
    else:
        print("连接服务器失败，程序退出")