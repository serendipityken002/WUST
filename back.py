import socket
import threading
import time
import queue
import os
import sys
import yaml
import json
import requests
from urllib3.exceptions import InsecureRequestWarning

# 禁用不安全请求警告
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

from Logger import logger
from process_data import DataProcessor

class ConfigLoader:
    """配置加载器类"""
    
    @staticmethod
    def load_config():
        """加载配置文件"""
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


class TCPClient:
    """TCP客户端类，用于连接服务器"""
    # 原来是设计有一个数据库TCP连接的，目前只有串口服务器需要连接
    
    def __init__(self, host='127.0.0.1', port=8888, connection_name="服务器"):
        """初始化TCP客户端"""
        self.host = host
        self.port = port
        self.connection_name = connection_name
        self.socket = None
        self.is_connected = False
        self.socket_lock = threading.Lock()
        
        # 发送和接收队列
        self.send_queue = queue.Queue()
        self.receive_queue = queue.Queue()
        
        # 线程对象
        self.send_thread = None
        self.receive_thread = None
    
    def connect(self):
        """连接到服务器"""
        try:
            # 创建TCP套接字
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.is_connected = True
            
            # 启动发送线程
            self.send_thread = threading.Thread(
                target=self._send_thread_func
            )
            self.send_thread.daemon = True
            self.send_thread.start()

            # 启动接收线程
            self.receive_thread = threading.Thread(
                target=self._receive_thread_func
            )
            self.receive_thread.daemon = True
            self.receive_thread.start()
            
            logger.info(f"成功连接到{self.connection_name} {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"连接{self.connection_name}失败: {e}")
            if self.socket:
                self.socket.close()
            self.socket = None
            self.is_connected = False
            return False
    
    def disconnect(self):
        """断开与服务器的连接"""
        if self.socket:
            try:
                self.socket.close()
            except Exception as e:
                logger.error(f"关闭{self.connection_name}连接错误: {e}")
            finally:
                self.socket = None
                self.is_connected = False
                logger.info(f"已断开与{self.connection_name}的连接")
    
    def is_connected_status(self):
        """检查是否已连接到服务器"""
        return self.is_connected and self.socket is not None
    
    def send(self, data):
        """发送数据到发送队列"""
        self.send_queue.put(data)
    
    def receive(self, timeout=1):
        """从接收队列获取数据"""
        try:
            return self.receive_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def _send_thread_func(self):
        """发送线程函数"""
        while self.is_connected:
            try:
                data = self.send_queue.get(timeout=1)
                self.socket.sendall(data.encode('utf-8'))
                time.sleep(0.1)
            except queue.Empty:
                # 队列为空，继续循环
                continue
            except Exception as e:
                logger.error(f"{self.connection_name}发送失败: {e}")
                self.disconnect()
                break
    
    def _receive_thread_func(self):
        """接收线程函数"""
        while self.is_connected:
            try:
                data_str = self.socket.recv(1024).decode('utf-8')
                if not data_str:
                    logger.warning(f"{self.connection_name}已断开连接")
                    self.disconnect()
                    break
                
                data = json.loads(data_str)
                # 记录接收到的数据
                logger.info(f"接收到{self.connection_name}数据: {data}")
                
                self.receive_queue.put(data)
            except Exception as e:
                logger.error(f"{self.connection_name}接收失败: {e}")
                self.disconnect()
                break

class RESTfulClient:
    """RESTful API客户端类
    
    主要用于发送数据到API服务器并接收响应
    """
    
    def __init__(self, base_url='http://127.0.0.1:5000/api', timeout=10):
        """初始化RESTful API客户端
        
        Args:
            base_url: API基础URL，默认为http://127.0.0.1:5000/api
            timeout: 请求超时时间，单位秒，默认为10
        """
        self.base_url = base_url
        self.timeout = timeout
        self.session = None
        self.is_connected = False
    
    def connect(self):
        """连接到RESTful API服务器
        
        Returns:
            bool: 连接是否成功
        """
        try:
            # 创建会话对象以复用连接
            self.session = requests.Session()
            
            # 测试连接
            response = self.session.get(f"{self.base_url}/health", timeout=self.timeout)
            if response.status_code == 200:
                self.is_connected = True
                logger.info(f"成功连接到RESTful API: {self.base_url}")
                return True
            else:
                logger.error(f"API连接测试失败: {response.status_code}")
                return False
        except requests.RequestException as e:
            logger.error(f"连接RESTful API失败: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self):
        """断开与RESTful API的连接"""
        if self.session:
            self.session.close()
            self.session = None
        
        self.is_connected = False
        logger.info("已断开RESTful API连接")
    
    def is_connected_status(self):
        """检查是否已连接到RESTful API
        
        Returns:
            bool: 是否已连接
        """
        return self.is_connected and self.session is not None
    
    def send_data(self, data, endpoint="/data"):
        """发送数据到RESTful API
        
        Args:
            data: 要发送的JSON数据
            endpoint: API端点路径，默认为/data
            
        Returns:
            dict: API响应数据，失败时返回None
        """
        if not self.is_connected_status():
            logger.error("未连接到RESTful API")
            return None
        
        try:
            url = f"{self.base_url}{endpoint}"
            response = self.session.post(
                url, 
                json=data,
                timeout=self.timeout
            )
            
            if response.status_code in (200, 201):
                logger.info(f"成功发送数据到API({url}): {data}")
                return response.json()
            else:
                logger.error(f"发送数据失败: {response.status_code}, {response.text}")
                return None
        except requests.RequestException as e:
            logger.error(f"API请求出错: {e}")
            return None
    
    def receive_data(self, endpoint="/receive", params=None):
        """从RESTful API接收数据
        
        Args:
            endpoint: API接收端点路径，默认为/receive
            params: 请求参数，默认为None
            
        Returns:
            dict: 接收到的数据，失败时返回None
        """
        if not self.is_connected_status():
            logger.error("未连接到RESTful API")
            return None
        
        try:
            url = f"{self.base_url}{endpoint}"
            response = self.session.get(
                url,
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"成功从API({url})接收数据")
                return data
            elif response.status_code == 204:
                logger.debug("API返回空数据")
                return None
            else:
                logger.error(f"接收数据失败: {response.status_code}, {response.text}")
                return None
        except requests.RequestException as e:
            logger.error(f"API请求出错: {e}")
            return None

class ModbusHelper:
    """Modbus助手类，处理Modbus相关功能"""
    
    @staticmethod
    def calculate_crc(data):
        """计算CRC校验码"""
        crc = 0xffff
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc = crc >> 1
        return crc.to_bytes(2, byteorder='little')
    
    @staticmethod
    def format_request(slave_address, function_code, start_address, quantity):
        """格式化Modbus请求"""
        request = f'{int(slave_address):02x} {int(function_code):02x} {int(start_address):04x} {int(quantity):04x}'
        request = bytes.fromhex(request)
        crc = ModbusHelper.calculate_crc(request)
        request += crc
        # 将bytes转换为十六进制字符串
        return ' '.join(f'{b:02X}' for b in request)


class DeviceManager:
    """设备管理器类，处理设备通信和数据处理"""
    
    def __init__(self, tcp_client, api_client, config):
        """初始化设备管理器"""
        self.tcp_client = tcp_client
        self.api_client = api_client
        self.config = config
        self.data_processor = DataProcessor()
    
    def init_serial(self):
        """初始化串口"""
        serial_ports = self.config.get('serial_ports', [])
        if not serial_ports:
            logger.error("未找到串口配置信息")
            return False
        
        if not self.tcp_client.is_connected_status():
            logger.error("未连接到服务器")
            return False
        
        # 将列表序列化为JSON字符串
        serial_ports_json = json.dumps(serial_ports)
        # 发送JSON字符串
        self.tcp_client.socket.sendall(serial_ports_json.encode('utf-8'))
        
        return True
    
    def send_data(self, data):
        """发送Modbus请求到服务器"""
        serial, slave_address, function_code, start_address, quantity = data
        
        # 使用ModbusHelper格式化请求
        request_hex = ModbusHelper.format_request(slave_address, function_code, start_address, quantity)
        
        # 发送json格式的内容
        data = json.dumps({
            "serial": serial,
            "request": request_hex,
            "time": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
        })
        self.tcp_client.send(data)
        return data
    
    def send_json_list(self, json_data_list):
        """发送多个JSON数据到服务器"""
        request_delay = self.config.get('modbus', {}).get('request_delay', 0.5)
        
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
                self.send_data(data)
                
                # 使用配置的延时
                time.sleep(request_delay)
                
            except Exception as e:
                logger.error(f"发送第 {i+1} 个JSON数据失败: {e}")
        
        logger.info("所有JSON数据发送完成")
        return len(json_data_list)
    
    def parse_all_data(self):
        """解析接收到的所有数据"""
        while not self.tcp_client.receive_queue.empty():
            try:
                data = self.tcp_client.receive()
                if not data or data.get('status') != 'success':
                    # 无需解析的数据
                    continue
                    
                serial = data.get('serial')
                response = data.get('response')
                parsed_data = self.data_processor.test_parse(serial, response)
                data_json = json.loads(parsed_data)
                logger.info(f"解析数据: {data_json}")
                
                # 发送到RESTful API
                self.api_client.send_data(data_json)
                
            except queue.Empty:
                # 队列为空
                logger.info("完成一轮数据解析")
                break
            except Exception as e:
                logger.error(f"解析数据失败: {e}")


class Application:
    """应用主类，管理整个应用生命周期"""
    
    def __init__(self):
        """初始化应用"""
        # 加载配置
        self.config = ConfigLoader.load_config()
        
        # 创建TCP客户端
        server_config = self.config.get('server', {})
        self.tcp_client = TCPClient(
            host=server_config.get('host', '127.0.0.1'),
            port=server_config.get('port', 8888)
        )
        
        # 创建RESTful API客户端
        api_config = self.config.get('api', {})
        self.api_client = RESTfulClient(
            base_url=api_config.get('base_url', 'http://127.0.0.1:5000/api'),
            timeout=api_config.get('timeout', 10)
        )
        
        # 创建设备管理器
        self.device_manager = DeviceManager(
            self.tcp_client,
            self.api_client,
            self.config
        )
    
    def run(self):
        """运行应用"""
        # 连接服务器和RESTful API
        server_connected = self.tcp_client.connect()
        api_connected = self.api_client.connect()
        
        if server_connected and api_connected:
            try:
                # 初始化串口
                self.device_manager.init_serial()
                
                # 加载命令列表
                with open('cmd_list.json', 'r', encoding='utf-8') as file:
                    json_data_list = json.load(file)
                    
                # 主循环
                while self.tcp_client.is_connected_status() and self.api_client.is_connected_status():
                    time.sleep(1)
                    # 发送命令列表
                    self.device_manager.send_json_list(json_data_list)
                    # 解析接收到的数据
                    self.device_manager.parse_all_data()

            finally:
                # 断开连接
                self.tcp_client.disconnect()
                self.api_client.disconnect()
        else:
            if not server_connected:
                logger.error("连接服务器失败")
            if not api_connected:
                logger.error("连接RESTful API失败")
            logger.error("程序退出")


if __name__ == "__main__":
    app = Application()
    app.run()