
# 股票-债券 滚动相关性报告

时间区间: 2020-09-28 ~ 2025-09-26

代表指数与字段:
- 股票: 000300.SH.close（沪深300）
- 债券: T.CFE.close（10年期国债期货）

窗口设置与文件:
- 1个月(≈21交易日): rolling_corr_1M.png
- 6个月(≈126交易日): rolling_corr_6M.png
- 1年(≈252交易日): rolling_corr_1Y.png
- 叠加图: rolling_corr_overlay.png
- CSV数据: rolling_correlation_stock_bond.csv

说明:
- 以日频收盘价计算收益率后，按共同交易日对齐，再计算滚动皮尔逊相关系数。
- 已配置中文字体: Songti SC
