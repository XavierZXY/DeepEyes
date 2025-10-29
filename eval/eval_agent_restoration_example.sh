#!/bin/bash
# Agent图像复原评估示例脚本

set -e  # 遇到错误立即退出

# ==================== 配置区域 ====================

# vLLM API配置
API_URL="http://localhost:8000/v1"
API_KEY="EMPTY"

# 数据路径
DATA_PATH="/app/xiaominl/air_full_v1/shard-test-000000.parquet"

# 输出目录
OUTPUT_BASE="./eval_results"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# 工具服务IP
TOOL_SERVICE_IP="10.21.9.6"

# 评估配置
NUM_SAMPLES=100  # 评估样本数，设为空则评估全部

# System Prompt配置
USE_PARQUET_PROMPT=true  # 是否使用parquet中的系统提示词
CUSTOM_PROMPT_FILE=""   # 自定义系统提示词文件路径（留空则不使用）

# ==================== 模式1: 多工具规划模式（使用parquet提示词） ====================
echo "=========================================="
echo "模式1: 多工具规划模式 (使用parquet中的系统提示词)"
echo "=========================================="

OUTPUT_DIR="${OUTPUT_BASE}/multi_tool_parquet_${TIMESTAMP}"

# 构建命令参数
CMD_ARGS="--api_url ${API_URL} \
    --api_key ${API_KEY} \
    --data_path ${DATA_PATH} \
    --output_dir ${OUTPUT_DIR} \
    --conversation_mode multi_tool_planning \
    --max_turns 1 \
    --temperature 0.7 \
    --top_p 0.9 \
    --tool_service_ip ${TOOL_SERVICE_IP} \
    --num_samples ${NUM_SAMPLES}"

# 如果不使用parquet提示词，添加标志
if [ "${USE_PARQUET_PROMPT}" != "true" ]; then
    CMD_ARGS="${CMD_ARGS} --no_parquet_system_prompt"
fi

# 如果有自定义提示词文件，添加参数
if [ -n "${CUSTOM_PROMPT_FILE}" ] && [ -f "${CUSTOM_PROMPT_FILE}" ]; then
    CMD_ARGS="${CMD_ARGS} --custom_system_prompt ${CUSTOM_PROMPT_FILE}"
    echo "使用自定义系统提示词: ${CUSTOM_PROMPT_FILE}"
fi

python eval/eval_agent_restoration.py ${CMD_ARGS}

echo ""
echo "✅ 多工具规划模式评估完成!"
echo "📊 结果保存在: ${OUTPUT_DIR}"
echo ""

# ==================== 模式2: 单工具迭代模式 ====================
echo "=========================================="
echo "模式2: 单工具迭代模式 (Single-Tool Iterative)"
echo "=========================================="

OUTPUT_DIR="${OUTPUT_BASE}/single_tool_${TIMESTAMP}"

python eval/eval_agent_restoration.py \
    --api_url ${API_URL} \
    --api_key ${API_KEY} \
    --data_path ${DATA_PATH} \
    --output_dir ${OUTPUT_DIR} \
    --conversation_mode single_tool_iterative \
    --max_turns 5 \
    --temperature 0.7 \
    --top_p 0.9 \
    --tool_service_ip ${TOOL_SERVICE_IP} \
    --num_samples ${NUM_SAMPLES}

echo ""
echo "✅ 单工具迭代模式评估完成!"
echo "📊 结果保存在: ${OUTPUT_DIR}"
echo ""

# ==================== 打印统计信息 ====================
echo "=========================================="
echo "📈 评估统计"
echo "=========================================="

for mode_dir in ${OUTPUT_BASE}/*_${TIMESTAMP}; do
    if [ -d "$mode_dir" ]; then
        echo ""
        echo "模式: $(basename $mode_dir)"
        echo "----------------------------------------"
        
        if [ -f "$mode_dir/summary.txt" ]; then
            cat "$mode_dir/summary.txt"
        fi
        
        echo ""
    fi
done

echo ""
echo "✅ 全部评估完成!"
echo ""
echo "📁 结果目录结构:"
echo "  ${OUTPUT_BASE}/"
echo "  ├── multi_tool_${TIMESTAMP}/"
echo "  │   ├── evaluation_results.csv"
echo "  │   ├── summary.txt"
echo "  │   ├── config.json"
echo "  │   ├── details/"
echo "  │   └── images/"
echo "  └── single_tool_${TIMESTAMP}/"
echo "      ├── evaluation_results.csv"
echo "      ├── summary.txt"
echo "      ├── config.json"
echo "      ├── details/"
echo "      └── images/"
echo ""

