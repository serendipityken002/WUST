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
from flask import Flask, request, jsonify
from flask_cors import CORS

# 禁用不安全请求警告
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# 添加上级目录到路径
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.Logger import logger
from utils.process_data import DataProcessor


class ConfigLoader:
    """配置加载器类"""
    
    @staticmethod
    def load_config():
        """加载配置文件"""
        # 首先尝试读取外部配置文件
        external_config = 'config/config.yaml'  # 与可执行文件同目录的配置文件
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
        
        config_path = os.path.join(base_path, 'config/config.yaml')
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

class APIService:
    """API服务类，封装Flask应用和路由处理"""
    
    def __init__(self, host='0.0.0.0', port=5000, data_manager=None):
        """初始化API服务
        
        Args:
            host: 服务器主机，默认为0.0.0.0
            port: 服务器端口，默认为5000
            data_manager: 数据管理器实例
        """
        self.app = Flask(__name__)
        CORS(self.app)
        self.host = host
        self.port = port
        self.data_manager = data_manager
        
        # 注册API蓝图
        self._register_routes()
    
    def _register_routes(self):
        """注册API路由"""
        # 健康检查
        @self.app.route('/health', methods=['GET'])
        def health_check():
            return jsonify({
                "status": "ok", 
                "time": time.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # 根据COM口和ID获取设备信息
        @self.app.route('/com/<com>/id/<id>', methods=['GET'])
        def get_device_info(com, id):
            """根据COM口和ID获取设备信息"""
            res_json = self.data_manager.get_comid_data(com, id)
            res = json.loads(res_json)
            return jsonify(res)
        
        # 获取整个data数据
        @self.app.route('/data', methods=['GET'])
        def get_all_data():
            """根据COM口和ID获取设备信息"""
            res = self.data_manager.get_all_data()
            return jsonify(res)

        # @self.app.route('/get_data', methods=['POST'])
        # def get_data():
        #     """依次获取后端解析的单个数据，作为历史数据存储到数据库"""
        #     pass
    
    def run(self, debug=False, use_reloader=False):
        """运行API服务器"""
        logger.info(f"启动API服务器 {self.host}:{self.port}")
        return self.app.run(
            host=self.host,
            port=self.port,
            debug=debug,
            use_reloader=use_reloader
        )
    
    def run_in_thread(self):
        """在线程中运行API服务器"""
        thread = threading.Thread(
            target=self.run,
            kwargs={"debug": False, "use_reloader": False}
        )
        thread.daemon = True
        thread.start()
        logger.info(f"API服务器已在后台运行 {self.host}:{self.port}")
        return True


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
    
    def __init__(self, tcp_client, config, data_processor):
        """初始化设备管理器"""
        self.tcp_client = tcp_client
        self.config = config
        self.data_processor = data_processor
    
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
                parsed_data = self.data_processor._parse_response(serial, response)
                data_json = json.loads(parsed_data)
                logger.info(f"解析数据: {data_json}")
                
                # 发送到数据库的API
                # 此处调用数据库的API即可，将data_json发送出去
                
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
        
        # 导入数据处理器
        self.data_processor = DataProcessor()

        # 创建API服务端
        api_config = self.config.get('api', {})
        self.api_server = APIService(
            host=api_config.get('host', '0.0.0.0'),
            port=api_config.get('port', 5000),
            data_manager=self.data_processor
        )

        # 创建设备管理器
        self.device_manager = DeviceManager(
            self.tcp_client,
            self.config,
            self.data_processor
        )
    
    def run(self):
        """运行应用"""
        # 连接服务器和RESTful API
        server_connected = self.tcp_client.connect()
        api_server = self.api_server.run_in_thread()
        
        if server_connected and api_server:
            try:
                # 初始化串口
                self.device_manager.init_serial()

                # 优先从可执行文件目录加载命令列表
                cmd_list_path = 'config/cmd_list.json'
                
                # 如果是打包环境，检查可执行文件所在目录
                if getattr(sys, 'frozen', False):
                    exe_dir = os.path.dirname(sys.executable)
                    external_cmd_list = os.path.join(exe_dir, 'config/cmd_list.json')
                    if os.path.exists(external_cmd_list):
                        cmd_list_path = external_cmd_list
                        logger.info(f"使用外部命令列表: {external_cmd_list}")
                    else:
                        # 使用打包内的命令列表
                        cmd_list_path = os.path.join(sys._MEIPASS, 'config/cmd_list.json')
                        logger.info(f"使用内部命令列表: {cmd_list_path}")

                # 加载命令列表
                with open(cmd_list_path, 'r', encoding='utf-8') as file:
                    json_data_list = json.load(file)
                    logger.info(f"成功加载命令列表，包含 {len(json_data_list)} 条命令")
                    
                # 主循环
                while self.tcp_client.is_connected_status():
                    time.sleep(1)
                    # 发送命令列表
                    self.device_manager.send_json_list(json_data_list)
                    # 解析接收到的数据
                    self.device_manager.parse_all_data()

            finally:
                # 断开连接
                self.tcp_client.disconnect()
        else:
            if not server_connected:
                logger.error("连接服务器失败")
            if not api_server:
                logger.error("连接RESTful API失败")
            logger.error("程序退出")


if __name__ == "__main__":
    app = Application()
    app.run()