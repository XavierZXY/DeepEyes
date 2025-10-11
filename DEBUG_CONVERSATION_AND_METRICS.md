# 对话内容和有参考指标为0的调试指南

## 🐛 问题描述

- 对话内容不显示（train 和 val 都是）
- 有参考指标（PSNR/SSIM/LPIPS）都为 0

## 🔍 调试步骤

### 步骤1: 检查 agent_rollout_loop 返回的数据

运行训练并查看日志：

```bash
bash examples/agent/IR.sh 2>&1 | tee logs/debug_$(date +%Y%m%d_%H%M%S).log
```

**查找关键日志**：

```bash
# 1. 检查 agent 模式输出
grep "DEBUG agent output proto" logs/debug_*.log

# 应该看到:
# batch.keys()=dict_keys(['response', 'action_mask', ...])
# non_tensor_batch.keys()=dict_keys(['multi_modal_inputs', 'image_history_list', 'conversation_history', 'original_images'])
```

```bash
# 2. 检查 non_tensor_batch 数据大小
grep "DEBUG agent non_tensor" logs/debug_*.log

# 应该看到:
# conversation_history: shape=(8,), dtype=object
# original_images: shape=(8,), dtype=object
# image_history_list: shape=(8,), dtype=object
# multi_modal_inputs: shape=(8,), dtype=object
```

```bash
# 3. 检查对话内容
grep "conversation_history\[0\]" logs/debug_*.log

# 应该看到类似:
# conversation_history[0]: [{'turn': 1, 'response': '...', ...}, {'turn': 2, ...}]
# 如果是空列表 []，说明对话没有被保存
```

```bash
# 4. 检查 original_images
grep "original_images\[0\] is None" logs/debug_*.log

# 应该看到:
# original_images[0] is None: False
# 如果是 True，说明 GT 图像没有传递
```

### 步骤2: 检查 env.reset() 是否获取到 extra_info

```bash
grep "DEBUG RESET" logs/debug_*.log

# 正常情况：
# [DEBUG RESET] ⚠️  Prompt 0 has no extra_info, original_image will fallback
# （这是警告，说明 extra_info 没传进来）

# 理想情况（修复后）：
# 应该没有这个警告
```

### 步骤3: 检查 GT 提取过程

```bash
grep "DEBUG GT" logs/debug_*.log

# 应该看到:
# [DEBUG GT] extra_info keys: ['index', 'split', 'original_image', ...]
# [DEBUG GT] original_image type: <class 'bytes'>
# [DEBUG GT] original_image is None: False
# [DEBUG GT] ✓ Using original_image from extra_info

# 如果看到:
# [DEBUG GT] ⚠️  Using origin_multi_modal_data (no extra_info)
# 说明 extra_info 没有正确传递
```

### 步骤4: 检查对话保存

```bash
grep "对话保存" logs/debug_*.log

# 应该看到:
# [DEBUG] Turn X 对话保存: {...}
```

## 🔧 可能的问题和解决方案

### 问题1: extra_info 没有传递到 agent_rollout_loop

**症状**：
- `original_images[0] is None: True`
- 有参考指标都为 0
- 看到 "⚠️ Prompt 0 has no extra_info"

**检查**：

在 `ray_trainer.py` 中检查是否包含 'extra_info'：

```bash
grep "pop.*extra_info" verl/trainer/ppo/ray_trainer.py
```

应该在两个地方看到 'extra_info'：
1. Training 的 gen_batch.pop (约第1036、1041行)
2. Validation 的 test_gen_batch.pop (约第599、604行)

**修复**：

确保这两个地方的 `non_tensor_batch_keys` 参数包含 `'extra_info'`。

### 问题2: conversation_history 为空

**症状**：
- `conversation_history[0]: []`
- 对话内容不显示

**检查**：

在 `parallel_env.py` 中检查对话保存逻辑：

```bash
grep -n "self.conversation_history.*append" verl/workers/agent/parallel_env.py
```

应该在工具执行成功后保存对话（约第425-430行）。

