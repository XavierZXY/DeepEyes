# Wandb Summary vs History 问题说明

## 问题描述

用户观察到：
1. `runs.summary["val/conversation_details"]` 只显示row
2. `val-core/image_restoration_v2/reward/best@25/mean` 在step 0, 5, 10都是相同的数值（小数点后四位都一样）

## 根本原因解释

### 问题1：Summary只显示row

**Wandb Summary机制：**
- `runs.summary` 只保存每个指标的**最后一个值**
- 对于Table类型，summary只显示metadata（如行数row），不显示完整数据
- **完整的表格数据在media/table文件夹中**

**解决方案：**
- 查看完整表格：在wandb UI的 **Tables tab** 查找 `val/conversation_details`
- 或者使用wandb API读取完整的table artifact

### 问题2：验证指标在不同step相同 ⚠️⚠️⚠️

**这确实不正常！**

从日志确认：
```
step 0: val-core/image_restoration_v2/reward/best@25/mean: 0.462
step 5: val-core/image_restoration_v2/reward/best@25/mean: 0.462
```

小数点后所有位数完全相同，这说明：

#### 可能原因A：验证时使用了相同的模型checkpoint

**假设：**
- Step 0: 使用初始模型验证
- Step 5: 训练5步后，但验证时**仍使用初始模型**（没有同步actor参数）
- 导致输出完全相同

**验证方法：**
检查验证时是否正确使用了更新后的actor：
```python
# 在_validate方法中，test_output_gen_batch_padded应该使用更新后的actor
test_output_gen_batch_padded = self.actor_rollout_wg.generate_sequences(test_gen_batch_padded)
```

**可能的bug：**
- actor_rollout_wg的参数没有被同步
- 验证时使用了cached的模型

#### 可能原因B：验证配置导致确定性输出 + 模型未更新

**验证配置：**
```yaml
val_kwargs:
  do_sample: False
  temperature: 0
  n: 1
```

**如果：**
1. do_sample=False（确定性）
2. 模型在early training变化极小
3. 验证集固定

**结果：**
- 相同输入 + 几乎相同的模型 = 相同的token选择
- 相同的输出 = 相同的reward
- **但小数点后四位完全相同仍然太巧合**

#### 可能原因C：reward_extra_infos_dict缓存bug ⭐️⭐️⭐️

**关键怀疑：**

让我检查在我修改`naive.py`后，是否导致某些字段被错误地缓存或复用。

**修改前（可能有问题的代码）：**
```python
for key, value in score.items():
    reward_extra_info[key].append(value)  # 所有字段都添加
```

**修改后：**
```python
skip_keys = {'degradation_type', ...} if data_source in ["image_restoration_v2"] else set()
for key, value in score.items():
    if key not in skip_keys:
        reward_extra_info[key].append(value)  # 跳过某些字段
```

**可能的问题：**
如果`score`字典本身被复用或缓存（比如在reward function中），跳过某些字段可能会导致其他逻辑出问题。

但这不应该影响验证输出本身，只应该影响reward_extra_info的收集。

#### 可能原因D：验证dataloader重复使用相同数据

**检查：**
验证时`self.val_dataloader`是否每次都返回相同的数据？

```python
for test_data in self.val_dataloader:
    test_batch = DataProto.from_single_dict(test_data)
    # ...
```

如果dataloader被错误地实现为只返回第一个batch，会导致所有验证使用相同数据。

但这不应该导致输出相同，因为模型应该更新了。

## 诊断步骤

### 1. 确认模型是否真的更新了

```bash
# 检查actor loss是否下降
grep "actor/loss" logs/*.log | head -10

# 检查参数更新
grep "actor.*grad" logs/*.log | head -10
```

### 2. 确认验证输出是否相同

```bash
# 查看不同step的验证输出（如果有日志）
grep -A 5 "validation generation end" logs/*.log | grep -A 3 "step:0"
grep -A 5 "validation generation end" logs/*.log | grep -A 3 "step:5"
```

### 3. 检查验证使用的模型

在`_validate`方法开始添加调试：
```python
def _validate(self):
    # 添加调试：打印actor模型的第一层参数和
    print(f"[DEBUG VAL] Actor model param sum: {sum(p.sum().item() for p in self.actor_rollout_wg.model.parameters() if p.requires_grad)}")
    
    # ... 原有代码
```

如果这个值在不同step相同，说明模型没有更新。

### 4. 检查是否有缓存机制

搜索代码中是否有@cache、lru_cache等装饰器，或者全局变量缓存。

## 我的修改可能的影响

**检查点：**

我修改的`naive.py`中的skip_keys逻辑，可能影响：
- reward_extra_infos_dict的内容
- 但**不应该**影响reward的计算值本身

**验证：**
```python
# 在naive.py中添加调试
print(f"[DEBUG REWARD] Sample 0 reward value: {reward}")
```

如果reward值在不同step相同，说明：
1. 模型输出相同
2. 或者reward计算被缓存

## 临时诊断方案

在`_validate`方法中添加调试：

```python
def _validate(self):
    import random
    debug_id = random.randint(1000, 9999)
    print(f"[DEBUG VAL {debug_id}] Starting validation at step {self.global_steps}")
    
    # ... 现有代码 ...
    
    # 在收集scores后
    print(f"[DEBUG VAL {debug_id}] Collected {len(sample_scores)} scores")
    if len(sample_scores) > 0:
        print(f"[DEBUG VAL {debug_id}] First 3 scores: {sample_scores[:3]}")
        print(f"[DEBUG VAL {debug_id}] Scores hash: {hash(tuple(sample_scores[:10]))}")
```

这样可以确认每次验证是否真的计算了新的scores，还是使用了缓存的结果。

## 结论

**小数点后四位完全相同**确实异常，需要进一步调试：

1. ✅ 不是wandb summary的问题（logs中确认step 0和5的值相同）
2. ⚠️ 可能是模型更新问题（验证时使用了旧模型）
3. ⚠️ 可能是验证输出被缓存
4. ⚠️ 可能是do_sample=False + 模型变化极小的巧合（但概率很低）

**建议：**
添加更多调试信息，确认模型是否真的更新了，以及验证输出是否真的变化了。

修复日期: 2025-10-10

