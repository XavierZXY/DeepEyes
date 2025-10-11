# Extra_info传递问题修复

## 🔴 问题

用户发现GT还是退化图，而不是真正的原图（parquet中extra_info['original_image']）。

## 🔍 根本原因

### 数据传递断裂

```python
# ray_trainer.py - _validate() 第597行
test_gen_batch = test_batch.pop(
    batch_keys=['input_ids', ...],
    non_tensor_batch_keys=['raw_prompt_ids', 'multi_modal_data', ...]
    # ❌ 没有包含 'extra_info'！
)

# 结果：
# test_gen_batch.non_tensor_batch: 没有extra_info
# test_batch.non_tensor_batch: extra_info还在这里（但不会被使用）

# 传递给agent_rollout_loop
generate_sequences(test_gen_batch)  # 没有extra_info

# parallel_env.py - reset()
extra_info = data_item.non_tensor_batch.get("extra_info", None)
# → None！因为test_gen_batch中没有

# 保存
self.extra_info_list.append(None)

# 后续使用
if saved_extra_info_list[i] is not None:  # False
    ...
else:
    # Fallback
    original_images_to_add.append(saved_original_images[i])  # ← 退化图！
```

## ✅ 修复方案

### 在pop时包含extra_info

**文件**: `verl/trainer/ppo/ray_trainer.py` 第597-605行

**修复前**:
```python
test_gen_batch = test_batch.pop(
    batch_keys=[...],
    non_tensor_batch_keys=['raw_prompt_ids', 'multi_modal_data', ...]
    # 缺少 extra_info
)
```

**修复后**:
```python
test_gen_batch = test_batch.pop(
    batch_keys=[...],
    non_tensor_batch_keys=['raw_prompt_ids', 'multi_modal_data', ..., 'extra_info']
    # ✓ 添加 extra_info
)
```

## 📊 修复后的数据流

```
Dataset
  ↓ extra_info: {'original_image': bytes, ...}

RLHFDataset.__getitem__
  ↓ 返回 sample['extra_info'] = {...}

DataLoader
  ↓ test_batch.non_tensor_batch['extra_info'] = {...}

ray_trainer._validate()
  ↓ test_gen_batch = test_batch.pop(..., 'extra_info')  ← 修复
  ↓ test_gen_batch.non_tensor_batch['extra_info'] = {...}

generate_sequences(test_gen_batch)
  ↓ agent_rollout_loop(prompts=test_gen_batch)

ParallelEnv.reset(prompts)
  ↓ extra_info = prompts[i].non_tensor_batch.get('extra_info')
  ↓ extra_info = {'original_image': bytes, ...}  ← 现在有了！
  ↓ self.extra_info_list.append(extra_info)

agent_rollout_loop保存
  ↓ saved_extra_info_list = env.extra_info_list
  ↓ = [{'original_image': bytes}, ...]  ← 不再是None

提取original_image
  ↓ if extra_info.get('original_image') is not None:
  ↓   original_images_to_add.append(extra_info['original_image'])
  ↓   ✓ 使用真正的GT！
```

## ✅ 验证

重新运行训练后，应该看到：

```bash
grep "DEBUG GT" logs/*.log

# 应该看到:
[DEBUG GT] extra_info keys: ['index', 'split', 'original_image', ...]
[DEBUG GT] original_image type: <class 'bytes'>
[DEBUG GT] original_image is None: False
[DEBUG GT] ✓ Using original_image from extra_info

# 不再看到:
# ⚠️  Using origin_multi_modal_data (no extra_info)
```

## 📊 GT正确性验证

在wandb中：
- Ground Truth列应该显示清晰原图
- Degraded Input列显示模糊/压缩的退化图
- **明显的区别**，不再"差不多"

## 🎯 关键修改

**位置**: `verl/trainer/ppo/ray_trainer.py`
- 第599行：添加'extra_info'到pop的non_tensor_batch_keys
- 第604行：添加'extra_info'到else分支的pop

**效果**: 
- ✓ extra_info被传递到agent_rollout_loop
- ✓ ParallelEnv.reset()能获取到extra_info
- ✓ 真正的original_image被保存
- ✓ wandb展示真实的GT vs 退化图

## 🚀 现在运行训练

所有数据传递问题已修复！GT应该是真正的清晰原图了！

