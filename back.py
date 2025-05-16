import socket
import threading
import time
import queue
import os
import sys
import yaml
import json

from Logger import logger
from process_data import DataProcessor

# 全局变量
client_socket = None
is_connected = False
db_socket = None
db_connected = False
socket_lock = threading.Lock()

# 队列
send_queue = queue.Queue()         # 服务器发送队列
receive_queue = queue.Queue()      # 服务器接收队列
data_send_queue = queue.Queue()    # 数据库发送队列
data_receive_queue = queue.Queue() # 数据库接收队列

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

def tcp_send_thread(socket_obj, connected_flag, queue_obj, conn_type="服务器"):
    """
    通用TCP发送线程
    
    Args:
        socket_obj: Socket对象引用
        connected_flag: 连接状态标志引用
        queue_obj: 消息队列
        conn_type: 连接类型描述
    """
    while globals()[connected_flag]:
        try:
            data = queue_obj.get(timeout=1)
            globals()[socket_obj].sendall(data.encode('utf-8'))
            time.sleep(0.1)
        except queue.Empty:
            # 队列为空，继续循环
            continue
        except Exception as e:
            logger.error(f"{conn_type}发送失败: {e}")
            disconnect_socket(socket_obj, connected_flag)
            break

def tcp_receive_thread(socket_obj, connected_flag, queue_obj, conn_type="服务器"):
    """
    通用TCP接收线程
    
    Args:
        socket_obj: Socket对象引用
        connected_flag: 连接状态标志引用
        queue_obj: 消息队列
        conn_type: 连接类型描述
    """
    while globals()[connected_flag]:
        try:
            data_str = globals()[socket_obj].recv(1024).decode('utf-8')
            data = json.loads(data_str)
            if not data:
                logger.warning(f"{conn_type}已断开连接")
                break
            
            # 记录接收到的数据
            logger.info(f"接收到{conn_type}数据: {data}")
            
            queue_obj.put(data)
        except Exception as e:
            logger.error(f"{conn_type}接收失败: {e}")
            disconnect_socket(socket_obj, connected_flag)
            break

def connect_tcp(host, port, socket_obj, connected_flag, send_queue, receive_queue, conn_type="服务器"):
    """
    通用TCP连接函数
    
    Args:
        host: 服务器主机地址
        port: 服务器端口
        socket_obj: Socket变量名（字符串）
        connected_flag: 连接状态标志变量名（字符串）
        send_queue: 发送队列
        receive_queue: 接收队列
        conn_type: 连接类型描述
    
    Returns:
        bool: 连接是否成功
    """
    try:
        # 创建TCP套接字
        new_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        new_socket.connect((host, port))
        globals()[socket_obj] = new_socket
        globals()[connected_flag] = True
        
        # 启动发送线程
        send_thread_obj = threading.Thread(
            target=tcp_send_thread, 
            args=(socket_obj, connected_flag, send_queue, conn_type)
        )
        send_thread_obj.daemon = True
        send_thread_obj.start()

        # 启动接收线程
        receive_thread_obj = threading.Thread(
            target=tcp_receive_thread, 
            args=(socket_obj, connected_flag, receive_queue, conn_type)
        )
        receive_thread_obj.daemon = True
        receive_thread_obj.start()
        
        logger.info(f"成功连接到{conn_type} {host}:{port}")
        return True
    except Exception as e:
        logger.error(f"连接{conn_type}失败: {e}")
        if globals().get(socket_obj):
            globals()[socket_obj].close()
        globals()[socket_obj] = None
        globals()[connected_flag] = False
        return False

def disconnect_socket(socket_obj, connected_flag):
    """
    断开与服务器的连接
    
    Args:
        socket_obj: Socket变量名（字符串）
        connected_flag: 连接状态标志变量名（字符串）
    """
    if globals().get(socket_obj):
        try:
            globals()[socket_obj].close()
        except Exception as e:
            logger.error(f"关闭连接错误: {e}")
        finally:
            globals()[socket_obj] = None
            globals()[connected_flag] = False
            logger.info(f"已断开连接")

# 保持向后兼容的函数
def connect_server(host='127.0.0.1', port=8888):
    """
    连接到服务器（保持兼容）
    """
    return connect_tcp(host, port, 'client_socket', 'is_connected', send_queue, receive_queue, "服务器")

