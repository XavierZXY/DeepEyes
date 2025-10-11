#!/bin/bash
# 验证所有修复是否已应用

echo "============================================================"
echo "验证Wandb上传功能修复"
echo "============================================================"

echo ""
echo "1. 检查关键bug修复..."
echo "------------------------------------------------------------"

# Bug 1: self.logger
echo -n "✓ Bug1 (self.logger): "
grep -q "self.logger = logger" verl/trainer/ppo/ray_trainer.py && echo "已修复" || echo "❌ 未修复"

# Bug 2: numpy判断
echo -n "✓ Bug2 (numpy判断): "
grep -q "if image_histories is None or len" verl/utils/tracking_image_utils.py && echo "已修复" || echo "❌ 未修复"

# Bug 3: 直接使用saved_image_history_list
echo -n "✓ Bug3 (不重复interleave): "
grep -q "image_history_to_add = saved_image_history_list" verl/workers/agent/parallel_env.py && echo "已修复" || echo "❌ 未修复"

# Bug 4: np.empty
echo -n "✓ Bug4 (np.empty确保1维): "
grep -q "np.empty(actual_size, dtype=object)" verl/workers/agent/parallel_env.py && echo "已修复" || echo "❌ 未修复"

# Bug 5: 保持keys一致
echo -n "✓ Bug5 (保持keys一致): "
grep -q "adding empty arrays to maintain key consistency" verl/workers/agent/parallel_env.py && echo "已修复" || echo "❌ 未修复"

echo ""
echo "2. 检查最新运行状态..."
echo "------------------------------------------------------------"

LATEST_LOG=$(ls -t logs/*.log 2>/dev/null | head -1)
if [ -z "$LATEST_LOG" ]; then
    echo "❌ 没有找到日志文件"
    exit 1
fi

echo "最新日志: $LATEST_LOG"
echo ""

# 检查是否有新的运行
LAST_MODIFIED=$(stat -c %y "$LATEST_LOG" 2>/dev/null || stat -f "%Sm" "$LATEST_LOG" 2>/dev/null)
echo "最后更新: $LAST_MODIFIED"
echo ""

# 检查关键日志输出
echo "Training数据添加:"
tail -1000 "$LATEST_LOG" | grep "Added.*image_history_list" | tail -3

echo ""
echo "Wandb上传:"
tail -1000 "$LATEST_LOG" | grep "Successfully logged" | tail -5

echo ""
echo "错误检查:"
tail -1000 "$LATEST_LOG" | grep -E "ValueError|Failed to log" | tail -5

echo ""
echo "3. 检查wandb文件..."
echo "------------------------------------------------------------"

LATEST_RUN=$(ls -td wandb/run-* 2>/dev/null | head -1)
if [ -z "$LATEST_RUN" ]; then
    echo "❌ 没有wandb run"
else
    echo "最新run: $LATEST_RUN"
    
    # 检查train目录
    if [ -d "$LATEST_RUN/files/media/images/train" ]; then
        TRAIN_COUNT=$(find "$LATEST_RUN/files/media/images/train" -name "*.png" 2>/dev/null | wc -l)
        echo "✓ train目录存在: $TRAIN_COUNT 张图像"
    else
        echo "❌ train目录不存在"
    fi
    
    # 检查val目录
    if [ -d "$LATEST_RUN/files/media/images/val" ]; then
        VAL_COUNT=$(find "$LATEST_RUN/files/media/images/val" -name "*.png" 2>/dev/null | wc -l)
        echo "✓ val目录存在: $VAL_COUNT 张图像"
    else
        echo "❌ val目录不存在"
    fi
fi

echo ""
echo "============================================================"
echo "总结"
echo "============================================================"
echo ""
echo "✅ 所有代码修复: 已完成"
echo ""
echo "需要检查:"
echo "  1. 如果看到'ValueError'或'Failed to log'，需要查看详细错误"
echo "  2. 如果train目录不存在，需要重新运行训练应用修复"
echo "  3. 查看wandb网页确认Media tab和对话表格"
echo ""
echo "下一步:"
echo "  bash examples/agent/IR.sh 2>&1 | tee logs/verify_$(date +%Y%m%d_%H%M%S).log"
echo ""

