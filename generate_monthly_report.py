#!/usr/bin/env python3
"""
近1月净值走势Excel生成器
从数据库中获取指定指标的近1个月数据并生成Excel报告

作者：Claude
创建时间：2025-09-17
"""

import sys
import os
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.database.models_v2 import DatabaseManager


def generate_monthly_net_value_report():
    """生成近1月净值走势Excel报告"""

    # 定义需要的Wind代码和对应的中文列名
    indicators = {
        '000001.SH': '上证指数',
        '000832.CSI': '中证转债',
        'SPX.GI': '标普500',
        '931472.CSI': '7-10年国开',
        'CBA01921.CS': '1-3年高信用等级债券财富',
        '10yrnote.gbm': '10年期美国国债收益率',
        'USDCNY.IB': 'USDCNY',
        'AU.SHF': '沪金',
        'RB.SHF': '螺纹钢',
        'SC.INE': '原油',
        'M.DCE': '豆粕'
    }

    print("生成近1月净值走势Excel报告...")
    print("=" * 50)

    try:
        # 连接数据库
        db = DatabaseManager()

        # 计算日期范围（近1个月）
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        print(f"数据时间范围: {start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')}")

        # 存储所有数据
        all_data = {}

        with sqlite3.connect(db.db_path) as conn:

            for wind_code, chinese_name in indicators.items():
                print(f"获取数据: {wind_code} ({chinese_name})")

                # 查询数据
                query = """
                    SELECT date, value
                    FROM time_series_data
                    WHERE wind_code = ?
                        AND date >= ?
                        AND date <= ?
                        AND value IS NOT NULL
                    ORDER BY date ASC
                """

                df = pd.read_sql_query(
                    query,
                    conn,
                    params=(wind_code, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
                )

                if df.empty:
                    print(f"  ⚠️  无数据")
                    continue

                # 转换日期格式
                df['date'] = pd.to_datetime(df['date'])
                df = df.set_index('date')

                # 存储数据
                all_data[chinese_name] = df['value']
                print(f"  ✓ 获取 {len(df)} 条记录")

        if not all_data:
            print("❌ 没有找到任何数据")
            return

        # 合并所有数据
        result_df = pd.DataFrame(all_data)

        # 按日期排序
        result_df = result_df.sort_index()

        # 只保留有数据的日期
        result_df = result_df.dropna(how='all')

        # 格式化日期为 2025/8/12 格式
        result_df.index = result_df.index.strftime('%Y/%-m/%-d')

        # 重命名索引
        result_df.index.name = '日期'

        # 按照用户指定的列顺序重新排列
        column_order = [
            '上证指数', '中证转债', '标普500', '7-10年国开',
            '1-3年高信用等级债券财富', '10年期美国国债收益率',
            'USDCNY', '沪金', '螺纹钢', '原油', '豆粕'
        ]

        # 只保留存在的列，按指定顺序排列
        available_columns = [col for col in column_order if col in result_df.columns]
        result_df = result_df[available_columns]

        # 生成Excel文件
        output_file = "近1月净值走势.xlsx"

        # 格式化数值（保留4位小数）
        result_df = result_df.round(4)

        # 保存到Excel
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            result_df.to_excel(writer, sheet_name='净值走势')

            # 获取工作表
            worksheet = writer.sheets['净值走势']

            # 调整列宽
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter

                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass

                adjusted_width = min(max_length + 2, 20)
                worksheet.column_dimensions[column_letter].width = adjusted_width

        print(f"\n✅ 成功生成Excel文件: {output_file}")
        print(f"📊 数据维度: {len(result_df)} 行 × {len(result_df.columns)} 列")
        print(f"📅 数据时间跨度: {result_df.index[0]} 到 {result_df.index[-1]}")

        # 显示数据摘要
        print(f"\n📋 数据摘要:")
        for col in result_df.columns:
            valid_count = result_df[col].count()
            if valid_count > 0:
                latest_value = result_df[col].dropna().iloc[-1]
                print(f"  {col}: {valid_count} 条记录，最新值: {latest_value}")
            else:
                print(f"  {col}: 无有效数据")

        # 显示前几行数据预览
        print(f"\n📄 数据预览 (前5行):")
        print(result_df.head().to_string())

        return output_file

    except Exception as e:
        print(f"❌ 错误: {e}")
        return None


def main():
    """主函数"""
    output_file = generate_monthly_net_value_report()

    if output_file:
        print(f"\n🎉 报告生成完成！")
        print(f"📁 文件位置: {os.path.abspath(output_file)}")
    else:
        print(f"\n❌ 报告生成失败")


if __name__ == "__main__":
    main()