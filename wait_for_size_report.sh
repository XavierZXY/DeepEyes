#!/bin/bash
# 等待并显示尺寸异常报告

LOG_FILE="logs/debug_for_AIR_multideg_plan_ref_bs32_n8_spv13_lr1e-6_datarand_mi300.log"

echo "========================================================================"
echo "等待尺寸异常报告（新batch完成后会显示）"
echo "========================================================================"
echo ""
echo "监控中... (Ctrl+C 退出)"
echo ""

# 记录当前日志大小
LAST_SIZE=$(wc -c < "$LOG_FILE" 2>/dev/null || echo "0")

while true; do
    sleep 5
    
    CURRENT_SIZE=$(wc -c < "$LOG_FILE" 2>/dev/null || echo "0")
    
    if [ "$CURRENT_SIZE" -gt "$LAST_SIZE" ]; then
        # 日志有更新，检查是否有尺寸报告
        tail -100 "$LOG_FILE" | grep -q "发现.*工具改变尺寸\|所有工具都保持"
        if [ $? -eq 0 ]; then
            echo ""
            echo "========================================================================"
            echo "✓ 发现尺寸报告！"
            echo "========================================================================"
            tail -200 "$LOG_FILE" | grep -A100 "发现.*工具改变尺寸\|所有工具都保持" | head -150
            break
        fi
        
        LAST_SIZE=$CURRENT_SIZE
    fi
done

echo ""
echo "========================================================================"
echo "监控结束"
echo "========================================================================"

