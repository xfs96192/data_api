#!/usr/bin/env python3
"""
数据覆盖范围检查脚本 V2
调整判断规则：15年以来的数据认为充足
"""

import pandas as pd
import sqlite3
from datetime import datetime, date
from src.database.models import DatabaseManager
import warnings
warnings.filterwarnings('ignore')

def check_data_coverage_v2():
    """检查所有指标的数据覆盖范围（调整后的规则）"""
    
    # 创建数据库连接
    db = DatabaseManager()
    
    print("正在检查数据库中所有指标的时间覆盖范围（调整后规则）...")
    print("新规则：开始时间不晚于2010年 且 结束时间不早于2020年 且 记录数>=500")
    print("=" * 80)
    
    # 获取所有指标
    indicators = db.get_indicators()
    print(f"数据库中共有 {len(indicators)} 个指标")
    
    # 存储检查结果
    coverage_results = []
    
    for i, indicator in enumerate(indicators, 1):
        wind_code = indicator['wind_code']
        name = indicator['name']
        category = indicator['category']
        
        print(f"[{i}/{len(indicators)}] 检查 {wind_code} - {name}")
        
        # 获取该指标的时间序列数据
        with sqlite3.connect(db.db_path) as conn:
            query = """
                SELECT 
                    MIN(date) as start_date,
                    MAX(date) as end_date,
                    COUNT(*) as record_count
                FROM time_series_data 
                WHERE wind_code = ?
            """
            result = pd.read_sql_query(query, conn, params=[wind_code])
        
        if result.iloc[0]['record_count'] > 0:
            start_date = result.iloc[0]['start_date']
            end_date = result.iloc[0]['end_date']
            record_count = result.iloc[0]['record_count']
            
            # 计算数据年份跨度
            start_year = int(start_date[:4]) if start_date else None
            end_year = int(end_date[:4]) if end_date else None
            year_span = end_year - start_year + 1 if start_year and end_year else 0
            
            # 新的判断标准：开始时间不晚于2010年 且 结束时间不早于2020年 且 记录数>=500
            is_sufficient = start_year <= 2010 and end_year >= 2020 and record_count >= 500
            
            # 额外分类：近期数据（开始时间在2015年之后但有较多数据）
            is_recent_but_complete = start_year >= 2015 and end_year >= 2022 and record_count >= 200
            
        else:
            start_date = None
            end_date = None
            record_count = 0
            start_year = None
            end_year = None
            year_span = 0
            is_sufficient = False
            is_recent_but_complete = False
        
        coverage_results.append({
            'wind_code': wind_code,
            'name': name,
            'category': category,
            'start_date': start_date,
            'end_date': end_date,
            'start_year': start_year,
            'end_year': end_year,
            'record_count': record_count,
            'year_span': year_span,
            'is_sufficient': is_sufficient,
            'is_recent_but_complete': is_recent_but_complete,
            'data_source': indicator['data_source']
        })
    
    # 转换为DataFrame并保存
    df_coverage = pd.DataFrame(coverage_results)
    
    print("\n" + "=" * 80)
    print("数据覆盖范围检查完成（调整后规则）")
    print("=" * 80)
    
    # 统计分析
    total_indicators = len(df_coverage)
    has_data = len(df_coverage[df_coverage['record_count'] > 0])
    no_data = len(df_coverage[df_coverage['record_count'] == 0])
    sufficient_data = len(df_coverage[df_coverage['is_sufficient'] == True])
    recent_complete = len(df_coverage[df_coverage['is_recent_but_complete'] == True])
    truly_insufficient = len(df_coverage[
        (df_coverage['is_sufficient'] == False) & 
        (df_coverage['is_recent_but_complete'] == False) &
        (df_coverage['record_count'] > 0)
    ])
    
    print(f"总指标数: {total_indicators}")
    print(f"有数据的指标: {has_data} ({has_data/total_indicators*100:.1f}%)")
    print(f"无数据的指标: {no_data} ({no_data/total_indicators*100:.1f}%)")
    print(f"数据充足的指标: {sufficient_data} ({sufficient_data/total_indicators*100:.1f}%)")
    print(f"近期数据完整的指标: {recent_complete} ({recent_complete/total_indicators*100:.1f}%)")
    print(f"真正数据不足的指标: {truly_insufficient} ({truly_insufficient/total_indicators*100:.1f}%)")
    
    # 按类别统计
    print(f"\n按类别统计:")
    category_stats = df_coverage.groupby('category').agg({
        'wind_code': 'count',
        'is_sufficient': 'sum',
        'is_recent_but_complete': 'sum',
        'record_count': 'mean'
    }).round(2)
    category_stats['truly_insufficient'] = category_stats['wind_code'] - category_stats['is_sufficient'] - category_stats['is_recent_but_complete']
    category_stats.columns = ['总数', '数据充足', '近期完整', '平均记录数', '真正不足']
    print(category_stats)
    
    # 显示真正数据不足的指标
    truly_insufficient_indicators = df_coverage[
        (df_coverage['is_sufficient'] == False) & 
        (df_coverage['is_recent_but_complete'] == False) &
        (df_coverage['record_count'] > 0)
    ].copy()
    
    if not truly_insufficient_indicators.empty:
        print(f"\n真正数据不足的指标详情 (共{len(truly_insufficient_indicators)}个):")
        print("-" * 130)
        print(f"{'序号':<4} {'Wind代码':<15} {'指标名称':<30} {'类别':<8} {'开始年份':<8} {'结束年份':<8} {'记录数':<8} {'数据源':<8}")
        print("-" * 130)
        
        for i, (_, row) in enumerate(truly_insufficient_indicators.iterrows(), 1):
            print(f"{i:<4} {row['wind_code']:<15} {row['name'][:29]:<30} {row['category']:<8} "
                  f"{row['start_year'] or 'N/A':<8} {row['end_year'] or 'N/A':<8} "
                  f"{row['record_count']:<8} {row['data_source']:<8}")
    
    # 显示无数据的指标
    no_data_indicators = df_coverage[df_coverage['record_count'] == 0].copy()
    if not no_data_indicators.empty:
        print(f"\n无数据的指标 (共{len(no_data_indicators)}个):")
        print("-" * 100)
        print(f"{'序号':<4} {'Wind代码':<15} {'指标名称':<30} {'类别':<8} {'数据源':<8}")
        print("-" * 100)
        
        for i, (_, row) in enumerate(no_data_indicators.iterrows(), 1):
            print(f"{i:<4} {row['wind_code']:<15} {row['name'][:29]:<30} {row['category']:<8} {row['data_source']:<8}")
    
    # 保存结果到文件
    df_coverage.to_csv('data_coverage_report_v2.csv', index=False, encoding='utf-8-sig')
    truly_insufficient_indicators.to_csv('truly_insufficient_indicators.csv', index=False, encoding='utf-8-sig')
    no_data_indicators.to_csv('no_data_indicators.csv', index=False, encoding='utf-8-sig')
    
    print(f"\n详细报告已保存:")
    print(f"- 完整覆盖报告: data_coverage_report_v2.csv")
    print(f"- 真正数据不足指标: truly_insufficient_indicators.csv")
    print(f"- 无数据指标: no_data_indicators.csv")
    
    return df_coverage, truly_insufficient_indicators, no_data_indicators

if __name__ == "__main__":
    check_data_coverage_v2()