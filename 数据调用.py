from src.database.models import DatabaseManager
import pandas as pd

# 创建数据库连接
db = DatabaseManager()

# 获取指标列表
indicators = db.get_indicators()
print(f"总指标数量: {len(indicators)}")

# 按类别获取指标
bond_indicators = db.get_indicators(category="债券")
macro_indicators = db.get_indicators(category="宏观")
# 获取单个指标的时间序列数据
data = db.get_time_series_data(
    wind_code='000300.SH', 
    start_date="2004-01-01", 
    end_date="2024-12-31"
)
print(data)
