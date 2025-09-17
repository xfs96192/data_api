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
            self.logger.error("WindPy库未安装，使用MCP客户端")
            self.wind_connected = False
            self.w = None
            self._init_mcp_client()
        except Exception as e:
            self.logger.error(f"WindPy初始化异常: {str(e)}，使用MCP客户端")
            self.wind_connected = False
            self.w = None
            self._init_mcp_client()
    
    def _init_mcp_client(self):
        """初始化MCP客户端"""
        try:
            from src.mcp_client import MCPWindClient
            self.mcp_client = MCPWindClient()
            self.wind_connected = True
            self.logger.info("MCP Wind客户端初始化成功")
        except Exception as e:
            self.logger.error(f"MCP客户端初始化失败: {str(e)}")
            self.wind_connected = False
    
    def test_connection(self) -> bool:
        """测试连接状态"""
        if self.w:
            # WindPy连接测试
            try:
                result = self.w.wsd("000001.SH", "close", "2024-01-01", "2024-01-01", "")
                return result.ErrorCode == 0
            except:
                return False
        elif hasattr(self, 'mcp_client'):
            # MCP连接测试
            try:
                return self.mcp_client.test_connection()
            except:
                return False
        return False
    
    def fetch_wsd_single_field(
        self, 
        wind_code: str, 
        field: str, 
        start_date: str, 
        end_date: str
    ) -> Optional[pd.Series]:
        """
        获取单字段WSD数据
        """
        try:
            self.logger.info(f"获取WSD单字段数据: {wind_code}.{field}, {start_date} - {end_date}")
            
            if not self.wind_connected:
                self.logger.error("Wind连接未初始化")
                return None
            
            if self.w:
                # 使用WindPy
                result = self.w.wsd(wind_code, field, start_date, end_date, "")
                
                if result.ErrorCode == 0:
                    data = result.Data
                    times = result.Times
                    
                    if data and times and len(data) > 0:
                        values = data[0] if isinstance(data[0], list) else data
                        series = pd.Series(
                            data=values,
                            index=pd.to_datetime(times),
                            name=field
                        )
                        series = series.dropna()
                        self.logger.info(f"成功获取 {len(series)} 条数据")
                        return series
                else:
                    self.logger.error(f"WSD数据获取失败，错误码: {result.ErrorCode}")
                    return None
            
            elif hasattr(self, 'mcp_client'):
                # 使用MCP客户端
                return self.mcp_client.get_wsd_data(wind_code, field, start_date, end_date)
            
            return None
            
        except Exception as e:
            self.logger.error(f"获取WSD数据异常: {str(e)}")
            return None
    
    def fetch_wsd_multi_fields(
        self, 
        wind_code: str, 
        fields: List[str], 
        start_date: str, 
        end_date: str
    ) -> Optional[pd.DataFrame]:
        """
        获取多字段WSD数据
        
        Args:
            wind_code: Wind代码
            fields: 字段列表
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            pd.DataFrame: 多字段时间序列数据，列名为字段名
        """
        try:
            self.logger.info(f"获取WSD多字段数据: {wind_code}, {fields}, {start_date} - {end_date}")
            
            if not self.wind_connected:
                self.logger.error("Wind连接未初始化")
                return None
            
            if self.w:
                # 使用WindPy批量获取多字段
                field_str = ",".join(fields)
                result = self.w.wsd(wind_code, field_str, start_date, end_date, "")
                
                if result.ErrorCode == 0:
                    data = result.Data
                    times = result.Times
                    
                    if data and times:
                        # 构建DataFrame
                        df_data = {}
                        for i, field in enumerate(fields):
                            if i < len(data):
                                df_data[field] = data[i]
                        
                        df = pd.DataFrame(
                            data=df_data,
                            index=pd.to_datetime(times)
                        )
                        
                        # 移除全部为空的行
                        df = df.dropna(how='all')
                        
                        self.logger.info(f"成功获取 {len(df)} 条记录，{len(fields)} 个字段")
                        return df
                else:
                    self.logger.error(f"WSD多字段数据获取失败，错误码: {result.ErrorCode}")
                    return None
            
            elif hasattr(self, 'mcp_client'):
                # 使用MCP客户端逐个获取
                all_data = {}
                for field in fields:
                    series = self.mcp_client.get_wsd_data(wind_code, field, start_date, end_date)
                    if series is not None:
                        all_data[field] = series
                
                if all_data:
                    df = pd.DataFrame(all_data)
                    df = df.dropna(how='all')
                    return df
                else:
                    return None
            
            return None
            
        except Exception as e:
            self.logger.error(f"获取WSD多字段数据异常: {str(e)}")
            return None
    
    def fetch_edb_data(
        self, 
        wind_code: str, 
        start_date: str, 
        end_date: str
    ) -> Optional[pd.Series]:
        """
        获取EDB数据（经济数据库）
        """
        try:
            self.logger.info(f"获取EDB数据: {wind_code}, {start_date} - {end_date}")
            
            if not self.wind_connected:
                self.logger.error("Wind连接未初始化")
                return None
            
            if self.w:
                # 使用WindPy
                result = self.w.edb(wind_code, start_date, end_date, "")
                
                if result.ErrorCode == 0:
                    data = result.Data
                    times = result.Times
                    
                    if data and times and len(data) > 0:
                        values = data[0] if isinstance(data[0], list) else data
                        series = pd.Series(
                            data=values,
                            index=pd.to_datetime(times),
                            name='value'
                        )
                        series = series.dropna()
                        self.logger.info(f"成功获取 {len(series)} 条数据")
                        return series
                else:
                    self.logger.error(f"EDB数据获取失败，错误码: {result.ErrorCode}")
                    return None
            
            elif hasattr(self, 'mcp_client'):
                # 使用MCP客户端
                return self.mcp_client.get_edb_data(wind_code, start_date, end_date)
            
            return None
            
        except Exception as e:
            self.logger.error(f"获取EDB数据异常: {str(e)}")
            return None
    
    def fetch_data_by_indicator(
        self, 
        indicator: Dict[str, Any], 
        start_date: str, 
        end_date: str
    ) -> Optional[pd.DataFrame]:
        """
        根据指标信息获取数据 - 支持多字段
        
        Args:
            indicator: 指标信息字典，包含wind_code, data_source等
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            pd.DataFrame: 数据，如果是多字段则列名为字段名，单字段则列名为字段名
        """
        try:
            wind_code = indicator['wind_code']
            data_source = indicator.get('data_source', 'EDB')
            
            if data_source == 'WSD':
                # 从数据库获取该指标的所有字段
                from src.database.models_v2 import DatabaseManager
                db_manager = DatabaseManager()
                fields = db_manager.get_indicator_fields(wind_code)
                
                if len(fields) == 1:
                    # 单字段
                    field_name = fields[0]['field_name']
                    series = self.fetch_wsd_single_field(wind_code, field_name, start_date, end_date)
                    if series is not None:
                        return pd.DataFrame({field_name: series})
                    return None
                
                elif len(fields) > 1:
                    # 多字段
                    field_names = [f['field_name'] for f in fields]
                    return self.fetch_wsd_multi_fields(wind_code, field_names, start_date, end_date)
                
                else:
                    self.logger.error(f"指标 {wind_code} 没有字段映射")
                    return None
            
            else:
                # EDB数据
                series = self.fetch_edb_data(wind_code, start_date, end_date)
                if series is not None:
                    return pd.DataFrame({'value': series})
                return None
                
        except Exception as e:
            self.logger.error(f"获取指标数据异常 {indicator.get('wind_code', 'Unknown')}: {str(e)}")
            return None