from flask import Flask, request, jsonify
import logging
import json
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('restful_api_server')

# 创建Flask应用
app = Flask(__name__)

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({"status": "ok", "time": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())})

@app.route('/api/data', methods=['POST'])
def receive_data():
    """数据接收端点 - 只打印数据，不存储"""
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "无数据"}), 400
        
        # 打印接收到的数据
        logger.info(f"接收到数据: {data}")
        print(f"\n{'='*50}\n接收到数据:\n{json.dumps(data, indent=2, ensure_ascii=False)}\n{'='*50}\n")
        
        return jsonify({
            "status": "success", 
            "message": "数据已接收"
        })
    
    except Exception as e:
        logger.error(f"处理数据时出错: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/receive', methods=['GET'])
def send_data():
    """数据发送端点 - 返回固定数据"""
    # 固定返回数据
    data = {
        "id": 1,
        "name": "测试数据",
        "value": 12345,
        "status": "ok",
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    }
    
    logger.info(f"发送固定数据: {data}")
    return jsonify(data)

if __name__ == '__main__':
    try:
        logger.info("启动简化版RESTful API服务器...")
        app.run(host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        logger.info("服务器正在关闭...")