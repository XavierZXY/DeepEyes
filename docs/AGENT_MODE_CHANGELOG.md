# Agent Conversation Mode - 修改日志

## 版本信息
- **版本：** v2.0
- **日期：** 2025-01-21
- **功能：** 新增双模式对话系统

---

## 📝 修改摘要

实现了两种agent对话模式的切换，支持不同的工具调用策略：

1. **multi_tool_planning（多工具链式规划）**：一轮输出多个工具，链式执行
2. **single_tool_iterative（单工具迭代）**：每轮只输出一个工具，轮次间传递

---

## 🔧 代码修改清单

### 1. `/app/xiaominl/DeepEyes_v2/verl/workers/agent/parallel_env.py`

#### 修改 1.1: `agent_rollout_loop` 函数（第286-305行）
**新增功能：** 读取环境变量 `AGENT_CONVERSATION_MODE` 并验证

```python
import os

# 读取对话模式配置
conversation_mode = os.environ.get('AGENT_CONVERSATION_MODE', 'multi_tool_planning')
print(f"[AGENT MODE] 对话模式: {conversation_mode}")

if conversation_mode not in ['multi_tool_planning', 'single_tool_iterative']:
    print(f"[AGENT MODE WARNING] 未知模式 '{conversation_mode}'，使用默认模式 'multi_tool_planning'")
    conversation_mode = 'multi_tool_planning'
```

**影响：** 启动时会在日志中显示当前使用的模式

---

#### 修改 1.2: `ParallelEnv.__init__` 方法（第1029行）
**新增参数：** `conversation_mode`

```python
def __init__(self, env_config, tokenizer, processor, conversation_mode='multi_tool_planning', **kwargs):
    self.conversation_mode = conversation_mode  # 保存模式
```

**影响：** 环境类现在知道当前使用的模式

---

#### 修改 1.3: `execute_tool_call` 函数（第886行）
**新增参数和逻辑：** 支持多工具链式传递图像

```python
def execute_tool_call(sample, tokenizer=None, processor=None, pbar=None, conversation_mode='multi_tool_planning'):
    # ... 原有代码 ...
    
    # 【关键修改】多工具链式规划模式：将当前工具的输出图像传递给下一个工具
    if conversation_mode == 'multi_tool_planning' and i < len(tools) - 1:
        if final_tool_result and isinstance(final_tool_result, dict) and 'multi_modal_data' in final_tool_result:
            next_tool = tools[i + 1]
            if next_tool is not None:
                next_tool.reset(
                    raw_prompt=next_tool.raw_prompt if hasattr(next_tool, 'raw_prompt') else None,
                    multi_modal_data=deepcopy(final_tool_result['multi_modal_data']),
                    origin_multi_modal_data=next_tool.origin_multi_modal_data if hasattr(next_tool, 'origin_multi_modal_data') else None,
                )
                print(f'[DEBUG {turn_info}] 链式传递: 工具{i+1}的输出 → 工具{i+2}的输入')
```

**影响：** 
- 多工具模式：工具间自动传递图像
- 单工具模式：无影响（每轮只有一个工具）

---

#### 修改 1.4: `ParallelEnv.step` 方法（第1121-1126行）
**新增验证：** 单工具模式格式检查

```python
# 【单工具模式验证】确保每轮只调用一个工具
if self.conversation_mode == 'single_tool_iterative' and len(parsed_output['tool_calls']) > 1:
    print(f'[FORMAT ERROR {turn_info}] 单工具迭代模式下，每轮只能调用一个工具，但检测到{len(parsed_output['tool_calls'])}个工具调用')
    # 只使用第一个工具，其余忽略
    parsed_output['tool_calls'] = [parsed_output['tool_calls'][0]]
```

**影响：** 单工具模式下，如果模型违规输出多个工具，系统会自动修正并给出警告

---

#### 修改 1.5: 调用处更新（第1169和1187行）
**传递模式参数：** 将 `conversation_mode` 传递给工具执行函数

```python
# 单工作器模式
obs, reward, done, info = execute_tool_call(agi, self.tokenizer, self.processor, pbar=pbar, conversation_mode=self.conversation_mode)

# 多工作器模式
partial_tool_func = partial(execute_tool_call, tokenizer=self.tokenizer, processor=self.processor, pbar=pbar, conversation_mode=self.conversation_mode)
```

---

### 2. `/app/xiaominl/DeepEyes_v2/examples/agent/IRv2.sh`

#### 修改 2.1: 配置说明更新（第51-81行）
**扩展说明：** 添加详细的模式说明和图像传递逻辑

