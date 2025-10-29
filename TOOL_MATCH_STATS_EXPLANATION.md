# 📊 Tool_Match统计逻辑说明

## 🎯 统计层级：批次级别（每个step更新）

### **为什么是批次级别？**

1. **避免panel爆炸**：样本级别会产生 `batch_size × n × 退化类型数` 个panel
2. **减少计算量**：批次统计更轻量
3. **趋势可见**：每个step的batch不同，统计值会变化

---

## 🔄 统计更新机制

### **数据流**

```
Step 1 (Batch 1):
  样本0-31: 各种退化类型
  → 计算当前批次的 tool_match/unique_ratio/rain = 0.75
  → 所有32个样本都记录这个值
  → Wandb显示: step=1, tool_match/unique_ratio/rain=0.75

Step 2 (Batch 2):
  样本32-63: 不同的退化分布
  → 计算当前批次的 tool_match/unique_ratio/rain = 0.82
  → 所有32个样本都记录这个值
  → Wandb显示: step=2, tool_match/unique_ratio/rain=0.82 ← 已更新！

Step 3 (Batch 3):
  样本64-95: 又不同的分布
  → 计算当前批次的 tool_match/unique_ratio/rain = 0.68
  → Wandb显示: step=3, tool_match/unique_ratio/rain=0.68 ← 继续更新！
```

---

## 📐 统计指标

### **每种退化类型的指标**

| 指标名称 | 含义 | 范围 | 示例 |
|---------|------|------|------|
| `tool_match/unique_ratio/{deg_type}` | 当前batch中调用了正确工具的样本比例 | 0.0-1.0 | 0.75 = 75%的rain样本调用了去雨工具 |
| `tool_match/unique_count/{deg_type}` | 当前batch中调用了正确工具的样本数 | 整数 | 18.0 = 18个样本调用了正确工具 |
| `tool_match/unique_total/{deg_type}` | 当前batch中有该退化的样本总数 | 整数 | 24.0 = 24个样本有rain退化 |
| `tool_match/repeat_ratio/{deg_type}` | 当前batch中有工具重复调用的样本比例 | 0.0-1.0 | 0.25 = 25%的样本重复调用了工具 |

---

## 🔍 为什么看起来"不更新"？

### **可能原因分析**

#### **1. 数据分布稳定**
```python
# 如果每个batch的数据分布相似
Batch 1: rain样本占比 30%, 匹配率 75%
Batch 2: rain样本占比 32%, 匹配率 76%
Batch 3: rain样本占比 29%, 匹配率 74%

# Wandb曲线看起来很平（但实际在更新）
```

#### **2. 模型性能稳定**
```python
# 如果模型已经收敛
Batch 1-100: 匹配率都在 75%-78% 之间
# 这说明模型性能稳定，不是统计没更新
```

#### **3. 日志缓冲**
```python
# Wandb可能有缓冲，不是实时显示
# 解决：手动刷新或等待自动同步
```

---

## ✅ 验证统计是否更新

### **方法1: 查看训练日志**
```bash
# 每个step都会打印统计
grep "TOOL STATS.*rain:" logs/*.log | tail -10

# 应该看到不同的值
step 245: rain: 18/24 = 0.750
step 246: rain: 20/25 = 0.800  ← 变化了
step 247: rain: 17/23 = 0.739  ← 继续变化
```

### **方法2: 监控wandb API**
```python
import wandb
api = wandb.Api()
run = api.run(f"{project}/{run_id}")

# 获取最近的tool_match数据
history = run.history(keys=["tool_match/unique_ratio/rain"])
print(history.tail(10))  # 应该看到不同的值
```

### **方法3: 添加调试日志**
```python
# 在 metric_utils.py 的 compute_agent_metrics 中
for key in tool_match_keys:
    value = tensor[0, 0].item()
    print(f"[DEBUG METRIC] {key} = {value:.4f}")  # 每个step打印
```

---

## 🔧 当前实现逻辑

