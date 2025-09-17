# 金融数据管理系统 - 完整参考指南

## 🚀 5分钟快速上手

### 系统概览
- **数据库类型**: SQLite 3.x (多字段架构)
- **文件位置**: `/data/financial_data.db`
- **数据库大小**: ~180MB
- **总指标数**: 391个
- **字段映射数**: 427个
- **多字段指标**: 36个 (支持收盘价+市盈率等多维度数据)
- **数据点总数**: 1,811,846条
- **数据完整性**: 388/391 (99.5%)
- **时间范围**: 2000年至今

### 核心表结构

```sql
-- 1. 指标基础信息表
CREATE TABLE indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,          -- 指标类别
    name TEXT NOT NULL,              -- 指标名称  
    wind_code TEXT NOT NULL UNIQUE,  -- Wind代码
    data_source TEXT NOT NULL,       -- 数据源 ('WSD' 或 'EDB')
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 指标字段映射表 (新增：支持多字段)
CREATE TABLE indicator_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wind_code TEXT NOT NULL,         -- Wind代码
    field_name TEXT NOT NULL,        -- 字段名 ('close', 'val_pe_nonnegative', 'value')
    field_display_name TEXT NOT NULL, -- 字段显示名 ('收盘价', '市盈率', '数值')
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wind_code) REFERENCES indicators (wind_code),
    UNIQUE(wind_code, field_name)
);

-- 3. 多维度时间序列数据表 (升级：支持多字段)
CREATE TABLE time_series_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wind_code TEXT NOT NULL,         -- 指标代码
    field_name TEXT NOT NULL,        -- 字段名 (新增)
    date TEXT NOT NULL,              -- 数据日期 (YYYY-MM-DD)
    value REAL,                      -- 数据值
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wind_code) REFERENCES indicators (wind_code),
    UNIQUE(wind_code, field_name, date) -- 三维唯一约束
);

-- 4. 更新日志表 (升级)
CREATE TABLE update_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wind_code TEXT NOT NULL,         -- 指标代码
    field_name TEXT,                 -- 字段名 (新增，NULL表示所有字段)
    update_type TEXT NOT NULL,       -- 更新类型: 'full', 'incremental', 'retry'
    start_date TEXT,                 -- 更新开始日期
    end_date TEXT,                   -- 更新结束日期
    records_count INTEGER,           -- 更新记录数
    status TEXT NOT NULL,            -- 状态: 'success' 或 'failed'
    error_message TEXT,              -- 错误信息
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wind_code) REFERENCES indicators (wind_code)
);
```

### 索引设计
```sql
-- 多字段时间序列查询优化
CREATE INDEX idx_time_series_wind_code_field_date ON time_series_data (wind_code, field_name, date);
CREATE INDEX idx_time_series_wind_code_date ON time_series_data (wind_code, date);

-- 指标和字段查询优化
CREATE INDEX idx_indicators_category ON indicators (category);
CREATE INDEX idx_indicator_fields_wind_code ON indicator_fields (wind_code);
```

## 📊 数据分类详解

### 指标类别统计
| 类别 | 指标数量 | 主要内容 |
|------|----------|----------|
| 债券 | 267个 | 国债收益率、信用债、城投债、中债指数等 |
| 宏观 | 33个 | GDP、CPI、PMI、M1/M2、进出口等宏观经济指标 |
| 权益 | 32个 | 申万行业指数（28个行业）等 |
| 海外 | 18个 | 美股指数、美债收益率、海外经济指标 |
| 资金 | 15个 | 货币市场利率、银行间利率、MLF利率 |
| 外汇 | 9个 | 人民币汇率、主要货币对 |
| 股票 | 8个 | 主要股票指数(沪深300、上证50、创业板等) |
| 商品 | 7个 | 大宗商品价格、期货指数 |
| 可转债 | 2个 | 可转债相关指数 |

### 数据源类型
| 数据源 | 指标数量 | 字段类型 | 说明 |
|--------|----------|----------|------|
| **EDB** | 315个 | `value` | 经济数据库，宏观经济指标，单一数值 |
| **WSD** | 112个 | `close`, `val_pe_nonnegative` | 证券数据，支持多字段 |

### 多字段指标详情
系统支持36个多字段指标，每个包含：
- **close**: 收盘价/指数点位
- **val_pe_nonnegative**: 市盈率

