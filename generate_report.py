#!/usr/bin/env python3
"""
简化版月度净值报告生成器
一键生成近1月净值走势Excel报告

使用方法:
python generate_report.py

作者：Claude
创建时间：2025-09-17
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from generate_monthly_report import generate_monthly_net_value_report


def main():
    """主函数 - 简化版"""
    print("🚀 启动月度净值报告生成器...")
    print()

    try:
        # 生成报告
        output_file = generate_monthly_net_value_report()

        if output_file:
            print()
            print("="*60)
            print("✅ 报告生成成功！")
            print(f"📄 文件名：{output_file}")
            print(f"📁 完整路径：{os.path.abspath(output_file)}")
            print()
            print("📝 说明：")
            print("• 包含近1个月的净值数据")
            print("• 数据来源：数据库中的Wind API数据")
            print("• 如有指标无数据，请先运行数据更新")
            print()
            print("🔄 获取缺失数据的方法：")
            print("  python main.py update --update-type smart")
            print("="*60)
        else:
            print("❌ 报告生成失败")
            return 1

    except Exception as e:
        print(f"❌ 发生错误: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())