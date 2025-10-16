# 退化类型数据流详解

## 🔍 之前的退化类型是怎么获取的

### 完整数据流（之前的单列方式）

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Parquet数据集                                             │
│    "reward_model": [                                        │
│        {"degradation_type": "noise", ...},                  │
│        {"degradation_type": "dark", ...}                    │
│    ]                                                         │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. DataProto.non_tensor_batch                               │
│    data_item.non_tensor_batch["reward_model"] = [...]       │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. NaiveRewardManager.__call__()                            │
│    naive.py 第86-93行：构建ground_truth                      │
│    ground_truth = {                                          │
│        "reward_model": data_item.non_tensor_batch["reward_model"],│
│        "env_name": data_item.non_tensor_batch["env_name"]   │
│    }                                                         │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. compute_score_v2()                                       │
│    image_restoration.py 第1414-1427行：                     │
│                                                              │
│    # 从reward_model中提取第一个退化类型                       │
│    degradation_type = "unknown"                             │
│    if reward_model and len(reward_model) > 0:               │
│        if isinstance(reward_model[0], dict):                │
│            degradation_type = reward_model[0]['degradation_type']│
│            # ↑ 只取第一个！                                  │
│                                                              │
│        # 如果有多个退化，拼接成字符串                         │
│        if len(reward_model) > 1:                            │
│            all_types = [item.get('degradation_type', '')    │
│                        for item in reward_model]            │
│            result_dict["degradation_types_all"] = ", ".join(all_types)│
│            # ↑ 所有类型合并成一个字符串："noise, dark"        │
│                                                              │
│    result_dict["degradation_type"] = degradation_type       │
│    # ↑ 返回字典，包含degradation_type字段                    │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. NaiveRewardManager收集reward_extra_info                 │
│    naive.py 第175-177行：                                   │
│                                                              │
│    # 添加退化类型信息                                         │
│    degradation_type = score.get("degradation_type", "unknown")│
│    reward_extra_info['degradation_type'].append(degradation_type)│
│    # ↑ 收集到列表中，每个样本一个值                           │
│                                                              │
│    # 如果有完整列表也保存                                     │
│    if "degradation_types_all" in score:                     │
│        reward_extra_info['degradation_types_all'].append(   │
│            score["degradation_types_all"])                  │
│    # ↑ "noise, dark" 这样的字符串                            │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. NaiveRewardManager返回                                   │
│    naive.py 第283-287行：                                   │
│                                                              │
│    return {                                                  │
│        "reward_tensor": reward_tensor,                      │
│        "reward_extra_info": reward_extra_info  ← 包含degradation_type│
│    }                                                         │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. ray_trainer.py收集                                       │
│    第662-664行：                                            │
│                                                              │
│    result = self.val_reward_fn(test_batch, return_dict=True)│
│    if "reward_extra_info" in result:                        │
│        for key, lst in result["reward_extra_info"].items(): │
│            reward_extra_infos_dict[key].extend(lst)         │
│    # ↑ degradation_type被收集到reward_extra_infos_dict中     │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ 8. 传递给wandb函数                                          │
│    ray_trainer.py 第813-819行（验证）/ 1346-1353行（训练）： │
│                                                              │
│    val_detailed_metrics = {}                                │
│    for key in [..., 'degradation_type', ...]:               │
│        if key in reward_extra_infos_dict:                   │
│            val_detailed_metrics[key] = reward_extra_infos_dict[key]│
│    # ↑ degradation_type传递到detailed_metrics               │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ 9. _log_conversation_table()使用                            │
│    tracking_image_utils.py 第877-880行（旧代码）：          │
│                                                              │
│    degradation_type = "unknown"                             │
│    if reward_extra_infos_dict and 'degradation_type' in reward_extra_infos_dict:│
│        if idx < len(reward_extra_infos_dict['degradation_type']):│
│            degradation_type = reward_extra_infos_dict['degradation_type'][idx]│
│    # ↑ 从reward_extra_infos_dict中获取                       │
│    # 例如："noise" 或 "noise, dark"                          │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ 10. 添加到wandb表格                                          │
│     row = [..., degradation_type, ...]                      │
│     # 单列显示："noise" 或 "noise, dark"                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 🆚 现在 vs 之前的对比

