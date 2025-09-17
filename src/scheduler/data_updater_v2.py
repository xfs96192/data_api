import schedule
import time
import threading
from datetime import datetime, timedelta, date
from typing import List, Dict, Any
import logging
from src.database.models_v2 import DatabaseManager
from src.data_fetcher.wind_client_v2 import WindDataFetcher


class DataUpdater:
    def __init__(self, db_manager: DatabaseManager, data_fetcher: WindDataFetcher):
        self.db_manager = db_manager
        self.data_fetcher = data_fetcher
        self.logger = logging.getLogger(__name__)
        self.is_running = False
        self.scheduler_thread = None
    
    def update_single_indicator(
        self, 
        indicator: Dict[str, Any], 
        start_date: str, 
        end_date: str,
        update_type: str = "incremental"
    ) -> bool:
        """
        更新单个指标的所有字段数据
        """
        wind_code = indicator['wind_code']
        
        try:
            self.logger.info(f"开始更新指标: {wind_code} ({indicator['name']})")
            
            # 获取该指标的所有字段
            fields = self.db_manager.get_indicator_fields(wind_code)
            if not fields:
                self.logger.warning(f"指标 {wind_code} 没有字段映射，跳过")
                return False
            
            # 获取数据
            data = self.data_fetcher.fetch_data_by_indicator(indicator, start_date, end_date)
            
            if data is not None and not data.empty:
                # 按字段分别保存到数据库
                total_records = 0
                
                for field_info in fields:
                    field_name = field_info['field_name']
                    
                    if field_name in data.columns:
                        field_data = data[field_name].dropna()
                        if not field_data.empty:
                            self.db_manager.insert_time_series_data(wind_code, field_name, field_data)
                            field_records = len(field_data)
                            total_records += field_records
                            
                            # 记录字段级别的更新日志
                            self.db_manager.log_update(
                                wind_code=wind_code,
                                field_name=field_name,
                                update_type=update_type,
                                start_date=start_date,
                                end_date=end_date,
                                records_count=field_records,
                                status="success"
                            )
                            
                            self.logger.info(f"成功更新字段 {wind_code}.{field_name}，{field_records} 条数据")
                    else:
                        self.logger.warning(f"数据中未找到字段 {field_name} 对于指标 {wind_code}")
                
                if total_records > 0:
                    # 记录指标级别的更新日志（汇总）
                    self.db_manager.log_update(
                        wind_code=wind_code,
                        field_name=None,  # 表示所有字段
                        update_type=update_type,
                        start_date=start_date,
                        end_date=end_date,
                        records_count=total_records,
                        status="success"
                    )
                    
                    self.logger.info(f"成功更新指标 {wind_code}，共 {total_records} 条数据")
                    return True
                else:
                    self.logger.warning(f"指标 {wind_code} 没有有效数据")
                    return False
            else:
                self.logger.warning(f"指标 {wind_code} 未获取到数据")
                
                # 记录失败日志
                self.db_manager.log_update(
                    wind_code=wind_code,
                    field_name=None,
                    update_type=update_type,
                    start_date=start_date,
                    end_date=end_date,
                    records_count=0,
                    status="failed",
                    error_message="未获取到数据"
                )
                return False
                
        except Exception as e:
            error_msg = f"更新指标 {wind_code} 失败: {str(e)}"
            self.logger.error(error_msg)
            
            # 记录错误日志
            self.db_manager.log_update(
                wind_code=wind_code,
                field_name=None,
                update_type=update_type,
                start_date=start_date,
                end_date=end_date,
                records_count=0,
                status="failed",
                error_message=str(e)
            )
            return False
    
    def full_historical_update(self, start_year: int = 2000):
        """
        全量历史数据更新（2000年至今）
        """
        self.logger.info("开始全量历史数据更新")
        
        # 获取所有指标
        indicators = self.db_manager.get_indicators()
        
        start_date = f"{start_year}-01-01"
        end_date = datetime.now().strftime("%Y-%m-%d")
        
        success_count = 0
        total_count = len(indicators)
        
        for i, indicator in enumerate(indicators):
            self.logger.info(f"更新进度: {i+1}/{total_count} - {indicator['name']}")
            
            if self.update_single_indicator(indicator, start_date, end_date, "full"):
                success_count += 1
            
            # 避免请求过于频繁
            time.sleep(1)
        
        self.logger.info(f"全量历史数据更新完成，成功: {success_count}/{total_count}")
    
    def incremental_update(self):
        """
        增量数据更新
        """
        self.logger.info("开始增量数据更新")
        
        indicators = self.db_manager.get_indicators()
        success_count = 0
        
        for indicator in indicators:
            wind_code = indicator['wind_code']
            
            # 获取最后更新日期（所有字段中的最新日期）
            last_update_date = self.db_manager.get_last_update_date(wind_code)
            
            if last_update_date:
                # 从最后更新日期的下一天开始
                start_date = (
                    datetime.strptime(last_update_date, "%Y-%m-%d") + timedelta(days=1)
                ).strftime("%Y-%m-%d")
            else:
                # 如果没有历史数据，从30天前开始
                start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            
            end_date = datetime.now().strftime("%Y-%m-%d")
            
            # 如果开始日期不晚于结束日期，则进行更新
            if start_date <= end_date:
                if self.update_single_indicator(indicator, start_date, end_date, "incremental"):
                    success_count += 1
                
                # 避免请求过于频繁
                time.sleep(0.5)
        
        self.logger.info(f"增量数据更新完成，成功更新 {success_count} 个指标")
    
    def setup_schedule(self):
        """
        设置定时任务
        """
        # 每日增量更新（工作日18:00）
        schedule.every().monday.at("18:00").do(self.incremental_update)
        schedule.every().tuesday.at("18:00").do(self.incremental_update)
        schedule.every().wednesday.at("18:00").do(self.incremental_update)
        schedule.every().thursday.at("18:00").do(self.incremental_update)
        schedule.every().friday.at("18:00").do(self.incremental_update)
        
        # 每周日全量更新（周日凌晨2:00）
        schedule.every().sunday.at("02:00").do(self.full_historical_update)
        
        self.logger.info("定时任务设置完成")
    
    def run_scheduler(self):
        """
        运行调度器
        """
        self.setup_schedule()
        self.is_running = True
        
        self.logger.info("数据更新调度器启动")
        
        while self.is_running:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    
    def start_scheduler(self):
        """
        启动调度器线程
        """
        if not self.is_running:
            self.scheduler_thread = threading.Thread(target=self.run_scheduler)
            self.scheduler_thread.daemon = True
            self.scheduler_thread.start()
            self.logger.info("调度器线程已启动")
    
    def stop_scheduler(self):
        """
        停止调度器
        """
        self.is_running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        self.logger.info("调度器已停止")
    
    def retry_failed_indicators(self, start_year: int = 2000):
        """
        重试失败和缺失的指标
        """
        self.logger.info("开始重试失败和缺失的指标")
        
        # 获取所有指标
        indicators = self.db_manager.get_indicators()
        
        # 查找失败和缺失的指标
        failed_indicators = []
        missing_indicators = []
        
        import sqlite3
        with sqlite3.connect(self.db_manager.db_path) as conn:
            cursor = conn.cursor()
            
            for indicator in indicators:
                wind_code = indicator['wind_code']
                
                # 检查是否有数据
                cursor.execute('SELECT COUNT(*) FROM time_series_data WHERE wind_code = ?', (wind_code,))
                data_count = cursor.fetchone()[0]
                
                if data_count == 0:
                    # 检查是否曾经尝试过更新
                    cursor.execute('SELECT status FROM update_logs WHERE wind_code = ? ORDER BY update_time DESC LIMIT 1', (wind_code,))
                    last_update = cursor.fetchone()
                    
                    if last_update and last_update[0] == 'failed':
                        failed_indicators.append(indicator)
                    else:
                        missing_indicators.append(indicator)
        
        retry_indicators = failed_indicators + missing_indicators
        self.logger.info(f"找到 {len(failed_indicators)} 个失败指标和 {len(missing_indicators)} 个缺失指标，共 {len(retry_indicators)} 个需要重试")
        
        if not retry_indicators:
            self.logger.info("没有需要重试的指标")
            return
        
        start_date = f"{start_year}-01-01"
        end_date = datetime.now().strftime("%Y-%m-%d")
        
        success_count = 0
        total_count = len(retry_indicators)
        
        for i, indicator in enumerate(retry_indicators):
            self.logger.info(f"重试进度: {i+1}/{total_count} - {indicator['name']} ({indicator['wind_code']})")
            
            if self.update_single_indicator(indicator, start_date, end_date, "retry"):
                success_count += 1
                self.logger.info(f"✓ 成功重试指标: {indicator['wind_code']}")
            else:
                self.logger.warning(f"✗ 重试失败指标: {indicator['wind_code']}")
            
            # 避免请求过于频繁
            time.sleep(1)
        
        self.logger.info(f"重试完成，成功: {success_count}/{total_count}")
    
    def run_immediate_update(self, update_type: str = "incremental"):
        """
        立即执行更新
        
        Args:
            update_type: 'incremental', 'full' 或 'retry'
        """
        if update_type == "full":
            self.full_historical_update()
        elif update_type == "retry":
            self.retry_failed_indicators()
        else:
            self.incremental_update()
    
    def get_update_summary(self) -> Dict:
        """获取更新状态摘要"""
        summary = self.db_manager.get_data_summary()
        
        # 添加最近更新状态
        import sqlite3
        with sqlite3.connect(self.db_manager.db_path) as conn:
            cursor = conn.cursor()
            
            # 最近24小时的更新
            cursor.execute('''
                SELECT COUNT(*) FROM update_logs 
                WHERE update_time >= datetime('now', '-1 day')
            ''')
            recent_updates = cursor.fetchone()[0]
            
            # 失败的更新
            cursor.execute('''
                SELECT COUNT(DISTINCT wind_code) FROM update_logs 
                WHERE status = 'failed'
            ''')
            failed_indicators = cursor.fetchone()[0]
            
            summary.update({
                'recent_updates_24h': recent_updates,
                'failed_indicators': failed_indicators
            })
        
        return summary
    
    def smart_incremental_update(self) -> tuple:
        """
        智能增量更新：
        - 对于新增指标（数据库中没有数据），从2000年开始全量更新
        - 对于存量指标（已有数据），从最新日期开始增量更新
        
        Returns:
            tuple: (成功的新增指标数, 成功的存量指标数)
        """
        self.logger.info("🚀 开始智能增量更新...")
        
        indicators = self.db_manager.get_indicators()
        self.logger.info(f"📊 总指标数量: {len(indicators)}")
        
        new_indicators = []      # 没有任何数据的指标
        existing_indicators = [] # 已有数据的指标
        
        # 分类指标
        import sqlite3
        with sqlite3.connect(self.db_manager.db_path) as conn:
            cursor = conn.cursor()
            
            for indicator in indicators:
                wind_code = indicator['wind_code']
                
                # 检查是否有数据
                cursor.execute('SELECT COUNT(*) FROM time_series_data WHERE wind_code = ?', (wind_code,))
                data_count = cursor.fetchone()[0]
                
                if data_count == 0:
                    new_indicators.append(indicator)
                else:
                    existing_indicators.append(indicator)
        
        self.logger.info(f"🆕 新增指标: {len(new_indicators)} 个（需要全量更新）")
        self.logger.info(f"📈 存量指标: {len(existing_indicators)} 个（需要增量更新）")
        
        success_new = 0
        success_existing = 0
        
        # 1. 处理新增指标 - 全量更新（2000年至今）
        if new_indicators:
            self.logger.info(f"\n🔄 开始更新新增指标（2000年至今）...")
            start_date = "2000-01-01"
            end_date = datetime.now().strftime("%Y-%m-%d")
            
            for i, indicator in enumerate(new_indicators):
                wind_code = indicator['wind_code']
                name = indicator['name']
                
                self.logger.info(f"📊 [{i+1:3d}/{len(new_indicators)}] 新增: {name} ({wind_code})")
                
                try:
                    if self.update_single_indicator(indicator, start_date, end_date, "full"):
                        success_new += 1
                        self.logger.info(f"✅ 成功: {wind_code}")
                    else:
                        self.logger.warning(f"❌ 失败: {wind_code}")
                        
                except Exception as e:
                    self.logger.error(f"❌ 异常 {wind_code}: {e}")
                
                # 避免请求过于频繁
                time.sleep(1)
                
                # 每10个指标显示进度
                if (i + 1) % 10 == 0:
                    progress = (i + 1) / len(new_indicators) * 100
                    self.logger.info(f"📈 新增指标进度: {i+1}/{len(new_indicators)} ({progress:.1f}%)")
        
        # 2. 处理存量指标 - 增量更新
        if existing_indicators:
            self.logger.info(f"\n🔄 开始更新存量指标（增量更新）...")
            end_date = datetime.now().strftime("%Y-%m-%d")
            
            for i, indicator in enumerate(existing_indicators):
                wind_code = indicator['wind_code']
                name = indicator['name']
                
                # 获取最后更新日期
                last_update_date = self.db_manager.get_last_update_date(wind_code)
                
                if last_update_date:
                    # 从最后更新日期的下一天开始
                    start_date = (
                        datetime.strptime(last_update_date, "%Y-%m-%d") + timedelta(days=1)
                    ).strftime("%Y-%m-%d")
                else:
                    # 如果没有历史数据，从30天前开始
                    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
                
                # 如果开始日期不晚于结束日期，则进行更新
                if start_date <= end_date:
                    days_to_update = (datetime.strptime(end_date, "%Y-%m-%d") - 
                                    datetime.strptime(start_date, "%Y-%m-%d")).days
                    
                    self.logger.info(f"📈 [{i+1:3d}/{len(existing_indicators)}] 存量: {name} ({wind_code}) - 更新{days_to_update}天")
                    
                    try:
                        if self.update_single_indicator(indicator, start_date, end_date, "incremental"):
                            success_existing += 1
                            self.logger.info(f"✅ 成功: {wind_code}")
                        else:
                            self.logger.warning(f"❌ 失败: {wind_code}")
                            
                    except Exception as e:
                        self.logger.error(f"❌ 异常 {wind_code}: {e}")
                else:
                    self.logger.info(f"⏭️  [{i+1:3d}/{len(existing_indicators)}] 跳过: {name} ({wind_code}) - 已是最新")
                
                # 避免请求过于频繁
                time.sleep(0.5)
                
                # 每20个指标显示进度
                if (i + 1) % 20 == 0:
                    progress = (i + 1) / len(existing_indicators) * 100
                    self.logger.info(f"📈 存量指标进度: {i+1}/{len(existing_indicators)} ({progress:.1f}%)")
        
        # 更新摘要
        self.logger.info(f"\n📊 智能增量更新完成:")
        self.logger.info(f"✅ 新增指标成功: {success_new}/{len(new_indicators)}")
        self.logger.info(f"✅ 存量指标成功: {success_existing}/{len(existing_indicators)}")
        self.logger.info(f"📋 总成功率: {(success_new + success_existing)}/{len(indicators)} ({(success_new + success_existing)/len(indicators)*100:.1f}%)")
        
        return success_new, success_existing