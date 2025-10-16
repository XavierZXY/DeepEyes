#!/bin/bash
# 图像修复工具测试脚本 - 快速运行

set -e

# 默认配置
DATASET_ROOT="/app/xiaominl/datasets/degraded_datasets/degraded_dataset"
OUTPUT_DIR="./test_results_$(date +%Y%m%d_%H%M%S)"
NUM_SAMPLES=10  # 默认每个级别测试10个样本
TOOL_SERVICE_IP="${TOOL_SERVICE_IP:-10.21.9.6}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印带颜色的信息
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示使用帮助
show_help() {
    cat << EOF
图像修复工具测试脚本

用法: $0 [选项]

选项:
    -d, --dataset PATH          数据集根目录 (默认: $DATASET_ROOT)
    -o, --output PATH           输出目录 (默认: ./test_results_TIMESTAMP)
    -n, --num-samples N         每个级别的样本数量 (默认: $NUM_SAMPLES, 0表示全部)
    -t, --types TYPE1,TYPE2     要测试的退化类型，逗号分隔 (默认: 全部)
    -e, --exclude TYPE1,TYPE2   要排除的退化类型，逗号分隔
    -l, --levels LEV1,LEV2      要测试的级别，逗号分隔 (默认: 全部)
    -i, --ip IP                 工具服务IP地址 (默认: $TOOL_SERVICE_IP)
    --quick                     快速测试模式 (每个级别只测试3个样本)
    --full                      完整测试模式 (测试所有样本)
    -h, --help                  显示此帮助信息

示例:
    # 快速测试雾霾类型
    $0 --quick --types haze

    # 测试所有类型，每个级别10个样本
    $0 -d /data/dataset -n 10

    # 排除dark和low_resolution类型
    $0 --exclude dark,low_resolution

    # 完整测试
    $0 --full -d /data/dataset -o ./full_test_results
EOF
}

# 解析命令行参数
TYPES=""
EXCLUDE=""
LEVELS=""
QUICK_MODE=0
FULL_MODE=0

while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--dataset)
            DATASET_ROOT="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -n|--num-samples)
            NUM_SAMPLES="$2"
            shift 2
            ;;
        -t|--types)
            TYPES="$2"
            shift 2
            ;;
        -e|--exclude)
            EXCLUDE="$2"
            shift 2
            ;;
        -l|--levels)
            LEVELS="$2"
            shift 2
            ;;
        -i|--ip)
            TOOL_SERVICE_IP="$2"
            shift 2
            ;;
        --quick)
            QUICK_MODE=1
            NUM_SAMPLES=3
            shift
            ;;
        --full)
            FULL_MODE=1
            NUM_SAMPLES=0
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            print_error "未知参数: $1"
            show_help
            exit 1
            ;;
    esac
done

# 检查数据集目录
if [ ! -d "$DATASET_ROOT" ]; then
    print_error "数据集目录不存在: $DATASET_ROOT"
    exit 1
fi

if [ ! -d "$DATASET_ROOT/original" ]; then
    print_error "数据集目录缺少original文件夹: $DATASET_ROOT/original"
    exit 1
fi

# 打印配置信息
print_info "================================"
print_info "测试配置"
print_info "================================"
print_info "数据集路径: $DATASET_ROOT"
print_info "输出目录: $OUTPUT_DIR"
print_info "工具服务IP: $TOOL_SERVICE_IP"

if [ $QUICK_MODE -eq 1 ]; then
    print_info "模式: 快速测试 (每级别3个样本)"
elif [ $FULL_MODE -eq 1 ]; then
    print_info "模式: 完整测试 (所有样本)"
else
    print_info "样本数量: $NUM_SAMPLES (每个级别)"
fi

if [ -n "$TYPES" ]; then
    print_info "测试类型: $TYPES"
else
    print_info "测试类型: 全部"
fi

if [ -n "$EXCLUDE" ]; then
    print_info "排除类型: $EXCLUDE"
fi

if [ -n "$LEVELS" ]; then
    print_info "测试级别: $LEVELS"
else
    print_info "测试级别: 全部"
fi

print_info "================================"

# 设置环境变量
export TOOL_SERVICE_IP=$TOOL_SERVICE_IP

# 构建命令
CMD="python test_restoration_tools.py --dataset \"$DATASET_ROOT\" --output \"$OUTPUT_DIR\""

if [ $NUM_SAMPLES -gt 0 ]; then
    CMD="$CMD --num-samples $NUM_SAMPLES"
fi

if [ -n "$TYPES" ]; then
    # 将逗号分隔转换为空格分隔
    TYPES_ARRAY=(${TYPES//,/ })
    CMD="$CMD --types ${TYPES_ARRAY[*]}"
fi

if [ -n "$EXCLUDE" ]; then
    EXCLUDE_ARRAY=(${EXCLUDE//,/ })
    CMD="$CMD --exclude-types ${EXCLUDE_ARRAY[*]}"
fi

if [ -n "$LEVELS" ]; then
    LEVELS_ARRAY=(${LEVELS//,/ })
    CMD="$CMD --levels ${LEVELS_ARRAY[*]}"
fi

CMD="$CMD --tool-service-ip $TOOL_SERVICE_IP"

# 打印并执行命令
print_info "执行命令:"
echo "$CMD"
echo ""

# 检查Python脚本是否存在
if [ ! -f "test_restoration_tools.py" ]; then
    print_error "找不到test_restoration_tools.py，请确保在正确的目录下运行此脚本"
    exit 1
fi

# 执行测试
eval $CMD

# 检查执行结果
if [ $? -eq 0 ]; then
    print_info "================================"
    print_info "测试完成！"
    print_info "================================"
    print_info "结果已保存到: $OUTPUT_DIR"
    print_info ""
    print_info "生成的文件:"
    if [ -f "$OUTPUT_DIR/test_results.json" ]; then
        print_info "  ✓ test_results.json (完整JSON数据)"
    fi
    if [ -f "$OUTPUT_DIR/test_results.csv" ]; then
        print_info "  ✓ test_results.csv (Excel表格)"
    fi
    if [ -f "$OUTPUT_DIR/test_results.md" ]; then
        print_info "  ✓ test_results.md (Markdown报告)"
    fi
    print_info ""
    print_info "查看报告: cat $OUTPUT_DIR/test_results.md"
else
    print_error "测试失败！请检查错误信息"
    exit 1
fi

