import socket
import threading
import json
import time

from Logger import logger

# 全局变量
DB_HOST = '0.0.0.0'  # 监听所有网络接口
DB_PORT = 8889       # 数据库服务器端口
running = True

def handle_client(client_socket, client_address):
    """处理客户端连接"""
    logger.info(f"客户端已连接: {client_address}")
    
    try:
        while running:
            # 接收数据
            data = client_socket.recv(4096)
            if not data:
                logger.info(f"客户端 {client_address} 已断开连接")
                break
                
            # 解析数据
            try:
                data_str = data.decode('utf-8')
                json_data = json.loads(data_str)
                
                # 打印收到的数据
                logger.info(f"收到数据: {json_data}")
                
                # # 打印格式化后的数据
                # pretty_data = json.dumps(json_data, indent=4, ensure_ascii=False)
                # print("\n" + "="*50)
                # print("收到数据:")
                # print(pretty_data)
                # print("="*50 + "\n")
                
                # # 发送确认响应
                # response = {
                #     "status": "success",
                #     "message": "数据已接收",
                #     "time": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
                # }
                # client_socket.sendall(json.dumps(response).encode('utf-8'))
                
            except json.JSONDecodeError:
                logger.error(f"无效的JSON数据: {data_str}")
                # 发送错误响应
                response = {
                    "status": "error",
                    "message": "无效的JSON数据",
                    "time": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
                }
                client_socket.sendall(json.dumps(response).encode('utf-8'))
                
            except Exception as e:
                logger.error(f"处理数据时出错: {e}")
                
    except Exception as e:
        logger.error(f"处理客户端连接时出错: {e}")
    finally:
        # 关闭客户端连接
        client_socket.close()
        logger.info(f"客户端 {client_address} 连接已关闭")

def start_db_server():
    """启动数据库TCP服务器"""
    global running
    
    # 创建服务器套接字
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        # 绑定地址和端口
        server_socket.bind((DB_HOST, DB_PORT))
        # 开始监听
        server_socket.listen(5)
        logger.info(f"数据库服务器已启动，监听 {DB_HOST}:{DB_PORT}")
        
        # 设置超时，以便可以定期检查running标志
        server_socket.settimeout(1.0)
        
        # 主循环
        while running:
            try:
                # 等待客户端连接
                client_socket, client_address = server_socket.accept()
                
                # 为每个客户端创建一个新线程
                client_thread = threading.Thread(
                    target=handle_client,
                    args=(client_socket, client_address)
                )
                client_thread.daemon = True
                client_thread.start()
                
            except socket.timeout:
                # 超时，继续循环
                continue
            except Exception as e:
                logger.error(f"接受客户端连接时出错: {e}")
                if not running:
                    break
        
    except Exception as e:
        logger.error(f"启动服务器时出错: {e}")
    finally:
        # 关闭服务器套接字
        server_socket.close()
        logger.info("数据库服务器已关闭")

if __name__ == "__main__":
    try:
        # 启动数据库服务器
        start_db_server()
    except KeyboardInterrupt:
        # 处理键盘中断（Ctrl+C）
        logger.info("接收到键盘中断，正在关闭服务器...")
        running = False
        time.sleep(2)  # 给线程一些时间来完成清理