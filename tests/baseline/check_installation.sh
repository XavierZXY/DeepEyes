#!/bin/bash
# 检查baseline测试安装是否完整

set -e

echo "=========================================="
echo "Baseline测试安装检查"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0
WARNINGS=0

# 检查函数
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} 文件存在: $1"
    else
        echo -e "${RED}✗${NC} 文件缺失: $1"
        ((ERRORS++))
    fi
}

check_executable() {
    if [ -x "$1" ]; then
        echo -e "${GREEN}✓${NC} 可执行: $1"
    else
        echo -e "${YELLOW}⚠${NC} 不可执行: $1"
        ((WARNINGS++))
    fi
}

# 1. 检查文件
echo "1. 检查文件完整性"
echo "-------------------"
check_file "test_baseline_restoration.py"
check_file "run_baseline_test.sh"
check_file "quick_test.sh"
check_file "verify_dataset.py"
check_file "README.md"
check_file "USAGE_EXAMPLES.md"
check_file "PROJECT_SUMMARY.md"
check_file "INSTALL_COMPLETE.md"
check_file ".gitignore"
echo ""

# 2. 检查可执行权限
echo "2. 检查可执行权限"
echo "-------------------"
check_executable "run_baseline_test.sh"
check_executable "quick_test.sh"
check_executable "verify_dataset.py"
echo ""

# 3. 检查Python语法
echo "3. 检查Python语法"
echo "-------------------"
cd /app/xiaominl/DeepEyes_v2
if python3 -m py_compile tests/baseline/test_baseline_restoration.py 2>/dev/null; then
    echo -e "${GREEN}✓${NC} test_baseline_restoration.py 语法正确"
else
    echo -e "${RED}✗${NC} test_baseline_restoration.py 语法错误"
    ((ERRORS++))
fi

if python3 -m py_compile tests/baseline/verify_dataset.py 2>/dev/null; then
    echo -e "${GREEN}✓${NC} verify_dataset.py 语法正确"
else
    echo -e "${RED}✗${NC} verify_dataset.py 语法错误"
    ((ERRORS++))
fi
echo ""

# 4. 检查导入
echo "4. 检查Python导入"
echo "-------------------"
export PYTHONPATH=/app/xiaominl/DeepEyes_v2:$PYTHONPATH

if python3 -c "from tests.baseline.test_baseline_restoration import DEGRADATION_TO_TOOLS" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} test_baseline_restoration.py 导入成功"
    
    # 显示支持的退化类型
    TOOL_COUNT=$(python3 -c "from tests.baseline.test_baseline_restoration import DEGRADATION_TO_TOOLS; print(len(DEGRADATION_TO_TOOLS))" 2>/dev/null)
    echo -e "  支持 ${GREEN}${TOOL_COUNT}${NC} 种退化类型"
else
    echo -e "${RED}✗${NC} test_baseline_restoration.py 导入失败"
    ((ERRORS++))
fi
echo ""

# 5. 检查数据集
echo "5. 检查默认数据集"
echo "-------------------"
DEFAULT_DATA="/app/xiaominl/datasets/air_sp11np_up3_sample1_nosw/shard-test-000000.parquet"
if [ -f "$DEFAULT_DATA" ]; then
    echo -e "${GREEN}✓${NC} 默认数据集存在"
    FILE_SIZE=$(du -h "$DEFAULT_DATA" | cut -f1)
    echo -e "  大小: ${FILE_SIZE}"
else
    echo -e "${YELLOW}⚠${NC} 默认数据集不存在: $DEFAULT_DATA"
    echo -e "  ${YELLOW}提示:${NC} 可以使用 --data-path 参数指定其他数据集"
    ((WARNINGS++))
fi
echo ""

# 6. 检查环境变量
echo "6. 检查环境变量"
echo "-------------------"
if [ -n "$TOOL_SERVICE_IP" ]; then
    echo -e "${GREEN}✓${NC} TOOL_SERVICE_IP 已设置: $TOOL_SERVICE_IP"
else
    echo -e "${YELLOW}⚠${NC} TOOL_SERVICE_IP 未设置（将使用默认值: 10.21.9.34）"
    ((WARNINGS++))
fi
echo ""

# 7. 检查Python依赖
echo "7. 检查Python依赖"
echo "-------------------"
check_python_package() {
    if python3 -c "import $1" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} $1"
    else
        echo -e "${RED}✗${NC} $1 (请安装: pip install $2)"
        ((ERRORS++))
    fi
}

check_python_package "pandas" "pandas"
check_python_package "numpy" "numpy"
check_python_package "PIL" "pillow"
check_python_package "cv2" "opencv-python"
check_python_package "skimage" "scikit-image"
check_python_package "torch" "torch"
check_python_package "lpips" "lpips"
echo ""

# 8. 生成摘要
echo "=========================================="
echo "检查摘要"
echo "=========================================="
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ 所有检查通过！${NC}"
    echo ""
    echo "你可以开始运行测试了："
    echo "  cd /app/xiaominl/DeepEyes_v2/tests/baseline"
    echo "  ./quick_test.sh"
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ 有 $WARNINGS 个警告${NC}"
    echo "警告不会阻止测试运行，但建议检查上述警告信息。"
    echo ""
    echo "你仍然可以运行测试："
    echo "  cd /app/xiaominl/DeepEyes_v2/tests/baseline"
    echo "  ./quick_test.sh"
else
    echo -e "${RED}✗ 发现 $ERRORS 个错误和 $WARNINGS 个警告${NC}"
    echo "请修复上述错误后再运行测试。"
    exit 1
fi
echo ""

