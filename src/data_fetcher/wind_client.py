import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import logging
import time


class WindDataFetcher:
    def __init__(self, mcp_host="localhost", mcp_port=8889):
        self.logger = logging.getLogger(__name__)
        self.mcp_host = mcp_host
        self.mcp_port = mcp_port
        self.wind_connected = False
        self.setup_logging()
        self.init_wind_api()
    
    def setup_logging(self):
        """设置日志配置"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/wind_data_fetcher.log'),
                logging.StreamHandler()
            ]
        )
    
    def init_wind_api(self):
        """初始化Wind API"""
        try:
            from WindPy import w
            self.w = w
            
            # 启动Wind API
            result = self.w.start()
            if result.ErrorCode == 0:
                self.wind_connected = True
                self.logger.info("WindPy API初始化成功")
            else:
                self.wind_connected = False
                self.logger.error(f"WindPy API初始化失败，错误码: {result.ErrorCode}")
                
        except ImportError:
            self.logger.error("WindPy库未安装")
            self.wind_connected = False
            self.w = None
        except Exception as e:
            self.logger.error(f"WindPy初始化异常: {str(e)}")
            self.wind_connected = False
            self.w = None
    
    def fetch_wsd_data(
        self, 
        wind_code: str, 
        field: str, 
        start_date: str, 
        end_date: str
    ) -> Optional[pd.Series]:
        """
        获取WSD数据（日时间序列数据）
        
        Args:
            wind_code: Wind代码，如 '000001.SH'
            field: 字段名，如 'close', 'val_pe_nonnegative'
            start_date: 开始日期，格式 'YYYY-MM-DD'
            end_date: 结束日期，格式 'YYYY-MM-DD'
        
        Returns:
            pd.Series: 时间序列数据
        """
        try:
            self.logger.info(f"获取WSD数据: {wind_code}, {field}, {start_date} - {end_date}")
            
            if not self.wind_connected or self.w is None:
                self.logger.error("WindPy连接未初始化")
                return None
            
            # 直接调用WindPy WSD接口
            result = self.w.wsd(wind_code, field, start_date, end_date, "")
            
            if result.ErrorCode == 0:
                data = result.Data
                times = result.Times
                
                if data and times and len(data) > 0:
                    # 处理数据格式
                    values = data[0] if isinstance(data[0], list) else data
                    
                    # 创建时间序列
                    series = pd.Series(
                        data=values,
                        index=pd.to_datetime(times),
                        name=field
                    )
                    
                    # 移除空值
                    series = series.dropna()
                    
                    self.logger.info(f"成功获取 {len(series)} 条数据")
                    return series
                else:
                    self.logger.warning(f"未获取到数据: {wind_code}")
                    return None
            else:
                error_msg = f"WindPy API错误: {result.ErrorCode}"
                self.logger.error(error_msg)
                return None
                
        except Exception as e:
            self.logger.error(f"获取WSD数据失败: {str(e)}")
            return None
    
    def fetch_edb_data(
        self, 
        wind_code: str, 
        start_date: str, 
        end_date: str
    ) -> Optional[pd.Series]:
        """
        获取EDB数据（经济数据库）
        
        Args:
            wind_code: Wind代码，如 'M6637815'
            start_date: 开始日期，格式 'YYYY-MM-DD'
            end_date: 结束日期，格式 'YYYY-MM-DD'
        
        Returns:
            pd.Series: 时间序列数据
        """
        try:
            self.logger.info(f"获取EDB数据: {wind_code}, {start_date} - {end_date}")
            
            if not self.wind_connected or self.w is None:
                self.logger.error("WindPy连接未初始化")
                return None
            
            # 直接调用WindPy EDB接口
            result = self.w.edb(wind_code, start_date, end_date, "")
            
            if result.ErrorCode == 0:
                data = result.Data
                times = result.Times
                
                if data and times and len(data) > 0:
                    # 处理数据格式
                    values = data[0] if isinstance(data[0], list) else data
                    
                    # 创建时间序列
                    series = pd.Series(
                        data=values,
                        index=pd.to_datetime(times),
                        name=wind_code
                    )
                    
                    # 移除空值
                    series = series.dropna()
                    
                    self.logger.info(f"成功获取 {len(series)} 条EDB数据")
                    return series
                else:
                    self.logger.warning(f"未获取到EDB数据: {wind_code}")
                    return None
            else:
                error_msg = f"WindPy EDB API错误: {result.ErrorCode}"
                self.logger.error(error_msg)
                return None
                
        except Exception as e:
            self.logger.error(f"获取EDB数据失败: {str(e)}")
            return None
    
    def fetch_data_by_indicator(
        self, 
        indicator: Dict[str, Any], 
        start_date: str, 
        end_date: str
    ) -> Optional[pd.Series]:
        """
        根据指标配置获取数据
        
        Args:
            indicator: 指标字典，包含wind_code, wind_field, data_source等
            start_date: 开始日期
            end_date: 结束日期
        
        Returns:
            pd.Series: 时间序列数据
        """
        wind_code = indicator['wind_code']
        data_source = indicator['data_source']
        
        if data_source == 'WSD':
            wind_field = indicator['wind_field']
            return self.fetch_wsd_data(wind_code, wind_field, start_date, end_date)
        elif data_source == 'EDB':
            return self.fetch_edb_data(wind_code, start_date, end_date)
        else:
            self.logger.error(f"未知的数据源: {data_source}")
            return None
    
    def test_connection(self) -> bool:
        """测试Wind连接"""
        try:
            if not self.wind_connected or self.w is None:
                return False
            
            # 尝试获取一个简单的数据来验证连接
            result = self.w.wsd("000001.SH", "close", "2024-08-16", "2024-08-16", "")
            return result.ErrorCode == 0
            
        except Exception as e:
            self.logger.error(f"测试连接失败: {str(e)}")
            return False
    
