# Agent对话模式切换指南

## 📋 概述

DeepEyes支持两种Agent对话训练模式，可以通过环境变量 `AGENT_CONVERSATION_MODE` 切换：

### 模式A: 多工具链式规划 (`multi_tool_planning`)
- **特点**: 模型一次输出多个工具，系统链式执行完整序列
- **适用**: 策略规划型训练，探索不同工具组合和顺序
- **优势**: 更强的策略探索能力，避免累积误差（每次从原图开始）
- **当前状态**: ✅ 已完全实现

### 模式B: 单工具迭代 (`single_tool_iterative`) 
- **特点**: 模型每次只输出一个工具，基于当前结果逐步处理
- **适用**: 逐步反应型训练，基于当前状态做决策
- **优势**: 更细粒度的反馈，更符合人类逐步处理的直觉
- **当前状态**: 🚧 部分实现（需要完整的状态管理）

---

## 🎯 模式对比

| 维度 | 多工具链式规划 | 单工具迭代 |
|-----|-------------|-----------|
| **每次预测** | 多个工具列表 | 单个工具 |
| **执行方式** | 链式执行整个序列 | 逐步执行 |
| **图像传递** | 每次从原图开始 | 逐步传递处理结果 |
| **max_turns** | 1-4（多次规划） | 3-8（需要多步） |
| **格式检查** | 允许多个tool_call | 强制单个tool_call |
| **灵活性** | 可任意重新规划 | 基于当前状态决策 |

---

## 🔧 配置方法

### 方式1: 在训练脚本中设置（推荐）

**模式A - 多工具链式规划** (当前默认)

```bash
# 在 IRv2.sh 或 IR.sh 中
export AGENT_CONVERSATION_MODE="multi_tool_planning"

# 配套设置
actor_rollout_ref.rollout.agent.max_turns=1  # 单轮，或2-4允许重新规划
actor_rollout_ref.rollout.agent.single_response_max_tokens=10240
export USE_SINGLE_TURN_FORMAT=True  # 如果max_turns=1
export USE_ENHANCED_FORMAT=True     # 如果max_turns>1
```

**模式B - 单工具迭代** (实验性)

```bash
# 在 IRv2.sh 或 IR.sh 中
export AGENT_CONVERSATION_MODE="single_tool_iterative"

# 配套设置
actor_rollout_ref.rollout.agent.max_turns=6  # 需要多轮处理
actor_rollout_ref.rollout.agent.single_response_max_tokens=4096
export USE_SINGLE_TURN_FORMAT=False
export USE_ENHANCED_FORMAT=False  # 使用标准多轮格式
```

### 方式2: 环境变量

```bash
export AGENT_CONVERSATION_MODE="multi_tool_planning"  # 或 "single_tool_iterative"
bash examples/agent/IRv2.sh
```

---

## 📝 模式A: 多工具链式规划（当前使用）

### System Prompt示例

```
You are an image restoration strategy planning expert.
Your task:
1. Analyze degraded image
2. Propose COMPLETE tool sequence
3. System executes entire sequence
4. Evaluate result, propose new sequence if needed
```

### 对话示例

**Turn 1**
```
User: Image with [rain, dark, noise]

Model:
<think>
Plan A: rain → dark → noise
</think>
<tool_call>
[
    {"name": "restormer_deraining", "degradation": "rain", "arguments": {}},
    {"name": "retinexformer_sdsd_indoor", "degradation": "dark", "arguments": {}},
    {"name": "scunet_real_denoising_gan", "degradation": "noise", "arguments": {}}
]
</tool_call>
```

**系统**: 执行 `原图 → 去雨 → 提亮 → 去噪 → 结果A`

**Turn 2** (如果模型不满意结果A)
```
Model:
<think>
Plan B: dark → rain → noise (调整顺序)
</think>
<tool_call>
[
    {"name": "retinexformer_sdsd_indoor", "degradation": "dark", "arguments": {}},
    {"name": "restormer_deraining", "degradation": "rain", "arguments": {}},
    {"name": "scunet_real_denoising_gan", "degradation": "noise", "arguments": {}}
]
</tool_call>
```

**系统**: 执行 `原图 → 提亮 → 去雨 → 去噪 → 结果B` ← 重新从原图开始

