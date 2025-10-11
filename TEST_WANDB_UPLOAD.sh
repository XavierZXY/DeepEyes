#!/bin/bash
# 测试wandb图像上传功能的脚本

echo "======================================================================"
echo "测试Wandb图像上传功能"
echo "======================================================================"

LOG_FILE="logs/test_wandb_$(date +%Y%m%d_%H%M%S).log"

echo ""
echo "1. 检查修复是否已应用..."
echo "----------------------------------------------------------------------"

# 检查关键修复
echo -n "检查 self.logger = logger ... "
if grep -q "self.logger = logger" verl/trainer/ppo/ray_trainer.py; then
    echo "✓"
else
    echo "✗ 缺失！"
fi

echo -n "检查 interleaving逻辑 ... "
if grep -q "After interleaving: batch_size" verl/workers/agent/parallel_env.py; then
    echo "✓"
else
    echo "✗ 缺失！"
fi

echo -n "检查 original_images收集 ... "
if grep -q "saved_extra_info_list" verl/workers/agent/parallel_env.py; then
    echo "✓"
else
    echo "✗ 缺失！"
fi

echo -n "检查 conversation_history收集 ... "
if grep -q "saved_conversation_history" verl/workers/agent/parallel_env.py; then
    echo "✓"
else
    echo "✗ 缺失！"
fi

echo -n "检查 detailed_metrics传递 ... "
if grep -q "detailed_metrics" verl/trainer/ppo/ray_trainer.py; then
    echo "✓"
else
    echo "✗ 缺失！"
fi

echo ""
echo "2. 查看最新的训练日志..."
echo "----------------------------------------------------------------------"

# 找到最新的日志文件
LATEST_LOG=$(ls -t logs/*.log | head -1)
echo "最新日志: $LATEST_LOG"

# 检查关键输出
echo ""
echo "检查 IMAGE_HISTORY 调试输出:"
tail -500 "$LATEST_LOG" | grep "DEBUG IMAGE_HISTORY" | tail -10

echo ""
echo "检查 WANDB IMAGE 调试输出:"
tail -500 "$LATEST_LOG" | grep "DEBUG WANDB IMAGE" | tail -10

echo ""
echo "检查 original_images 收集:"
tail -500 "$LATEST_LOG" | grep "original_images" | tail -5

echo ""
echo "检查 conversation_history 收集:"
tail -500 "$LATEST_LOG" | grep "conversation_history" | tail -5

echo ""
echo "3. 检查wandb本地文件..."
echo "----------------------------------------------------------------------"

# 查找最新的run
LATEST_RUN=$(ls -td wandb/run-* 2>/dev/null | head -1)
if [ -z "$LATEST_RUN" ]; then
    echo "✗ 没有找到wandb run目录"
else
    echo "最新run: $LATEST_RUN"
    
    if [ -d "$LATEST_RUN/media/images" ]; then
        IMAGE_COUNT=$(ls "$LATEST_RUN/media/images"/*.png 2>/dev/null | wc -l)
        echo "✓ Media目录存在，包含 $IMAGE_COUNT 张图像"
        
        if [ $IMAGE_COUNT -gt 0 ]; then
            echo "  最新的5张图像:"
            ls -lth "$LATEST_RUN/media/images"/*.png | head -5 | awk '{print "  ", $9, "  ", $5}'
        fi
    else
        echo "✗ Media目录不存在"
    fi
fi

echo ""
echo "4. 总结..."
echo "----------------------------------------------------------------------"

# 统计关键指标
echo -n "image_history_list 添加成功次数: "
grep -c "✓ Added.*image_history_list" "$LATEST_LOG" 2>/dev/null || echo "0"

echo -n "original_images 添加成功次数: "
grep -c "✓ Added.*original_images" "$LATEST_LOG" 2>/dev/null || echo "0"

echo -n "conversation_history 添加成功次数: "
grep -c "✓ Added.*conversation_history" "$LATEST_LOG" 2>/dev/null || echo "0"

echo -n "Successfully logged 次数: "
grep -c "Successfully logged.*trajectories" "$LATEST_LOG" 2>/dev/null || echo "0"

echo ""
echo "======================================================================"
echo "测试完成！"
echo "======================================================================"
echo ""
echo "下一步："
echo "  1. 如果看到'✓ Added'相关消息，说明数据收集成功"
echo "  2. 如果看到'Successfully logged'，说明上传成功"
echo "  3. 如果Media目录有图像文件，说明本地保存成功"
echo "  4. 检查wandb网页是否有Media tab"
echo ""

