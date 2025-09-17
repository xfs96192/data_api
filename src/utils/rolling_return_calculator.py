#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
标准滚动收益率计算器
提供统一、准确的滚动收益率计算方法

Author: 银行理财多资产投资部
Date: 2025-08-26
Version: 1.0
"""

import sqlite3
import pandas as pd
import numpy as np
from typing import Dict, Optional, Union
from datetime import datetime
import os

class RollingReturnCalculator:
    """滚动收益率计算器"""
    
    def __init__(self, db_path: str = None):
        """
        初始化计算器
        
        Args:
            db_path (str): 数据库路径，默认使用相对路径
        """
        if db_path is None:
            # 默认数据库路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(current_dir, '../../data/financial_data.db')
        
        self.db_path = db_path
    
    def get_data(self, wind_code: str) -> pd.DataFrame:
        """
        获取指标数据
        
        Args:
            wind_code (str): Wind指标代码
            
        Returns:
            pd.DataFrame: 时间序列数据
        """
        conn = sqlite3.connect(self.db_path)
        query = f"SELECT date, value FROM time_series_data WHERE wind_code = '{wind_code}' ORDER BY date"
        data = pd.read_sql(query, conn)
        conn.close()
        
        if len(data) == 0:
            raise ValueError(f"未找到 {wind_code} 的数据")
        
        # 数据预处理
        data['date'] = pd.to_datetime(data['date'])
        data = data.set_index('date').sort_index()
        data = data[~data.index.duplicated(keep='last')]
        data = data.dropna()
        
        return data
    
    def rolling_return_3y_standard(self, wind_code: str) -> Optional[Dict]:
        """
        计算标准滚动3年年化收益率 (月末数据法)
        
        这是推荐的标准方法：
        1. 使用月末数据消除日内波动
        2. 严格按36个月计算时间跨度
        3. 符合业界惯例
        
        Args:
            wind_code (str): Wind指标代码
            
        Returns:
            dict: 包含收益率及相关信息，如果数据不足则返回None
        """
        try:
            data = self.get_data(wind_code)
            
            # 转换为月末数据
            monthly_data = data.resample('M').last()
            
            if len(monthly_data) < 37:
                return None
                
            # 标准计算：(当前月末值/36个月前月末值)^(1/3) - 1
            current_value = monthly_data['value'].iloc[-1]
            past_value = monthly_data['value'].iloc[-37]  # 36个月前
            rolling_return = (current_value / past_value) ** (1/3) - 1
            
            return {
                'wind_code': wind_code,
                'method': 'monthly_standard',
                'rolling_3y_return': rolling_return,
                'rolling_3y_return_pct': rolling_return * 100,
                'current_date': monthly_data.index[-1],
                'current_value': current_value,
                'base_date': monthly_data.index[-37],
                'base_value': past_value,
                'data_points_used': len(monthly_data),
                'calculation_date': datetime.now()
            }
            
        except Exception as e:
            return {
                'wind_code': wind_code,
                'error': str(e),
                'method': 'monthly_standard'
            }
    
    def rolling_return_3y_daily(self, wind_code: str) -> Optional[Dict]:
        """
        计算滚动3年年化收益率 (日频数据法)
        
        参考方法，用于对比验证：
        1. 使用所有交易日数据
        2. 按实际时间跨度计算
        
        Args:
            wind_code (str): Wind指标代码
            
        Returns:
            dict: 包含收益率及相关信息
        """
        try:
            data = self.get_data(wind_code)
            
            current_date = data.index[-1]
            target_past_date = current_date - pd.DateOffset(months=36)
            
            # 找到最接近36个月前的数据点
            past_data = data[data.index <= target_past_date]
            if len(past_data) == 0:
                return None
                
            actual_past_date = past_data.index[-1]
            current_value = data['value'].iloc[-1]
            past_value = past_data['value'].iloc[-1]
            
            # 计算实际时间跨度
            days_diff = (current_date - actual_past_date).days
            years_diff = days_diff / 365.25
            rolling_return = (current_value / past_value) ** (1/years_diff) - 1
            
            return {
                'wind_code': wind_code,
                'method': 'daily_reference',
                'rolling_3y_return': rolling_return,
                'rolling_3y_return_pct': rolling_return * 100,
                'current_date': current_date,
                'current_value': current_value,
                'base_date': actual_past_date,
                'base_value': past_value,
                'actual_years': years_diff,
                'actual_days': days_diff,
                'data_points_used': len(data),
                'calculation_date': datetime.now()
            }
            
        except Exception as e:
            return {
                'wind_code': wind_code,
                'error': str(e),
                'method': 'daily_reference'
            }
    
    def compare_methods(self, wind_code: str) -> Dict:
        """
        对比两种计算方法
        
        Args:
            wind_code (str): Wind指标代码
            
        Returns:
            dict: 包含两种方法的结果和对比分析
        """
        standard_result = self.rolling_return_3y_standard(wind_code)
        daily_result = self.rolling_return_3y_daily(wind_code)
        
        comparison = {
            'wind_code': wind_code,
            'standard_method': standard_result,
            'daily_method': daily_result
        }
        
        # 如果两种方法都成功，计算差异
        if (standard_result and 'rolling_3y_return' in standard_result and 
            daily_result and 'rolling_3y_return' in daily_result):
            
            diff = standard_result['rolling_3y_return'] - daily_result['rolling_3y_return']
            comparison.update({
                'difference_pct': diff * 100,
                'abs_difference_pct': abs(diff) * 100,
                'recommended_method': 'standard_method',
                'recommended_value': standard_result['rolling_3y_return_pct']
            })
        
        return comparison

# 便捷函数
def get_rolling_3y_return(wind_code: str, method: str = 'standard', db_path: str = None) -> Optional[Dict]:
    """
    获取滚动3年年化收益率的便捷函数
    
    Args:
        wind_code (str): Wind指标代码
        method (str): 计算方法，'standard' 或 'daily'
        db_path (str): 数据库路径，默认None
        
    Returns:
        dict: 计算结果
    """
    calculator = RollingReturnCalculator(db_path)
    
    if method == 'standard':
        return calculator.rolling_return_3y_standard(wind_code)
    elif method == 'daily':
        return calculator.rolling_return_3y_daily(wind_code)
    elif method == 'compare':
        return calculator.compare_methods(wind_code)
    else:
        raise ValueError("method 必须是 'standard', 'daily' 或 'compare'")

def format_result(result: Dict) -> str:
    """
    格式化输出结果
    
    Args:
        result (dict): 计算结果
        
    Returns:
        str: 格式化的字符串
    """
    if 'error' in result:
        return f"错误: {result['error']}"
    
    if 'rolling_3y_return_pct' not in result:
        return "无法计算收益率"
    
    output = []
    output.append(f"指标代码: {result['wind_code']}")
    output.append(f"计算方法: {result['method']}")
    output.append(f"滚动3年年化收益率: {result['rolling_3y_return_pct']:.4f}%")
    output.append(f"当前日期: {result['current_date'].strftime('%Y-%m-%d')}")
    output.append(f"基准日期: {result['base_date'].strftime('%Y-%m-%d')}")
    output.append(f"当前值: {result['current_value']:.4f}")
    output.append(f"基准值: {result['base_value']:.4f}")
    
    if 'actual_years' in result:
        output.append(f"实际年数: {result['actual_years']:.6f}")
    
    return '\n'.join(output)

# 示例用法
if __name__ == "__main__":
    # 测试标准方法
    print("=== 测试标准滚动收益率计算器 ===")
    
    result = get_rolling_3y_return('885001.WI', 'standard')
    if result:
        print(format_result(result))
    else:
        print("计算失败")
    
    print("\n=== 对比两种方法 ===")
    comparison = get_rolling_3y_return('885001.WI', 'compare')
    
    if 'recommended_value' in comparison:
        print(f"推荐结果: {comparison['recommended_value']:.4f}%")
        print(f"方法差异: {comparison['abs_difference_pct']:.4f}%")