**Turn 3** (满意结果B)
```
Model:
<think>Result B is excellent.</think>
<answer>
{
    "restoration_log": ["dark", "rain", "noise"]
}
</answer>
```

### 数据集格式

System prompt 使用 `ConversationModePrompts.MULTI_TOOL_PLANNING_SYSTEM`

User prompt:
- 首轮: `Image analysis indicates these degradation types: {degradations}`
- 反馈: `Here is the result image after executing your previous restoration plan`

---

## 📝 模式B: 单工具迭代（实验性）

### System Prompt示例

```
You are an image restoration expert working step-by-step.
Your task:
1. Analyze current image
2. Select ONE tool to apply
3. System executes tool, shows result
4. Continue until complete
```

### 对话示例

**Turn 1**
```
User: Image with [rain, dark, noise]

Model:
<think>
Rain is most urgent. Remove it first.
</think>
<tool_call>
[
    {"name": "restormer_deraining", "degradation": "rain", "arguments": {}}
]
</tool_call>
```

**系统**: 执行 `当前图（原图）→ 去雨 → 结果1`

**Turn 2**
```
User: Processed: [rain]. Remaining: [dark, noise]
Result image: <image>

Model:
<think>
Rain removed. Now address darkness.
</think>
<tool_call>
[
    {"name": "retinexformer_sdsd_indoor", "degradation": "dark", "arguments": {}}
]
</tool_call>
```

**系统**: 执行 `当前图（结果1）→ 提亮 → 结果2` ← 基于上一轮结果

**Turn 3**
```
User: Processed: [rain, dark]. Remaining: [noise]
Result image: <image>

Model:
<think>
Final degradation: noise.
</think>
<tool_call>
[
    {"name": "scunet_real_denoising_gan", "degradation": "noise", "arguments": {}}
]
</tool_call>
```

**系统**: 执行 `当前图（结果2）→ 去噪 → 结果3`

**Turn 4**
```
User: Processed: [rain, dark, noise]. All complete.
Result image: <image>

Model:
<think>All degradations addressed.</think>
<answer>
{
    "restoration_log": ["rain", "dark", "noise"]
}
</answer>
```

### 数据集格式

System prompt 使用 `ConversationModePrompts.SINGLE_TOOL_ITERATIVE_SYSTEM`

User prompt:
- 首轮: `Image analysis indicates these degradation types: {degradations}`
- 反馈: `Processed: {processed}. Remaining: {remaining}. <image>`

---

## 🚧 实现状态

### ✅ 已完成
- [x] 环境变量配置（AGENT_CONVERSATION_MODE）
- [x] 两种模式的 System Prompt 模板
- [x] parallel_env.py 中的模式检测
- [x] 单工具迭代模式的工具数量限制（只取第一个）
- [x] IRv2.sh 中的配置说明

### 🚧 待完成（单工具迭代模式）
- [ ] ParallelEnv 状态管理
  - [ ] 添加 `current_multi_modal_data_list` 跟踪每个样本的当前图像
  - [ ] 在 step() 中根据模式选择使用原图/当前图
  - [ ] 工具执行后更新当前图像状态
- [ ] 格式检查适配
  - [ ] 单工具迭代模式强制只允许1个tool_call
  - [ ] 修改格式奖励函数
- [ ] 数据集生成
  - [ ] 创建单工具迭代模式的数据生成脚本
  - [ ] 生成带有逐步反馈的训练数据
- [ ] User Prompt 动态生成
  - [ ] 根据模式选择不同的反馈prompt
  - [ ] 跟踪已处理/剩余降质类型
- [ ] 文档和测试
  - [ ] 单工具迭代模式的完整测试
  - [ ] 两种模式的性能对比

---

## 💡 使用建议

### 何时使用多工具链式规划？

✅ **适合场景**:
- 探索不同工具组合的效果
- 学习全局最优策略
- 降质数量较少（2-4个）
- 训练数据充足

❌ **不适合场景**:
- 降质数量过多（>5个）
- 需要细粒度反馈
- 计算资源有限（链式执行消耗更多）

### 何时使用单工具迭代？

✅ **适合场景**:
- 降质数量较多（>4个）
- 需要基于中间结果做决策
- 模拟人类逐步处理流程
- 更容易调试和理解

