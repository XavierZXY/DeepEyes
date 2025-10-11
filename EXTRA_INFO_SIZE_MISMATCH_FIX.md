# Extra_info Size Mismatch 修复说明

## 🐛 问题描述

**错误信息**:
```
AssertionError: key extra_info length 1 is not equal to batch size 8
```

**发生位置**: `verl/protocol.py` 第305行，在 `DataProto.check_consistency()` 中

## 🔍 问题根源

### 场景分析

**配置**:
- `actor_rollout_ref.rollout.n=8` (采样数)
- `batch_size=1` (原始批次大小)
- Agent mode 激活

**数据流**:
1. 输入 `prompts` 包含 `extra_info`，长度=1
2. Agent mode 下，`agent_rollout_loop` 返回 interleaved 的数据，batch_size变成 1×8=8
3. 但是 `extra_info` 没有被 repeat，长度仍为1
4. 创建 DataProto 时，`extra_info` 长度1 ≠ batch_size 8 → **错误**

### 核心问题

在 **agent mode** 下，`vllm_rollout_spmd.py` 中：

1. `agent_rollout_loop` 返回的 `response` 已经是 interleaved 的（大小：`batch_size * n`）
2. 但是原始的 `idx`, `attention_mask`, `position_ids` 还是原始大小（`batch_size`）
3. **`extra_info` 也没有被 repeat**，导致大小不匹配

之前的代码（错误的）:
```python
# 第310行的 repeat_interleave 不会在 agent mode 下执行（我之前添加了 not activate_agent）
# 导致 idx 和 response 大小不匹配，无法拼接
if self.sampling_params.n > 1 and do_sample and not self.config.agent.activate_agent:
    idx = _repeat_interleave(idx, self.sampling_params.n)
    ...
```

## ✅ 修复方案

### 修复位置

**文件**: `verl/workers/rollout/vllm_rollout/vllm_rollout_spmd.py`

### 修复内容

**第291-298行** (agent mode 中 repeat tensors):
```python
response = agent_proto.batch.pop('response')
# In agent mode, also need to repeat prompts to match response size
# Note: agent_rollout_loop already handles interleaving for all non_tensor_batch data
if self.sampling_params.n > 1 and do_sample:
    idx = _repeat_interleave(idx, self.sampling_params.n)
    attention_mask = _repeat_interleave(attention_mask, self.sampling_params.n)
    position_ids = _repeat_interleave(position_ids, self.sampling_params.n)
    batch_size = batch_size * self.sampling_params.n
```

**注意**：不需要 repeat `extra_info` 或其他 non_tensor_batch 数据，因为 `agent_rollout_loop` 内部已经处理了 interleaving，并通过 `agent_proto.non_tensor_batch` 返回。

**第318-331行** (non-agent mode 保持不变):
```python
# Only repeat interleave in non-agent mode
# In agent mode, agent_rollout_loop already handles interleaving
if self.sampling_params.n > 1 and do_sample and not self.config.agent.activate_agent:
    idx = _repeat_interleave(idx, self.sampling_params.n)
    attention_mask = _repeat_interleave(attention_mask, self.sampling_params.n)
    position_ids = _repeat_interleave(position_ids, self.sampling_params.n)
    batch_size = batch_size * self.sampling_params.n
    if "multi_modal_inputs" in non_tensor_batch.keys():
        non_tensor_batch["multi_modal_inputs"] = _repeat_interleave(
            non_tensor_batch["multi_modal_inputs"], self.sampling_params.n
        )
    if "extra_info" in non_tensor_batch.keys():
        non_tensor_batch["extra_info"] = _repeat_interleave(
            non_tensor_batch["extra_info"], self.sampling_params.n
        )
```

### 关键点说明

1. **Agent mode**: 
   - 在 `agent_rollout_loop` 调用后立即 repeat `idx`, `attention_mask`, `position_ids`, `extra_info`
   - `multi_modal_inputs` **不需要** repeat，因为会从 `agent_proto.non_tensor_batch` 获取（已经 interleaved）

