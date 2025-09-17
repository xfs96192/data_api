#!/usr/bin/env python3
"""
全量指标更新脚本 - 更新到2025年最新时间点
更新所有指标数据到最新可用日期，包括债券指标
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.data_fetcher.wind_client import WindDataFetcher
from src.database.models import DatabaseManager
from datetime import datetime, date
import time
import sqlite3
import pandas as pd

def get_current_date():
    """获取当前日期字符串"""
    return datetime.now().strftime("%Y-%m-%d")

def update_all_indicators_to_latest():
    """更新所有指标数据到最新时间点"""
    
    # 初始化
    try:
        wind_client = WindDataFetcher()
        db = DatabaseManager()
        
        # 检查Wind连接状态
        if not wind_client.wind_connected:
            print("Wind API连接失败，请检查Wind终端是否已启动")
            return
        
        print("Wind API连接成功")
        
        # 获取当前日期
        current_date = get_current_date()
        print(f"更新目标时间: 2000-01-01 至 {current_date}")
        
        # 获取所有指标
        indicators = db.get_indicators()
        print(f"开始更新所有 {len(indicators)} 个指标到最新时间点...")
        
        # 按类别分组处理
        categories = {}
        for indicator in indicators:
            category = indicator['category']
            if category not in categories:
                categories[category] = []
            categories[category].append(indicator)
        
        total_success = 0
        total_error = 0
        category_results = {}
        
        for category, category_indicators in categories.items():
            print(f"\n=== 处理 {category} 类别指标 (共{len(category_indicators)}个) ===")
            
            success_count = 0
            error_count = 0
            
            for i, indicator in enumerate(category_indicators, 1):
                wind_code = indicator['wind_code']
                name = indicator['name']
                data_source = indicator['data_source']
                
                print(f"[{category} {i}/{len(category_indicators)}] {wind_code} - {name}")
                
                try:
                    # 获取数据
                    if data_source == 'WSD':
                        data = wind_client.fetch_wsd_data(
                            wind_code=wind_code,
                            field="close",
                            start_date="2000-01-01",
                            end_date=current_date  # 使用当前日期
                        )
                    else:  # EDB
                        data = wind_client.fetch_edb_data(
                            wind_code=wind_code,
                            start_date="2000-01-01",
                            end_date=current_date  # 使用当前日期
                        )
                    
                    if data is not None and not data.empty:
                        # 删除旧数据
                        with sqlite3.connect(db.db_path) as conn:
                            conn.execute("DELETE FROM time_series_data WHERE wind_code = ?", (wind_code,))
                            conn.commit()
                        
                        # 保存新数据
                        db.insert_time_series_data(wind_code, data)
                        record_count = len(data.dropna())
                        
                        # 记录更新日志
                        db.log_update(
                            wind_code=wind_code,
                            update_type='full',
                            start_date="2000-01-01",
                            end_date=current_date,
                            records_count=record_count,
                            status='success'
                        )
                        
                        data_start = data.index.min().strftime('%Y-%m-%d')
                        data_end = data.index.max().strftime('%Y-%m-%d')
                        print(f"  ✓ 成功: {record_count} 条记录 ({data_start} 至 {data_end})")
                        success_count += 1
                    else:
                        print(f"  ✗ 未获取到数据")
                        error_count += 1
                        
                        # 记录错误日志
                        db.log_update(
                            wind_code=wind_code,
                            update_type='full',
                            start_date="2000-01-01",
                            end_date=current_date,
                            records_count=0,
                            status='failed',
                            error_message='未获取到数据'
                        )
                        
                except Exception as e:
                    print(f"  ✗ 更新失败: {str(e)}")
                    error_count += 1
                    
                    # 记录错误日志
                    try:
                        db.log_update(
                            wind_code=wind_code,
                            update_type='full',
                            start_date="2000-01-01",
                            end_date=current_date,
                            records_count=0,
                            status='failed',
                            error_message=str(e)
                        )
                    except:
                        pass
                
                # 控制请求频率
                time.sleep(0.2)
                
                # 每10个指标后稍作休息
                if i % 10 == 0:
                    print(f"  已处理 {i}/{len(category_indicators)}，休息1秒...")
                    time.sleep(1)
            
            category_results[category] = {
                'success': success_count,
                'error': error_count,
                'total': len(category_indicators)
            }
            
            total_success += success_count
            total_error += error_count
            
            print(f"{category} 类别完成: 成功{success_count}, 失败{error_count}")
            time.sleep(2)  # 类别间休息
        
        # 输出总结
        print(f"\n" + "="*80)
        print(f"全量更新完成")
        print(f"="*80)
        print(f"总成功: {total_success}")
        print(f"总失败: {total_error}")
        print(f"总指标: {len(indicators)}")
        print(f"成功率: {total_success/len(indicators)*100:.1f}%")
        
        print(f"\n按类别统计:")
        for category, result in category_results.items():
            success_rate = result['success']/result['total']*100
            print(f"  {category}: {result['success']}/{result['total']} ({success_rate:.1f}%)")
        
        # 验证更新后的数据覆盖
        print(f"\n验证关键指标数据...")
        key_indicators = [
            '000300.SH',  # 沪深300
            '000001.SH',  # 上证指数
            'M0000612',   # CPI
            'S0059749',   # 10年国债收益率
        ]
        
        for wind_code in key_indicators:
            verify_data = db.get_time_series_data(wind_code)
            if not verify_data.empty:
                print(f"✓ {wind_code}: {len(verify_data)} 条记录 ({verify_data.index.min().strftime('%Y-%m-%d')} 至 {verify_data.index.max().strftime('%Y-%m-%d')})")
            else:
                print(f"✗ {wind_code}: 无数据")
                
    except Exception as e:
        print(f"更新过程出错: {str(e)}")

def update_by_batches():
    """分批更新，避免超时"""
    
    # 初始化
    wind_client = WindDataFetcher()
    db = DatabaseManager()
    
    if not wind_client.wind_connected:
        print("Wind API连接失败")
        return
    
    # 获取所有指标
    indicators = db.get_indicators()
    current_date = get_current_date()
    
    # 分批处理（每批50个）
    batch_size = 50
    total_batches = (len(indicators) + batch_size - 1) // batch_size
    
    print(f"分 {total_batches} 批处理，每批 {batch_size} 个指标")
    
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min((batch_num + 1) * batch_size, len(indicators))
        batch_indicators = indicators[start_idx:end_idx]
        
        print(f"\n=== 批次 {batch_num + 1}/{total_batches}: 指标 {start_idx + 1}-{end_idx} ===")
        
        success_count = 0
        error_count = 0
        
        for i, indicator in enumerate(batch_indicators, 1):
            wind_code = indicator['wind_code']
            name = indicator['name']
            data_source = indicator['data_source']
            
            print(f"[{start_idx + i}] {wind_code} - {name}")
            
            try:
                # 获取数据
                if data_source == 'WSD':
                    data = wind_client.fetch_wsd_data(
                        wind_code=wind_code,
                        field="close",
                        start_date="2000-01-01",
                        end_date=current_date
                    )
                else:
                    data = wind_client.fetch_edb_data(
                        wind_code=wind_code,
                        start_date="2000-01-01",
                        end_date=current_date
                    )
                
                if data is not None and not data.empty:
                    # 删除旧数据并插入新数据
                    with sqlite3.connect(db.db_path) as conn:
                        conn.execute("DELETE FROM time_series_data WHERE wind_code = ?", (wind_code,))
                        conn.commit()
                    
                    db.insert_time_series_data(wind_code, data)
                    record_count = len(data.dropna())
                    
                    db.log_update(
                        wind_code=wind_code,
                        update_type='full',
                        start_date="2000-01-01",
                        end_date=current_date,
                        records_count=record_count,
                        status='success'
                    )
                    
                    print(f"  ✓ {record_count} 条记录")
                    success_count += 1
                else:
                    print(f"  ✗ 无数据")
                    error_count += 1
                    
            except Exception as e:
                print(f"  ✗ 错误: {str(e)}")
                error_count += 1
            
            time.sleep(0.3)  # 控制频率
        
        print(f"批次 {batch_num + 1} 完成: 成功{success_count}, 失败{error_count}")
        
        if batch_num < total_batches - 1:  # 不是最后一批
            print("等待5秒后处理下一批...")
            time.sleep(5)

if __name__ == "__main__":
    print("开始分批更新所有指标到2025年最新时间点...")
    update_by_batches()