def connect_database(host='127.0.0.1', port=8889):
    """
    连接到数据库（保持兼容）
    """
    return connect_tcp(host, port, 'db_socket', 'db_connected', data_send_queue, data_receive_queue, "数据库")

def disconnect():
    """
    断开与服务器的连接（保持兼容）
    """
    disconnect_socket('client_socket', 'is_connected')

def is_server_connected():
    """
    检查是否已连接到服务器
    
    Returns:
        bool: 是否已连接
    """
    return is_connected and client_socket is not None

def is_database_connected():
    """
    检查是否已连接到数据库
    
    Returns:
        bool: 是否已连接
    """
    return db_connected and db_socket is not None

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

    # 将bytes转换为十六进制字符串，使其可以被JSON序列化
    request_hex = ' '.join(f'{b:02X}' for b in request)

    # 发送json格式的内容
    data = json.dumps({
        "serial": serial,
        "request": request_hex,
        "time": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
    })
    send_queue.put(data)
    return data

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

def parse_one_data(dp):
    """
    解析接收到的数据
    """
    try:
        data = receive_queue.get(timeout=1)
        if data['status'] != 'success':
            # 无需解析的数据
            return
        serial = data.get('serial')
        response = data.get('response')
        data = dp.test_parse(serial, response)
        logger.info(f"解析数据: {json.loads(data)}")
        data_send_queue.put(data)
        
    except queue.Empty:
        # 队列为空
        logger.warning("接收队列为空，无法解析数据")
    except Exception as e:
        logger.error(f"解析数据失败: {e}")

def parse_all_data(dp):
    """
    解析接收到的所有数据
    """
    while not receive_queue.empty():
        try:
            data = receive_queue.get(timeout=1)
            if data['status'] != 'success':
                # 无需解析的数据
                continue
            serial = data.get('serial')
            response = data.get('response')
            data = dp.test_parse(serial, response)
            logger.info(f"解析数据: {json.loads(data)}")
            data_send_queue.put(data)
            
        except queue.Empty:
            # 队列为空
            logger.info("完成一轮数据解析")
        except Exception as e:
            logger.error(f"解析数据失败: {e}")

def send_one_json():
    """获取前端json数据"""
    json_data = {
        'serial': 'COM 45',
        'slave_adress': '1',
        'function_code': '3',
        'start_address': '2',
        'quantity': '4',
    }
    data = json_data['serial'], json_data['slave_adress'], json_data['function_code'], json_data['start_address'], json_data['quantity']
    send_data(data)

def send_json_list(json_data_list):
    """
    发送多个JSON数据到服务器
    包含不同设备的查询指令，循环发送
    """
    # 循环发送每个JSON数据
    for i, json_data in enumerate(json_data_list):
        try:
            # 转换为元组格式
            data = (
                json_data['serial'], 
                json_data['slave_adress'], 
                json_data['function_code'], 
                json_data['start_address'], 
                json_data['quantity']
            )
            
            # 发送数据
            send_data(data)
            
            # 延时，避免发送过快
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"发送第 {i+1} 个JSON数据失败: {e}")
    
    logger.info("所有JSON数据发送完成")
    return len(json_data_list)

# 使用示例
if __name__ == "__main__":
    # 连接服务器和数据库
    server_connected = connect_server()
    db_connected = connect_database()
    
    if server_connected and db_connected:
        try:
            # 初始化串口
            init_serial()
            # 创建数据解析器实例
            dp = DataProcessor()
            
            # 加载命令列表
            with open('cmd_list.json', 'r', encoding='utf-8') as file:
                json_data_list = json.load(file)
                
            # 主循环
            while is_server_connected() and is_database_connected():
                time.sleep(1)
                # 发送命令列表
                send_json_list(json_data_list)
                # 解析接收到的数据
                # parse_one_data(dp)
                parse_all_data(dp)

        finally:
            # 断开连接
            disconnect_socket('client_socket', 'is_connected')
            disconnect_socket('db_socket', 'db_connected')
    else:
        if not server_connected:
            logger.error("连接服务器失败")
        if not db_connected:
            logger.error("连接数据库失败")
        logger.error("程序退出")