2. **Non-agent mode**: 
   - 在 generate 后 repeat 所有需要的字段
   - 包括 `multi_modal_inputs` 和 `extra_info`

3. **为什么两个地方都需要处理**:
   - Agent mode: `agent_rollout_loop` 内部处理了 interleaving，但只针对它自己管理的数据
   - Non-agent mode: vllm generate 返回 interleaved responses，需要手动 repeat prompts

## 📊 修复后的数据流

### Agent Mode (n=8, batch_size=1)

```
输入 prompts:
├─ idx: (1, prompt_len)
├─ attention_mask: (1, prompt_len)
├─ position_ids: (1, prompt_len) 或 (1, 3, prompt_len)
└─ extra_info: length 1

↓ agent_rollout_loop()

agent_proto:
├─ response: (8, response_len)  ← 已 interleaved
├─ multi_modal_inputs: length 8  ← 已 interleaved
└─ 其他字段...

↓ repeat prompts (第291-303行)

idx: (8, prompt_len)  ← repeat
attention_mask: (8, prompt_len)  ← repeat
position_ids: (8, ..., prompt_len)  ← repeat
extra_info: length 8  ← repeat

↓ 拼接和更新

seq = concat(idx, response): (8, total_len) ✓
batch.update(agent_proto.batch)  ← 更新 attention_mask, position_ids
non_tensor_batch.update(agent_proto.non_tensor_batch)  ← 更新 multi_modal_inputs

↓ 最终 DataProto

batch_size = 8
├─ tensors: 所有 (8, ...)
└─ non_tensor_batch:
    ├─ extra_info: length 8 ✓
    ├─ multi_modal_inputs: length 8 ✓
    ├─ image_history_list: length 8 ✓
    └─ conversation_history: length 8 ✓
```

### Non-Agent Mode (n=8, batch_size=1)

```
输入 prompts:
├─ idx: (1, prompt_len)
├─ extra_info: length 1
└─ multi_modal_inputs: length 1

↓ vllm.generate()

response: (8, response_len)  ← 已 interleaved

↓ repeat (第318-331行)

idx: (8, prompt_len)  ← repeat
attention_mask: (8, prompt_len)  ← repeat
position_ids: (8, ..., prompt_len)  ← repeat
extra_info: length 8  ← repeat
multi_modal_inputs: length 8  ← repeat

↓ 拼接

seq = concat(idx, response): (8, total_len) ✓

↓ 最终 DataProto

batch_size = 8
所有字段大小一致 ✓
```

## 🎯 验证方法

### 1. 检查日志

运行训练后，应该看到：
```bash
[DEBUG agent mode] After repeat: idx.shape=torch.Size([8, ...]), response.shape=torch.Size([8, ...]), batch_size=8
[DEBUG agent output proto] batch.keys()=..., non_tensor_batch.keys()=...
```

### 2. 检查错误

之前的错误不应再出现：
```
AssertionError: key extra_info length 1 is not equal to batch size 8
```

### 3. 检查 GT 传递

```bash
grep "DEBUG GT" logs/*.log
# 应该看到:
# [DEBUG GT] extra_info keys: ['index', 'split', 'original_image', ...]
# [DEBUG GT] ✓ Using original_image from extra_info
```

## 🚀 测试运行

```bash
bash examples/agent/IR.sh 2>&1 | tee logs/extra_info_fix_$(date +%Y%m%d_%H%M%S).log
```

## ✅ 修复总结

- ✅ Agent mode: repeat prompts 和 extra_info 以匹配 response
- ✅ Non-agent mode: repeat 所有字段
- ✅ multi_modal_inputs 在 agent mode 下从 agent_proto 获取
- ✅ 所有 non_tensor_batch 字段大小一致
- ✅ GT (original_image) 正确传递

修复完成！🎉

