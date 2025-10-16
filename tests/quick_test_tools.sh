#!/bin/bash
# 快速测试脚本 - 用于验证工具测试功能是否正常

set -e

echo "=================================="
echo "🚀 快速工具测试"
echo "=================================="

# 配置环境变量
export TOOL_SERVICE_IP=${TOOL_SERVICE_IP:-10.21.9.6}

echo "工具服务IP: $TOOL_SERVICE_IP"

# 默认数据路径
PARQUET_PATH=${1:-/app/xiaominl/datasets/air_d1_sp9_up2_bs128_n8_balanced/shard-test-000000.parquet}
OUTPUT_DIR=${2:-./quick_test_results}

echo "数据文件: $PARQUET_PATH"
echo "输出目录: $OUTPUT_DIR"

# 检查文件是否存在
if [ ! -f "$PARQUET_PATH" ]; then
    echo "❌ 错误: 数据文件不存在: $PARQUET_PATH"
    echo ""
    echo "用法: ./quick_test_tools.sh [parquet文件路径] [输出目录]"
    echo ""
    echo "示例:"
    echo "  ./quick_test_tools.sh /path/to/data.parquet ./results"
    exit 1
fi

echo ""
echo "=================================="
echo "📊 测试配置"
echo "=================================="
echo "- 样本数: 5 个（快速测试）"
echo "- 工具: 所有可用工具"
echo "- 保存图像: 是"
echo ""

# 运行测试
python3 tests/test_all_tools_metrics.py \
    --parquet "$PARQUET_PATH" \
    --output_dir "$OUTPUT_DIR" \
    --max_samples 5

echo ""
echo "=================================="
echo "✅ 测试完成！"
echo "=================================="
echo ""
echo "查看结果:"
echo "  详细结果: $OUTPUT_DIR/detailed_results.csv"
echo "  汇总报告: $OUTPUT_DIR/summary_report.txt"
echo "  图像文件: $OUTPUT_DIR/images/"
echo ""
echo "查看报告:"
echo "  cat $OUTPUT_DIR/summary_report.txt"
echo ""

