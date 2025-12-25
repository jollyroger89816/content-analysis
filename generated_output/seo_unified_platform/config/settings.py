# -*- coding: utf-8 -*-
"""
统一SEO分析平台 - 配置文件
"""
import os

class Config:
    """基础配置类"""

    # 基础目录
    BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = False
    TESTING = False

    # 数据库配置
    DATABASE_PATH = os.path.join(BASE_DIR, 'seo_platform.db')
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{DATABASE_PATH}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 上传文件配置
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'txt', 'csv', 'json'}

    # 日志配置
    LOG_LEVEL = 'INFO'
    LOG_FILE = os.path.join(BASE_DIR, 'logs', 'seo_platform.log')
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5

    # 并发处理配置
    MAX_WORKERS = 4
    REQUEST_TIMEOUT = 15

    # 重复检测配置
    DUPLICATE_THRESHOLD = 15.0  # 重复率阈值(%)
    SIMILARITY_THRESHOLD = 0.65  # 相似度阈值(与原项目一致)

    # 质量评分配置
    IMPLICIT_LANGUAGE_WEIGHT = 0.3  # 暗示性语言权重
    DUPLICATE_CONTENT_WEIGHT = 0.7  # 内容重复权重

    # 千帆API配置
    QIANFAN_ACCESS_KEY = os.environ.get('QIANFAN_ACCESS_KEY', '')
    QIANFAN_SECRET_KEY = os.environ.get('QIANFAN_SECRET_KEY', '')
    QIANFAN_MODEL = 'ERNIE-4.0-8K'

    # 缓存配置
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 3600

    # 报告配置
    REPORT_OUTPUT_DIR = os.path.join(BASE_DIR, 'reports')
    REPORT_TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    ENV = 'development'


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    ENV = 'production'
    # 生产环境建议使用PostgreSQL
    # SQLALCHEMY_DATABASE_URI = 'postgresql://user:password@localhost/seo_platform'


class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    DATABASE_PATH = ':memory:'


# 配置字典
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
