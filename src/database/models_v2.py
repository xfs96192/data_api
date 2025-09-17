import sqlite3
import pandas as pd
from datetime import datetime, date
from typing import Optional, List, Dict, Any
import os


class DatabaseManager:
    def __init__(self, db_path: str = "data/financial_data.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_database()
    
    def init_database(self):
        """初始化数据库表结构 - 支持多字段"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 1. 指标基础信息表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS indicators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    name TEXT NOT NULL,
                    wind_code TEXT NOT NULL,
                    data_source TEXT NOT NULL,  -- 'WSD' or 'EDB'
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(wind_code)
                )
            ''')
            
            # 2. 指标字段映射表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS indicator_fields (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wind_code TEXT NOT NULL,
                    field_name TEXT NOT NULL,  -- 'close', 'val_pe_nonnegative', etc.
                    field_display_name TEXT NOT NULL,  -- '收盘价', '市盈率', etc.
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (wind_code) REFERENCES indicators (wind_code),
                    UNIQUE(wind_code, field_name)
                )
            ''')
            
            # 3. 多维度时间序列数据表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS time_series_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wind_code TEXT NOT NULL,
                    field_name TEXT NOT NULL,  -- 字段名
                    date TEXT NOT NULL,
                    value REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (wind_code) REFERENCES indicators (wind_code),
                    UNIQUE(wind_code, field_name, date)
                )
            ''')
            
            # 4. 更新日志表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS update_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wind_code TEXT NOT NULL,
                    field_name TEXT,  -- 字段名，为空表示所有字段
                    update_type TEXT NOT NULL,  -- 'full', 'incremental', 'retry'
                    start_date TEXT,
                    end_date TEXT,
                    records_count INTEGER,
                    status TEXT NOT NULL,  -- 'success' or 'failed'
                    error_message TEXT,
                    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (wind_code) REFERENCES indicators (wind_code)
                )
            ''')
            
            # 创建索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_time_series_wind_code_field_date 
                ON time_series_data (wind_code, field_name, date)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_time_series_wind_code_date 
                ON time_series_data (wind_code, date)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_indicators_category 
                ON indicators (category)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_indicator_fields_wind_code 
                ON indicator_fields (wind_code)
            ''')
            
            conn.commit()
    
    def load_indicators_from_excel(self, excel_path: str):
        """从Excel文件加载指标到数据库"""
        df = pd.read_excel(excel_path)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for _, row in df.iterrows():
                wind_code = row['wind代码']
                category = row['指标类别']
                name = row['指标名称']
                wind_field = row['wind字段'] if pd.notna(row['wind字段']) else None
                data_source = 'WSD' if wind_field else 'EDB'
                
                # 插入指标基础信息
                cursor.execute('''
                    INSERT OR REPLACE INTO indicators 
                    (category, name, wind_code, data_source, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (category, name, wind_code, data_source, datetime.now()))
                
                # 插入字段映射
                if wind_field:  # WSD数据有具体字段
                    field_display_name = self._get_field_display_name(wind_field)
                    cursor.execute('''
                        INSERT OR REPLACE INTO indicator_fields 
                        (wind_code, field_name, field_display_name)
                        VALUES (?, ?, ?)
                    ''', (wind_code, wind_field, field_display_name))
                else:  # EDB数据使用默认字段
                    cursor.execute('''
                        INSERT OR REPLACE INTO indicator_fields 
                        (wind_code, field_name, field_display_name)
                        VALUES (?, ?, ?)
                    ''', (wind_code, 'value', '数值'))
            
            conn.commit()
    
    def _get_field_display_name(self, field_name):
        """获取字段的中文显示名称"""
        field_mapping = {
            'close': '收盘价',
            'val_pe_nonnegative': '市盈率',
            'open': '开盘价',
            'high': '最高价',
            'low': '最低价',
            'volume': '成交量',
            'amt': '成交额',
            'pct_chg': '涨跌幅',
            'value': '数值'
        }
        return field_mapping.get(field_name, field_name)
    
    def get_indicators(self, category: Optional[str] = None) -> List[Dict]:
        """获取指标列表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if category:
                cursor.execute(
                    "SELECT * FROM indicators WHERE category = ? ORDER BY name",
                    (category,)
                )
            else:
                cursor.execute("SELECT * FROM indicators ORDER BY category, name")
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_indicator_fields(self, wind_code: str) -> List[Dict]:
        """获取指标的所有字段"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM indicator_fields WHERE wind_code = ? ORDER BY field_name",
                (wind_code,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def insert_time_series_data(self, wind_code: str, field_name: str, data: pd.DataFrame):
        """插入单字段时间序列数据"""
        with sqlite3.connect(self.db_path) as conn:
            for date_str, value in data.items():
                if pd.notna(value):
                    conn.execute('''
                        INSERT OR REPLACE INTO time_series_data (wind_code, field_name, date, value)
                        VALUES (?, ?, ?, ?)
                    ''', (wind_code, field_name, str(date_str)[:10], float(value)))
            conn.commit()
    
    def insert_multi_field_data(self, wind_code: str, data: pd.DataFrame):
        """插入多字段时间序列数据
        
        Args:
            wind_code: Wind代码
            data: 包含多字段的DataFrame，列名为字段名，索引为日期
        """
        with sqlite3.connect(self.db_path) as conn:
            for date_idx, row in data.iterrows():
                date_str = str(date_idx)[:10]
                for field_name, value in row.items():
                    if pd.notna(value):
                        conn.execute('''
                            INSERT OR REPLACE INTO time_series_data (wind_code, field_name, date, value)
                            VALUES (?, ?, ?, ?)
                        ''', (wind_code, field_name, date_str, float(value)))
            conn.commit()
    
    def get_time_series_data(
        self, 
        wind_code: str, 
        field_name: Optional[str] = None,
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """获取时间序列数据"""
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT date, field_name, value FROM time_series_data WHERE wind_code = ?"
            params = [wind_code]
            
            if field_name:
                query += " AND field_name = ?"
                params.append(field_name)
            
            if start_date:
                query += " AND date >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND date <= ?"
                params.append(end_date)
            
            query += " ORDER BY date, field_name"
            
            df = pd.read_sql_query(query, conn, params=params)
            
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'])
                # 如果有多个字段，透视表格式
                if field_name is None and len(df['field_name'].unique()) > 1:
                    df = df.pivot(index='date', columns='field_name', values='value')
                else:
                    df.set_index('date', inplace=True)
                    if len(df.columns) == 2:  # 只有field_name和value
                        df = df['value'].to_frame('value')
            
            return df
    
    def log_update(
        self, 
        wind_code: str,
        field_name: Optional[str],
        update_type: str, 
        start_date: str, 
        end_date: str,
        records_count: int,
        status: str,
        error_message: Optional[str] = None
    ):
        """记录更新日志"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO update_logs 
                (wind_code, field_name, update_type, start_date, end_date, records_count, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (wind_code, field_name, update_type, start_date, end_date, records_count, status, error_message))
            conn.commit()
    
    def get_last_update_date(self, wind_code: str, field_name: Optional[str] = None) -> Optional[str]:
        """获取指标字段的最后更新日期"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if field_name:
                cursor.execute('''
                    SELECT MAX(date) FROM time_series_data WHERE wind_code = ? AND field_name = ?
                ''', (wind_code, field_name))
            else:
                cursor.execute('''
                    SELECT MAX(date) FROM time_series_data WHERE wind_code = ?
                ''', (wind_code,))
            
            result = cursor.fetchone()
            return result[0] if result[0] else None
    
    def get_data_summary(self) -> Dict:
        """获取数据库统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 统计指标数量
            cursor.execute("SELECT COUNT(*) FROM indicators")
            indicators_count = cursor.fetchone()[0]
            
            # 统计字段数量
            cursor.execute("SELECT COUNT(*) FROM indicator_fields")
            fields_count = cursor.fetchone()[0]
            
            # 统计数据点数量
            cursor.execute("SELECT COUNT(*) FROM time_series_data")
            data_points = cursor.fetchone()[0]
            
            # 按类别统计指标
            cursor.execute('''
                SELECT category, COUNT(*) 
                FROM indicators 
                GROUP BY category 
                ORDER BY COUNT(*) DESC
            ''')
            category_stats = dict(cursor.fetchall())
            
            # 多字段指标统计
            cursor.execute('''
                SELECT wind_code, COUNT(*) as field_count 
                FROM indicator_fields 
                GROUP BY wind_code 
                HAVING COUNT(*) > 1
            ''')
            multi_field_count = len(cursor.fetchall())
            
            return {
                'indicators_count': indicators_count,
                'fields_count': fields_count,
                'data_points': data_points,
                'category_stats': category_stats,
                'multi_field_indicators': multi_field_count
            }