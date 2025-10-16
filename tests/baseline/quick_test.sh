#!/bin/bash
# Quick test script - 快速验证baseline测试是否能正常运行
# 只测试1-2个样本来快速验证环境配置

set -e

echo "======================================"
echo "Quick Baseline Test"
echo "======================================"
echo ""
echo "This will test 2 samples with both strategies to verify the setup."
echo ""

# 设置环境变量
export TOOL_SERVICE_IP=${TOOL_SERVICE_IP:-"10.21.9.6"}
export PYTHONPATH=/app/xiaominl/DeepEyes_v2:$PYTHONPATH

# 运行快速测试
cd /app/xiaominl/DeepEyes_v2/tests/baseline

./run_baseline_test.sh \
    --num-samples 2 \
    --strategy both

echo ""
echo "======================================"
echo "Quick test completed!"
echo "If you see this message, the baseline test is working correctly."
echo "======================================"
echo ""
echo "To run a full test, use:"
echo "  ./run_baseline_test.sh --num-samples 10 --strategy both"

