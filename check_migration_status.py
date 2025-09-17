#!/usr/bin/env python3
"""
检查数据迁移状态
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.database.models_v2 import DatabaseManager
import sqlite3

def check_migration_status():
    """检查迁移状态"""
    
    db_manager = DatabaseManager()
    
    print("📊 数据迁移状态检查")
    print("=" * 50)
    
    with sqlite3.connect(db_manager.db_path) as conn:
        cursor = conn.cursor()
        
        # 1. 总体统计
        cursor.execute("SELECT COUNT(*) FROM indicators")
        total_indicators = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM indicator_fields")
        total_fields = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM time_series_data")
        total_data_points = cursor.fetchone()[0]
        
        print(f"📈 总体统计:")
        print(f"指标数量: {total_indicators}")
        print(f"字段映射: {total_fields}")  
        print(f"数据点总数: {total_data_points:,}")
        
        # 2. 多字段指标统计
        cursor.execute("""
            SELECT COUNT(*) FROM (
                SELECT wind_code FROM indicator_fields 
                GROUP BY wind_code HAVING COUNT(*) > 1
            )
        """)
        multi_field_count = cursor.fetchone()[0]
        print(f"多字段指标: {multi_field_count}")
        
        # 3. 检查多字段指标的数据状态
        cursor.execute("""
            SELECT i.wind_code, i.name,
                   COUNT(DISTINCT f.field_name) as field_count,
                   COUNT(t.id) as data_points
            FROM indicators i
            JOIN indicator_fields f ON i.wind_code = f.wind_code
            LEFT JOIN time_series_data t ON i.wind_code = t.wind_code
            WHERE i.wind_code IN (
                SELECT wind_code FROM indicator_fields 
                GROUP BY wind_code HAVING COUNT(*) > 1
            )
            GROUP BY i.wind_code, i.name
            ORDER BY data_points DESC
        """)
        
        multi_status = cursor.fetchall()
        
        print(f"\n📋 多字段指标数据状态:")
        print(f"{'序号':<3} {'代码':<12} {'名称':<20} {'字段数':<6} {'数据点':<8}")
        print("-" * 60)
        
        completed_count = 0
        in_progress_count = 0
        
        for i, (wind_code, name, field_count, data_points) in enumerate(multi_status, 1):
            status = "✅" if data_points > 1000 else ("🔄" if data_points > 0 else "❌")
            name_short = name[:18] + ".." if len(name) > 20 else name
            
            print(f"{i:2d}. {wind_code:<12} {name_short:<20} {field_count:<6} {data_points:<8} {status}")
            
            if data_points > 1000:
                completed_count += 1
            elif data_points > 0:
                in_progress_count += 1
        
        # 4. 测试关键指标数据
        print(f"\n🧪 关键指标数据测试:")
        test_indicators = [
            ('000300.SH', 'close', '沪深300收盘价'),
            ('000300.SH', 'val_pe_nonnegative', '沪深300市盈率'),
            ('000016.SH', 'close', '上证50收盘价'),
            ('M0000612', 'value', 'CPI同比')
        ]
        
        for wind_code, field_name, desc in test_indicators:
            cursor.execute("""
                SELECT COUNT(*), MIN(date), MAX(date)
                FROM time_series_data 
                WHERE wind_code = ? AND field_name = ?
            """, (wind_code, field_name))
            
            result = cursor.fetchone()
            if result and result[0] > 0:
                count, min_date, max_date = result
                print(f"✅ {desc}: {count} 条数据 ({min_date} ~ {max_date})")
            else:
                print(f"❌ {desc}: 无数据")
        
        print(f"\n📊 多字段指标更新进度:")
        print(f"✅ 已完成: {completed_count}/{multi_field_count}")
        print(f"🔄 进行中: {in_progress_count}/{multi_field_count}")
        print(f"❌ 待处理: {multi_field_count - completed_count - in_progress_count}/{multi_field_count}")
        
        progress = completed_count / multi_field_count * 100 if multi_field_count > 0 else 0
        print(f"📈 完成率: {progress:.1f}%")

if __name__ == "__main__":
    check_migration_status()