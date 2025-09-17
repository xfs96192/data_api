#!/usr/bin/env python3
"""
数据库结构迁移 - 支持多字段存储
"""

import sqlite3
import pandas as pd
import os
from datetime import datetime

def backup_current_database():
    """备份当前数据库"""
    db_path = "data/financial_data.db"
    backup_path = f"data/financial_data_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    
    if os.path.exists(db_path):
        import shutil
        shutil.copy2(db_path, backup_path)
        print(f"✓ 数据库已备份到: {backup_path}")
        return backup_path
    else:
        print("原数据库不存在，无需备份")
        return None

def create_new_database_structure():
    """创建新的数据库结构"""
    
    db_path = "data/financial_data.db"
    
    # 重命名旧数据库
    if os.path.exists(db_path):
        old_db_path = f"data/financial_data_old_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        os.rename(db_path, old_db_path)
        print(f"✓ 旧数据库重命名为: {old_db_path}")
    
    # 创建新数据库
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # 1. 指标基础信息表 (不变)
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
        
        # 2. 指标字段映射表 (新增)
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
        
        # 3. 多维度时间序列数据表 (修改)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS time_series_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wind_code TEXT NOT NULL,
                field_name TEXT NOT NULL,  -- 新增字段名
                date TEXT NOT NULL,
                value REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (wind_code) REFERENCES indicators (wind_code),
                UNIQUE(wind_code, field_name, date)
            )
        ''')
        
        # 4. 更新日志表 (修改)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS update_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wind_code TEXT NOT NULL,
                field_name TEXT,  -- 新增字段名，为空表示所有字段
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
        print("✓ 新数据库结构创建完成")

def load_indicators_and_fields():
    """从Excel加载指标和字段映射"""
    
    df = pd.read_excel('data/数据指标.xlsx')
    
    with sqlite3.connect('data/financial_data.db') as conn:
        cursor = conn.cursor()
        
        indicators_added = 0
        fields_added = 0
        
        for _, row in df.iterrows():
            wind_code = row['wind代码']
            category = row['指标类别']
            name = row['指标名称']
            wind_field = row['wind字段'] if pd.notna(row['wind字段']) else None
            data_source = 'WSD' if wind_field else 'EDB'
            
            # 插入指标基础信息
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO indicators 
                    (category, name, wind_code, data_source, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (category, name, wind_code, data_source, datetime.now()))
                
                if cursor.rowcount > 0:
                    indicators_added += 1
            except Exception as e:
                print(f"插入指标失败 {wind_code}: {e}")
                continue
            
            # 插入字段映射
            if wind_field:  # WSD数据有具体字段
                field_display_name = get_field_display_name(wind_field)
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO indicator_fields 
                        (wind_code, field_name, field_display_name)
                        VALUES (?, ?, ?)
                    ''', (wind_code, wind_field, field_display_name))
                    
                    if cursor.rowcount > 0:
                        fields_added += 1
                except Exception as e:
                    print(f"插入字段映射失败 {wind_code}.{wind_field}: {e}")
            else:  # EDB数据使用默认字段
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO indicator_fields 
                        (wind_code, field_name, field_display_name)
                        VALUES (?, ?, ?)
                    ''', (wind_code, 'value', '数值'))
                    
                    if cursor.rowcount > 0:
                        fields_added += 1
                except Exception as e:
                    print(f"插入EDB字段映射失败 {wind_code}: {e}")
        
        conn.commit()
        print(f"✓ 加载完成: {indicators_added}个指标, {fields_added}个字段映射")

def get_field_display_name(field_name):
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

def verify_new_structure():
    """验证新数据库结构"""
    
    with sqlite3.connect('data/financial_data.db') as conn:
        cursor = conn.cursor()
        
        # 检查表结构
        tables = ['indicators', 'indicator_fields', 'time_series_data', 'update_logs']
        
        print("\n数据库结构验证:")
        print("=" * 60)
        
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            print(f"\n{table} 表结构:")
            for col in columns:
                print(f"  - {col[1]} ({col[2]})")
        
        # 统计数据
        cursor.execute("SELECT COUNT(*) FROM indicators")
        indicators_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM indicator_fields")
        fields_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM time_series_data")
        data_count = cursor.fetchone()[0]
        
        print(f"\n数据统计:")
        print(f"指标数量: {indicators_count}")
        print(f"字段映射数量: {fields_count}")
        print(f"时间序列数据点: {data_count}")
        
        # 显示多字段指标
        cursor.execute('''
            SELECT wind_code, COUNT(*) as field_count 
            FROM indicator_fields 
            GROUP BY wind_code 
            HAVING COUNT(*) > 1
            ORDER BY field_count DESC
            LIMIT 10
        ''')
        
        multi_field_indicators = cursor.fetchall()
        print(f"\n多字段指标示例:")
        for wind_code, field_count in multi_field_indicators:
            cursor.execute('''
                SELECT field_name, field_display_name 
                FROM indicator_fields 
                WHERE wind_code = ?
            ''', (wind_code,))
            fields = cursor.fetchall()
            print(f"  {wind_code}: {field_count}个字段")
            for field_name, display_name in fields:
                print(f"    - {field_name} ({display_name})")

def main():
    """主函数"""
    print("开始数据库结构迁移...")
    
    # 1. 备份当前数据库
    backup_path = backup_current_database()
    
    # 2. 创建新数据库结构
    create_new_database_structure()
    
    # 3. 加载指标和字段映射
    load_indicators_and_fields()
    
    # 4. 验证新结构
    verify_new_structure()
    
    print("\n✓ 数据库结构迁移完成！")
    print(f"新数据库支持多字段存储，可以正确区分同一wind_code的不同维度数据")

if __name__ == "__main__":
    main()