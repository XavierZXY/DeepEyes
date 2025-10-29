#!/bin/bash
# Baseline Restoration Test Runner - 支持多个 parquet 文件
# 用于测试随机修复和逆序修复策略的效果

set -e

# 设置环境变量
export TOOL_SERVICE_IP=${TOOL_SERVICE_IP:-"10.21.9.6"}
export PYTHONPATH=/app/xiaominl/DeepEyes_v2:$PYTHONPATH

# 默认参数
DATA_PATHS=()
NUM_SAMPLES=${NUM_SAMPLES:-10}
STRATEGY=${STRATEGY:-"both"}
SAVE_IMAGES=${SAVE_IMAGES:-"false"}
NUM_SAMPLES_PER_FILE=${NUM_SAMPLES_PER_FILE:-""}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --data-path)
            DATA_PATHS+=("$2")
            shift 2
            ;;
        --data-dir)
            # 读取目录下所有 parquet 文件
            DATA_DIR="$2"
            if [ -d "$DATA_DIR" ]; then
                while IFS= read -r -d '' file; do
                    DATA_PATHS+=("$file")
                done < <(find "$DATA_DIR" -name "*.parquet" -print0 | sort -z)
                echo "Found ${#DATA_PATHS[@]} parquet files in $DATA_DIR"
            else
                echo "Error: Directory not found: $DATA_DIR"
                exit 1
            fi
            shift 2
            ;;
        --num-samples)
            NUM_SAMPLES="$2"
            shift 2
            ;;
        --num-samples-per-file)
            NUM_SAMPLES_PER_FILE="$2"
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
            echo "  --data-path PATH              Path to parquet file (can be specified multiple times)"
            echo "  --data-dir DIR                Directory containing parquet files (auto-discover all .parquet files)"
            echo "  --num-samples N               Total number of samples to test across all files (default: 10)"
            echo "  --num-samples-per-file N      Number of samples per file (overrides --num-samples)"
            echo "  --strategy STRATEGY           Strategy: random, reverse, or both (default: both)"
            echo "  --save-images                 Save degraded, restored, and original images"
            echo "  --tool-service-ip IP          Tool service IP address (default: 10.21.9.6)"
            echo "  -h, --help                    Show this help message"
            echo ""
            echo "Examples:"
            echo "  # 测试多个指定文件"
            echo "  $0 --data-path file1.parquet --data-path file2.parquet --num-samples 20"
            echo ""
            echo "  # 测试目录下所有 parquet 文件"
            echo "  $0 --data-dir /path/to/dataset/ --num-samples-per-file 10"
            echo ""
            echo "  # 每个文件固定数量样本"
            echo "  $0 --data-path file1.parquet --data-path file2.parquet --num-samples-per-file 5"
            echo ""
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# 如果没有指定文件，使用默认文件
if [ ${#DATA_PATHS[@]} -eq 0 ]; then
    DATA_PATHS=("/app/xiaominl/datasets/air_sp11np_up3_sample1_nosw/shard-test-000000.parquet")
    echo "No data path specified, using default: ${DATA_PATHS[0]}"
fi

# 打印配置
echo "========================================"
echo "Baseline Restoration Test Configuration"
echo "========================================"
echo "Number of Files:    ${#DATA_PATHS[@]}"
echo "Files:"
for path in "${DATA_PATHS[@]}"; do
    echo "  - $path"
done
if [ -n "$NUM_SAMPLES_PER_FILE" ]; then
    echo "Samples per File:   $NUM_SAMPLES_PER_FILE"
    echo "Total Samples:      $((${#DATA_PATHS[@]} * NUM_SAMPLES_PER_FILE))"
else
    echo "Total Samples:      $NUM_SAMPLES"
fi
echo "Strategy:           $STRATEGY"
echo "Save Images:        $SAVE_IMAGES"
echo "Tool Service IP:    $TOOL_SERVICE_IP"
echo "========================================"
echo ""

# 计算每个文件的样本数
if [ -n "$NUM_SAMPLES_PER_FILE" ]; then
    # 如果指定了每个文件的样本数，使用该值
    SAMPLES_PER_FILE=$NUM_SAMPLES_PER_FILE
else
    # 否则，平均分配总样本数到各个文件
    SAMPLES_PER_FILE=$((NUM_SAMPLES / ${#DATA_PATHS[@]}))
    if [ $SAMPLES_PER_FILE -eq 0 ]; then
        SAMPLES_PER_FILE=1
    fi
fi

echo "Samples per file: $SAMPLES_PER_FILE"
echo ""

# 遍历所有文件并运行测试
FILE_NUM=1
for DATA_PATH in "${DATA_PATHS[@]}"; do
    echo ""
    echo "========================================"
    echo "Processing File $FILE_NUM/${#DATA_PATHS[@]}"
    echo "========================================"
    echo "File: $DATA_PATH"
    echo ""
    
    # 检查文件是否存在
    if [ ! -f "$DATA_PATH" ]; then
        echo "Warning: File not found: $DATA_PATH"
        echo "Skipping..."
        FILE_NUM=$((FILE_NUM + 1))
        continue
    fi
    
    # 构建命令
    CMD="python3 /app/xiaominl/DeepEyes_v2/tests/baseline/test_baseline_restoration.py \
        --data-path $DATA_PATH \
        --num-samples $SAMPLES_PER_FILE \
        --strategy $STRATEGY"
    
    if [ "$SAVE_IMAGES" = "true" ]; then
        CMD="$CMD --save-images"
    fi
    
    # 运行测试
    echo "Command: $CMD"
    echo ""
    
    if $CMD; then
        echo ""
        echo "✓ File $FILE_NUM completed successfully"
    else
        echo ""
        echo "✗ File $FILE_NUM failed"
        exit 1
    fi
    
    FILE_NUM=$((FILE_NUM + 1))
done

echo ""
echo "========================================"
echo "All Tests Completed!"
echo "========================================"
echo "Processed ${#DATA_PATHS[@]} files"
echo "Results are saved in: /app/xiaominl/DeepEyes_v2/tests/baseline/results/"
echo ""

