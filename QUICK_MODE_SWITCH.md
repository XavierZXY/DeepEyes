# 🚀 快速模式切换指南

## 当前状态

✅ **多工具链式规划模式** - 完全实现，推荐使用
🚧 **单工具迭代模式** - 基础框架已就绪，需要完整状态管理

---

## 方法1: 使用切换脚本（推荐）

```bash
# 切换到多工具链式规划模式
./switch_conversation_mode.sh multi

# 切换到单工具迭代模式（实验性）
./switch_conversation_mode.sh single
```

脚本会提示是否自动更新配置文件。

---

## 方法2: 手动修改 IRv2.sh

### 配置A: 多工具链式规划（当前默认）

```bash
# Line 53: 模式选择
export AGENT_CONVERSATION_MODE="multi_tool_planning"

# Line 79: 格式检查
export USE_SINGLE_TURN_FORMAT=True  # 单轮场景
# 或
export USE_SINGLE_TURN_FORMAT=False  # 多轮场景
export USE_ENHANCED_FORMAT=True      # 多轮场景

# Line 207-208: Rollout配置
actor_rollout_ref.rollout.agent.single_response_max_tokens=10240 \
actor_rollout_ref.rollout.agent.max_turns=1 \  # 或 2-4
```

**适用场景**: 
- ✅ 一次输出完整工具序列
- ✅ 策略规划型训练
- ✅ 当前稳定版本

---

### 配置B: 单工具迭代（实验性）

```bash
# Line 53: 模式选择
export AGENT_CONVERSATION_MODE="single_tool_iterative"

# Line 79: 格式检查
export USE_SINGLE_TURN_FORMAT=False
export USE_ENHANCED_FORMAT=False

# Line 207-208: Rollout配置
actor_rollout_ref.rollout.agent.single_response_max_tokens=4096 \
actor_rollout_ref.rollout.agent.max_turns=6 \  # 或 3-8
```

**适用场景**: 
- 🚧 每次输出单个工具
- 🚧 逐步反应型训练
- 🚧 需要完整实现

---

## 验证配置

启动训练后，检查日志：

```bash
# 查看模式
grep "AGENT MODE" logs/*.log
# 输出: [AGENT MODE] Using conversation mode: multi_tool_planning

# 查看工具创建
grep "DEBUG CREATE_TOOLS.*模式" logs/*.log
# 输出: [DEBUG CREATE_TOOLS] ... (模式: multi_tool_planning)

# 单工具模式检测
grep "ITERATIVE MODE" logs/*.log
# 输出: [ITERATIVE MODE] ... 单工具迭代模式只使用第一个
```

---

## 对比表

| 配置项 | 多工具链式 | 单工具迭代 |
|-------|----------|----------|
| MODE | `multi_tool_planning` | `single_tool_iterative` |
| max_turns | 1-4 | 3-8 |
| max_tokens | 10240 | 4096 |
| SINGLE_TURN | True (max_turns=1) | False |
| ENHANCED | False/True | False |
| 实现状态 | ✅ 完整 | 🚧 基础 |

---

## 完整示例

### 示例1: 单轮多工具规划

**IRv2.sh**:
```bash
export AGENT_CONVERSATION_MODE="multi_tool_planning"
export USE_SINGLE_TURN_FORMAT=True
export USE_ENHANCED_FORMAT=False

actor_rollout_ref.rollout.agent.max_turns=1 \
actor_rollout_ref.rollout.agent.single_response_max_tokens=10240 \
```

**效果**:
- Turn 1: 模型输出 `[tool1, tool2, tool3]` → 系统执行 → 结束
- 适合: 快速训练，明确策略

---

### 示例2: 多轮多工具规划

**IRv2.sh**:
```bash
export AGENT_CONVERSATION_MODE="multi_tool_planning"
export USE_SINGLE_TURN_FORMAT=False
export USE_ENHANCED_FORMAT=True

actor_rollout_ref.rollout.agent.max_turns=3 \
actor_rollout_ref.rollout.agent.single_response_max_tokens=10240 \
```

**效果**:
- Turn 1: 模型输出 `[tool1, tool2]` → 执行（从原图）
- Turn 2: 模型看结果，输出 `[tool3, tool4]` → 执行（从原图）
- Turn 3: 模型输出 `<answer>`
- 适合: 探索不同策略组合

---

### 示例3: 单工具迭代（实验性）

**IRv2.sh**:
```bash
export AGENT_CONVERSATION_MODE="single_tool_iterative"
export USE_SINGLE_TURN_FORMAT=False
export USE_ENHANCED_FORMAT=False

actor_rollout_ref.rollout.agent.max_turns=6 \
actor_rollout_ref.rollout.agent.single_response_max_tokens=4096 \
```

**效果**:
- Turn 1: 输出 `[tool1]` → 执行（从原图） → 结果1
- Turn 2: 输出 `[tool2]` → 执行（从结果1） → 结果2
- Turn 3: 输出 `[tool3]` → 执行（从结果2） → 结果3
- Turn 4: 输出 `<answer>`
- 适合: 逐步决策，细粒度反馈

⚠️ **注意**: 需要完整实现 `current_multi_modal_data_list` 状态管理

---

## 常见问题

### Q1: 两个模式可以同时用吗？
❌ 不行。一次训练只能用一种模式。数据格式和System Prompt不兼容。

### Q2: 如何切换回默认模式？
```bash
./switch_conversation_mode.sh multi
```
或手动设置：
```bash
export AGENT_CONVERSATION_MODE="multi_tool_planning"
```

### Q3: 单工具迭代模式为什么是实验性？
因为需要完整的状态管理代码（跟踪每个样本的当前图像）。

基础框架已经就绪：
- ✅ 环境变量读取
- ✅ 工具数量限制（只取第一个）
- ✅ System Prompt 模板
- 🚧 ParallelEnv 状态管理（待实现）
- 🚧 图像数据在turn间传递（待实现）

### Q4: 如何验证单工具模式生效？
查看日志：
```bash
grep "ITERATIVE MODE.*只使用第一个" logs/*.log
```
如果看到这个输出，说明模式检测生效。

---

## 更多信息

- 完整文档: `CONVERSATION_MODE_GUIDE.md`
- Prompt模板: `verl/workers/agent/envs/mm_process_engine/ConversationModePrompts.py`
- 核心代码: `verl/workers/agent/parallel_env.py`
- 配置脚本: `examples/agent/IRv2.sh`

---

## 推荐配置

🎯 **当前推荐**: 多工具链式规划模式（单轮）
```bash
export AGENT_CONVERSATION_MODE="multi_tool_planning"
export USE_SINGLE_TURN_FORMAT=True
max_turns=1
```

原因:
- ✅ 完全实现并测试
- ✅ 训练稳定高效
- ✅ 策略探索能力强
- ✅ 避免累积误差

