import os
import time
import logging
from logging.handlers import RotatingFileHandler
import traceback

class LevelFilter(logging.Filter):
    """自定义日志过滤器，根据日志级别过滤日志"""
    def __init__(self, level):
        super().__init__()
        self.level = level

    def filter(self, record):
        return record.levelno == self.level


class LogUtils:

    def __init__(self, base_log_path="logs"):
        # 创建分级目录结构
        current_time = time.localtime()
        
        # 第一级目录 - 年月日 (YYYY_MM_DD)
        date_dir = time.strftime('%Y_%m_%d', current_time)
        
        # 第二级目录 - 小时 (HH)
        hour_dir = time.strftime('%H', current_time)
        
        # 完整日志路径
        self.logfile_path = os.path.join(base_log_path, date_dir, hour_dir)

        # 检查并创建日志目录结构
        if not os.path.exists(self.logfile_path):
            os.makedirs(self.logfile_path)

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
            # 创建日志文件路径 (第三级 - 文件)
            log_file = os.path.join(self.logfile_path, f"{file_prefix}.log")
            # 创建并配置handler
            handler = RotatingFileHandler(log_file, maxBytes=1024*1024, backupCount=5, encoding='utf-8')
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

        print(f"日志目录已准备好：{self.logfile_path}")

    def get_log(self):
        return self.logger


def divide(x,y):
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

    try:
        result = divide(10, 0)
    except:
        error_info = traceback.format_exc()
        logger.error("捕获到异常:\n%s", error_info)
    logger.info({"error":1})
    logger.error('error')