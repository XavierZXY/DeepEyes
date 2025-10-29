# V8分支需要的所有修复

## 🎯 现状

**当前分支**: `air_v8-2`
**代码状态**: 不包含今天在air_v7上做的任何修复

---

## ❌ V8分支存在的所有问题

### 问题1: 工具链执行模式（旧的逐个执行）🔴

**当前代码**:
```python
# parallel_env.py execute_tool_call
for i, tool in enumerate(tools):
    tool_result = tool.execute(...)
    final_tool_result = tool_result  # 覆盖上一个
```

**问题**: 
- 逐个执行，不是工具链模式
- 每个工具在上一个结果上处理
- 不符合规划-执行-评估模式

**需要**: 改为从原图开始的工具链执行

---

### 问题2: fetch_image污染整个image_history 🔴

**当前代码**:
```python
# 初始化（reset）
image_history = [deepcopy(multi_modal_data)]  # ❌ fetch后的

# 工具执行后保存
self.multi_modal_data_history_list[idx].append(
    deepcopy(obs['multi_modal_data'])  # ❌ 也是fetch后的
)
```

**问题**:
- image_history全部是fetch_image处理后的
- reward计算时尺寸不准确

**需要**: 
- 初始化用`origin_multi_modal_data`
- 保存`multi_modal_data_for_reward`（原始PIL）

---

### 问题3: GT原图索引错位 🔴

**当前代码**:
```python
# 构建original_images
for i in range(expected_size):
    extra_info = saved_extra_info_list[i]  # 直接用i

# 添加extra_info
for i in range(expected_size):
    orig_idx = i // sampling_params.n  # 用interleave
    extra_info_array[i] = saved_extra_info_list[orig_idx]
```

**问题**: 
- 两者索引逻辑不一致
- 导致GT和复原图来自不同样本

**需要**: 统一索引逻辑，自动检测是否需要interleave

---

### 问题4: Reward计算使用fetch_image 🔴

**文件**: `verl/utils/reward_score/image_restoration.py`

**问题**:
- 复原图和GT原图都使用fetch_image
- 导致尺寸padding，对齐不准

**需要**: 移除所有fetch_image，直接使用PIL

---

### 问题5: 工具调用统计不准确 🟡

**当前代码**:
```python
if parsed_action.get('tool_calls'):
    tool_call_cnt += 1  # 只要有就计数
```

**问题**: 不管工具是否成功执行都计数

**需要**: 检查executed_tools，只有成功才计数

---

## 📝 需要应用的所有修复

### 文件1: `verl/workers/agent/parallel_env.py`

| 修复 | 位置 | 说明 |
|------|------|------|
| 工具链执行 | execute_tool_call整个函数 | 从原图开始执行工具链 |
| 数据传递 | agent_inputs构建 | 添加origin_multi_modal_data和raw_prompt |
| 保存原始PIL | execute_tool_call返回 | 添加multi_modal_data_for_reward |
| 历史保存 | step函数 | 优先保存multi_modal_data_for_reward |
| 初始化修复 | reset函数 | 用origin_multi_modal_data |
| GT索引修复 | original_images构建 | 统一索引逻辑 |
| extra_info索引 | extra_info添加 | 移除interleave逻辑 |
| 统计逻辑 | tool_call_cnt | 检查executed_tools |
| 尺寸检测 | 整个agent_rollout_loop | 添加size_anomaly_records |

### 文件2: `verl/utils/reward_score/image_restoration.py`

| 修复 | 位置 | 说明 |
|------|------|------|
| 移除fetch (复原图) | 889-892行 | 直接使用PIL |
| 移除fetch (GT原图) | 943-954行 | 直接使用PIL |

### 文件3: `verl/utils/tracking_image_utils.py`

| 修复 | 位置 | 说明 |
|------|------|------|
| 移除fetch (tracking) | 1784-1797行 | 直接使用PIL |

---

## 🚀 建议方案

### 方案1: 不修改v8，使用v7训练（推荐）

```bash
# v7已经包含所有修复（虽然没提交，但在工作目录）
git checkout air_v7
git stash pop  # 如果有stash

# 运行训练
bash examples/agent/IRv2.sh
```

### 方案2: 将所有修复复制到v8

这需要大量工作，因为有8个主要修改点。

---

## ✅ 总结

**v8分支状态**: ❌ 包含所有今天发现的问题
**v7分支状态**: ✅ 所有修复已完成（在工作目录，未提交）

**建议**: 
1. 在v7上提交所有修改
2. 然后从v7创建v8，或将v7合并到v8