```bash
# ========== Agent Conversation Mode Configuration ==========
# 控制对话模式：多工具链式规划 vs 单工具迭代
export AGENT_CONVERSATION_MODE="multi_tool_planning"  # 可选: "multi_tool_planning" 或 "single_tool_iterative"
# 
# 【模式说明】
# 1. multi_tool_planning (多工具链式规划模式):
#    - 模型一次输出多个工具 [tool1, tool2, tool3]
#    - 系统链式执行: 原图 → tool1 → tool2 → tool3 → 结果
#    - 工具间自动传递图像（tool1的输出是tool2的输入）
#    ...
#
# 2. single_tool_iterative (单工具迭代模式):
#    - 模型每次只输出一个工具（格式强制限制）
#    - 每个工具接收上一轮工具处理后的图像
#    ...
```

#### 修改 2.2: 推荐配置更新（第142-165行）
**新增建议：** 不同模式的 max_turns 配置建议

```bash
# 【推荐配置】
# Mode: multi_tool_planning + max_turns=1
#   → AGENT_CONVERSATION_MODE=multi_tool_planning
#   → max_turns=1 (一轮完成，可以多个工具链式执行)
#
# Mode: single_tool_iterative + max_turns>1
#   → AGENT_CONVERSATION_MODE=single_tool_iterative
#   → max_turns=3-8 (每轮一个工具，需要足够轮次)
```

---

## 📚 新增文档

### 1. `/app/xiaominl/DeepEyes_v2/docs/AGENT_CONVERSATION_MODE_GUIDE.md`
**完整使用指南**，包含：
- 详细的模式说明
- 配置方法
- 测试验证步骤
- FAQ
- 实现细节

### 2. `/app/xiaominl/DeepEyes_v2/docs/AGENT_MODE_QUICK_REFERENCE.md`
**快速参考卡**，包含：
- 一键配置
- 对比表格
- 验证关键词
- 故障排查

---

## 🎯 使用方法

### 方法1：切换到多工具模式（现有默认）
```bash
# 在 IRv2.sh 中
export AGENT_CONVERSATION_MODE="multi_tool_planning"
actor_rollout_ref.rollout.agent.max_turns=1
```

### 方法2：切换到单工具模式（新增）
```bash
# 在 IRv2.sh 中
export AGENT_CONVERSATION_MODE="single_tool_iterative"
actor_rollout_ref.rollout.agent.max_turns=5
```

---

## ✅ 测试验证

### 验证步骤
1. 修改 `IRv2.sh` 中的 `AGENT_CONVERSATION_MODE`
2. 运行训练脚本
3. 检查日志输出：
   - 启动时应显示：`[AGENT MODE] 对话模式: <your_mode>`
   - 工具执行时应显示对应的模式行为

### 预期行为

**多工具模式：**
```
[DEBUG T1-样本0] 执行工具1/3: tool1
[DEBUG T1-样本0] 链式传递: 工具1的输出 → 工具2的输入
[DEBUG T1-样本0] 执行工具2/3: tool2
```

**单工具模式：**
```
[DEBUG T1-样本0] 执行工具1/1: tool1
[DEBUG T2-样本0] 执行工具1/1: tool2
[DEBUG T3-样本0] 执行工具1/1: tool3
```

---

## 🐛 已知问题和限制

### 限制1：不支持运行时切换
- **描述：** 训练开始后无法切换模式
- **原因：** 两种模式训练的策略不同
- **建议：** 每个模式单独训练一个完整的模型

### 限制2：单工具模式需要更多轮次
- **描述：** 需要设置足够的 max_turns
- **建议：** 根据平均降质数量设置（通常3-8轮）

---

## 🔄 向后兼容性

- ✅ **完全兼容**：如果不设置 `AGENT_CONVERSATION_MODE`，默认使用 `multi_tool_planning`
- ✅ **无破坏性更改**：现有代码和配置无需修改即可继续使用
- ✅ **可选功能**：新模式是可选的，不影响现有训练流程

---

## 📞 支持

如有问题，请查看：
1. 完整指南：`AGENT_CONVERSATION_MODE_GUIDE.md`
2. 快速参考：`AGENT_MODE_QUICK_REFERENCE.md`
3. 提交 Issue 或联系开发团队

---

## 🎉 总结

本次更新实现了灵活的双模式对话系统，让训练者可以根据需求选择：
- **全局规划能力**（multi_tool_planning）
- **逐步反应能力**（single_tool_iterative）

两种模式互补，可用于不同的训练目标和应用场景！