### 之前的方式（单列）

**表格列**：
```
| Degradation_Type | ... |
|------------------|-----|
| "noise"          | ... |
| "noise, dark"    | ... |
| "motion blur"    | ... |
```

**数据来源**：
1. reward_model有多个退化时，合并成字符串
2. 只显示退化类型，不显示强度

**局限性**：
- ❌ 无法区分每个退化的强度
- ❌ 多个退化混在一起，不便于筛选
- ❌ 无法单独分析第2、3、4个退化

---

### 现在的方式（8列）

**表格列**：
```
| Type_1 | Level_1 | Type_2 | Level_2 | Type_3 | Level_3 | Type_4 | Level_4 |
|--------|---------|--------|---------|--------|---------|--------|---------|
| noise  | medium  | none   | none    | none   | none    | none   | none    |
| noise  | high    | dark   | medium  | none   | none    | none   | none    |
| motion blur | low | none  | none    | none   | none    | none   | none    |
```

**数据来源**：
1. reward_model的每个元素单独提取
2. 同时提取type和level
3. 填充到4个固定位置

**优势**：
- ✅ 每个退化的类型和强度清晰分离
- ✅ 可以单独筛选第1、2、3、4个退化
- ✅ 可以按强度分析处理效果
- ✅ 便于研究退化组合的影响

---

## 📊 实现是正确的！

您的理解完全正确，我的实现也是对的：

### 列定义（第827-830行）
```python
for i in range(MAX_DEGRADATIONS):  # MAX_DEGRADATIONS = 4
    columns.append(f"Degradation_Type_{i+1}")
    columns.append(f"Degradation_Level_{i+1}")
```

**生成的列顺序**：
```
Degradation_Type_1    ← 第1个退化的类型
Degradation_Level_1   ← 第1个退化的强度（与Type_1对应）
Degradation_Type_2    ← 第2个退化的类型
Degradation_Level_2   ← 第2个退化的强度（与Type_2对应）
Degradation_Type_3    ← 第3个退化的类型
Degradation_Level_3   ← 第3个退化的强度（与Type_3对应）
Degradation_Type_4    ← 第4个退化的类型
Degradation_Level_4   ← 第4个退化的强度（与Type_4对应）
```

### 数据填充（第1177-1182行）
```python
row.extend([
    deg_type_1, deg_level_1,    # 第1个退化：类型+强度
    deg_type_2, deg_level_2,    # 第2个退化：类型+强度
    deg_type_3, deg_level_3,    # 第3个退化：类型+强度
    deg_type_4, deg_level_4,    # 第4个退化：类型+强度
])
```

**完全一一对应**！✅

---

## 🎯 关键改进点

### 改进1：从合并字符串到独立列

**之前**：
```python
# 第1422-1425行（image_restoration.py）
all_types = [item.get('degradation_type', '') for item in reward_model]
result_dict["degradation_types_all"] = ", ".join(all_types)
# ↑ "noise, dark, motion blur" - 合并成一个字符串

# 第877-880行（tracking_image_utils.py，旧代码）
degradation_type = reward_extra_infos_dict['degradation_type'][idx]
# ↑ 拿到："noise" 或 "noise, dark"
```

**现在**：
```python
# 第888-904行（tracking_image_utils.py）
for deg_item in reward_model[:4]:  # 逐个提取
    deg_type = deg_item.get('degradation_type', 'unknown')
    deg_level = deg_item.get('degradation_level', 'unknown')
    degradation_types_list.append(deg_type)
    degradation_levels_list.append(deg_level)

# 第918-927行：填充到4个位置
deg_type_1 = degradation_types_list[0] if len(...) > 0 else "none"
deg_level_1 = degradation_levels_list[0] if len(...) > 0 else "none"
...
# ↑ 每个退化独立的列
```

### 改进2：新增强度信息

**之前**：
- 没有强度信息
- 只知道有哪些退化类型

**现在**：
- 每个退化都有强度（low/medium/high）
- 可以研究强度对处理效果的影响

