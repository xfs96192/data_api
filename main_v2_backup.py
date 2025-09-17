#!/usr/bin/env python3
"""
金融数据管理系统主启动脚本 - 支持多字段版本
银行理财多资产投资数据管理系统

功能：
1. 数据库初始化（支持多字段）
2. Wind API数据获取
3. 定期数据更新
4. REST API服务

作者：Claude
创建时间：2024
更新时间：2025-08-21 (支持多字段数据结构)
"""

import sys
import os
import argparse
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.config import settings, ensure_directories
from src.database.models_v2 import DatabaseManager
from src.data_fetcher.wind_client_v2 import WindDataFetcher
from src.scheduler.data_updater_v2 import DataUpdater


def setup_logging():
    """设置日志配置"""
    ensure_directories()
    
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # 配置根日志记录器
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format=log_format,
        handlers=[
            logging.FileHandler(
                os.path.join(settings.LOG_DIR, 'main.log'),
                encoding='utf-8'
            ),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger(__name__)
    return logger


def init_database():
    """初始化数据库"""
    logger = logging.getLogger(__name__)
    logger.info("初始化数据库（多字段支持）...")
    
    db_manager = DatabaseManager()
    
    # 从Excel加载指标
    excel_path = "data/数据指标.xlsx"
    if os.path.exists(excel_path):
        logger.info(f"从 {excel_path} 加载数据指标...")
        db_manager.load_indicators_from_excel(excel_path)
        
        # 获取统计信息
        summary = db_manager.get_data_summary()
        
        logger.info(f"成功加载 {summary['indicators_count']} 个数据指标")
        logger.info(f"字段映射总数: {summary['fields_count']}")
        logger.info(f"多字段指标数: {summary['multi_field_indicators']}")
        
        # 按类别统计
        logger.info("指标类别统计:")
        for category, count in summary['category_stats'].items():
            logger.info(f"  {category}: {count} 个指标")
    else:
        logger.warning(f"未找到指标文件: {excel_path}")
    
    return db_manager


def test_wind_connection():
    """测试Wind连接"""
    logger = logging.getLogger(__name__)
    logger.info("测试Wind API连接...")
    
    # 使用配置中的MCP连接设置
    data_fetcher = WindDataFetcher(
        mcp_host=settings.WIND_MCP_HOST,
        mcp_port=settings.WIND_MCP_PORT
    )
    connected = data_fetcher.test_connection()
    
    if connected:
        logger.info(f"Wind服务连接正常 ({settings.WIND_MCP_HOST}:{settings.WIND_MCP_PORT})")
    else:
        logger.warning(f"Wind服务连接失败 ({settings.WIND_MCP_HOST}:{settings.WIND_MCP_PORT})")
    
    return data_fetcher


def run_data_update(update_type="incremental"):
    """运行数据更新"""
    logger = logging.getLogger(__name__)
    logger.info(f"开始 {update_type} 数据更新...")
    
    db_manager = init_database()
    data_fetcher = test_wind_connection()
    data_updater = DataUpdater(db_manager, data_fetcher)
    
    if update_type == "full":
        data_updater.full_historical_update(settings.HISTORICAL_START_YEAR)
    elif update_type == "retry":
        data_updater.retry_failed_indicators(settings.HISTORICAL_START_YEAR)
    else:
        data_updater.incremental_update()
    
    # 显示更新摘要
    summary = data_updater.get_update_summary()
    logger.info(f"更新完成 - 数据点总数: {summary['data_points']}")
    logger.info(f"多字段指标: {summary['multi_field_indicators']}")
    logger.info(f"最近24小时更新: {summary['recent_updates_24h']}")
    if summary['failed_indicators'] > 0:
        logger.warning(f"失败指标数: {summary['failed_indicators']}")


def run_api_server():
    """运行API服务器"""
    logger = logging.getLogger(__name__)
    logger.info("启动API服务器...")
    
    import uvicorn
    from src.api.main import app
    
    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        workers=settings.API_WORKERS,
        log_level=settings.LOG_LEVEL.lower()
    )


def run_scheduler():
    """运行调度器"""
    logger = logging.getLogger(__name__)
    logger.info("启动数据更新调度器...")
    
    db_manager = init_database()
    data_fetcher = test_wind_connection()
    data_updater = DataUpdater(db_manager, data_fetcher)
    
    try:
        data_updater.run_scheduler()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在停止调度器...")
        data_updater.stop_scheduler()


