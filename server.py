import socket
import threading
import time
import json

# 全局变量存储串口配置
serial_ports_config = []

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
        
        # 判断数据类型
        if isinstance(data, list) and len(data) > 0 and "name" in data[0]:
            # 是串口配置列表
            return process_serial_ports(data)
        elif isinstance(data, dict) and "serial" in data and "request" in data:
            # 是Modbus请求
            return process_modbus_request(data)
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

def process_serial_ports(serial_ports):
    """
    处理串口配置列表
    """
    global serial_ports_config
    serial_ports_config = serial_ports
    
    print(f"接收到串口配置: {len(serial_ports)} 个串口")
    for port in serial_ports:
        print(f"  - {port['name']}: {port['description']}, {port['baudrate']}波特率")
    
    # 模拟初始化串口
    time.sleep(0.5)  # 模拟串口初始化时间
    
    # 返回初始化成功响应
    return json.dumps({
        "status": "success",
        "message": f"已初始化 {len(serial_ports)} 个串口",
        "initialized_ports": [port["name"] for port in serial_ports]
    })

def process_modbus_request(request_data):
    """
    处理Modbus请求
    """
    serial = request_data.get('serial')
    request = request_data.get('request')
    timestamp = request_data.get('time')
    
    # 检查请求的串口是否已初始化
    port_found = False
    for port in serial_ports_config:
        if port["name"] == serial:
            port_found = True
            break
    
    if not port_found and serial_ports_config:
        return json.dumps({
            "status": "error",
            "message": f"串口 {serial} 未初始化",
            "available_ports": [port["name"] for port in serial_ports_config]
        })
    
    print(f"接收到Modbus请求: 串口={serial}, 请求={request}, 时间={timestamp}")
    
    # 根据不同的串口返回不同的响应
    # 这里只是示例，你可以根据实际情况修改
    response = None
    if serial == "COM 44":
        response = "01 03 06 12 34 56 78 9A BC DD EF"
    elif serial == "COM 45":
        response = "1F 03 3A 00 00 00 00 00 00 00 00 00 00 00 08 02 28 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 34 00 00 00 00 00 00 00 00 00 00 03 24 00 00 00 00 00 00 00 00 00 00 00 00 46 A8"
    elif serial == "COM 50":
        response = "58 03 0A 07 03 06 FF 07 61 07 28 07 5F AC 2B"
    else:
        response = "FF FF FF FF"  # 默认响应
    
    # 返回响应
    return json.dumps({
        "status": "success",
        "serial": serial,
        "request": request,
        "response": response,
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
    start_serve()