#!/bin/bash

# ============================================================
# Agent对话模式切换脚本
# ============================================================
# 用法:
#   ./switch_conversation_mode.sh multi   # 切换到多工具链式规划模式
#   ./switch_conversation_mode.sh single  # 切换到单工具迭代模式
# ============================================================

MODE=$1

if [ -z "$MODE" ]; then
    echo "❌ 错误: 请指定模式"
    echo ""
    echo "用法:"
    echo "  $0 multi   # 多工具链式规划模式"
    echo "  $0 single  # 单工具迭代模式"
    echo ""
    exit 1
fi

case $MODE in
    multi|multi_tool_planning|planning)
        echo "🔄 切换到: 多工具链式规划模式"
        echo "============================================"
        AGENT_MODE="multi_tool_planning"
        MAX_TURNS=1
        MAX_TOKENS=10240
        USE_SINGLE_TURN="True"
        USE_ENHANCED="False"
        echo "配置:"
        echo "  - AGENT_CONVERSATION_MODE=$AGENT_MODE"
        echo "  - max_turns=$MAX_TURNS"
        echo "  - single_response_max_tokens=$MAX_TOKENS"
        echo "  - USE_SINGLE_TURN_FORMAT=$USE_SINGLE_TURN"
        echo "  - USE_ENHANCED_FORMAT=$USE_ENHANCED"
        echo ""
        echo "特点:"
        echo "  ✓ 模型一次输出多个工具"
        echo "  ✓ 系统链式执行完整序列"
        echo "  ✓ 每次从原图重新开始"
        echo "  ✓ 可探索不同工具组合"
        ;;
    single|single_tool_iterative|iterative)
        echo "🔄 切换到: 单工具迭代模式 (实验性)"
        echo "============================================"
        AGENT_MODE="single_tool_iterative"
        MAX_TURNS=6
        MAX_TOKENS=4096
        USE_SINGLE_TURN="False"
        USE_ENHANCED="False"
        echo "配置:"
        echo "  - AGENT_CONVERSATION_MODE=$AGENT_MODE"
        echo "  - max_turns=$MAX_TURNS"
        echo "  - single_response_max_tokens=$MAX_TOKENS"
        echo "  - USE_SINGLE_TURN_FORMAT=$USE_SINGLE_TURN"
        echo "  - USE_ENHANCED_FORMAT=$USE_ENHANCED"
        echo ""
        echo "特点:"
        echo "  ✓ 模型每次输出一个工具"
        echo "  ✓ 基于当前结果逐步处理"
        echo "  ✓ 图像逐步传递"
        echo "  ✓ 更细粒度的反馈"
        echo ""
        echo "⚠️  注意: 此模式需要完整实现，当前为实验性"
        ;;
    *)
        echo "❌ 错误: 未知模式 '$MODE'"
        echo ""
        echo "支持的模式:"
        echo "  multi   - 多工具链式规划模式"
        echo "  single  - 单工具迭代模式"
        echo ""
        exit 1
        ;;
esac

echo ""
echo "============================================"
echo "📝 下一步:"
echo ""
echo "1. 设置环境变量:"
echo "   export AGENT_CONVERSATION_MODE=\"$AGENT_MODE\""
echo ""
echo "2. 修改训练脚本 (examples/agent/IRv2.sh):"
echo "   - 第53行: export AGENT_CONVERSATION_MODE=\"$AGENT_MODE\""
echo "   - 第208行: max_turns=$MAX_TURNS"
echo "   - 第207行: single_response_max_tokens=$MAX_TOKENS"
echo "   - 第79行: USE_SINGLE_TURN_FORMAT=$USE_SINGLE_TURN"
echo ""
echo "3. 启动训练:"
echo "   bash examples/agent/IRv2.sh"
echo ""
echo "4. 验证模式:"
echo "   grep 'AGENT MODE' logs/*.log"
echo ""
echo "============================================"

# 可选: 自动更新 IRv2.sh
read -p "是否自动更新 IRv2.sh? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    SCRIPT_PATH="examples/agent/IRv2.sh"
    
    if [ ! -f "$SCRIPT_PATH" ]; then
        echo "❌ 错误: 找不到 $SCRIPT_PATH"
        exit 1
    fi
    
    # 备份原文件
    cp "$SCRIPT_PATH" "${SCRIPT_PATH}.backup.$(date +%Y%m%d_%H%M%S)"
    echo "✅ 已备份原文件"
    
    # 更新 AGENT_CONVERSATION_MODE
    sed -i "s/^export AGENT_CONVERSATION_MODE=.*/export AGENT_CONVERSATION_MODE=\"$AGENT_MODE\"  # 可选: \"multi_tool_planning\" 或 \"single_tool_iterative\"/" "$SCRIPT_PATH"
    echo "✅ 已更新 AGENT_CONVERSATION_MODE"
    
    # 更新 USE_SINGLE_TURN_FORMAT
    sed -i "s/^export USE_SINGLE_TURN_FORMAT=.*/export USE_SINGLE_TURN_FORMAT=$USE_SINGLE_TURN          # 是否使用单轮格式检查（默认False，单轮对话设为True）/" "$SCRIPT_PATH"
    echo "✅ 已更新 USE_SINGLE_TURN_FORMAT"
    
    echo ""
    echo "============================================"
    echo "✅ 配置更新完成!"
    echo ""
    echo "⚠️  注意: max_turns 和 single_response_max_tokens 需要手动修改"
    echo "   建议值:"
    echo "   - max_turns=$MAX_TURNS"
    echo "   - single_response_max_tokens=$MAX_TOKENS"
    echo ""
    echo "现在可以运行训练:"
    echo "   bash $SCRIPT_PATH"
    echo "============================================"
else
    echo ""
    echo "请手动更新配置文件。"
fi