def show_status():
    """显示系统状态"""
    logger = logging.getLogger(__name__)
    
    print("\n=== 金融数据管理系统状态（多字段支持） ===")
    
    # 数据库状态
    try:
        db_manager = DatabaseManager()
        summary = db_manager.get_data_summary()
        
        print(f"数据库状态: 正常")
        print(f"总指标数量: {summary['indicators_count']}")
        print(f"字段映射数量: {summary['fields_count']}")
        print(f"多字段指标数: {summary['multi_field_indicators']}")
        print(f"数据点总数: {summary['data_points']}")
        
        print("\n指标类别分布:")
        for category, count in summary['category_stats'].items():
            print(f"  {category}: {count}")
        
        # 显示多字段指标示例
        import sqlite3
        with sqlite3.connect(db_manager.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT i.wind_code, i.name, COUNT(f.field_name) as field_count
                FROM indicators i
                LEFT JOIN indicator_fields f ON i.wind_code = f.wind_code
                WHERE i.wind_code IN (
                    SELECT wind_code FROM indicator_fields 
                    GROUP BY wind_code HAVING COUNT(*) > 1
                )
                GROUP BY i.wind_code, i.name
                ORDER BY field_count DESC
                LIMIT 5
            ''')
            
            multi_examples = cursor.fetchall()
            if multi_examples:
                print("\n多字段指标示例:")
                for wind_code, name, field_count in multi_examples:
                    print(f"  {wind_code} ({name}): {field_count}个字段")
            
    except Exception as e:
        print(f"数据库状态: 错误 - {e}")
    
    # Wind连接状态
    try:
        data_fetcher = WindDataFetcher(
            mcp_host=settings.WIND_MCP_HOST,
            mcp_port=settings.WIND_MCP_PORT
        )
        connected = data_fetcher.test_connection()
        print(f"\nWind服务 ({settings.WIND_MCP_HOST}:{settings.WIND_MCP_PORT}): {'连接正常' if connected else '连接失败'}")
    except Exception as e:
        print(f"Wind服务: 错误 - {e}")
    
    print("\n=== 状态检查完成 ===\n")


def show_field_analysis():
    """显示字段分析"""
    try:
        db_manager = DatabaseManager()
        
        print("\n=== 字段分析报告 ===")
        
        import sqlite3
        with sqlite3.connect(db_manager.db_path) as conn:
            cursor = conn.cursor()
            
            # 字段类型统计
            cursor.execute('''
                SELECT field_name, field_display_name, COUNT(*) as count
                FROM indicator_fields
                GROUP BY field_name, field_display_name
                ORDER BY count DESC
            ''')
            
            field_stats = cursor.fetchall()
            print("\n字段类型分布:")
            for field_name, display_name, count in field_stats:
                print(f"  {field_name} ({display_name}): {count}个指标")
            
            # 多字段指标详情
            cursor.execute('''
                SELECT i.wind_code, i.name, i.category,
                       GROUP_CONCAT(f.field_name || ':' || f.field_display_name) as fields
                FROM indicators i
                JOIN indicator_fields f ON i.wind_code = f.wind_code
                WHERE i.wind_code IN (
                    SELECT wind_code FROM indicator_fields 
                    GROUP BY wind_code HAVING COUNT(*) > 1
                )
                GROUP BY i.wind_code, i.name, i.category
                ORDER BY i.category, i.name
            ''')
            
            multi_indicators = cursor.fetchall()
            print(f"\n多字段指标详情 (共{len(multi_indicators)}个):")
            current_category = None
            
            for wind_code, name, category, fields in multi_indicators:
                if category != current_category:
                    print(f"\n  [{category}]")
                    current_category = category
                
                field_list = [f.split(':') for f in fields.split(',')]
                field_str = ', '.join([f"{fname}({fname_cn})" for fname, fname_cn in field_list])
                print(f"    {wind_code} - {name}")
                print(f"      字段: {field_str}")
        
        print("\n=== 字段分析完成 ===\n")
        
    except Exception as e:
        print(f"字段分析错误: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="金融数据管理系统（多字段支持）")
    parser.add_argument(
        "command",
        choices=["init", "update", "server", "scheduler", "status", "fields"],
        help="执行命令"
    )
    parser.add_argument(
        "--update-type",
        choices=["incremental", "full", "retry"],
        default="incremental",
        help="更新类型: incremental(增量), full(全量), retry(重试失败) (仅用于 update 命令)"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="日志级别"
    )
    
    args = parser.parse_args()
    
    # 设置日志级别
    settings.LOG_LEVEL = args.log_level
    logger = setup_logging()
    
    logger.info(f"启动命令: {args.command}")
    
    try:
        if args.command == "init":
            init_database()
            logger.info("数据库初始化完成")
            
        elif args.command == "update":
            run_data_update(args.update_type)
            
        elif args.command == "server":
            run_api_server()
            
        elif args.command == "scheduler":
            run_scheduler()
            
        elif args.command == "status":
            show_status()
            
        elif args.command == "fields":
            show_field_analysis()
            
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序执行错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()