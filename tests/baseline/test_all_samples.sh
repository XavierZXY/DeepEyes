#!/bin/bash
# 测试所有样本的脚本

set -e

echo "=========================================="
echo "测试所有样本"
echo "=========================================="
echo ""

# 设置环境变量
export TOOL_SERVICE_IP=${TOOL_SERVICE_IP:-"10.21.9.6"}
export PYTHONPATH=/app/xiaominl/DeepEyes_v2:$PYTHONPATH

# 数据集路径
DATA_PATH=${DATA_PATH:-"/app/xiaominl/datasets/air_sp11np_up3_sample1_nosw/shard-test-000000.parquet"}

# 获取总样本数
TOTAL_SAMPLES=$(python3 << 'EOF'
import pandas as pd
df = pd.read_parquet('/app/xiaominl/datasets/air_sp11np_up3_sample1_nosw/shard-test-000000.parquet')
print(len(df))
EOF
)

echo "数据集: $DATA_PATH"
echo "总样本数: $TOTAL_SAMPLES"
echo ""
echo "⚠️  注意: 测试所有样本可能需要较长时间"
echo "   估计时间: 约 $((TOTAL_SAMPLES * 30 / 60)) 分钟"
echo ""

# 询问确认
read -p "是否继续测试所有 $TOTAL_SAMPLES 个样本? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "已取消"
    exit 0
fi

echo ""
echo "开始测试..."
echo ""

# 运行测试
cd /app/xiaominl/DeepEyes_v2/tests/baseline

./run_baseline_test.sh \
    --data-path "$DATA_PATH" \
    --num-samples "$TOTAL_SAMPLES" \
    --strategy both

echo ""
echo "=========================================="
echo "所有样本测试完成！"
echo "=========================================="
echo ""
echo "查看结果:"
echo "  cat results/summary_*.txt"
echo "  cat results/detailed_stats_*.txt"
echo ""

