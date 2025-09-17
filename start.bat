@echo off
chcp 65001 > nul

echo === 金融数据管理系统 ===
echo 银行理财多资产投资数据管理系统
echo.

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到 Python，请先安装 Python 3.7+
    pause
    exit /b 1
)

REM 安装依赖
echo 检查并安装依赖包...
if exist requirements.txt (
    pip install -r requirements.txt
) else (
    echo 警告: 未找到 requirements.txt 文件
)

REM 创建必要目录
if not exist data mkdir data
if not exist logs mkdir logs
if not exist temp mkdir temp

echo.
echo 可用命令:
echo 1. 初始化数据库:     python main.py init
echo 2. 增量数据更新:     python main.py update
echo 3. 全量数据更新:     python main.py update --update-type full
echo 4. 启动API服务:      python main.py server
echo 5. 启动调度器:       python main.py scheduler
echo 6. 查看系统状态:     python main.py status
echo.

REM 如果有参数，直接执行
if "%~1"=="" (
    echo 请选择要执行的命令，或使用: start.bat [命令]
    echo 例如: start.bat init
    pause
) else (
    echo 执行命令: python main.py %*
    python main.py %*
)