**主要多字段指标**:
- **股票指数**: 000300.SH(沪深300), 000016.SH(上证50), 000852.SH(中证1000), 399006.SZ(创业板指), 881001.WI(万得全A)
- **申万行业**: 801010.SI(农林牧渔), 801030.SI(基础化工), 801150.SI(医药生物), 801750.SI(计算机)等28个行业
对于多字段指标，默认一般提取和需要的字段的是收盘价指标field_name使用`close`,
若明确说需要获取估值指标，提取的field_name是`val_pe_nonnegative`,


## 📋 常用查询模板

### 1. 指标管理查询

```sql
-- 查看所有指标及其字段
SELECT i.wind_code, i.name, i.category, i.data_source,
       GROUP_CONCAT(f.field_name || ':' || f.field_display_name) as fields
FROM indicators i
LEFT JOIN indicator_fields f ON i.wind_code = f.wind_code
GROUP BY i.wind_code, i.name, i.category, i.data_source
ORDER BY i.category, i.name;

-- 查看多字段指标
SELECT i.wind_code, i.name, i.category,
       COUNT(f.field_name) as field_count,
       GROUP_CONCAT(f.field_display_name) as field_names
FROM indicators i
JOIN indicator_fields f ON i.wind_code = f.wind_code
GROUP BY i.wind_code, i.name, i.category
HAVING COUNT(f.field_name) > 1
ORDER BY field_count DESC, i.name;

-- 查看特定类别指标
SELECT i.wind_code, i.name, 
       GROUP_CONCAT(f.field_display_name) as available_fields
FROM indicators i
LEFT JOIN indicator_fields f ON i.wind_code = f.wind_code
WHERE i.category = '股票'
GROUP BY i.wind_code, i.name
ORDER BY i.name;
```

### 2. 时间序列数据查询

```sql
-- 获取单字段数据
SELECT date, value 
FROM time_series_data 
WHERE wind_code = '000300.SH' AND field_name = 'close'
ORDER BY date DESC LIMIT 10;

-- 获取多字段数据 (透视格式)
SELECT date,
       MAX(CASE WHEN field_name = 'close' THEN value END) as 收盘价,
       MAX(CASE WHEN field_name = 'val_pe_nonnegative' THEN value END) as 市盈率
FROM time_series_data 
WHERE wind_code = '000300.SH'
  AND date >= '2024-01-01'
GROUP BY date
ORDER BY date DESC;

-- 获取最新数据
SELECT i.name, t.wind_code, t.field_name, f.field_display_name, 
       t.date, t.value
FROM time_series_data t
JOIN indicators i ON t.wind_code = i.wind_code
JOIN indicator_fields f ON t.wind_code = f.wind_code AND t.field_name = f.field_name
WHERE (t.wind_code, t.field_name, t.date) IN (
    SELECT wind_code, field_name, MAX(date)
    FROM time_series_data
    GROUP BY wind_code, field_name
)
AND i.category = '股票'
ORDER BY i.name, f.field_name;
```

### 3. 多指标对比分析

```sql
-- 股票指数收盘价对比
SELECT date,
       MAX(CASE WHEN wind_code = '000300.SH' THEN value END) as 沪深300,
       MAX(CASE WHEN wind_code = '000016.SH' THEN value END) as 上证50,
       MAX(CASE WHEN wind_code = '399006.SZ' THEN value END) as 创业板指
FROM time_series_data 
WHERE wind_code IN ('000300.SH', '000016.SH', '399006.SZ')
  AND field_name = 'close'
  AND date >= '2024-01-01'
GROUP BY date
HAVING COUNT(*) = 3  -- 确保所有指标都有数据
ORDER BY date;

-- 收盘价与市盈率关系分析
SELECT date, value as 收盘价,
       (SELECT value FROM time_series_data t2 
        WHERE t2.wind_code = t1.wind_code 
        AND t2.field_name = 'val_pe_nonnegative' 
        AND t2.date = t1.date) as 市盈率
FROM time_series_data t1
WHERE wind_code = '000300.SH' 
  AND field_name = 'close'
  AND date >= '2024-01-01'
ORDER BY date;
```

## 🎯 重要指标快速索引

