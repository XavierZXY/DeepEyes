# Agent Conversation Mode 使用指南

## 概述

DeepEyes_v2 支持两种对话模式，用于控制模型如何调用工具处理图像降质：

1. **multi_tool_planning（多工具链式规划模式）**
2. **single_tool_iterative（单工具迭代模式）**

## 模式详细说明

### 1. 多工具链式规划模式 (multi_tool_planning)

**工作原理：**
```
第1轮：
  模型输出：[tool1, tool2, tool3]
  执行流程：原图 → tool1 → tool2 → tool3 → 结果图
  
第2轮（如果需要）：
  模型输出：[tool4, tool5]
  执行流程：上一轮结果图 → tool4 → tool5 → 最终结果
```

**特点：**
- ✅ 模型一次性规划完整的工具序列
- ✅ 工具在同一轮内链式执行（tool1的输出自动传给tool2）
- ✅ 适合训练模型的全局规划能力
- ✅ 每轮可以输出多个工具
- ⚡ 执行效率高（一轮解决多个问题）

**推荐配置：**
```bash
export AGENT_CONVERSATION_MODE="multi_tool_planning"
actor_rollout_ref.rollout.agent.max_turns=1  # 通常1-4轮
```

**典型应用场景：**
- 一次性规划所有降质处理步骤
- 需要全局优化工具顺序的场景
- 训练模型的策略规划能力

---

### 2. 单工具迭代模式 (single_tool_iterative)

**工作原理：**
```
第1轮：
  模型输出：[tool1]  # 只能一个
  执行流程：原图 → tool1 → 中间结果1
  
第2轮：
  模型输出：[tool2]  # 只能一个
  执行流程：中间结果1 → tool2 → 中间结果2
  
第3轮：
  模型输出：[tool3]  # 只能一个
  执行流程：中间结果2 → tool3 → 最终结果
```

**特点：**
- ✅ 每轮只能输出一个工具（格式强制限制）
- ✅ 每轮看到上一轮的处理结果
- ✅ 适合训练模型的逐步反应能力
- ✅ 更符合人类逐步分析的思维模式
- ⏱️ 需要更多轮次才能完成处理

**推荐配置：**
```bash
export AGENT_CONVERSATION_MODE="single_tool_iterative"
actor_rollout_ref.rollout.agent.max_turns=5  # 通常3-8轮
```

**典型应用场景：**
- 逐步诊断和处理降质
- 需要根据中间结果调整策略的场景
- 训练模型的反馈响应能力

---

## 关键区别对比

| 维度 | multi_tool_planning | single_tool_iterative |
|------|---------------------|----------------------|
| **每轮工具数** | 可多个（无限制） | 只能一个（强制） |
| **图像传递** | 轮内链式（tool1→tool2） | 轮间传递（turn1→turn2） |
| **所需轮次** | 少（1-4轮） | 多（3-8轮） |
| **训练目标** | 全局规划能力 | 逐步反应能力 |
| **执行效率** | 高 | 中等 |
| **可解释性** | 一次性规划，难以调试 | 逐步执行，易于调试 |

---

## 配置方法

### 在 IRv2.sh 中配置

```bash
# 方式1：多工具链式规划（推荐用于策略型训练）
export AGENT_CONVERSATION_MODE="multi_tool_planning"
actor_rollout_ref.rollout.agent.max_turns=1

# 方式2：单工具迭代（推荐用于反应型训练）
export AGENT_CONVERSATION_MODE="single_tool_iterative"
actor_rollout_ref.rollout.agent.max_turns=5
```

### 验证配置是否生效

训练开始时，查看日志输出：
```
[AGENT MODE] 对话模式: multi_tool_planning
```
或
```
[AGENT MODE] 对话模式: single_tool_iterative
```

---

## 测试验证

### 1. 验证模式加载

运行训练脚本后，检查日志中是否出现：
```
[AGENT MODE] 对话模式: <your_mode>
```

### 2. 验证工具执行逻辑

**多工具模式**应该看到：
```
[DEBUG T1-样本0] 执行工具1/3: tool_name_1
[DEBUG T1-样本0] 链式传递: 工具1的输出 → 工具2的输入
[DEBUG T1-样本0] 执行工具2/3: tool_name_2
[DEBUG T1-样本0] 链式传递: 工具2的输出 → 工具3的输入
[DEBUG T1-样本0] 执行工具3/3: tool_name_3
```

**单工具模式**应该看到：
```
[DEBUG T1-样本0] 执行工具1/1: tool_name_1
[DEBUG T2-样本0] 执行工具1/1: tool_name_2
[DEBUG T3-样本0] 执行工具1/1: tool_name_3
```

如果在单工具模式下检测到多个工具，会看到警告：
```
[FORMAT ERROR T1-样本0] 单工具迭代模式下，每轮只能调用一个工具，但检测到3个工具调用
```

### 3. 验证图像传递

在多工具模式下，日志应显示工具间的图像传递：
```
[DEBUG T1-样本0] 链式传递: 工具1的输出 → 工具2的输入
```

---

## 常见问题 FAQ

### Q1: 如何选择合适的模式？

**A:** 取决于训练目标：
- 如果希望模型学会**一次性规划**所有步骤 → `multi_tool_planning`
- 如果希望模型学会**逐步分析**和调整 → `single_tool_iterative`

### Q2: max_turns 如何设置？

**A:** 根据模式调整：
- `multi_tool_planning`: 1-4轮（通常1轮就够）
- `single_tool_iterative`: 3-8轮（需要足够轮次处理所有降质）

### Q3: 两种模式的奖励计算有区别吗？

**A:** 没有区别。奖励计算逻辑相同，都基于：
- 格式奖励（format_score）
- 图像质量奖励（quality_score）
- 可选的退化类型奖励（degradation_type_score）

### Q4: 可以在训练过程中切换模式吗？

**A:** 不建议。两种模式训练的策略不同，中途切换会导致模型混淆。
建议：
1. 先用一种模式训练一个完整的模型
2. 如需对比，从头开始用另一种模式训练另一个模型

### Q5: 单工具模式下，如果模型输出多个工具会怎样？

**A:** 系统会自动截取第一个工具并给出警告：
```
[FORMAT ERROR] 单工具迭代模式下，每轮只能调用一个工具，但检测到3个工具调用
```
后续的工具会被忽略。

---

## 实现细节（开发者参考）

### 核心代码位置

1. **模式读取：** `parallel_env.py:291-296`
```python
conversation_mode = os.environ.get('AGENT_CONVERSATION_MODE', 'multi_tool_planning')
```

2. **模式传递：** `parallel_env.py:358`
```python
env = ParallelEnv(config.agent, tokenizer, processor, conversation_mode=conversation_mode)
```

3. **工具链式传递：** `parallel_env.py:950-966`
```python
if conversation_mode == 'multi_tool_planning' and i < len(tools) - 1:
    # 将工具i的输出传递给工具i+1
    next_tool.reset(multi_modal_data=deepcopy(final_tool_result['multi_modal_data']))
```

4. **单工具验证：** `parallel_env.py:1122-1126`
```python
if self.conversation_mode == 'single_tool_iterative' and len(parsed_output['tool_calls']) > 1:
    parsed_output['tool_calls'] = [parsed_output['tool_calls'][0]]
```

---

## 版本历史

- **v1.0** (2025-01-21): 初始版本，支持两种对话模式
- 新增多工具链式规划模式
- 新增单工具迭代模式
- 添加格式验证和自动修正

---

## 联系与反馈

如有问题或建议，请联系开发团队或提交 Issue。

