from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import pandas as pd
import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.database.models import DatabaseManager
from src.data_fetcher.wind_client import WindDataFetcher
from src.scheduler.data_updater import DataUpdater
from src.analyzer.financial_data_processor import FinancialDataProcessor

app = FastAPI(
    title="金融数据API",
    description="银行理财多资产投资数据管理系统",
    version="1.0.0"
)

# 启用CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局变量
db_manager = None
data_fetcher = None
data_updater = None
data_processor = None


class UpdateRequest(BaseModel):
    update_type: str = "incremental"  # 'incremental' 或 'full'


class DataQueryRequest(BaseModel):
    wind_codes: List[str]
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class AnalysisRequest(BaseModel):
    user_request: str
    auto_confirm: bool = False  # 是否自动确认，跳过用户确认步骤


class ConfirmationRequest(BaseModel):
    session_id: str
    confirmed: bool
    modified_codes: Optional[List[str]] = None


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    global db_manager, data_fetcher, data_updater, data_processor
    
    # 创建logs目录
    os.makedirs("logs", exist_ok=True)
    
    # 初始化组件
    db_manager = DatabaseManager()
    data_fetcher = WindDataFetcher()
    data_updater = DataUpdater(db_manager, data_fetcher)
    data_processor = FinancialDataProcessor()
    
    # 从Excel加载指标（如果存在）
    excel_path = "data/数据指标.xlsx"
    if os.path.exists(excel_path):
        db_manager.load_indicators_from_excel(excel_path)
    
    # 启动调度器
    data_updater.start_scheduler()


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理"""
    if data_updater:
        data_updater.stop_scheduler()


@app.get("/")
async def root():
    """API根路径"""
    return {
        "message": "金融数据API服务",
        "version": "1.0.0",
        "endpoints": {
            "indicators": "/indicators - 获取指标列表",
            "data": "/data/{wind_code} - 获取时间序列数据",
            "batch_data": "/batch-data - 批量获取数据",
            "update": "/update - 手动触发数据更新",
            "status": "/status - 获取系统状态",
            "analyze": "/analyze - 智能分析请求 (带确认步骤)",
            "confirm": "/confirm - 确认分析请求"
        }
    }


@app.get("/indicators")
async def get_indicators(category: Optional[str] = Query(None, description="指标类别")):
    """获取指标列表"""
    try:
        indicators = db_manager.get_indicators(category)
        return {
            "total": len(indicators),
            "indicators": indicators
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/categories")
async def get_categories():
    """获取所有指标类别"""
    try:
        indicators = db_manager.get_indicators()
        categories = list(set(indicator['category'] for indicator in indicators))
        return {
            "categories": sorted(categories)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/data/{wind_code}")
async def get_time_series_data(
    wind_code: str,
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    format: Optional[str] = Query("json", description="返回格式: json 或 csv")
):
    """获取单个指标的时间序列数据"""
    try:
        df = db_manager.get_time_series_data(wind_code, start_date, end_date)
        
        if df.empty:
            raise HTTPException(status_code=404, detail=f"未找到指标 {wind_code} 的数据")
        
        if format.lower() == "csv":
            csv_content = df.to_csv()
            return JSONResponse(
                content={"data": csv_content},
                headers={"Content-Type": "text/csv"}
            )
        else:
            # 转换为JSON格式
            data = []
            for date, row in df.iterrows():
                data.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "value": row['value']
                })
            
            return {
                "wind_code": wind_code,
                "data_points": len(data),
                "data": data
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/batch-data")
async def get_batch_data(request: DataQueryRequest):
    """批量获取多个指标的时间序列数据"""
    try:
        result = {}
        
        for wind_code in request.wind_codes:
            df = db_manager.get_time_series_data(
                wind_code, 
                request.start_date, 
                request.end_date
            )
            
            if not df.empty:
                data = []
                for date, row in df.iterrows():
                    data.append({
                        "date": date.strftime("%Y-%m-%d"),
                        "value": row['value']
                    })
                result[wind_code] = data
            else:
                result[wind_code] = []
        
        return {
            "requested_codes": request.wind_codes,
            "data": result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/update")
async def trigger_update(
    request: UpdateRequest,
    background_tasks: BackgroundTasks
):
    """手动触发数据更新"""
    try:
        if request.update_type not in ["incremental", "full"]:
            raise HTTPException(
                status_code=400, 
                detail="update_type 必须是 'incremental' 或 'full'"
            )
        
        # 在后台执行更新
        background_tasks.add_task(
            data_updater.run_immediate_update, 
            request.update_type
        )
        
        return {
            "message": f"已启动{request.update_type}数据更新",
            "update_type": request.update_type,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
async def get_system_status():
    """获取系统状态"""
    try:
        # 检查Wind连接
        wind_connected = data_fetcher.test_connection()
        
        # 获取数据库统计
        indicators = db_manager.get_indicators()
        
        # 计算各类别指标数量
        category_stats = {}
        for indicator in indicators:
            category = indicator['category']
            category_stats[category] = category_stats.get(category, 0) + 1
        
        # 检查最近更新时间
        recent_updates = []
        with db_manager.db_manager.connect(db_manager.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT wind_code, MAX(update_time) as last_update, status
                FROM update_logs 
                GROUP BY wind_code 
                ORDER BY last_update DESC 
                LIMIT 10
            ''')
            recent_updates = [
                {
                    "wind_code": row[0],
                    "last_update": row[1],
                    "status": row[2]
                }
                for row in cursor.fetchall()
            ]
        
        return {
            "timestamp": datetime.now().isoformat(),
            "wind_connection": {
                "connected": wind_connected,
                "status": "正常" if wind_connected else "连接失败"
            },
            "database": {
                "total_indicators": len(indicators),
                "category_stats": category_stats
            },
            "scheduler": {
                "running": data_updater.is_running,
                "status": "运行中" if data_updater.is_running else "已停止"
            },
            "recent_updates": recent_updates
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


# 用于存储分析会话的临时存储（生产环境中应使用Redis等持久化存储）
analysis_sessions = {}


@app.post("/analyze")
async def analyze_request(request: AnalysisRequest):
    """
    智能分析请求 - 带确认步骤
    
    工作流程：
    1. 解析用户请求，识别相关指标
    2. 如果 auto_confirm=True，直接执行分析
    3. 如果 auto_confirm=False，返回确认信息等待用户确认
    """
    try:
        # 步骤1: 解析用户请求
        parsed_request = data_processor.parse_user_request(request.user_request)
        
        if not parsed_request["indicators_detail"]:
            return {
                "status": "no_indicators",
                "message": "未能识别到任何金融指标",
                "suggestions": [
                    "使用明确的指标名称 (如: 沪深300, 国债收益率)",
                    "或直接提供Wind代码 (如: 000300.SH)"
                ],
                "parsed_request": parsed_request
            }
        
        # 检查数据可用性
        available_indicators = [
            ind for ind in parsed_request["indicators_detail"] 
            if ind["data_available"]
        ]
        
        if not available_indicators:
            return {
                "status": "no_data",
                "message": "识别的指标都没有可用数据",
                "indicators": parsed_request["indicators_detail"]
            }
        
        # 如果设置了自动确认，直接执行分析
        if request.auto_confirm:
            results = data_processor.execute_analysis()
            return {
                "status": "completed",
                "message": "分析完成",
                "results": results
            }
        
        # 否则，生成会话ID并等待用户确认
        session_id = f"session_{datetime.now().timestamp()}"
        analysis_sessions[session_id] = parsed_request
        
        return {
            "status": "confirmation_needed",
            "session_id": session_id,
            "message": "请确认指标选择",
            "request_summary": {
                "original_input": parsed_request["original_input"],
                "analysis_type": parsed_request["analysis_type"],
                "date_range": parsed_request["date_range"],
                "matched_keywords": parsed_request["matched_keywords"]
            },
            "indicators": parsed_request["indicators_detail"],
            "data_availability": {
                "total_indicators": len(parsed_request["indicators_detail"]),
                "available_indicators": len(available_indicators),
                "availability_rate": len(available_indicators) / len(parsed_request["indicators_detail"])
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/confirm")
async def confirm_analysis(request: ConfirmationRequest):
    """
    确认分析请求
    
    用户确认后执行实际的数据分析
    """
    try:
        # 检查会话是否存在
        if request.session_id not in analysis_sessions:
            raise HTTPException(
                status_code=404, 
                detail="分析会话不存在或已过期"
            )
        
        parsed_request = analysis_sessions[request.session_id]
        
        if not request.confirmed:
            # 用户取消分析
            del analysis_sessions[request.session_id]
            return {
                "status": "cancelled",
                "message": "分析已取消"
            }
        
        # 如果用户修改了指标列表
        if request.modified_codes:
            new_indicators_detail = data_processor._get_indicators_detail(request.modified_codes)
            parsed_request["indicators_detail"] = new_indicators_detail
            parsed_request["identified_codes"] = request.modified_codes
        
        # 设置当前请求为待处理请求
        data_processor.pending_request = parsed_request
        
        # 执行分析
        results = data_processor.execute_analysis()
        
        # 清理会话
        del analysis_sessions[request.session_id]
        
        return {
            "status": "completed",
            "message": "分析完成",
            "results": results
        }
        
    except Exception as e:
        # 出错时清理会话
        if request.session_id in analysis_sessions:
            del analysis_sessions[request.session_id]
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analyze/sessions")
async def get_active_sessions():
    """获取活动的分析会话"""
    return {
        "active_sessions": len(analysis_sessions),
        "sessions": {
            session_id: {
                "original_input": session_data["original_input"],
                "timestamp": session_data["timestamp"],
                "indicators_count": len(session_data["indicators_detail"])
            }
            for session_id, session_data in analysis_sessions.items()
        }
    }


@app.delete("/analyze/sessions/{session_id}")
async def cancel_session(session_id: str):
    """取消特定的分析会话"""
    if session_id not in analysis_sessions:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    del analysis_sessions[session_id]
    return {
        "status": "cancelled",
        "message": f"会话 {session_id} 已取消"
    }


@app.get("/analyze/examples")
async def get_analysis_examples():
    """获取分析请求示例"""
    return {
        "examples": [
            {
                "category": "股票分析",
                "requests": [
                    "分析沪深300指数最近1年的表现和趋势",
                    "对比沪深300和上证50的相关性",
                    "研究创业板指最近6个月的波动率"
                ]
            },
            {
                "category": "债券分析", 
                "requests": [
                    "分析10年期国债收益率最近6个月的变化",
                    "对比1年期和10年期国债收益率的利差",
                    "研究国债收益率曲线的变化趋势"
                ]
            },
            {
                "category": "货币市场",
                "requests": [
                    "分析DR007最近3个月的波动情况",
                    "研究DR007与国债收益率的利差关系",
                    "对比SHIBOR不同期限的变化"
                ]
            },
            {
                "category": "宏观经济",
                "requests": [
                    "分析CPI和PPI最近1年的变化趋势",
                    "研究GDP增长率的变化情况",
                    "对比PMI指数与股票市场的关联性"
                ]
            }
        ],
        "tips": [
            "使用明确的指标名称可以提高识别准确率",
            "可以直接使用Wind代码进行精确指定",
            "支持多种时间表达方式：最近1年、2024年1月-6月等",
            "系统会自动识别分析类型：趋势、相关性、利差等"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)