### **计算流程**

```python
# 1. 每个batch开始时
tool_calls_per_sample = [{}, {}, ...]  # 初始化

# 2. rollout过程中收集数据
for step in range(max_turns):
    for idx, action in enumerate(actions):
        parsed = parse_output(action)
        if parsed['tool_calls']:
            tool_calls_per_sample[idx][step+1] = [tool_names]

# 3. rollout结束后计算统计
tool_stats = compute_tool_degradation_matching_stats(
    tool_calls_per_sample,  # 当前batch的工具调用记录
    degradation_types_per_sample,  # 当前batch的退化类型
    ...
)
# 返回: {'tool_match/unique_ratio/rain': 0.75, ...}

# 4. 转换为tensor（batch内所有样本用同一个值）
tool_match_tensors = {}
for key, value in tool_stats.items():
    tool_match_tensors[key] = torch.full(
        (batch_size * n, 1), 
        value  # ← 当前batch的统计值
    )

# 5. 返回给trainer
return DataProto(tensors={..., **tool_match_tensors})

# 6. trainer收集metrics
for key in tool_match_keys:
    metrics[key] = tensor[0, 0].item()  # 提取批次统计值

# 7. 记录到wandb
wandb.log({
    'tool_match/unique_ratio/rain': 0.75,  # Step 1的值
    'tool_match/unique_ratio/rain': 0.82,  # Step 2的值
    ...
})
```

---

## 🎯 关键点

### **✅ 统计会更新的原因**

1. **每个batch重新计算**：
   ```python
   # agent_rollout_loop 每次都重新初始化
   tool_calls_per_sample = []  # 空列表
   ```

2. **batch数据不同**：
   ```python
   # 每个step的batch从数据集不同位置采样
   Step 1: 样本 0-31
   Step 2: 样本 32-63
   Step 3: 样本 64-95
   ```

3. **模型在学习**：
   ```python
   # 随着训练，模型调用正确工具的概率上升
   Early: tool_match/unique_ratio/rain = 0.30
   Mid:   tool_match/unique_ratio/rain = 0.65
   Late:  tool_match/unique_ratio/rain = 0.90
   ```

### **❌ 可能看起来不更新的原因**

1. **数据分布均匀**：数据集well-shuffled，每个batch分布相似
2. **模型收敛**：性能稳定，匹配率不再变化
3. **wandb显示延迟**：刷新不及时

---

## 📈 监控建议

### **关注这些指标的变化**

```python
# 1. 每种退化的匹配率（应该随训练上升）
tool_match/unique_ratio/rain       # 0.3 → 0.9
tool_match/unique_ratio/haze       # 0.4 → 0.85
tool_match/unique_ratio/noise      # 0.5 → 0.92

# 2. 批次之间的方差（判断是否真的在更新）
import numpy as np
values = [step1_value, step2_value, step3_value, ...]
variance = np.var(values)
if variance > 0.01:
    print("✅ 统计在更新")
else:
    print("⚠️  统计变化很小（可能是收敛了）")
```

---

## 💡 如果确实不更新的调试步骤

```bash
# 1. 检查compute_tool_degradation_matching_stats是否被调用
grep "TOOL STATS.*开始计算" logs/*.log | wc -l
# 应该 = 训练step数

# 2. 检查每次计算的结果
grep "TOOL STATS.*rain:" logs/*.log | tail -20
# 应该看到不同的数值

# 3. 检查tensor是否被正确创建
grep "tool_match_tensors" logs/*.log

# 4. 检查metrics是否被正确收集
grep "METRICS.*收集了.*工具-退化" logs/*.log
```

---

**总结**：
- ✅ 当前实现是批次级别统计
- ✅ 每个step都会重新计算
- ✅ 统计值会随batch数据变化
- ⚠️  如果看起来不变，可能是数据分布稳定或模型收敛
- 📊 通过日志可以验证每个step的实际数值

**修复状态**: 已回退到批次统计，逻辑正确

