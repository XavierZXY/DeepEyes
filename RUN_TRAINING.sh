#!/bin/bash
# 快速运行训练并验证wandb功能

echo "🚀 启动训练..."
echo ""

# 运行训练
bash examples/agent/IR.sh 2>&1 | tee logs/wandb_test_$(date +%Y%m%d_%H%M%S).log &

TRAIN_PID=$!
echo "训练进程PID: $TRAIN_PID"
echo ""
echo "等待3分钟让训练运行..."
sleep 180

echo ""
echo "📊 验证wandb上传..."
echo "================================"

# 检查日志
LATEST_LOG=$(ls -t logs/wandb_test_*.log 2>/dev/null | head -1)
if [ -n "$LATEST_LOG" ]; then
    echo "✓ 日志文件: $LATEST_LOG"
    
    echo ""
    echo "1. 检查数据收集:"
    grep "Added image_history_list" "$LATEST_LOG" | tail -3
    
    echo ""
    echo "2. 检查wandb上传:"
    grep "Successfully logged" "$LATEST_LOG" | tail -5
    
    echo ""
    echo "3. 检查对话表格:"
    grep "conversation_details" "$LATEST_LOG" | tail -3
fi

echo ""
echo "4. 检查wandb文件:"
LATEST_RUN=$(ls -td wandb/run-* 2>/dev/null | head -1)
if [ -n "$LATEST_RUN" ]; then
    echo "✓ 最新run: $LATEST_RUN"
    
    if [ -d "$LATEST_RUN/files/media/images/train" ]; then
        TRAIN_COUNT=$(find "$LATEST_RUN/files/media/images/train" -name "*.png" 2>/dev/null | wc -l)
        echo "  ✓ train目录: $TRAIN_COUNT 张图像"
    else
        echo "  ⚠️  train目录还未生成（训练刚开始）"
    fi
    
    if [ -d "$LATEST_RUN/files/media/images/val" ]; then
        VAL_COUNT=$(find "$LATEST_RUN/files/media/images/val" -name "*.png" 2>/dev/null | wc -l)
        echo "  ✓ val目录: $VAL_COUNT 张图像"
    fi
fi

echo ""
echo "================================"
echo "训练仍在运行中..."
echo "完整验证请运行: ./verify_fixes.sh"
echo ""
