# WandB 指标缺失问题排查

## 🔍 问题：wandb上没有 tool_count_match 指标

### 排查步骤

---

## 步骤1️⃣: 检查日志输出

### 查找关键日志

运行训练后，在日志中搜索以下关键词：

#### 日志1: 统计计算是否执行

```bash
grep "tool_degradation_stats 返回了" logs/*.log
```

**期望输出：**
```
[DEBUG STATS] tool_degradation_stats 返回了 62 个指标
[DEBUG STATS] 其中 tool_count_match/ 指标: 14 个
[DEBUG STATS] tool_count_match 指标示例: ['tool_count_match/deg2_less_ratio', ...]
```

**如果没有这个输出：**
- ❌ 统计函数没有被调用
- 检查是否启用了 agent：`actor_rollout_ref.rollout.agent.activate_agent=True`

---

#### 日志2: 工具数量匹配统计详情

```bash
grep "工具数量匹配统计" logs/*.log
```

**期望输出：**
```
[TOOL STATS] 工具数量匹配统计（样本调用的工具数 vs 退化数量）:
[TOOL STATS]   2种退化的样本 (共45个):
[TOOL STATS]     少调用: 12/45 = 0.267
[TOOL STATS]     刚好: 28/45 = 0.622
[TOOL STATS]     多调用: 5/45 = 0.111
```

**如果输出是：**
```
[TOOL STATS]   2种退化的样本 (共0个):
```
- ⚠️ 批次中没有2种或3种退化的样本
- 检查数据集的退化分布

---

#### 日志3: 指标收集

```bash
grep "收集了.*工具数量匹配指标" logs/*.log
```

**期望输出：**
```
[METRICS] 收集了 48 个工具-退化匹配指标 + 14 个工具数量匹配指标
```

**如果输出是：**
```
[METRICS] 收集了 48 个工具-退化匹配指标 + 0 个工具数量匹配指标
```
- ❌ 指标没有被正确添加到 batch.batch
- 需要检查代码逻辑

---

## 步骤2️⃣: 检查数据集

### 问题：批次中没有2种或3种退化的样本

#### 查看数据分布

在训练日志中查找：

```bash
grep "真实退化类型" logs/*.log | head -20
```

**期望看到：**
```
[TOOL STATS] 样本0: 真实退化类型 ['rain', 'haze'] (来源: reward_model)
[TOOL STATS] 样本1: 真实退化类型 ['rain', 'haze', 'noise'] (来源: reward_model)
[TOOL STATS] 样本2: 真实退化类型 ['dark', 'motion blur'] (来源: env_name)
```

**如果看到：**
```
[TOOL STATS] 样本0: 真实退化类型 [] (来源: env_name)
[TOOL STATS] 样本1: 真实退化类型 ['rain'] (来源: reward_model)
[TOOL STATS] 样本2: 真实退化类型 ['rain', 'haze', 'noise', 'dark'] (来源: reward_model)
```

**问题诊断：**
- 样本0：clean样本，不统计 ✓
- 样本1：1种退化，不统计（只统计2种和3种）⚠️
- 样本2：4种退化，不统计（只统计2种和3种）⚠️

**解决方法：** 
- 检查数据集是否有足够的2种和3种退化的样本
- 或者扩展统计范围（见下文）

---

## 步骤3️⃣: 验证代码逻辑

### 添加调试日志

在 `parallel_env.py` 第376-391行附近，添加计数验证：

```python
# 在 if num_degradations == 2: 之前
print(f"[DEBUG] 样本{idx}: 退化数={num_degradations}, 匹配工具数={num_matched_tools}")

if num_degradations == 2:
    print(f"[DEBUG] 样本{idx}: 分类到 deg2")
    tool_count_match_stats['deg2']['total'] += 1
    ...
elif num_degradations == 3:
    print(f"[DEBUG] 样本{idx}: 分类到 deg3")
    ...
else:
    print(f"[DEBUG] 样本{idx}: 退化数={num_degradations}，不统计")
```

---

## 步骤4️⃣: 检查 WandB 上传

### 确认指标在 batch 中

在 `ray_trainer.py` 中，在 `compute_agent_metrics` 调用后添加日志：