### 股票指数 (多字段)
| 代码 | 名称 | 字段 | 数据范围 |
|------|------|------|----------|
| `000300.SH` | 沪深300 | close, val_pe_nonnegative | 2002-2025 |
| `000016.SH` | 上证50 | close, val_pe_nonnegative | 2004-2025 |
| `000852.SH` | 中证1000 | close, val_pe_nonnegative | 2005-2025 |
| `399006.SZ` | 创业板指 | close, val_pe_nonnegative | 2010-2025 |
| `881001.WI` | 万得全A | close, val_pe_nonnegative | 2004-2025 |

### 宏观经济指标 (单字段)
| 代码 | 名称 | 数据范围 |
|------|------|----------|
| `M0000612` | CPI:当月同比 | 2000-2025 |
| `M0039354` | GDP:不变价:当季同比 | 2000-2025 |
| `M0017126` | PMI | 2005-2025 |
| `M0001385` | M2:同比 | 2000-2025 |
| `M0001227` | PPI:全部工业品:当月同比 | 2000-2025 |

### 申万行业指数 (多字段)
```sql
-- 获取所有申万行业指数
SELECT wind_code, name
FROM indicators 
WHERE wind_code LIKE '801%.SI'
  AND category = '权益'
ORDER BY wind_code;
```

## 🔧 Python 使用指南

### 方法1: 使用新版数据库管理器 (推荐)

```python
from src.database.models_v2 import DatabaseManager

db = DatabaseManager()

# 获取指标列表
indicators = db.get_indicators(category='股票')

# 获取单字段数据
close_data = db.get_time_series_data('000300.SH', 'close', '2024-01-01', '2024-12-31')

# 获取多字段数据
all_data = db.get_time_series_data('000300.SH', start_date='2024-01-01')  # 自动包含所有字段

# 获取指标的字段信息
fields = db.get_indicator_fields('000300.SH')
print(f"字段: {[f['field_display_name'] for f in fields]}")

# 获取数据库统计
summary = db.get_data_summary()
print(f"总数据点: {summary['data_points']:,}")
print(f"多字段指标: {summary['multi_field_indicators']}个")
```

### 方法2: 直接SQL查询

```python
import sqlite3
import pandas as pd

conn = sqlite3.connect('data/financial_data.db')

# 获取多字段数据
query = """
SELECT date,
       MAX(CASE WHEN field_name = 'close' THEN value END) as close,
       MAX(CASE WHEN field_name = 'val_pe_nonnegative' THEN value END) as pe
FROM time_series_data 
WHERE wind_code = '000300.SH'
GROUP BY date
ORDER BY date
"""
df = pd.read_sql_query(query, conn)

# 获取所有股票指数的最新收盘价
query = """
SELECT i.name, t.value as latest_close, t.date
FROM time_series_data t
JOIN indicators i ON t.wind_code = i.wind_code
WHERE i.category = '股票' 
  AND t.field_name = 'close'
  AND (t.wind_code, t.date) IN (
    SELECT wind_code, MAX(date)
    FROM time_series_data 
    WHERE field_name = 'close'
    GROUP BY wind_code
  )
ORDER BY t.value DESC
"""
latest_prices = pd.read_sql_query(query, conn)
conn.close()
```

### 方法3: REST API

```bash
# 启动API服务
python main_v2.py server

# 获取多字段数据
curl "http://localhost:8000/api/v1/data/000300.SH?start_date=2024-01-01"

# 获取单字段数据
curl "http://localhost:8000/api/v1/data/000300.SH/close?start_date=2024-01-01"
```

## 🔍 数据检查和维护

### 状态检查命令

```bash
# 系统状态 (新版)
python main_v2.py status

# 字段分析
python main_v2.py fields

# 检查数据迁移状态
python check_migration_status.py

# 数据覆盖分析
python check_data_coverage_v2.py
```

### 数据更新命令

```bash
# 增量更新 (推荐)
python main_v2.py update

# 全量更新
python main_v2.py update --update-type full

# 重试失败指标
python main_v2.py update --update-type retry
```

### 数据质量检查

