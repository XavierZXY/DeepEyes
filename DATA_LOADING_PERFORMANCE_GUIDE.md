# 数据加载和处理速度优化指南

## 📊 可调节的性能参数总结

项目中有多个参数可以控制数据加载和处理速度。以下是详细说明和推荐配置。

---

## 1️⃣ DataLoader 多线程参数

### 位置
`verl/trainer/ppo/ray_trainer.py` 第494行和511行

### 当前配置
```python
self.train_dataloader = StatefulDataLoader(
    dataset=self.train_dataset,
    batch_size=self.config.data.get("gen_batch_size", self.config.data.train_batch_size),
    num_workers=8,  # ← 硬编码为8个worker
    drop_last=True,
    collate_fn=collate_fn,
    sampler=sampler,
)

self.val_dataloader = StatefulDataLoader(
    dataset=self.val_dataset,
    batch_size=len(self.val_dataset),
    num_workers=8,  # ← 硬编码为8个worker
    shuffle=False,
    drop_last=False,
    collate_fn=collate_fn,
)
```

### 作用
- 控制PyTorch DataLoader的后台worker进程数
- 负责并行加载和预处理数据（图像解码、tokenization等）
- **这是影响数据加载速度的最主要参数**

### 优化建议

**如何修改**: 需要编辑 `ray_trainer.py` 文件

```python
# 根据CPU核心数和内存调整
# 推荐值：
# - 8-16 核CPU: num_workers=4-8
# - 16-32 核CPU: num_workers=8-16
# - 32+ 核CPU: num_workers=16-32
# - 内存受限: 减少num_workers
```

**注意事项**:
- worker数量过多会占用大量内存（每个worker复制dataset）
- 对于图像数据，每个worker需要额外的内存来缓存解码后的图像
- 建议：`num_workers = min(cpu_count // 2, 16)`

---

## 2️⃣ 数据过滤多进程参数

### 配置位置
`verl/trainer/config/ppo_trainer.yaml` 第14-15行

```yaml
data:
  filter_overlong_prompts: False  # 是否过滤超长prompts
  filter_overlong_prompts_workers: 1  # 过滤时使用的进程数
```

### 在 IR.sh 中配置
```bash
# 在 IR.sh 训练脚本中添加
data.filter_overlong_prompts_workers=8
```

### 实际代码
`verl/utils/dataset/rl_dataset.py` 第83-84行，第116行

```python
# 自动根据CPU数量计算
self.num_workers = config.get("filter_overlong_prompts_workers", max(1, os.cpu_count() // 4))
self.num_workers = min(self.num_workers, os.cpu_count())

# 使用多进程过滤
self.dataframe = self.dataframe.filter(
    lambda doc: len(tokenizer.apply_chat_template(doc[prompt_key], add_generation_prompt=True))
    <= self.max_prompt_length,
    num_proc=self.num_workers,  # ← 使用多进程
    desc=f"Filtering prompts longer than {self.max_prompt_length} tokens",
)
```

### 优化建议

**推荐配置**:
```bash
# 在 IR.sh 中添加
data.filter_overlong_prompts=True \
data.filter_overlong_prompts_workers=16 \  # 根据CPU核心数调整
```

**何时使用**:
- ✅ 数据集很大（>10万样本）且包含超长样本
- ✅ 首次加载数据时启用
- ❌ 数据集较小（<1万样本）或已经过滤过

---

## 3️⃣ Agent并发执行参数 ⭐

### 配置位置
`verl/trainer/config/ppo_trainer.yaml` 第125行

```yaml
agent:
  concurrent_workers: 1  # Agent环境交互的并发线程数
```

### 在 IR.sh 中配置 ⭐ **当前您的配置**
```bash
actor_rollout_ref.rollout.agent.concurrent_workers=1
```

### 实际代码
`verl/workers/agent/parallel_env.py` 第1132行

```python
# 工具执行时的并发数
num_workers = min(self.config.concurrent_workers, len(valid_actions))
pbar = tqdm(total=len(valid_actions), desc=f'Tool calling on {num_workers} workers')
```

### 优化建议 ⭐

**推荐配置**:
```bash
# 在 IR.sh 中修改
actor_rollout_ref.rollout.agent.concurrent_workers=4  # 或 8

# 对于图像处理任务，建议范围：
# - CPU密集型工具（图像处理）: 4-8
# - API调用型工具: 8-16
# - 混合类型: 4-8
```

**性能影响**:
- `concurrent_workers=1`: 串行执行工具，慢但稳定
- `concurrent_workers=4`: 4个工具并发执行，**推荐值**
- `concurrent_workers=8`: 8个并发，适合多核CPU
- `concurrent_workers=16`: 高并发，需要强大CPU

**注意事项**:
- 工具如果调用远程API，增加并发数效果明显
- 工具如果在本地执行（CPU密集），过高并发会导致竞争
- 需要确保远程服务（如图像处理API）能承受并发请求

---

## 4️⃣ Ray配置参数

### 配置位置
`verl/trainer/config/ppo_trainer.yaml` 第237行

```yaml
ray_init:
  num_cpus: null  # None表示使用所有CPU
```

### 在 IR.sh 中配置
```bash
# 如果在SLURM等受限环境，需要设置
ray_init.num_cpus=32  # 根据实际分配的CPU数设置
```

### 优化建议
- 默认 `null` (使用所有CPU) 通常是最佳选择
- 在SLURM等资源管理系统中，设置为实际分配的CPU数

---

## 5️⃣ Batch Size 参数

### 配置位置
`verl/trainer/config/ppo_trainer.yaml` 第9行