```python
# ray_trainer.py 第1339行附近
agent_metrics = compute_agent_metrics(batch=batch)
print(f"[DEBUG] agent_metrics keys: {list(agent_metrics.keys())}")

# 查找 tool_count_match
tool_count_keys = [k for k in agent_metrics.keys() if 'tool_count_match' in k]
print(f"[DEBUG] tool_count_match keys: {tool_count_keys}")

metrics.update(agent_metrics)
```

---

## 🔧 可能的问题和解决方案

### 问题1: 数据集中没有2种或3种退化的样本

**检查方法：**
```bash
grep "tool_count_match_stats\['deg2'\]\['total'\]" logs/*.log
```

**如果总是0：**
- 数据集主要是单退化或4+退化
- 需要调整数据集或扩展统计范围

**解决方案：** 扩展统计范围（支持1-4种退化）

```python
# 修改 parallel_env.py 第324-327行
tool_count_match_stats = {
    'deg1': {'less': 0, 'exact': 0, 'more': 0, 'total': 0},  # 1种退化
    'deg2': {'less': 0, 'exact': 0, 'more': 0, 'total': 0},  # 2种退化
    'deg3': {'less': 0, 'exact': 0, 'more': 0, 'total': 0},  # 3种退化
    'deg4': {'less': 0, 'exact': 0, 'more': 0, 'total': 0},  # 4种退化
}

# 并在第376行附近添加
if num_degradations == 1:
    tool_count_match_stats['deg1']['total'] += 1
    ...
elif num_degradations == 4:
    tool_count_match_stats['deg4']['total'] += 1
    ...
```

---

### 问题2: 指标没有被添加到返回字典

**检查方法：**
```python
# 在 parallel_env.py 第500行 return results 之前添加
print(f"[DEBUG] compute_tool_degradation_matching_stats 返回的keys:")
for key in sorted(results.keys()):
    if 'tool_count_match' in key:
        print(f"[DEBUG]   {key} = {results[key]}")
```

---

### 问题3: 指标被过滤掉了

**检查 metric_utils.py：**

确认第214-219行正确收集了 `tool_count_match/`：

```python
tool_count_match_keys = [key for key in batch.batch.keys() if key.startswith('tool_count_match/')]

for key in tool_count_match_keys:
    tensor = batch.batch.pop(key).detach().cpu()
    metrics[key] = tensor[0, 0].item() if tensor.numel() > 0 else 0.0
```

**添加调试：**
```python
print(f"[DEBUG METRICS] batch.batch 中的 tool_count_match keys: {tool_count_match_keys}")
```

---

## 🎯 快速诊断脚本

### 创建诊断脚本

```bash
cat > debug_tool_count_match.sh << 'EOF'
#!/bin/bash

LOG_FILE="$1"

echo "=== 诊断 tool_count_match 指标 ==="

echo -e "\n1. 检查统计函数是否执行:"
grep "tool_degradation_stats 返回了" "$LOG_FILE" | tail -5

echo -e "\n2. 检查 tool_count_match 指标数量:"
grep "tool_count_match/ 指标:" "$LOG_FILE" | tail -5

echo -e "\n3. 检查样本分布:"
grep "种退化的样本 (共" "$LOG_FILE" | tail -10

echo -e "\n4. 检查指标收集:"
grep "工具数量匹配指标" "$LOG_FILE" | tail -5

echo -e "\n5. 检查数据集退化类型:"
grep "真实退化类型" "$LOG_FILE" | head -20

echo -e "\n=== 诊断完成 ==="
EOF

chmod +x debug_tool_count_match.sh
./debug_tool_count_match.sh logs/your_experiment.log
```

---

## 💡 最可能的原因

### 原因1: 数据集中2种和3种退化的样本很少

**验证：**
```bash
grep "种退化的样本 (共" logs/*.log
```

如果看到：
```
[TOOL STATS]   2种退化的样本 (共0个):
[TOOL STATS]   3种退化的样本 (共0个):
```

**解决方案：** 扩展统计范围，支持更多退化数量

---

### 原因2: 指标键名有问题

**验证：**
```bash
grep "tool_count_match 指标示例" logs/*.log
```

应该看到：
```
[DEBUG STATS] tool_count_match 指标示例: ['tool_count_match/deg2_less_ratio', ...]
```

---

## ✅ 临时解决方案（扩展统计范围）

如果你的数据集主要是1种、4种退化，可以快速修改代码支持：

<function_calls>
<invoke name="read_file">
<parameter name="target_file">/app/xiaominl/DeepEyes_v2/verl/workers/agent/parallel_env.py
