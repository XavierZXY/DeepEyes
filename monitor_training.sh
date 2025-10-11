#!/bin/bash
# 实时监控训练日志中的关键诊断信息

LOG_FILE="./logs/debug_for_TIR_IR_bs16_mi300.log"

echo "监控训练日志: $LOG_FILE"
echo "等待日志文件创建..."

# 等待日志文件创建
while [ ! -f "$LOG_FILE" ]; do
    sleep 1
done

echo "✅ 日志文件已创建，开始监控..."
echo ""
echo "==============================================="
echo "关键诊断信息"
echo "==============================================="
echo ""

# 实时监控关键信息
tail -f "$LOG_FILE" | grep --line-buffered -E '\[HOOK\]|\[DEBUG.*IMAGE\]|image_history|quality_score|total_score|图像历史|image_quality_reward'

