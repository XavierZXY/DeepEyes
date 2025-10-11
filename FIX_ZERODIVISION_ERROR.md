# 修复 ZeroDivisionError 问题

## 错误信息
```
ZeroDivisionError: integer modulo by zero
  File "/app/xiaominl/AIR/verl/protocol.py", line 615, in chunk
    assert len(self) % chunks == 0
```

## 根本原因

在 `verl/workers/actor/dp_actor.py` 第296行：
```python
num_micro_batches = mini_batch.batch.batch_size[0] // self.config.ppo_micro_batch_size_per_gpu
```

当 `mini_batch.batch.batch_size[0]` < `ppo_micro_batch_size_per_gpu` 时，整数除法结果为0，导致后续chunk操作除以0。

### 触发条件
1. **多模态输入场景** (`has_multi_modal_inputs=True`)
2. **batch_size 小于 micro_batch_size**

常见场景：
- 验证阶段的小batch
- 数据集最后一个不完整的batch
- 配置的micro_batch_size过大

## 修复方案

### 方案1：代码保护（已实现）✅

在 `dp_actor.py` 第297-300行添加保护：
```python
num_micro_batches = mini_batch.batch.batch_size[0] // self.config.ppo_micro_batch_size_per_gpu
# 确保num_micro_batches至少为1，避免除以0错误
if num_micro_batches == 0:
    print(f"[WARNING] num_micro_batches=0 (batch_size={mini_batch.batch.batch_size[0]}, micro_batch_size={self.config.ppo_micro_batch_size_per_gpu}), setting to 1")
    num_micro_batches = 1
```

### 方案2：配置调整（推荐）⚠️

调整 `IR.sh` 中的配置，确保合理的批次大小关系：

**当前配置（可能有问题）：**
```bash
data.train_batch_size=8 \
actor_rollout_ref.actor.ppo_mini_batch_size=8 \
actor_rollout_ref.actor.ppo_micro_batch_size_per_gpu=8 \
actor_rollout_ref.rollout.n=4
```

**问题分析：**
- `train_batch_size=8`：每个batch 8个样本
- `rollout.n=4`：每个样本生成4个response
- 总共：8 × 4 = 32个response
- 但在chunk之后，mini_batch可能只有8个样本（取决于dataloader分割）
- 如果mini_batch < 8，则num_micro_batches = 0

**推荐配置：**

选项A - 减小micro_batch_size（推荐）：
```bash
data.train_batch_size=8 \
actor_rollout_ref.actor.ppo_mini_batch_size=8 \
actor_rollout_ref.actor.ppo_micro_batch_size_per_gpu=4 \  # 改为4
actor_rollout_ref.rollout.n=4
```

选项B - 增大batch_size：
```bash
data.train_batch_size=16 \  # 改为16
actor_rollout_ref.actor.ppo_mini_batch_size=16 \  # 改为16
actor_rollout_ref.actor.ppo_micro_batch_size_per_gpu=8 \
actor_rollout_ref.rollout.n=4
```

选项C - 调整rollout.n：
```bash
data.train_batch_size=8 \
actor_rollout_ref.actor.ppo_mini_batch_size=8 \
actor_rollout_ref.actor.ppo_micro_batch_size_per_gpu=4 \  # 改为4
actor_rollout_ref.rollout.n=2  # 改为2
```

## 配置原则

**关键约束：**
```
mini_batch_size >= micro_batch_size_per_gpu
```

**推荐关系：**
```
train_batch_size × rollout.n = total_samples
total_samples / num_mini_batches = mini_batch_size
mini_batch_size / num_gpus >= micro_batch_size_per_gpu
```

**对于多模态任务：**
- `micro_batch_size_per_gpu` 应该设置较小（1-4），因为图片占用显存大
- `mini_batch_size` 应该是 `micro_batch_size_per_gpu` 的倍数
- 确保 `mini_batch_size >= micro_batch_size_per_gpu × num_gpus`

## 验证步骤

1. 运行训练，查看是否有WARNING：
   ```bash
   grep "num_micro_batches=0" logs/*.log
   ```

2. 如果看到WARNING，说明配置需要调整，按照上述建议修改

3. 验证修复：
   - 不再出现 `ZeroDivisionError`
   - 训练正常进行
   - 没有 `num_micro_batches=0` 的警告

## 相关文件

- ✅ `verl/workers/actor/dp_actor.py` - 已添加保护措施
- ⚠️ `examples/agent/IR.sh` - 需要检查配置

## 修复日期
2025-10-10

