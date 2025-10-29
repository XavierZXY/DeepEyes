#!/bin/bash
# 一键诊断脚本

# 自动找到最新的日志文件
if [ -n "$1" ]; then
    LOG="$1"
else
    # 默认使用实验名称对应的日志
    LOG="logs/debug_for_AIR_multideg_plan_ref_bs32_n8_spv13_lr1e-6_datarand_mi300-.log"
    
    # 如果找不到，尝试找最新的
    if [ ! -f "$LOG" ]; then
        LOG=$(ls -t logs/*.log 2>/dev/null | grep -v "tool_call_tracker" | head -1)
    fi
fi

if [ ! -f "$LOG" ]; then
    echo "❌ 找不到日志文件！"
    echo "请指定日志文件: bash quick_check.sh <log_file>"
    exit 1
fi

echo "========================================================================"
echo "AIR V7 训练诊断报告"
echo "========================================================================"
echo "日志文件: $LOG"
echo "文件大小: $(ls -lh $LOG | awk '{print $5}')"
echo "最后修改: $(ls -l $LOG | awk '{print $6, $7, $8}')"
echo ""

echo "1. GT索引验证（前6个样本的GT和复原图尺寸）"
echo "========================================================================"
grep "DEBUG GT SIZE" $LOG 2>/dev/null | head -12 || echo "⚠️  暂无数据（等待batch完成）"
echo ""

echo "2. Interleave逻辑检查"
echo "========================================================================"
grep "needs_interleave\|orig_idx=" $LOG 2>/dev/null | head -5 || echo "⚠️  暂无数据"
echo ""

echo "3. 工具尺寸异常检测"
echo "========================================================================"
tail -200 $LOG 2>/dev/null | grep -A30 "所有工具都保持\|发现.*工具改变" | head -35 || echo "⚠️  暂无数据"
echo ""

echo "4. 工具链执行统计"
echo "========================================================================"
SUCCESS=$(grep "DEBUG TOOL CNT.*✅" $LOG 2>/dev/null | wc -l)
FAIL=$(grep "DEBUG TOOL CNT.*❌" $LOG 2>/dev/null | wc -l)
echo "  ✅ 成功执行的工具链: $SUCCESS"
echo "  ❌ 失败的工具链: $FAIL"
if [ $SUCCESS -gt 0 ]; then
    RATIO=$((SUCCESS * 100 / (SUCCESS + FAIL)))
    echo "  成功率: ${RATIO}%"
fi
echo ""

echo "5. fetch_image检查"
echo "========================================================================"
FETCH=$(grep "after fetch_image" $LOG 2>/dev/null | wc -l)
SAVE_PIL=$(grep "保存原始PIL" $LOG 2>/dev/null | wc -l)
echo "  after fetch_image: $FETCH (应该=0)"
echo "  保存原始PIL: $SAVE_PIL (应该>0)"

if [ $FETCH -eq 0 ] && [ $SAVE_PIL -gt 0 ]; then
    echo "  ✅ fetch_image已成功移除"
else
    echo "  ⚠️  可能还有fetch_image或未保存原始PIL"
fi
echo ""

echo "6. 尺寸匹配情况（最近20个）"
echo "========================================================================"
tail -500 $LOG 2>/dev/null | grep "尺寸不匹配: restored" | tail -10 || echo "⚠️  暂无数据"
echo ""

echo "========================================================================"
echo "诊断完成"
echo "========================================================================"
echo ""
echo "💡 如何判断GT索引是否正确？"
echo "  查看Sample 0-2的GT和复原图尺寸比例："
echo "  - 如果都是整数倍（2.0x, 4.0x）→ ✅ 索引正确"
echo "  - 如果宽高比例不一致（1.5x vs 2.1x）→ ❌ 可能索引错位"
echo ""
echo "详细文档: cat QUICK_DEBUG_GUIDE.md"

