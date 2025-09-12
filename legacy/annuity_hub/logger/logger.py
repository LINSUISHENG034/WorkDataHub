import os
import logging
from logging.handlers import RotatingFileHandler
import sys


class SingletonType(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class Logger(metaclass=SingletonType):
    def __init__(self):
        if not hasattr(self, 'initialized'):  # 防止重复初始化
            self.initialized = True
            self.configure_logger()

    def configure_logger(self):
        log_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'application.log')

        self.logger = logging.getLogger('')
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                                      datefmt='%Y/%m/%d %H:%M:%S')

        # 文件日志处理器，指定utf-8编码
        file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # 控制台日志处理器，设置utf-8编码
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # 确保 stdout 使用 utf-8 编码
        sys.stdout.reconfigure(encoding='utf-8')

    def get_logger(self):
        return self.logger


# 对外提供的logger实例
logger = Logger().get_logger()

if __name__ == '__main__':
    logger.info('This is an info message with utf-8 characters: 你好，林穗生!')
