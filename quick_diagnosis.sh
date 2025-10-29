#!/bin/bash
# 快速诊断工具调用问题

echo "================================================================================"
echo "快速诊断：工具调用检查"
echo "================================================================================"

echo ""
echo "=== 1. 检查工具注册 ==="
echo "--------------------------------------------------------------------------------"
python debug_tool_registration.py 2>/dev/null | tail -25

echo ""
echo "=== 2. 检查模型是否输出tool_call ==="
echo "--------------------------------------------------------------------------------"
echo "最近5个工具解析结果:"
grep "工具解析:" logs/*.log 2>/dev/null | tail -5 || echo "⚠️  没有找到日志文件"

echo ""
echo "=== 3. 检查工具创建 ==="
echo "--------------------------------------------------------------------------------"
grep "DEBUG CREATE_TOOLS.*tool_calls数量" logs/*.log 2>/dev/null | head -5 || echo "⚠️  没有找到工具创建日志"

echo ""
echo "=== 4. 检查工具执行 ==="
echo "--------------------------------------------------------------------------------"
SUCCESS_COUNT=$(grep "工具链执行完成" logs/*.log 2>/dev/null | wc -l)
echo "✅ 成功执行的工具链数量: $SUCCESS_COUNT"

FAIL_COUNT=$(grep "所有工具执行失败" logs/*.log 2>/dev/null | wc -l)
echo "❌ 失败的工具链数量: $FAIL_COUNT"

echo ""
echo "最近3个成功执行的工具链:"
grep "工具链执行完成" logs/*.log 2>/dev/null | tail -3 || echo "⚠️  没有找到成功执行的工具链"

echo ""
echo "=== 5. 检查工具调用统计 ==="
echo "--------------------------------------------------------------------------------"
COUNTED=$(grep "DEBUG TOOL CNT.*✅" logs/*.log 2>/dev/null | wc -l)
echo "✅ 统计计数的工具链: $COUNTED"

NOT_COUNTED=$(grep "DEBUG TOOL CNT.*❌" logs/*.log 2>/dev/null | wc -l)  
echo "❌ 未计数的工具链: $NOT_COUNTED"

echo ""
echo "=== 6. 检查错误 ==="
echo "--------------------------------------------------------------------------------"
echo "工具未找到的错误:"
grep "ERROR TOOL.*未在注册表中找到" logs/*.log 2>/dev/null | head -3 || echo "✅ 没有工具未找到的错误"

echo ""
echo "格式错误:"
grep "ERROR TOOL.*格式错误" logs/*.log 2>/dev/null | head -3 || echo "✅ 没有格式错误"

echo ""
echo "================================================================================"
echo "诊断完成"
echo "================================================================================"

echo ""
echo "💡 建议:"
if [ "$SUCCESS_COUNT" -eq 0 ]; then
    echo "  ⚠️  没有成功执行的工具链！"
    echo "  请检查:"
    echo "    1. 模型是否输出了<tool_call>"
    echo "    2. 工具创建是否成功"
    echo "    3. 工具服务是否运行 (TOOL_SERVICE_IP=$TOOL_SERVICE_IP)"
elif [ "$NOT_COUNTED" -gt "$COUNTED" ]; then
    echo "  ⚠️  失败的工具链多于成功的！"
    echo "  请查看具体错误: grep 'ERROR.*工具' logs/*.log"
else
    echo "  ✅ 工具调用看起来正常"
    echo "  成功率: $((COUNTED * 100 / (COUNTED + NOT_COUNTED)))%"
fi

echo ""
echo "详细诊断指南: cat DEBUG_NO_TOOL_CALLS.md"