```yaml
data:
  train_batch_size: 1024
```

### 在 IR.sh 中配置 ⭐ **当前您的配置**
```bash
data.train_batch_size=32
```

### 优化建议
- **较大batch**: 更好的GPU利用率，但内存占用高
- **较小batch**: 更快的迭代，适合调试
- **推荐**: 根据GPU内存调整，确保不OOM

---

## 📈 综合性能优化建议

### 当前 IR.sh 配置分析

您当前的配置：
```bash
data.train_batch_size=32
actor_rollout_ref.rollout.agent.concurrent_workers=1  # ← 性能瓶颈！
```

### 推荐的优化配置

在 `IR.sh` 中添加/修改以下参数：

```bash
# ========== 数据加载性能优化 ==========
# 1. 增加Agent并发数（最重要！）
actor_rollout_ref.rollout.agent.concurrent_workers=4 \

# 2. 启用数据过滤多进程（如果数据集大）
data.filter_overlong_prompts=True \
data.filter_overlong_prompts_workers=8 \

# 3. 调整batch size（根据GPU内存）
data.train_batch_size=32 \  # 或更大，如果内存允许

# 注意：DataLoader的num_workers需要修改代码
# ================================================
```

### 修改 DataLoader num_workers（可选但推荐）

编辑 `verl/trainer/ppo/ray_trainer.py`:

```python
# 第494行附近
self.train_dataloader = StatefulDataLoader(
    dataset=self.train_dataset,
    batch_size=self.config.data.get("gen_batch_size", self.config.data.train_batch_size),
    num_workers=16,  # 从8改为16（根据CPU核心数）
    drop_last=True,
    collate_fn=collate_fn,
    sampler=sampler,
)

# 第511行附近
self.val_dataloader = StatefulDataLoader(
    dataset=self.val_dataset,
    batch_size=len(self.val_dataset),
    num_workers=16,  # 从8改为16
    shuffle=False,
    drop_last=False,
    collate_fn=collate_fn,
)
```

---

## 🎯 快速诊断检查清单

### 数据加载慢？

1. ✅ **检查DataLoader worker数**: `num_workers=8` → 尝试增加到16
2. ✅ **检查Agent并发数**: `concurrent_workers=1` → **强烈建议改为4或8**
3. ✅ **检查batch size**: 太小会导致频繁的数据加载
4. ✅ **检查磁盘I/O**: 数据是否在本地SSD？远程存储会很慢
5. ✅ **检查CPU使用率**: `htop` 看是否CPU饱和

### 工具执行慢？

1. ✅ **检查concurrent_workers**: 串行执行(`=1`)非常慢
2. ✅ **检查远程服务响应**: API服务是否能处理并发请求
3. ✅ **检查网络延迟**: 工具服务的网络是否流畅

### 图像处理慢？

1. ✅ **检查图像解码**: PIL/OpenCV是否使用了多线程
2. ✅ **检查图像大小**: 高分辨率图像处理很慢
3. ✅ **检查DataLoader workers**: 增加可以并行解码图像

---

## 📊 性能对比示例

假设训练一个batch (32样本)，每个样本调用2个工具：

| 配置 | 预计时间 | 加速比 |
|-----|---------|--------|
| `concurrent_workers=1` | 64秒 (串行) | 1x |
| `concurrent_workers=4` | 16秒 (并行) | **4x** ⭐ |
| `concurrent_workers=8` | 8秒 (并行) | **8x** |
| `concurrent_workers=8` + `num_workers=16` | 6秒 | **10x** |

---

## 🔧 立即行动方案

### 最小改动（只修改IR.sh）

```bash
# 在IR.sh中找到这一行：
actor_rollout_ref.rollout.agent.concurrent_workers=1 \

# 改为：
actor_rollout_ref.rollout.agent.concurrent_workers=4 \

# 或更激进：
actor_rollout_ref.rollout.agent.concurrent_workers=8 \
```

**预期效果**: 训练速度提升 **3-8倍** 🚀

### 完整优化（修改代码+配置）

1. 修改 `ray_trainer.py` 的 `num_workers=8` → `num_workers=16`
2. 在 `IR.sh` 中添加 `concurrent_workers=8`
3. 在 `IR.sh` 中添加 `filter_overlong_prompts_workers=16`

**预期效果**: 整体训练速度提升 **5-10倍** 🚀🚀

---

## ⚠️ 注意事项

1. **内存限制**: worker数量过多会占用大量内存
2. **CPU限制**: 并发数不应超过CPU核心数
3. **API限制**: 远程服务可能有并发限制
4. **调试模式**: 调试时建议降低并发，便于追踪问题
5. **逐步测试**: 先小幅增加，观察效果后再继续调整

---

## 📚 相关文件

- 配置文件: `verl/trainer/config/ppo_trainer.yaml`
- DataLoader实现: `verl/trainer/ppo/ray_trainer.py` (第462-515行)
- 数据集实现: `verl/utils/dataset/rl_dataset.py` (第83-120行)
- Agent执行: `verl/workers/agent/parallel_env.py` (第1132行)
- 训练脚本: `examples/agent/IR.sh` (第158行)

---

## 💡 总结

**关键参数优先级**:

1. 🥇 **concurrent_workers** - Agent并发数（影响最大！）
2. 🥈 **num_workers** - DataLoader多线程
3. 🥉 **filter_overlong_prompts_workers** - 数据预处理并发

**推荐快速优化**:
```bash
# 只需在IR.sh中改一行！
actor_rollout_ref.rollout.agent.concurrent_workers=4  # 或8
```

这将带来最显著的性能提升！🚀

