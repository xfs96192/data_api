import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""
    
    # 数据库配置
    DATABASE_PATH: str = "data/financial_data.db"
    
    # Wind API配置
    WIND_CONNECTION_TIMEOUT: int = 30
    WIND_REQUEST_INTERVAL: float = 0.5  # 请求间隔时间（秒）
    
    # Wind MCP服务配置
    WIND_MCP_HOST: str = "localhost"
    WIND_MCP_PORT: int = 8889
    WIND_MCP_TIMEOUT: int = 30
    WIND_MCP_RETRY_ATTEMPTS: int = 3
    
    # 数据更新配置
    HISTORICAL_START_YEAR: int = 2000
    UPDATE_BATCH_SIZE: int = 10  # 批量更新大小
    MAX_RETRY_ATTEMPTS: int = 3
    
    # API配置
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 1
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"
    LOG_MAX_SIZE: int = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT: int = 5
    
    # 调度器配置
    DAILY_UPDATE_TIME: str = "18:00"  # 每日更新时间
    WEEKLY_UPDATE_TIME: str = "02:00"  # 每周全量更新时间
    SCHEDULER_CHECK_INTERVAL: int = 60  # 调度器检查间隔（秒）
    
    # 数据验证配置
    MAX_MISSING_DAYS: int = 7  # 最大允许缺失天数
    DATA_QUALITY_THRESHOLD: float = 0.95  # 数据质量阈值
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# 创建全局配置实例
settings = Settings()


def get_database_url() -> str:
    """获取数据库URL"""
    return f"sqlite:///{settings.DATABASE_PATH}"


def ensure_directories():
    """确保必要的目录存在"""
    directories = [
        "data",
        settings.LOG_DIR,
        "config",
        "temp"
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)


def get_trading_calendar():
    """获取交易日历配置"""
    return {
        "exchanges": ["SSE", "SZSE"],  # 上交所、深交所
        "holidays": [
            # 这里可以配置节假日
            "2024-01-01",  # 元旦
            "2024-02-10",  # 春节
            # ... 更多节假日
        ]
    }


def get_wind_fields_mapping():
    """获取Wind字段映射"""
    return {
        # 价格相关字段
        "close": "收盘价",
        "open": "开盘价", 
        "high": "最高价",
        "low": "最低价",
        "volume": "成交量",
        "amt": "成交额",
        
        # 估值相关字段
        "val_pe_nonnegative": "市盈率(TTM,非负)",
        "val_pb_lf": "市净率(LF)",
        "val_ps_ttm": "市销率(TTM)",
        "val_pcf_ocf_ttm": "市现率(OCF,TTM)",
        
        # 技术指标
        "ma5": "5日均线",
        "ma10": "10日均线",
        "ma20": "20日均线",
        "ma60": "60日均线",
        
        # 基本面指标
        "roe_ttm": "净资产收益率(TTM)",
        "roa_ttm": "总资产收益率(TTM)",
        "grossprofitmargin_ttm": "毛利率(TTM)",
        "netprofitmargin_ttm": "净利率(TTM)"
    }


def get_data_source_config():
    """获取数据源配置"""
    return {
        "WSD": {
            "description": "万得时间序列数据",
            "frequency": ["daily", "weekly", "monthly", "quarterly", "yearly"],
            "delay_seconds": 0.5
        },
        "EDB": {
            "description": "万得经济数据库",
            "frequency": ["monthly", "quarterly", "yearly"],
            "delay_seconds": 1.0
        },
        "WSS": {
            "description": "万得截面数据",
            "frequency": ["realtime"],
            "delay_seconds": 0.2
        }
    }