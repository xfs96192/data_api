#!/bin/bash

# 金融数据管理系统启动脚本

echo "=== 金融数据管理系统 ==="
echo "银行理财多资产投资数据管理系统"
echo ""

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 Python3，请先安装 Python 3.7+"
    exit 1
fi

# 检查虚拟环境
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "建议: 请先激活Python虚拟环境"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo ""
fi

# 安装依赖
echo "检查并安装依赖包..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "警告: 未找到 requirements.txt 文件"
fi

# 创建必要目录
mkdir -p data logs temp

echo ""
echo "可用命令:"
echo "1. 初始化数据库:     python main.py init"
echo "2. 增量数据更新:     python main.py update"
echo "3. 全量数据更新:     python main.py update --update-type full"
echo "4. 启动API服务:      python main.py server"
echo "5. 启动调度器:       python main.py scheduler"
echo "6. 查看系统状态:     python main.py status"
echo ""

# 如果有参数，直接执行
if [ $# -gt 0 ]; then
    echo "执行命令: python main.py $@"
    python main.py "$@"
else
    echo "请选择要执行的命令，或使用: ./start.sh [命令]"
    echo "例如: ./start.sh init"
fi