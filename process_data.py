import time
from Logger import logger
import random
import traceback
import pprint
import json
import threading

class DataGen:
    def __init__(self):
        self.serial_manager = None
        self.data = self._initialize_data()

    def _generate_random_value(self, value_type):
        """生成初始值"""
        if value_type == "运行状态":
            return False
        else:
            return 0

    def _create_ventilation_hood(self):
        """创建通风柜数据结构"""
        return {
            "视窗高度": {"value": self._generate_random_value("视窗高度"), "unit": "mm", "display": True},
            "排风速": {"value": self._generate_random_value("排风速"), "unit": "m³/h", "display": True},
            "面风速": {"value": self._generate_random_value("面风速"), "unit": "m/s", "display": True},
            "阀门开度": {"value": self._generate_random_value("阀门开度"), "unit": "%", "display": True},
            "强排开关": {"value": self._generate_random_value("运行状态"), "unit": " ", "display": False},
            
            "报警信息": {"value": self._generate_random_value("报警信息"), "unit": " ", "display": True},
            "运行状态": {"value": self._generate_random_value("运行状态"), "unit": " ", "display": True,"sort":1},
        }

    def _create_exhaust_fan(self):
        """创建排风机数据结构"""
        return {
            
            "排风频率": {"value": self._generate_random_value("排风频率"), "unit": "Hz", "display": True},
            "排风转速": {"value": self._generate_random_value("排风转速"), "unit": "r/min", "display": True},
            "管道压力": {"value": self._generate_random_value("管道压力"), "unit": "Pa", "display": True},
            "管道压力设定": {"value": self._generate_random_value("管道压力"), "unit": "Pa", "display": True},
            "运行状态": {"value": self._generate_random_value("运行状态"), "unit": " ", "display": True,"sort":1},
        }

    def _create_clean_room(self):
        """创建洁净室数据结构"""
        return {
            "温度": {"value": self._generate_random_value("温度"), "unit": "℃", "display": True},
            "湿度": {"value": self._generate_random_value("湿度"), "unit": "%", "display": True},
            "压差": {"value": self._generate_random_value("压差"), "unit": "Pa", "display": True}
        }

    def _initialize_data(self):
        """初始化完整的数据结构"""
        return {
            "通风柜": {
                "201通风柜": self._create_ventilation_hood(),
                "202通风柜": self._create_ventilation_hood(),
                "204通风柜": self._create_ventilation_hood(),
                "205通风柜": self._create_ventilation_hood(),
                "206通风柜": self._create_ventilation_hood(),
                "301通风柜": self._create_ventilation_hood(),
                "302通风柜": self._create_ventilation_hood(),
                "303通风柜": self._create_ventilation_hood(),
                "304通风柜": self._create_ventilation_hood(),
                "305通风柜": self._create_ventilation_hood(),
            },
            "Second":{
                "更衣室": self._create_clean_room(),
                "缓冲间": self._create_clean_room(),
                "洁净走廊": self._create_clean_room(),
                "生物医学实验室2": self._create_clean_room(),
                "生物医学实验室1": self._create_clean_room(),
            }
        }

