# 月度净值报告生成指南

## 概述

这套工具可以从数据库中提取指定金融指标的近1个月数据，并生成格式化的Excel报告。

## 包含的指标

| Wind代码 | 中文名称 | 类别 |
|----------|----------|------|
| 000001.SH | 上证指数 | 股票 |
| 000832.CSI | 中证转债 | 债券 |
| SPX.GI | 标普500 | 股票 |
| 931472.CSI | 7-10年国开 | 债券 |
| CBA01921.CS | 1-3年高信用等级债券财富 | 债券 |
| 10yrnote.gbm | 10年期美国国债收益率 | 债券 |
| USDCNY.IB | USDCNY | 外汇 |
| AU.SHF | 沪金 | 商品 |
| RB.SHF | 螺纹钢 | 商品 |
| SC.INE | 原油 | 商品 |
| M.DCE | 豆粕 | 商品 |

## 使用方法

### 方法1：一键生成报告
```bash
python generate_report.py
```

### 方法2：详细版本
```bash
python generate_monthly_report.py
```

## 输出文件

- **文件名**：`近1月净值走势.xlsx`
- **格式**：Excel工作簿，包含一个"净值走势"工作表
- **列结构**：
  - 第一列：日期（格式：2025/8/12）
  - 其他列：各指标的数值数据

## 数据更新

如果发现某些指标没有数据，请先更新数据库：

### 智能增量更新（推荐）
```bash
python main.py update --update-type smart
```

### 全量更新
```bash
python main.py update --update-type full
```

### 重试失败指标
```bash
python main.py update --update-type retry
```

## 数据检查

### 检查指标状态
```bash
python main.py status
```

### 检查数据覆盖情况
```bash
python check_data_coverage_v2.py
```

## 故障排除

### 1. 指标无数据
**原因**：数据库中该指标没有近期数据
**解决**：运行数据更新命令

### 2. Wind连接失败
**原因**：Wind服务未启动或连接配置错误
**解决**：
- 检查Wind Terminal是否登录
- 检查Wind MCP服务状态
- 运行 `python main.py status` 查看连接状态

### 3. 文件权限错误
**原因**：无法写入Excel文件
**解决**：确保当前目录有写入权限

### 4. 数据格式错误
**原因**：数据库中数据格式异常
**解决**：运行数据验证和修复

## 定制化

### 修改时间范围
编辑 `generate_monthly_report.py` 文件中的时间范围：
```python
# 计算日期范围（可修改天数）
start_date = end_date - timedelta(days=30)  # 改为你需要的天数
```

### 添加新指标
1. 将新指标添加到 `data/数据指标.xlsx`
2. 运行数据库初始化：`python main.py init`
3. 更新 `generate_monthly_report.py` 中的指标字典
4. 运行数据更新获取新指标数据

### 修改输出格式
编辑 `generate_monthly_report.py` 文件中的Excel格式设置部分。

## 技术说明

### 数据来源
- **数据库**：SQLite数据库（`data/financial_data.db`）
- **数据源**：Wind API（WSD和EDB接口）
- **更新频率**：支持自动调度更新

### 程序架构
- `generate_monthly_report.py`：完整功能的报告生成器
- `generate_report.py`：简化版一键运行脚本
- 依赖：`src/database/models_v2.py`（数据库管理模块）

### 输出特性
- 自动数值格式化（4位小数）
- 智能列宽调整
- 日期格式标准化
- 缺失数据处理

## 常见问题

**Q: 为什么某些指标显示"无数据"？**
A: 该指标可能是新添加的，需要先运行数据更新命令获取历史数据。

**Q: 可以修改报告的时间范围吗？**
A: 可以，编辑程序中的 `timedelta(days=30)` 参数。

**Q: 输出的Excel文件可以自定义格式吗？**
A: 可以，编辑程序中的Excel格式设置部分。

**Q: 如何添加新的指标？**
A: 按照定制化章节的说明，依次添加到Excel配置文件和程序代码中。