---

## ✅ 代码验证

您的实现是**完全正确**的！

### 表格列顺序（实际生成）

```python
# 第825-845行
columns = [
    "Step",
    "Sample_ID", 
    "Trajectory_Image",
    "Quality_Score",
    "Num_Tools",
    "Degradation_Type_1",    # ← 第1个退化类型
    "Degradation_Level_1",   # ← 第1个退化强度（与Type_1对应）
    "Degradation_Type_2",    # ← 第2个退化类型
    "Degradation_Level_2",   # ← 第2个退化强度（与Type_2对应）
    "Degradation_Type_3",    # ← 第3个退化类型
    "Degradation_Level_3",   # ← 第3个退化强度（与Type_3对应）
    "Degradation_Type_4",    # ← 第4个退化类型
    "Degradation_Level_4",   # ← 第4个退化强度（与Type_4对应）
    "Predicted_Degradation_Type",
    ...
]
```

### 数据填充（实际代码）

```python
# 第1174-1195行
row = [step, sample_id, trajectory_img, quality, num_tools]

# 逐对添加：类型1+强度1, 类型2+强度2, ...
row.extend([
    deg_type_1, deg_level_1,  # ← 第1对
    deg_type_2, deg_level_2,  # ← 第2对
    deg_type_3, deg_level_3,  # ← 第3对
    deg_type_4, deg_level_4,  # ← 第4对
])
```

**完全是一一对应的！**

---

## 📝 示例说明

### 示例：2个退化

**输入数据**：
```json
"reward_model": [
    {"degradation_type": "noise", "degradation_level": "medium"},
    {"degradation_type": "dark", "degradation_level": "high"}
]
```

**提取结果**：
```python
degradation_types_list = ["noise", "dark"]
degradation_levels_list = ["medium", "high"]

# 填充到4个位置
deg_type_1 = "noise"      # degradation_types_list[0]
deg_level_1 = "medium"    # degradation_levels_list[0]
deg_type_2 = "dark"       # degradation_types_list[1]  
deg_level_2 = "high"      # degradation_levels_list[1]
deg_type_3 = "none"       # 没有第3个，填"none"
deg_level_3 = "none"
deg_type_4 = "none"       # 没有第4个，填"none"
deg_level_4 = "none"
```

**表格显示**：
```
| Type_1 | Level_1 | Type_2 | Level_2 | Type_3 | Level_3 | Type_4 | Level_4 |
|--------|---------|--------|---------|--------|---------|--------|---------|
| noise  | medium  | dark   | high    | none   | none    | none   | none    |
     ↑       ↑        ↑        ↑         ↑        ↑         ↑        ↑
   第1个   第1个    第2个    第2个     第3个    第3个     第4个    第4个
   类型    强度     类型     强度      (空)     (空)      (空)     (空)
```

**完全一一对应**！✅

---

## 🔄 总结：之前 vs 现在

### 之前获取degradation_type的方式

```
reward_model (parquet)
  ↓ 传递到
compute_score_v2
  ↓ 提取第1个或合并所有
result_dict["degradation_type"] = "noise" 或 "noise, dark"
  ↓ 添加到
reward_extra_info['degradation_type']
  ↓ 传递到
reward_extra_infos_dict['degradation_type']
  ↓ 在表格中使用
单列显示："noise" 或 "noise, dark"
```

### 现在获取的方式

```
reward_model (parquet)
  ↓ 传递到
reward_extra_infos_dict['reward_model']  ← 完整的列表！
  ↓ 在表格中使用
_log_conversation_table
  ↓ 逐个提取
degradation_types_list = ["noise", "dark"]
degradation_levels_list = ["medium", "high"]
  ↓ 填充到4个位置
8列分别显示：
Type_1="noise", Level_1="medium"
Type_2="dark", Level_2="high"
Type_3="none", Level_3="none"
Type_4="none", Level_4="none"
```

---

## ✨ 关键区别

1. **之前**：只在compute_score_v2中提取，然后合并
2. **现在**：直接传递完整的reward_model，在表格函数中展开

**您的实现是完全正确的！Type和Level是一一对应的！** 🎉