class DataProcessor:
    def __init__(self):
        self.logger = logger
        # 存储各个串口和指令的数据
        self.port_data = {}
        self.dataGen = DataGen()
        self.data = self.dataGen.data
        self.data_lock = threading.Lock()
        self.info = {
            "COM5": {
                "01": "301通风柜",
                "02": "302通风柜",
            },
            "COM6": {
                "01": "201通风柜",
                "02": "202通风柜",
                "03": "204通风柜",
                "04": "205通风柜",
                "05": "206通风柜",
            },
        }

    def test_parse(self, serial, response):
        try:
            data_bytes = bytes.fromhex(response.replace(" ", ""))
            id = int(data_bytes[0])
            name = self.info[serial][str(id).zfill(2)]
            start_index = 3  # 跳过Modbus协议头
            
            if len(data_bytes) >= start_index + 52:  # 确保有足够的数据
                hood_values = {
                    "信息": name,
                    "状态": bool(int.from_bytes(data_bytes[start_index+0:start_index+2], byteorder='big')),
                    "开度": bool(int.from_bytes(data_bytes[start_index+6:start_index+8], byteorder='big')),
                    "警告": int.from_bytes(data_bytes[start_index+10:start_index+12], byteorder='big'),
                    "高度": int.from_bytes(data_bytes[start_index+12:start_index+14], byteorder='big'),
                    "阀门开度": int.from_bytes(data_bytes[start_index+14:start_index+16], byteorder='big'),
                    "排风速": int.from_bytes(data_bytes[start_index+18:start_index+20], byteorder='big'),
                    "面风速": round(int.from_bytes(data_bytes[start_index+16:start_index+18], byteorder='big') * 0.01, 2), # 面风速的单位是0.01m/s
                    "解析时间": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
                }
                self.data['通风柜'][name] = hood_values
                return json.dumps(hood_values)
        except Exception as e:
            self.logger.error(f"通风柜数据解析错误: {e}\n{traceback.format_exc()}")
            return None

    def get_data(self):
        """获取当前数据"""
        with self.data_lock:
            return self.data
        
    def get_comid_data(self, com, id):
        """获取指定串口和ID的数据"""
        with self.data_lock:
            name = self.info[com][str(id).zfill(2)]
            if name in self.data['通风柜']:
                return self.data['通风柜'][name]
            else:
                return None

    def _parse_response(self, response_hex: str):
        """解析响应数据
        Args:
            port_name: 串口名称
            command: 发送的命令 (例如: "58 03 00 00 00 0A C9 04")
            response_hex: 接收到的十六进制数据
            description: 命令描述
        """
        try:
            # 获取命令的第一个字节并转换为十进制
            device_id = int(response_hex.split()[0], 16)  # 将16进制字符串转换为10进制整数
            
            # 根据设备ID选择解析方法
            if device_id == 88:  # 0x58 = 88
                self.parse_modbus_response_ID88(response_hex)
            elif 145 <= device_id <= 149:  # 0x91-0x95
                # 计算对应的洁净室索引（0-4）
                room_index = device_id - 145
                self.parse_modbus_response_ID145(response_hex, room_index)
            elif device_id == 2:  # 0x02，排风机数据
                self.parse_modbus_response_ID2(response_hex)
            elif 21 <= device_id <= 25:  # 0x15-0x19，2F的通风柜数据
                self.parse_modbus_response_ventilation_hood(response_hex, "2F", device_id - 21)
            elif 31 <= device_id <= 37:  # 0x1F-0x25，3F的通风柜数据
                self.parse_modbus_response_ventilation_hood(response_hex, "3F", device_id - 31)
            else:
                self.logger.warning(f"未知的设备ID: {hex(device_id)}")
            # logger.info(f"解析: {device_id}")
            return self.data
            
        except Exception as e:
            self.logger.error(f"数据解析错误: {e}\n{traceback.format_exc()}")
            return self.data  # 即使发生错误也返回当前数据

    def parse_modbus_response_ID88(self, response_hex: str) -> dict:
        """解析Modbus响应数据，提取洁净室压差值"""
        try:
            data_bytes = bytes.fromhex(response_hex.replace(" ", ""))
            
            
            # 先获取房间列表并计算所有压差值，避免长时间持有锁
            pressure_updates = {}
            with self.data_lock:
                clean_rooms = list(self.data["2F"]["Second"].keys())
            # 在锁外进行数据解析
            for i, room in enumerate(clean_rooms):
                start_index = 3 + i * 2
                if start_index + 2 <= len(data_bytes):
                    # 将原始值转换为电流值(mA)
                    current_ma = int.from_bytes(data_bytes[start_index:start_index+2], byteorder='big') / 150
                    # 将4-20mA线性映射到-60到60Pa
                    pressure_value = (current_ma - 4) * (60 - (-60)) / (20 - 4) + (-60)
                    # 四舍五入到1位小数
                    pressure_value = round(pressure_value, 1)
                    pressure_updates[room] = pressure_value
            # 只在更新数据时短暂持有锁
            with self.data_lock:
                for room, pressure in pressure_updates.items():
                    self.data["2F"]["Second"][room]["压差"]["value"] = pressure
                    
                    # logger.info(f"data_bytes: {pressure}")
                    # logger.info({room: self.data["2F"]["Second"][room]["压差"], "pressure": pressure})
            
            return {"message": "压差数据更新成功"}

        except Exception as e:
            logger.error(f"Modbus数据解析错误: {e}")
            return None
        

    def parse_modbus_response_ID145(self, response_hex: str, room_index: int) -> dict:
        """解析Modbus响应数据，提取单个洁净室的温度和湿度值
        Args:
            response_hex: 接收到的十六进制数据
            room_index: 洁净室索引（0-4）
        """
        try:
            data_bytes = bytes.fromhex(response_hex.replace(" ", ""))
            
            # 先获取房间名
            with self.data_lock:
                clean_rooms = list(self.data["2F"]["Second"].keys())
                if room_index >= len(clean_rooms):
                    return {"message": "房间索引超出范围"}
                room = clean_rooms[room_index]
            
            # 在锁外进行数据解析
            if len(data_bytes) >= 7:  # 确保有足够的数据（3字节头 + 4字节数据）
                # 解析湿度值（前2个字节）并除以10
                humid_value = int.from_bytes(data_bytes[3:5], byteorder='big') / 10.0
                # 解析温度值（后2个字节）并除以10
                temp_value = int.from_bytes(data_bytes[5:7], byteorder='big') / 10.0
                
                # 只在更新数据时短暂持有锁
                with self.data_lock:
                    self.data["2F"]["Second"][room]["湿度"]["value"] = humid_value
                    self.data["2F"]["Second"][room]["温度"]["value"] = temp_value
                
                print(f"更新 {room} 数据: 温度={temp_value}℃, 湿度={humid_value}%")
                return {"message": f"{room} 温湿度数据更新成功"}
            else:
                return {"message": "数据长度不足"}

        except Exception as e:
            self.logger.error(f"Modbus数据解析错误: {e}\n{traceback.format_exc()}")
            return None

    def parse_modbus_response_ID2(self, response_hex: str):
        """解析排风机数据
        协议地址对应关系：
        40003: 启动指示 -> 运行状态
        40004: 运行频率 -> 排风频率
        40012: 运行转速 -> 排风转速
        40014: 管道压力 -> 管道压力
        40016: 管道压力设定 -> 管道压力设定
        """
        try:
            data_bytes = bytes.fromhex(response_hex.replace(" ", ""))
            start_index = 3  # 跳过Modbus协议头
            
            # 在锁外进行数据解析
            if len(data_bytes) >= start_index + 32:  # 确保有足够的数据到40016
                fan_values = {
                    "运行状态": bool(int.from_bytes(data_bytes[start_index+4:start_index+6], byteorder='big')),
                    "排风频率": int.from_bytes(data_bytes[start_index+6:start_index+8], byteorder='big'),
                    "排风转速": int.from_bytes(data_bytes[start_index+22:start_index+24], byteorder='big'),
                    "管道压力": int.from_bytes(data_bytes[start_index+26:start_index+28], byteorder='big'),
                    "管道压力设定": int.from_bytes(data_bytes[start_index+30:start_index+32], byteorder='big')
                }
                
                # 只在更新数据时短暂持有锁
                with self.data_lock:
                    for key, value in fan_values.items():
                        self.data["2F"]["First"]["排风机"][key]["value"] = value
                
                return {"message": "排风机数据更新成功"}
            else:
                return {"message": "数据长度不足"}

        except Exception as e:
            self.logger.error(f"排风机数据解析错误: {e}\n{traceback.format_exc()}")
            return None

    def parse_modbus_response_ventilation_hood(self, response_hex: str, floor: str, hood_index: int):
        """解析通风柜数据
        协议地址对应关系：
        40020: 运行状态
        40021: 强排开关
        40022: 报警信息
        40023: 视窗高度
        40024: 阀门开度
        40025: 排风速
        40026: 面风速
        """
        try:
            data_bytes = bytes.fromhex(response_hex.replace(" ", ""))
            start_index = 3  # 跳过Modbus协议头
            
            # 在锁外进行数据解析
            if len(data_bytes) >= start_index + 52:  # 确保有足够的数据
                # self.logger.info(f"通风柜数据: {data_bytes}")
                # self.logger.info(f"视窗高度解析之前: {data_bytes[start_index+12:start_index+14]}")
                
                
                hood_values = {
                    "运行状态": bool(int.from_bytes(data_bytes[start_index+0:start_index+2], byteorder='big')),
                    "强排开关": bool(int.from_bytes(data_bytes[start_index+6:start_index+8], byteorder='big')),
                    "报警信息": int.from_bytes(data_bytes[start_index+10:start_index+12], byteorder='big'),
                    "视窗高度": int.from_bytes(data_bytes[start_index+12:start_index+14], byteorder='big'),
                    "阀门开度": int.from_bytes(data_bytes[start_index+14:start_index+16], byteorder='big'),
                    "排风速": int.from_bytes(data_bytes[start_index+18:start_index+20], byteorder='big'),
                    "面风速": round(int.from_bytes(data_bytes[start_index+16:start_index+18], byteorder='big') * 0.01, 2) # 面风速的单位是0.01m/s
                }
                # self.logger.info(f"视窗高度解析之后: {hood_values['视窗高度']}")
                
                # 只在更新数据时短暂持有锁
                if floor == "2F":
                    floor_keys = list(self.data[floor]["First"].keys())
                    with self.data_lock:
                        if 0 <= hood_index < len(floor_keys):
                            hood_key = floor_keys[hood_index]
                            hood_data = self.data[floor]["First"][hood_key]
                        
                        for key, value in hood_values.items():
                            hood_data[key]["value"] = value
                        self.data[floor]["First"][hood_key] = hood_data
                elif floor == "3F":
                    floor_keys = list(self.data[floor].keys())
                    with self.data_lock:
                        if 0 <= hood_index < len(floor_keys):
                            hood_key = floor_keys[hood_index]
                            hood_data = self.data[floor][hood_key]
                        
                        for key, value in hood_values.items():
                            hood_data[key]["value"] = value
                        self.data[floor][hood_key] = hood_data
                
                return {"message": f"通风柜{hood_index + 1}数据更新成功"}
            else:
                return {"message": "数据长度不足"}

        except Exception as e:
            self.logger.error(f"通风柜数据解析错误: {e}\n{traceback.format_exc()}")
            return None

if __name__ == "__main__":
    dp = DataProcessor()
    dp._parse_response("1F 03 3A 00 00 00 00 00 00 00 00 00 00 00 08 02 28 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 34 00 00 00 00 00 00 00 00 00 00 03 24 00 00 00 00 00 00 00 00 00 00 00 00 46 A8")
    