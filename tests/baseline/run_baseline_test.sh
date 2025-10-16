#!/bin/bash
# Baseline Restoration Test Runner
# 用于测试随机修复和逆序修复策略的效果

set -e

# 设置环境变量
export TOOL_SERVICE_IP=${TOOL_SERVICE_IP:-"10.21.9.6"}
export PYTHONPATH=/app/xiaominl/DeepEyes_v2:$PYTHONPATH

# 默认参数
DATA_PATH=${DATA_PATH:-"/app/xiaominl/datasets/air_sp11np_up3_sample1_nosw/shard-test-000000.parquet"}
NUM_SAMPLES=${NUM_SAMPLES:-10}
STRATEGY=${STRATEGY:-"both"}
SAVE_IMAGES=${SAVE_IMAGES:-"false"}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --data-path)
            DATA_PATH="$2"
            shift 2
            ;;
        --num-samples)
            NUM_SAMPLES="$2"
            shift 2
            ;;
        --strategy)
            STRATEGY="$2"
            shift 2
            ;;
        --save-images)
            SAVE_IMAGES="true"
            shift
            ;;
        --tool-service-ip)
            export TOOL_SERVICE_IP="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --data-path PATH         Path to parquet file (default: air_sp11np_up3_sample1_nosw/shard-test-000000.parquet)"
            echo "  --num-samples N          Number of samples to test (default: 10)"
            echo "  --strategy STRATEGY      Strategy: random, reverse, or both (default: both)"
            echo "  --save-images            Save degraded, restored, and original images"
            echo "  --tool-service-ip IP     Tool service IP address (default: 10.21.9.34)"
            echo "  -h, --help               Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  TOOL_SERVICE_IP          IP address of the tool service"
            echo "  DATA_PATH                Path to the parquet data file"
            echo "  NUM_SAMPLES              Number of samples to test"
            echo "  STRATEGY                 Restoration strategy"
            echo ""
            echo "Examples:"
            echo "  $0 --num-samples 5 --strategy random"
            echo "  $0 --num-samples 20 --save-images"
            echo "  TOOL_SERVICE_IP=10.21.9.35 $0 --num-samples 10"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# 打印配置
echo "========================================"
echo "Baseline Restoration Test Configuration"
echo "========================================"
echo "Data Path:          $DATA_PATH"
echo "Number of Samples:  $NUM_SAMPLES"
echo "Strategy:           $STRATEGY"
echo "Save Images:        $SAVE_IMAGES"
echo "Tool Service IP:    $TOOL_SERVICE_IP"
echo "========================================"
echo ""

# 构建命令
CMD="python3 /app/xiaominl/DeepEyes_v2/tests/baseline/test_baseline_restoration.py \
    --data-path $DATA_PATH \
    --num-samples $NUM_SAMPLES \
    --strategy $STRATEGY"

if [ "$SAVE_IMAGES" = "true" ]; then
    CMD="$CMD --save-images"
fi

# 运行测试
echo "Starting baseline restoration test..."
echo "Command: $CMD"
echo ""

$CMD

echo ""
echo "Test completed!"
echo "Results are saved in: /app/xiaominl/DeepEyes_v2/tests/baseline/results/"


