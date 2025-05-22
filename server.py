import socket
import threading
import time
import json
import serial
from Logger import logger
import serial.tools.list_ports

class SerialManager:
    """串口管理类，用于管理多个串口连接"""
    def __init__(self):
        self.serial_ports = {}  # 存储所有串口对象 {port_name: SerialHandler}
        
class SerialHandler:
    """单个串口处理类"""
    def __init__(self, port_name, baudrate, timeout=1):
        self.port_name = port_name
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_port = None
        self.is_connected = False
        self.logger = logger

    def connect(self):
        """连接串口"""
        try:
            if self.is_connected:
                self.logger.warning(f"串口{self.port_name}已连接，无需重复连接")
                return True
            self.serial_port = serial.Serial(
                port=self.port_name,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            self.is_connected = True
            self.logger.info(f"成功连接到{self.port_name}，波特率{self.baudrate}")
            return True
        except Exception as e:
            self.logger.error(f"串口{self.port_name}连接失败: {e}")
            self.is_connected = False
            return False

    def send_data(self, request):
        """发送Modbus请求，并返回响应"""
        if not self.is_connected:
            self.logger.warning("串口未连接，无法发送数据")
            return None
        try:
            self.serial_port.write(request)
            self.logger.info(f"成功发送请求: {request.hex()}")

            # 接收数据
            time.sleep(0.2)  # 等待数据到达
            data = None
            if self.serial_port.in_waiting > 0:
                data = self.serial_port.read(self.serial_port.in_waiting)
            return data
        except Exception as e:
            self.logger.error(f"发送请求失败: {e}")
            return None

def handle_client(client_socket, client_address):
    print(f"连接到客户端: {client_address}")
    while True:
        try:
            # 接收原始数据
            raw_data = client_socket.recv(1024)
            if not raw_data:
                break
                
            # 尝试解码为UTF-8
            data_str = raw_data.decode('utf-8')
            
            # 判断数据类型并处理
            response = process_data(data_str)
            
            # 发送响应
            client_socket.sendall(response.encode('utf-8'))
            
        except Exception as e:
            print(f"处理客户端数据出错: {e}")
            break
            
    client_socket.close()
    print(f"{client_address} 已断开连接")

def process_data(data_str):
    """
    根据不同的数据格式进行处理
    """
    try:
        # 尝试解析JSON
        data = json.loads(data_str)
        # print(f"解析后的数据: {data}")
        
        # 判断数据类型
        if isinstance(data, list) and len(data) > 0 and "name" in data[0]:
            # 是串口配置列表
            return process_serial_ports(data)
        elif isinstance(data, dict) and "serial" in data and "request" in data:
            # 是Modbus请求
            # return process_modbus_request(data)
            return test_response(data)
        else:
            # 未知数据格式
            return json.dumps({
                "status": "error",
                "message": "未知的数据格式"
            })
            
    except json.JSONDecodeError:
        return json.dumps({
            "status": "error",
            "message": "无效的JSON格式"
        })
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"处理数据错误: {str(e)}"
        })

def find_serial_ports(config_ports):
    """
    根据配置的串口信息查找实际的串口
    
    Args:
        config_ports: 后端返回的串口列表，每个元素包含 name, description, baudrate
        
    Returns:
        list: 更新后的串口配置列表
    """
    available_ports = list(serial.tools.list_ports.comports())
    updated_ports = []
    
    # 记录所有可用的串口信息
    logger.info("系统可用串口:")
    for port in available_ports:
        logger.info(f"端口: {port.device}, 描述: {port.description}")
    
    for port_config in config_ports:
        config_name = port_config['name']      # 配置的串口名 (如 COM5)
        config_desc = port_config.get('description', '')  # 配置的描述 (如 'A')
        
        # 首先尝试通过描述匹配
        found_port = None
        if config_desc:
            for port in available_ports:
                if config_desc.upper() in port.description.upper():
                    found_port = port
                    break
        
        # 如果通过描述没找到，使用配置的名称
        if not found_port:
            for port in available_ports:
                if port.device == config_name:
                    found_port = port
                    break
        
        if found_port:
            # 更新配置中的串口名称为实际找到的串口
            new_config = port_config.copy()
            new_config['name'] = found_port.device
            new_config['actual_description'] = found_port.description
            updated_ports.append(new_config)
            logger.info(f"串口匹配成功 - 配置: {config_name}({config_desc}) -> 实际: {found_port.device}({found_port.description})")
        else:
            # 如果没找到，保持原配置不变，但添加警告日志
            updated_ports.append(port_config)
            logger.warning(f"未找到匹配的串口 - 使用默认配置: {config_name}({config_desc})")
    
    return updated_ports

