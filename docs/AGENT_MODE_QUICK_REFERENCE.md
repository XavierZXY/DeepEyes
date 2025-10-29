# Agent Conversation Mode - 快速参考卡

## 🚀 快速配置

### 模式1：多工具链式规划 (推荐：一次性规划)

```bash
# 在 IRv2.sh 中设置
export AGENT_CONVERSATION_MODE="multi_tool_planning"

# 对应的 max_turns 设置
actor_rollout_ref.rollout.agent.max_turns=1  # 一轮完成
```

**执行示例：**
```
第1轮: [dehaze, deblur, denoise] → 原图 → 去雾 → 去模糊 → 去噪 → 结果
```

---

### 模式2：单工具迭代 (推荐：逐步分析)

```bash
# 在 IRv2.sh 中设置
export AGENT_CONVERSATION_MODE="single_tool_iterative"

# 对应的 max_turns 设置
actor_rollout_ref.rollout.agent.max_turns=5  # 多轮迭代
```

**执行示例：**
```
第1轮: [dehaze] → 原图 → 去雾 → 中间结果1
第2轮: [deblur] → 中间结果1 → 去模糊 → 中间结果2
第3轮: [denoise] → 中间结果2 → 去噪 → 最终结果
```

---

## 📊 一键对比

| 特性 | multi_tool_planning | single_tool_iterative |
|------|---------------------|----------------------|
| **图标** | 🔗 | 🔄 |
| **每轮工具数** | 多个 | 1个（强制） |
| **max_turns** | 1-4 | 3-8 |
| **图像流** | 轮内链式 | 轮间传递 |
| **训练目标** | 全局规划 | 逐步反应 |

---

## ✅ 验证日志关键词

### 启动时
```
[AGENT MODE] 对话模式: multi_tool_planning
```

### 多工具模式执行
```
[DEBUG] 执行工具1/3: dehaze
[DEBUG] 链式传递: 工具1的输出 → 工具2的输入
[DEBUG] 执行工具2/3: deblur
```

### 单工具模式执行
```
[DEBUG T1] 执行工具1/1: dehaze
[DEBUG T2] 执行工具1/1: deblur
[DEBUG T3] 执行工具1/1: denoise
```

### 单工具模式违规警告
```
[FORMAT ERROR] 单工具迭代模式下，每轮只能调用一个工具，但检测到3个工具调用
```

---

## 🎯 使用建议

### 什么时候用多工具模式？
- ✅ 想训练模型一次性规划完整方案
- ✅ 降质类型已知且固定
- ✅ 追求执行效率

### 什么时候用单工具模式？
- ✅ 想训练模型逐步分析能力
- ✅ 需要根据中间结果调整策略
- ✅ 更接近人类思考方式

---

## 📝 完整配置示例

### 多工具链式规划配置
```bash
export AGENT_CONVERSATION_MODE="multi_tool_planning"
export USE_SINGLE_TURN_FORMAT=True
export USE_ENHANCED_FORMAT=False

actor_rollout_ref.rollout.agent.max_turns=1
```

### 单工具迭代配置
```bash
export AGENT_CONVERSATION_MODE="single_tool_iterative"
export USE_SINGLE_TURN_FORMAT=False
export USE_ENHANCED_FORMAT=False

actor_rollout_ref.rollout.agent.max_turns=5
```

---

## 🔧 故障排查

### 问题1：日志没有显示模式
**解决：** 检查环境变量是否正确导出
```bash
echo $AGENT_CONVERSATION_MODE
```

### 问题2：单工具模式还是执行了多个工具
**解决：** 查看是否有格式错误警告，系统会自动只使用第一个工具

### 问题3：多工具模式的工具没有链式传递
**解决：** 检查日志中是否有 "链式传递" 关键词，如果没有可能是工具执行失败

---

## 📚 更多信息

详细文档请参考：`AGENT_CONVERSATION_MODE_GUIDE.md`

