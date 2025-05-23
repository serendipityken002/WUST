import os
import time
import logging
from logging.handlers import RotatingFileHandler
import traceback
import threading

class LevelFilter(logging.Filter):
    """自定义日志过滤器，根据日志级别过滤日志"""
    def __init__(self, level):
        super().__init__()
        self.level = level

    def filter(self, record):
        return record.levelno == self.level


class TimedRotatingHandler(RotatingFileHandler):
    """时间敏感的日志处理器，根据当前时间确定日志文件路径"""
    
    def __init__(self, base_path, level_name, **kwargs):
        self.base_path = base_path
        self.level_name = level_name.lower()
        self.last_time_check = 0
        self.lock = threading.Lock()
        
        # 初始化时设置正确的路径
        filepath = self._get_log_file_path()
        super().__init__(filepath, **kwargs)
    
    def _get_log_file_path(self):
        """根据当前时间获取日志文件路径"""
        current_time = time.localtime()
        
        # 第一级目录 - 年月日 (YYYY_MM_DD)
        date_dir = time.strftime('%Y_%m_%d', current_time)
        
        # 第二级目录 - 小时 (HH)
        hour_dir = time.strftime('%H', current_time)
        
        # 完整日志目录路径
        log_dir = os.path.join(self.base_path, date_dir, hour_dir)
        
        # 确保目录存在
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # 日志文件路径
        return os.path.join(log_dir, f"{self.level_name}.log")
    
    def emit(self, record):
        """重写emit方法，在发送日志前检查时间变化"""
        current_time = int(time.time())
        
        # 每60秒检查一次时间变化
        if current_time - self.last_time_check >= 60:
            with self.lock:
                # 再次检查以避免竞争条件
                if current_time - self.last_time_check >= 60:
                    self.last_time_check = current_time
                    new_path = self._get_log_file_path()
                    
                    # 如果路径变化了，关闭旧文件并切换到新文件
                    if new_path != self.baseFilename:
                        if self.stream:
                            self.stream.close()
                            self.stream = None
                        self.baseFilename = new_path
                        self._open()
        
        # 调用父类的emit方法
        super().emit(record)


class LogUtils:

    def __init__(self, base_log_path="logs"):
        # 存储基础路径
        self.base_log_path = base_log_path
        
        # 创建日志对象logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)  # 设置最低日志级别为DEBUG
        
        # 防止日志重复
        if self.logger.handlers:
            self.logger.handlers.clear()

        # 定义日志格式
        formatter = logging.Formatter('%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s')

        # 对应的日志文件名前缀
        log_levels = {
            'DEBUG': 'debug',
            'INFO': 'info',
            'WARNING': 'warning',
            'ERROR': 'error',
            'CRITICAL': 'critical'
        }

        for level_name, file_prefix in log_levels.items():
            level = getattr(logging, level_name)
            
            # 使用新的时间敏感处理器
            handler = TimedRotatingHandler(
                base_path=self.base_log_path, 
                level_name=file_prefix,
                maxBytes=1024*1024, 
                backupCount=5, 
                encoding='utf-8'
            )
            handler.setLevel(level)
            handler.setFormatter(formatter)

            # 创建自定义过滤器，确保只有对应级别的日志会被记录到相应的文件
            handler.addFilter(LevelFilter(level))

            # 添加处理器到logger
            self.logger.addHandler(handler)

        # 控制台输出设置
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(formatter)
        self.logger.addHandler(console)

        print(f"日志系统已初始化，基础路径: {self.base_log_path}")

    def get_log(self):
        return self.logger


def divide(x, y):
    return x / y

# 使用示例
log_util = LogUtils()
logger = log_util.get_log()

if __name__ == "__main__":
    log_util = LogUtils()
    logger = log_util.get_log()
    
    # 测试不同级别的日志
    logger.debug('这是一个debug级别的日志信息')
    logger.info('这是一个info级别的日志信息')
    logger.warning('这是一个warning级别的日志信息')
    logger.error('这是一个error级别的日志信息')
    logger.critical('这是一个critical级别的日志信息')

    # 模拟时间变化
    print("模拟运行一段时间，日志会自动切换到新目录...")
    
    try:
        result = divide(10, 0)
    except:
        error_info = traceback.format_exc()
        logger.error("捕获到异常:\n%s", error_info)
    
    logger.info({"error": 1})
    logger.error('error')