**可能原因**：
1. 工具没有执行（所有样本都直接返回 answer）
2. 对话保存逻辑被跳过

**调试**：

添加打印：
```python
# 在 parallel_env.py 第430行后添加
print(f"[DEBUG CONV] Saved conversation for idx {idx}: {self.conversation_history[idx]}")
```

### 问题3: original_images 都是 None

**症状**：
- PSNR/SSIM/LPIPS 都为 0
- `original_images[0] is None: True`

**检查流程**：

```
Dataset → extra_info['original_image'] (bytes)
    ↓
ray_trainer.pop(..., 'extra_info')  ← 检查点1
    ↓
prompts.non_tensor_batch['extra_info']
    ↓
agent_rollout_loop(prompts=prompts)
    ↓
env.reset: prompts[i].non_tensor_batch.get('extra_info')  ← 检查点2
    ↓
env.extra_info_list.append(deepcopy(extra_info))
    ↓
saved_extra_info_list = env.extra_info_list.copy()  ← 检查点3
    ↓
extract original_image from saved_extra_info_list  ← 检查点4
    ↓
non_tensors_dict['original_images']
```

**逐个检查点验证**。

## 📊 完整调试脚本

创建调试脚本 `debug_data_flow.sh`：

```bash
#!/bin/bash

LOG_FILE="logs/debug_$(date +%Y%m%d_%H%M%S).log"

echo "=== 运行训练 ==="
bash examples/agent/IR.sh 2>&1 | tee $LOG_FILE

echo ""
echo "=== 调试报告 ==="
echo ""

echo "1. Agent 输出检查:"
grep "DEBUG agent output proto" $LOG_FILE | head -3

echo ""
echo "2. Non-tensor 数据大小:"
grep "DEBUG agent non_tensor" $LOG_FILE | head -10

echo ""
echo "3. 对话内容检查:"
grep "conversation_history\[0\]" $LOG_FILE | head -3

echo ""
echo "4. GT 图像检查:"
grep "original_images\[0\] is None" $LOG_FILE | head -3

echo ""
echo "5. Extra_info 传递:"
grep "DEBUG RESET" $LOG_FILE | head -3
grep "DEBUG GT" $LOG_FILE | head -10

echo ""
echo "6. IMAGE_HISTORY 调试:"
grep "DEBUG IMAGE_HISTORY" $LOG_FILE | head -20

echo ""
echo "=== 调试完成 ==="
echo "完整日志: $LOG_FILE"
```

运行：
```bash
chmod +x debug_data_flow.sh
./debug_data_flow.sh
```

## ✅ 预期正常输出

**正常情况应该看到**：

```
[DEBUG agent output proto] batch.keys()=..., non_tensor_batch.keys()=dict_keys(['multi_modal_inputs', 'image_history_list', 'conversation_history', 'original_images'])

[DEBUG agent non_tensor] conversation_history: shape=(8,), dtype=object
[DEBUG agent non_tensor] conversation_history[0]: [{'turn': 1, 'response': '...', 'is_done': False}, ...]

[DEBUG agent non_tensor] original_images: shape=(8,), dtype=object
[DEBUG agent non_tensor] original_images[0] is None: False

[DEBUG GT] extra_info keys: ['index', 'split', 'original_image', 'use_original', ...]
[DEBUG GT] ✓ Using original_image from extra_info

[DEBUG IMAGE_HISTORY] ✓ Added image_history_list, original_images, and conversation_history
```

## 🚀 快速验证命令

```bash
# 运行训练
bash examples/agent/IR.sh 2>&1 | tee logs/debug.log

# 快速检查
echo "=== 检查对话 ==="
grep -A1 "conversation_history\[0\]" logs/debug.log | head -5

echo "=== 检查GT ==="
grep "original_images.*is None" logs/debug.log | head -3

echo "=== 检查extra_info ==="
grep "DEBUG GT" logs/debug.log | head -10
```

根据这些调试信息，我们可以准确定位问题所在！