def process_serial_ports(serial_ports):
    """
    处理串口配置列表
    """
    updated_ports = find_serial_ports(serial_ports)
    for port_config in updated_ports:
        port_name = port_config['name']
        baudrate = port_config.get('baudrate', 9600)
        timeout = port_config.get('timeout', 1)
        
        # 创建串口处理对象
        serial_handler = SerialHandler(port_name, baudrate, timeout)
        if serial_handler.connect():
            serial_manager.serial_ports[port_name] = serial_handler
    
    # 返回初始化成功响应
    return json.dumps({
        "status": "serial_success",
        "message": f"已初始化 {len(updated_ports)} 个串口",
        "initialized_ports": [port["name"] for port in updated_ports]
    })

def process_modbus_request(request_data):
    """
    处理Modbus请求
    """
    serial = request_data.get('serial')
    request = request_data.get('request')
    timestamp = request_data.get('time')
    
    # 检查请求的串口是否已初始化
    if serial not in serial_manager.serial_ports:
        return json.dumps({
            "status": "error",
            "message": f"串口 {serial} 未初始化或不存在"
        })
    
    # 如果请求是bytes类型，不需要转换，如果是字符串，则需要转换为bytes
    if isinstance(request, str):
        try:
            # 假设request是十六进制字符串，尝试转换为bytes
            request_bytes = bytes.fromhex(request.replace(' ', ''))
        except ValueError as e:
            return json.dumps({
                "status": "error",
                "message": f"无效的十六进制请求字符串: {e}"
            })
    elif isinstance(request, bytes):
        request_bytes = request
    else:
        return json.dumps({
            "status": "error",
            "message": f"请求类型错误，应为字符串或bytes，实际为 {type(request)}"
        })

    serial_handler = serial_manager.serial_ports[serial]
    # 发送Modbus请求
    response = serial_handler.send_data(request_bytes)
    if response is None:
        return json.dumps({
            "status": "error",
            "message": f"串口 {serial} 没有响应数据"
        })
    
    # 将bytes转换为十六进制字符串以便JSON序列化
    response_hex = ' '.join([f'{b:02X}' for b in response])
    request_hex = ' '.join([f'{b:02X}' for b in request_bytes])
   

    # 返回响应
    return json.dumps({
        "status": "success",
        "serial": serial,
        "request": request_hex,
        "response": response_hex,
        "time": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    })

def test_response(request_data):
    """
    模拟串口返回数据
    """
    print(f"串口发送的数据: {request_data}")
    return json.dumps({
        "status": "success",
        "serial": "COM5",
        "request": "20 03 00 10 00 1D 82 B7",
        "response": "20 03 3A 00 00 00 00 00 00 00 00 00 00 00 08 02 33 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 34 00 00 00 00 00 00 00 00 00 00 04 70 00 00 00 00 00 00 00 00 00 00 00 00 FB 52",
        "time": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    })

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
            print(f"接受客户端连接错误: {e}")
            break

if __name__ == "__main__":
    # 创建全局串口管理器实例
    serial_manager = SerialManager()
    start_serve()
    # serial_ports = [
    #     {"name": "COM5", "description": "WCH USB-SERIAL Ch A", "baudrate": 9600},
    #     {"name": "COM7", "description": "WCH USB-SERIAL Ch C", "baudrate": 9600}
    # ]
    # process_serial_ports(serial_ports)
    # request_data = {
    #     "serial": "COM5",
    #     "request": "01 03 00 02 00 1D 24 03",
    #     "time": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    # }
    # data = process_modbus_request(request_data)
    # print(data)