```sql
-- 检查多字段指标的数据完整性
SELECT 
    i.wind_code, i.name,
    COUNT(DISTINCT f.field_name) as expected_fields,
    COUNT(DISTINCT t.field_name) as actual_fields,
    MAX(t.date) as latest_date,
    COUNT(t.id) as total_records
FROM indicators i
JOIN indicator_fields f ON i.wind_code = f.wind_code
LEFT JOIN time_series_data t ON i.wind_code = t.wind_code
WHERE i.wind_code IN (
    SELECT wind_code FROM indicator_fields 
    GROUP BY wind_code HAVING COUNT(*) > 1
)
GROUP BY i.wind_code, i.name
ORDER BY (COUNT(DISTINCT t.field_name) * 1.0 / COUNT(DISTINCT f.field_name)) DESC;

-- 检查数据缺失情况
SELECT 
    category,
    COUNT(*) as total_indicators,
    COUNT(DISTINCT t.wind_code) as indicators_with_data,
    ROUND(COUNT(DISTINCT t.wind_code) * 100.0 / COUNT(*), 1) as success_rate
FROM indicators i
LEFT JOIN time_series_data t ON i.wind_code = t.wind_code
GROUP BY category
ORDER BY success_rate DESC;
```

## 🎯 典型使用场景

### 1. 多资产配置分析

```python
import pandas as pd
import sqlite3

conn = sqlite3.connect('data/financial_data.db')

# 获取主要资产类别的最新数据
query = """
SELECT 
    CASE 
        WHEN i.category = '股票' THEN i.name
        WHEN i.wind_code LIKE 'M10%' AND i.name LIKE '%国债%' THEN '10年国债收益率'
        WHEN i.name LIKE '%CPI%' THEN 'CPI'
        ELSE i.name
    END as asset_class,
    t.value as latest_value,
    t.date as latest_date
FROM time_series_data t
JOIN indicators i ON t.wind_code = i.wind_code
WHERE (t.wind_code = '000300.SH' AND t.field_name = 'close')  -- 沪深300
   OR (t.wind_code = 'M1004264' AND t.field_name = 'value')   -- 10年国债
   OR (t.wind_code = 'M0000612' AND t.field_name = 'value')   -- CPI
AND (t.wind_code, t.field_name, t.date) IN (
    SELECT wind_code, field_name, MAX(date)
    FROM time_series_data
    GROUP BY wind_code, field_name
)
"""

asset_data = pd.read_sql_query(query, conn)
conn.close()
```

### 2. 指数估值分析

```python
# 获取沪深300的估值历史
query = """
SELECT date, 
       MAX(CASE WHEN field_name = 'close' THEN value END) as price,
       MAX(CASE WHEN field_name = 'val_pe_nonnegative' THEN value END) as pe
FROM time_series_data 
WHERE wind_code = '000300.SH'
  AND date >= '2020-01-01'
GROUP BY date
ORDER BY date
"""

valuation_data = pd.read_sql_query(query, conn)

# 计算估值分位数
valuation_data['pe_percentile'] = valuation_data['pe'].rank(pct=True)
```

### 3. 行业轮动分析

```python
# 获取申万行业指数表现
query = """
SELECT i.name as industry,
       t.value as latest_close,
       t.date as latest_date
FROM time_series_data t
JOIN indicators i ON t.wind_code = i.wind_code
WHERE i.wind_code LIKE '801%.SI'
  AND t.field_name = 'close'
  AND (t.wind_code, t.date) IN (
    SELECT wind_code, MAX(date)
    FROM time_series_data 
    WHERE field_name = 'close'
    GROUP BY wind_code
  )
ORDER BY t.value DESC
"""

industry_performance = pd.read_sql_query(query, conn)
```

## ⚠️ 重要说明

### 多字段数据特性
1. **数据完整性**: 不同字段可能有不同的数据起始时间
2. **字段组合**: 同一wind_code的多个字段独立存储
3. **查询方式**: 需指定field_name或使用透视查询获取多字段数据

### 性能优化建议
1. **索引使用**: 查询时尽量包含wind_code和field_name
2. **批量查询**: 使用IN子句查询多个指标
3. **日期过滤**: 大范围查询时添加日期范围限制

### 数据更新说明
- **增量更新**: 自动处理新增指标和多字段更新
- **字段映射**: 新增指标会自动创建字段映射
- **数据一致性**: 多字段数据确保同步更新

---

**最后更新**: 2025年8月21日  
**版本**: v2.0 (多字段架构)  
**维护团队**: 银行理财多资产投资部  
**系统状态**: ✅ 正常运行 (99.5%数据完整性)