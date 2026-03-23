"""
日志工具模块
提供统一的日志记录功能
"""
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

def setup_logger(name, log_file=None, level=logging.INFO):
    """
    设置日志记录器

    Args:
        name: 日志记录器名称
        log_file: 日志文件路径
        level: 日志级别

    Returns:
        logger: 配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加处理器
    if logger.handlers:
        return logger

    # 格式化
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器
    if log_file:
        # 确保日志目录存在
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # 使用RotatingFileHandler限制日志文件大小
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name):
    """
    获取已存在的日志记录器

    Args:
        name: 日志记录器名称

    Returns:
        logger: 日志记录器
    """
    return logging.getLogger(name)


class LoggerMixin:
    """
    日志混入类，为类提供logger属性

    使用方式:
        class MyClass(LoggerMixin):
            def __init__(self):
                super().__init__()
                self.logger.info('Initializing...')
    """

    def __init__(self):
        self._logger = None

    @property
    def logger(self):
        if self._logger is None:
            self._logger = logging.getLogger(self.__class__.__name__)
        return self._logger


def log_execution_time(logger=None, level=logging.DEBUG):
    """
    函数执行时间装饰器

    使用方式:
        @log_execution_time()
        def my_function():
            pass
    """
    def decorator(func):
        nonlocal logger
        if logger is None:
            logger = logging.getLogger(func.__module__)

        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            result = func(*args, **kwargs)
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            logger.log(
                level,
                f"{func.__name__} executed in {execution_time:.3f}s"
            )

            return result

        return wrapper
    return decorator


# 便捷函数
def debug(msg, *args, **kwargs):
    """记录DEBUG级别日志"""
    logging.debug(msg, *args, **kwargs)

def info(msg, *args, **kwargs):
    """记录INFO级别日志"""
    logging.info(msg, *args, **kwargs)

def warning(msg, *args, **kwargs):
    """记录WARNING级别日志"""
    logging.warning(msg, *args, **kwargs)

def error(msg, *args, **kwargs):
    """记录ERROR级别日志"""
    logging.error(msg, *args, **kwargs)

def critical(msg, *args, **kwargs):
    """记录CRITICAL级别日志"""
    logging.critical(msg, *args, **kwargs)


# 如果直接运行此文件，进行测试
if __name__ == '__main__':
    # 设置日志
    logger = setup_logger('test', 'logs/test.log', logging.DEBUG)

    # 测试各级别日志
    logger.debug('This is a debug message')
    logger.info('This is an info message')
    logger.warning('This is a warning message')
    logger.error('This is an error message')
    logger.critical('This is a critical message')

    # 测试执行时间装饰器
    @log_execution_time(logger)
    def test_function():
        import time
        time.sleep(0.1)
        return 'done'

    result = test_function()
    print(f'Function returned: {result}')
