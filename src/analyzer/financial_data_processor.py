#!/usr/bin/env python3
"""
Enhanced Financial Data Processor with Confirmation Workflow
银行理财多资产投资数据分析处理器 - 带确认步骤

功能：
1. 智能解析用户请求
2. 识别和展示相关金融指标
3. 用户确认后执行数据提取和分析
4. 防止错误的指标识别导致的数据提取错误

作者：Claude
创建时间：2025
"""

import re
import sys
import os
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.database.models import DatabaseManager


class FinancialDataProcessor:
    """带确认步骤的金融数据处理器"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.indicators_cache = None
        self.pending_request = None
        
        # 预定义的指标关键词映射
        self.indicator_keywords = {
            # 股票指数
            "沪深300": ["000300.SH"],
            "上证指数": ["000001.SH"],
            "上证50": ["000016.SH"],
            "中证1000": ["000852.SH"],
            "创业板指": ["399006.SZ"],
            "深证成指": ["399001.SZ"],
            
            # 债券相关
            "国债": ["S0059744", "S0059745", "S0059746", "S0059747", "S0059748"],
            "国债收益率": ["S0059744", "S0059745", "S0059746", "S0059747", "S0059748"],
            "10年期国债": ["S0059747"],
            "1年期国债": ["S0059744"],
            "5年期国债": ["S0059746"],
            "债券收益率": ["S0059744", "S0059745", "S0059746", "S0059747", "S0059748"],
            
            # 货币市场
            "DR007": ["M0041371"],
            "银行间拆借": ["M0041371", "M0041372"],
            "SHIBOR": ["M0000272", "M0000273", "M0000274", "M0000275"],
            
            # 宏观经济
            "GDP": ["M0000545"],
            "CPI": ["M0000612"],
            "PPI": ["M0001227"],
            "PMI": ["M0017126"],
            "失业率": ["M0000088"],
            
            # 汇率
            "美元": ["M0000141"],
            "人民币": ["M0000141"],
            "汇率": ["M0000141"],
            
            # 大宗商品
            "黄金": ["AU9999.SGE"],
            "原油": ["CL00Y.NYM"],
            "铜": ["CU00Y.SHF"],
        }
    
    def _load_indicators_cache(self):
        """加载指标缓存"""
        if self.indicators_cache is None:
            self.indicators_cache = self.db_manager.get_indicators()
        return self.indicators_cache
    
    def parse_user_request(self, user_input: str) -> Dict[str, Any]:
        """
        步骤1: 解析用户请求，识别所需的金融指标
        
        Args:
            user_input: 用户输入的分析请求
            
        Returns:
            解析结果字典，包含识别的指标、时间范围等
        """
        print("🔍 正在解析您的请求...")
        print(f"用户请求: {user_input}")
        print("-" * 50)
        
        # 识别的指标代码
        identified_codes = set()
        matched_keywords = []
        
        # 通过关键词匹配识别指标
        for keyword, codes in self.indicator_keywords.items():
            if keyword in user_input:
                identified_codes.update(codes)
                matched_keywords.append(keyword)
        
        # 直接从输入中提取Wind代码
        wind_code_pattern = r'[A-Z0-9]{6,10}\.[A-Z]{2,3}'
        wind_codes = re.findall(wind_code_pattern, user_input)
        identified_codes.update(wind_codes)
        
        # 识别时间范围
        date_range = self._extract_date_range(user_input)
        
        # 识别分析类型
        analysis_type = self._identify_analysis_type(user_input)
        
        # 从数据库获取指标详细信息
        indicators_detail = self._get_indicators_detail(list(identified_codes))
        
        parsed_request = {
            "original_input": user_input,
            "identified_codes": list(identified_codes),
            "matched_keywords": matched_keywords,
            "indicators_detail": indicators_detail,
            "date_range": date_range,
            "analysis_type": analysis_type,
            "timestamp": datetime.now().isoformat()
        }
        
        self.pending_request = parsed_request
        return parsed_request
    
    def _extract_date_range(self, text: str) -> Dict[str, Optional[str]]:
        """从文本中提取日期范围"""
        date_range = {"start_date": None, "end_date": None}
        
        # 常见日期模式
        date_patterns = [
            r'(\d{4})-(\d{1,2})-(\d{1,2})',  # YYYY-MM-DD
            r'(\d{4})年(\d{1,2})月(\d{1,2})日',  # YYYY年MM月DD日
            r'(\d{4})年(\d{1,2})月',  # YYYY年MM月
            r'(\d{4})年',  # YYYY年
        ]
        
        dates_found = []
        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if len(match) == 3:  # 年月日
                    date_str = f"{match[0]}-{match[1]:0>2}-{match[2]:0>2}"
                elif len(match) == 2:  # 年月
                    date_str = f"{match[0]}-{match[1]:0>2}-01"
                else:  # 年
                    date_str = f"{match[0]}-01-01"
                dates_found.append(date_str)
        
        if dates_found:
            dates_found.sort()
            date_range["start_date"] = dates_found[0]
            if len(dates_found) > 1:
                date_range["end_date"] = dates_found[-1]
        
        # 处理相对日期表达
        if "最近" in text:
            if "1年" in text:
                date_range["start_date"] = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
            elif "半年" in text:
                date_range["start_date"] = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
            elif "3个月" in text:
                date_range["start_date"] = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
            elif "1个月" in text:
                date_range["start_date"] = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        return date_range
    
    def _identify_analysis_type(self, text: str) -> str:
        """识别分析类型"""
        analysis_keywords = {
            "correlation": ["相关性", "关联", "相关", "协整"],
            "trend": ["趋势", "走势", "变化", "发展"],
            "spread": ["利差", "价差", "差值", "差异"],
            "volatility": ["波动", "风险", "标准差"],
            "comparison": ["对比", "比较", "对照"],
            "statistics": ["统计", "描述", "汇总", "分析"],
            "forecast": ["预测", "预估", "展望"],
        }
        
        for analysis_type, keywords in analysis_keywords.items():
            if any(keyword in text for keyword in keywords):
                return analysis_type
        
        return "general"  # 默认分析类型
    
    def _get_indicators_detail(self, wind_codes: List[str]) -> List[Dict]:
        """获取指标详细信息"""
        if not wind_codes:
            return []
        
        indicators = self._load_indicators_cache()
        detail_list = []
        
        for code in wind_codes:
            # 查找匹配的指标
            matching_indicators = [ind for ind in indicators if ind['wind_code'] == code]
            
            if matching_indicators:
                indicator = matching_indicators[0]
                # 检查是否有数据
                try:
                    data = self.db_manager.get_time_series_data(code)
                    data_available = not data.empty
                    data_count = len(data) if data_available else 0
                    latest_date = data.index.max().strftime("%Y-%m-%d") if data_available else "无数据"
                except:
                    data_available = False
                    data_count = 0
                    latest_date = "无数据"
                
                detail_list.append({
                    "wind_code": code,
                    "name": indicator["name"],
                    "category": indicator["category"],
                    "data_source": indicator.get("data_source", "N/A"),
                    "data_available": data_available,
                    "data_count": data_count,
                    "latest_date": latest_date
                })
            else:
                detail_list.append({
                    "wind_code": code,
                    "name": f"未知指标 ({code})",
                    "category": "未知",
                    "data_source": "N/A",
                    "data_available": False,
                    "data_count": 0,
                    "latest_date": "无数据"
                })
        
        return detail_list
    
    def display_confirmation_request(self, parsed_request: Dict[str, Any]) -> str:
        """
        步骤2: 展示识别的指标并请求用户确认
        
        Args:
            parsed_request: 解析结果
            
        Returns:
            格式化的确认请求字符串
        """
        print("\n" + "="*60)
        print("📋 指标识别结果 - 请确认")
        print("="*60)
        
        if not parsed_request["indicators_detail"]:
            print("❌ 未能识别到任何金融指标")
            print("💡 建议:")
            print("  - 使用明确的指标名称 (如: 沪深300, 国债收益率)")
            print("  - 或直接提供Wind代码 (如: 000300.SH)")
            return "no_indicators"
        
        print(f"🎯 根据您的请求「{parsed_request['original_input']}」")
        print(f"📅 识别到的时间范围: {parsed_request['date_range']['start_date']} 至 {parsed_request['date_range']['end_date']}")
        print(f"🔬 分析类型: {parsed_request['analysis_type']}")
        
        if parsed_request["matched_keywords"]:
            print(f"🔍 匹配的关键词: {', '.join(parsed_request['matched_keywords'])}")
        
        print(f"\n📊 识别到 {len(parsed_request['indicators_detail'])} 个指标:")
        print("-" * 60)
        
        # 创建表格显示
        headers = ["序号", "Wind代码", "指标名称", "类别", "数据状态", "数据量", "最新日期"]
        
        # 计算列宽
        col_widths = [4, 12, 25, 8, 8, 6, 12]
        
        # 打印表头
        header_line = " | ".join(h.center(w) for h, w in zip(headers, col_widths))
        print(header_line)
        print("-" * len(header_line))
        
        # 打印数据行
        for i, indicator in enumerate(parsed_request["indicators_detail"], 1):
            status_icon = "✅" if indicator["data_available"] else "❌"
            data_status = f"{status_icon} {'有数据' if indicator['data_available'] else '无数据'}"
            
            row_data = [
                str(i),
                indicator["wind_code"],
                indicator["name"][:23] + "..." if len(indicator["name"]) > 25 else indicator["name"],
                indicator["category"],
                data_status,
                str(indicator["data_count"]),
                indicator["latest_date"]
            ]
            
            row_line = " | ".join(data.ljust(w) if i != 0 else data.center(w) 
                                 for i, (data, w) in enumerate(zip(row_data, col_widths)))
            print(row_line)
        
        print("-" * len(header_line))
        
        # 统计信息
        available_count = sum(1 for ind in parsed_request["indicators_detail"] if ind["data_available"])
        total_count = len(parsed_request["indicators_detail"])
        
        print(f"\n📈 数据可用性: {available_count}/{total_count} 个指标有数据")
        
        if available_count == 0:
            print("⚠️  警告: 所有识别的指标都没有数据!")
        elif available_count < total_count:
            print("⚠️  注意: 部分指标缺少数据，分析结果可能受限")
        
        print("\n" + "="*60)
        print("🤔 确认选择:")
        print("  输入 'y' 或 'yes' - 确认使用上述指标进行分析")
        print("  输入 'n' 或 'no'  - 取消分析")
        print("  输入 'modify'    - 手动修改指标列表")
        print("="*60)
        
        return "confirmation_needed"
    
    def process_user_confirmation(self, user_response: str) -> str:
        """
        步骤3: 处理用户确认响应
        
        Args:
            user_response: 用户确认响应
            
        Returns:
            处理结果状态
        """
        response = user_response.lower().strip()
        
        if response in ['y', 'yes', '是', '确认']:
            print("✅ 用户确认，开始数据分析...")
            return "confirmed"
        elif response in ['n', 'no', '否', '取消']:
            print("❌ 用户取消分析")
            self.pending_request = None
            return "cancelled"
        elif response in ['modify', '修改', 'm']:
            print("🔧 进入手动修改模式...")
            return "modify"
        else:
            print("⚠️  无效输入，请重新选择")
            return "invalid"
    
    def execute_analysis(self) -> Dict[str, Any]:
        """
        步骤4: 执行实际的数据提取和分析
        
        Returns:
            分析结果字典
        """
        if not self.pending_request:
            raise ValueError("没有待处理的请求，请先解析用户请求")
        
        print("\n🚀 开始执行数据分析...")
        print("-" * 50)
        
        request = self.pending_request
        results = {
            "request_summary": request,
            "data_extraction": {},
            "analysis_results": {},
            "execution_time": datetime.now().isoformat()
        }
        
        # 提取数据
        for indicator in request["indicators_detail"]:
            if not indicator["data_available"]:
                continue
                
            wind_code = indicator["wind_code"]
            print(f"📊 提取数据: {indicator['name']} ({wind_code})")
            
            try:
                data = self.db_manager.get_time_series_data(
                    wind_code=wind_code,
                    start_date=request["date_range"]["start_date"],
                    end_date=request["date_range"]["end_date"]
                )
                
                if not data.empty:
                    results["data_extraction"][wind_code] = {
                        "name": indicator["name"],
                        "data_points": len(data),
                        "date_range": [
                            data.index.min().strftime("%Y-%m-%d"),
                            data.index.max().strftime("%Y-%m-%d")
                        ],
                        "statistics": {
                            "mean": float(data["value"].mean()),
                            "std": float(data["value"].std()),
                            "min": float(data["value"].min()),
                            "max": float(data["value"].max()),
                            "latest": float(data["value"].iloc[-1])
                        }
                    }
                    print(f"  ✅ 成功提取 {len(data)} 个数据点")
                else:
                    print(f"  ❌ 该时间范围内无数据")
                    
            except Exception as e:
                print(f"  ❌ 提取失败: {str(e)}")
                results["data_extraction"][wind_code] = {"error": str(e)}
        
        # 执行分析
        if results["data_extraction"]:
            results["analysis_results"] = self._perform_analysis(
                request["analysis_type"], 
                results["data_extraction"]
            )
        
        print(f"\n✅ 分析完成! 共处理 {len(results['data_extraction'])} 个指标")
        return results
    
    def _perform_analysis(self, analysis_type: str, data_extraction: Dict) -> Dict:
        """执行具体分析"""
        analysis_results = {
            "analysis_type": analysis_type,
            "summary": {}
        }
        
        if analysis_type == "correlation" and len(data_extraction) >= 2:
            # 相关性分析
            analysis_results["correlation_matrix"] = self._calculate_correlation(data_extraction)
        
        elif analysis_type == "trend":
            # 趋势分析
            analysis_results["trend_analysis"] = self._analyze_trends(data_extraction)
        
        elif analysis_type == "spread" and len(data_extraction) >= 2:
            # 利差分析
            analysis_results["spread_analysis"] = self._calculate_spreads(data_extraction)
        
        # 通用统计摘要
        analysis_results["summary"] = {
            "total_indicators": len(data_extraction),
            "date_coverage": self._get_date_coverage(data_extraction),
            "data_quality": self._assess_data_quality(data_extraction)
        }
        
        return analysis_results
    
    def _calculate_correlation(self, data_extraction: Dict) -> Dict:
        """计算相关性矩阵"""
        # 这里实现相关性计算逻辑
        return {"message": "相关性分析功能待实现"}
    
    def _analyze_trends(self, data_extraction: Dict) -> Dict:
        """分析趋势"""
        # 这里实现趋势分析逻辑
        return {"message": "趋势分析功能待实现"}
    
    def _calculate_spreads(self, data_extraction: Dict) -> Dict:
        """计算利差"""
        # 这里实现利差计算逻辑
        return {"message": "利差分析功能待实现"}
    
    def _get_date_coverage(self, data_extraction: Dict) -> Dict:
        """获取日期覆盖范围"""
        if not data_extraction:
            return {}
        
        all_start_dates = []
        all_end_dates = []
        
        for wind_code, data_info in data_extraction.items():
            if "date_range" in data_info:
                all_start_dates.append(data_info["date_range"][0])
                all_end_dates.append(data_info["date_range"][1])
        
        if all_start_dates and all_end_dates:
            return {
                "earliest_start": min(all_start_dates),
                "latest_end": max(all_end_dates),
                "common_start": max(all_start_dates),
                "common_end": min(all_end_dates)
            }
        
        return {}
    
    def _assess_data_quality(self, data_extraction: Dict) -> Dict:
        """评估数据质量"""
        if not data_extraction:
            return {}
        
        total_points = sum(data_info.get("data_points", 0) 
                          for data_info in data_extraction.values())
        avg_points = total_points / len(data_extraction) if data_extraction else 0
        
        return {
            "total_data_points": total_points,
            "average_points_per_indicator": round(avg_points, 2),
            "indicators_with_data": len(data_extraction)
        }
    
    def modify_indicator_selection(self) -> Dict[str, Any]:
        """手动修改指标选择"""
        if not self.pending_request:
            raise ValueError("没有待处理的请求")
        
        print("\n🔧 手动修改指标选择")
        print("-" * 40)
        
        current_codes = [ind["wind_code"] for ind in self.pending_request["indicators_detail"]]
        print(f"当前指标: {', '.join(current_codes)}")
        
        print("\n请输入新的Wind代码列表 (用逗号分隔):")
        print("例如: 000300.SH, 000001.SH, S0059747")
        
        new_codes_input = input("新指标代码: ").strip()
        
        if new_codes_input:
            new_codes = [code.strip() for code in new_codes_input.split(',')]
            new_indicators_detail = self._get_indicators_detail(new_codes)
            
            self.pending_request["indicators_detail"] = new_indicators_detail
            self.pending_request["identified_codes"] = new_codes
            
            print(f"✅ 已更新指标列表，共 {len(new_codes)} 个指标")
            return self.pending_request
        else:
            print("❌ 未输入有效代码，保持原有选择")
            return self.pending_request
    
    def run_interactive_session(self, user_input: str):
        """运行交互式分析会话"""
        print("\n" + "="*60)
        print("🏦 金融数据分析处理器 - 交互式会话")
        print("="*60)
        
        # 步骤1: 解析请求
        parsed_request = self.parse_user_request(user_input)
        
        # 步骤2: 显示确认请求
        confirmation_status = self.display_confirmation_request(parsed_request)
        
        if confirmation_status == "no_indicators":
            return None
        
        # 步骤3: 等待用户确认
        while True:
            user_response = input("\n👤 您的选择: ").strip()
            
            response_status = self.process_user_confirmation(user_response)
            
            if response_status == "confirmed":
                # 步骤4: 执行分析
                results = self.execute_analysis()
                return results
                
            elif response_status == "cancelled":
                return None
                
            elif response_status == "modify":
                # 修改指标选择
                modified_request = self.modify_indicator_selection()
                # 重新显示确认请求
                self.display_confirmation_request(modified_request)
                
            elif response_status == "invalid":
                continue  # 继续等待有效输入
    
    def get_available_indicators_by_category(self, category: str = None) -> List[Dict]:
        """获取可用指标列表（按类别）"""
        indicators = self._load_indicators_cache()
        
        if category:
            indicators = [ind for ind in indicators if ind['category'] == category]
        
        # 检查数据可用性
        available_indicators = []
        for indicator in indicators[:20]:  # 限制检查数量以提高性能
            try:
                data = self.db_manager.get_time_series_data(indicator['wind_code'])
                if not data.empty:
                    available_indicators.append({
                        **indicator,
                        "data_available": True,
                        "data_count": len(data),
                        "latest_date": data.index.max().strftime("%Y-%m-%d")
                    })
            except:
                continue
        
        return available_indicators


def main():
    """主函数 - 演示用法"""
    processor = FinancialDataProcessor()
    
    # 示例1: 基本分析请求
    print("="*60)
    print("示例1: 沪深300指数分析")
    print("="*60)
    
    sample_request = "分析沪深300指数最近1年的表现和趋势"
    results = processor.run_interactive_session(sample_request)
    
    if results:
        print("\n📊 分析结果摘要:")
        print(f"  处理指标数: {results['analysis_results']['summary']['total_indicators']}")
        print(f"  数据质量: {results['analysis_results']['summary']['data_quality']}")


if __name__ == "__main__":
    main()