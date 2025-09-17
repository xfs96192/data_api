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
        """初始化数据库表结构"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 数据指标表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS indicators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    name TEXT NOT NULL,
                    wind_code TEXT NOT NULL UNIQUE,
                    wind_field TEXT,
                    data_source TEXT NOT NULL,  -- 'WSD' or 'EDB'
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 时间序列数据表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS time_series_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wind_code TEXT NOT NULL,
                    date TEXT NOT NULL,
                    value REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (wind_code) REFERENCES indicators (wind_code),
                    UNIQUE(wind_code, date)
                )
            ''')
            
            # 数据更新日志表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS update_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wind_code TEXT NOT NULL,
                    update_type TEXT NOT NULL,  -- 'full' or 'incremental'
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
                CREATE INDEX IF NOT EXISTS idx_time_series_wind_code_date 
                ON time_series_data (wind_code, date)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_indicators_category 
                ON indicators (category)
            ''')
            
            conn.commit()
    
    def load_indicators_from_excel(self, excel_path: str):
        """从Excel文件加载指标到数据库"""
        df = pd.read_excel(excel_path)
        
        with sqlite3.connect(self.db_path) as conn:
            for _, row in df.iterrows():
                wind_field = row['wind字段'] if pd.notna(row['wind字段']) else None
                data_source = 'WSD' if wind_field else 'EDB'
                
                conn.execute('''
                    INSERT OR REPLACE INTO indicators 
                    (category, name, wind_code, wind_field, data_source, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    row['指标类别'],
                    row['指标名称'],
                    row['wind代码'],
                    wind_field,
                    data_source,
                    datetime.now()
                ))
            conn.commit()
    
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
    
    def insert_time_series_data(self, wind_code: str, data: pd.DataFrame):
        """插入时间序列数据"""
        with sqlite3.connect(self.db_path) as conn:
            for date_str, value in data.items():
                if pd.notna(value):
                    conn.execute('''
                        INSERT OR REPLACE INTO time_series_data (wind_code, date, value)
                        VALUES (?, ?, ?)
                    ''', (wind_code, str(date_str)[:10], float(value)))
            conn.commit()
    
    def get_time_series_data(
        self, 
        wind_code: str, 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """获取时间序列数据"""
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT date, value FROM time_series_data WHERE wind_code = ?"
            params = [wind_code]
            
            if start_date:
                query += " AND date >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND date <= ?"
                params.append(end_date)
            
            query += " ORDER BY date"
            
            df = pd.read_sql_query(query, conn, params=params)
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
            
            return df
    
    def log_update(
        self, 
        wind_code: str, 
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
                (wind_code, update_type, start_date, end_date, records_count, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (wind_code, update_type, start_date, end_date, records_count, status, error_message))
            conn.commit()
    
    def get_last_update_date(self, wind_code: str) -> Optional[str]:
        """获取指标的最后更新日期"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT MAX(date) FROM time_series_data WHERE wind_code = ?
            ''', (wind_code,))
            result = cursor.fetchone()
            return result[0] if result[0] else None