❌ **不适合场景**:
- 需要探索不同顺序的效果
- 训练样本有限
- 需要快速收敛

---

## 🔍 调试技巧

### 查看当前模式
```bash
grep "AGENT MODE" logs/*.log
# 输出: [AGENT MODE] Using conversation mode: multi_tool_planning
```

### 查看工具创建日志
```bash
grep "DEBUG CREATE_TOOLS" logs/*.log | grep "模式"
# 输出: [DEBUG CREATE_TOOLS] T1-样本0 开始创建工具 (模式: multi_tool_planning)
```

### 单工具迭代模式检测
```bash
grep "ITERATIVE MODE" logs/*.log
# 输出: [ITERATIVE MODE] T1-样本0 检测到3个工具，单工具迭代模式只使用第一个
```

---

## 📚 相关文件

### Prompt 模板
- `verl/workers/agent/envs/mm_process_engine/ConversationModePrompts.py`
  - MULTI_TOOL_PLANNING_SYSTEM
  - SINGLE_TOOL_ITERATIVE_SYSTEM

### 核心逻辑
- `verl/workers/agent/parallel_env.py`
  - AGENT_CONVERSATION_MODE 变量
  - `_create_tools_from_parsed_output()` - 工具创建
  - `agent_rollout_loop()` - 主循环
  - `ParallelEnv.step()` - 环境交互

### 配置脚本
- `examples/agent/IRv2.sh` - 配置和说明
- `examples/agent/IR.sh` - 配置和说明

### 格式检查
- `verl/utils/reward_score/image_restoration.py`
  - `check_single_turn_format()`
  - `check_multiturn_format_v2()`

---

## 🎓 进阶：完整实现单工具迭代模式

如果需要完整实现单工具迭代模式，需要修改以下内容：

### 1. ParallelEnv 状态管理

```python
# 在 ParallelEnv.__init__ 中添加
self.current_multi_modal_data_list = []  # 当前图像状态

# 在 ParallelEnv.reset 中初始化
self.current_multi_modal_data_list = deepcopy(self.origin_multi_modal_data_list)

# 在 ParallelEnv.step 中使用
if AGENT_CONVERSATION_MODE == 'single_tool_iterative':
    multi_modal_data = self.current_multi_modal_data_list[idx]
else:
    multi_modal_data = self.origin_multi_modal_data_list[idx]

# 工具执行后更新
if AGENT_CONVERSATION_MODE == 'single_tool_iterative' and tool_executed_successfully:
    self.current_multi_modal_data_list[idx] = result_image_data
```

### 2. execute_tool_call 逻辑修改

```python
# Line 1078 附近
if AGENT_CONVERSATION_MODE == 'single_tool_iterative':
    # 使用当前图像数据（不是原图）
    current_image_data = multi_modal_data  # 传入的当前状态
else:
    # 使用原图
    current_image_data = origin_multi_modal_data
```

### 3. 数据集生成

创建 `generate_iterative_dataset.py`:
```python
# 生成单工具迭代格式的训练数据
# - Turn 1: 原图 + 所有降质
# - Turn 2-N: 当前图 + 已处理/剩余降质
# - Final Turn: answer
```

---

## ❓ FAQ

### Q1: 如何快速切换模式？

修改训练脚本中的一行：
```bash
export AGENT_CONVERSATION_MODE="single_tool_iterative"
```

### Q2: 两种模式可以混合训练吗？

不建议。两种模式的数据格式、System Prompt、期望行为都不同，混合训练会让模型confused。

### Q3: 单工具迭代模式为什么还没完全实现？

因为需要：
1. 复杂的状态管理（跟踪每个样本的当前图像）
2. 动态生成反馈prompt（已处理/剩余降质）
3. 数据集重新生成
4. 充分测试

目前多工具链式规划模式已经工作良好，优先使用它。

### Q4: 如何验证模式是否生效？

查看日志：
```bash
# 应该看到
[AGENT MODE] Using conversation mode: multi_tool_planning
[DEBUG CREATE_TOOLS] ... (模式: multi_tool_planning)
```

---

## 📧 联系

如需帮助实现单工具迭代模式的完整功能，请提issue或联系开发者。

**当前推荐**: 使用多工具链式规划模式 (`multi_tool_planning`)，已经过充分测试和验证。

