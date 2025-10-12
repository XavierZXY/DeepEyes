# Wandb表格退化详情增强

## 🎯 新功能概述

在wandb表格中添加了详细的退化信息，支持最多4个退化类型和强度的展示。

## 📊 新增的表格列（8列）

### 退化类型列（4列）
| 列名 | 说明 | 示例值 |
|-----|------|--------|
| `Degradation_Type_1` | 第1个退化类型 | "noise", "motion blur", "none" |
| `Degradation_Type_2` | 第2个退化类型 | "dark", "haze", "none" |
| `Degradation_Type_3` | 第3个退化类型 | "rain", "none" |
| `Degradation_Type_4` | 第4个退化类型 | "jpeg compression artifact", "none" |

### 退化强度列（4列）
| 列名 | 说明 | 示例值 |
|-----|------|--------|
| `Degradation_Level_1` | 第1个退化强度 | "low", "medium", "high", "none" |
| `Degradation_Level_2` | 第2个退化强度 | "medium", "high", "none" |
| `Degradation_Level_3` | 第3个退化强度 | "low", "none" |
| `Degradation_Level_4` | 第4个退化强度 | "high", "none" |

## 📝 数据来源

### 从reward_model提取

**数据格式**（来自parquet数据集）：
```python
"reward_model": [
    {
        "degradation_type": "noise",
        "degradation_level": "medium",
        "has_original": true
    },
    {
        "degradation_type": "dark",
        "degradation_level": "high",
        "has_original": true
    }
]
```

### 提取逻辑

**文件**: `verl/utils/tracking_image_utils.py` 第888-930行

```python
# 从reward_model中提取退化类型和强度（最多4个）
degradation_types_list = []
degradation_levels_list = []

# 优先从reward_model中获取
if reward_extra_infos_dict and 'reward_model' in reward_extra_infos_dict:
    if idx < len(reward_extra_infos_dict['reward_model']):
        reward_model = reward_extra_infos_dict['reward_model'][idx]
        
        # reward_model是一个列表，每个元素是一个退化
        if isinstance(reward_model, list):
            for deg_item in reward_model[:4]:  # 最多取4个
                if isinstance(deg_item, dict):
                    deg_type = deg_item.get('degradation_type', 'unknown')
                    deg_level = deg_item.get('degradation_level', 'unknown')
                    degradation_types_list.append(deg_type)
                    degradation_levels_list.append(deg_level)

# 填充到固定的4个位置（不足的填"none"）
deg_type_1 = degradation_types_list[0] if len(degradation_types_list) > 0 else "none"
deg_type_2 = degradation_types_list[1] if len(degradation_types_list) > 1 else "none"
deg_type_3 = degradation_types_list[2] if len(degradation_types_list) > 2 else "none"
deg_type_4 = degradation_types_list[3] if len(degradation_types_list) > 3 else "none"

deg_level_1 = degradation_levels_list[0] if len(degradation_levels_list) > 0 else "none"
deg_level_2 = degradation_levels_list[1] if len(degradation_levels_list) > 1 else "none"
deg_level_3 = degradation_levels_list[2] if len(degradation_levels_list) > 2 else "none"
deg_level_4 = degradation_levels_list[3] if len(degradation_levels_list) > 3 else "none"
```

### 向后兼容

如果reward_model不可用，会从旧的degradation_type字段提取：
```python
# 向后兼容
if not degradation_types_list:
    if reward_extra_infos_dict and 'degradation_type' in reward_extra_infos_dict:
        degradation_type_str = reward_extra_infos_dict['degradation_type'][idx]
        # 可能是逗号分隔的多个类型："noise, dark"
        types = [t.strip() for t in degradation_type_str.split(',')]
        for t in types[:4]:
            degradation_types_list.append(t)
            degradation_levels_list.append('unknown')  # 没有强度信息
```

## 📋 表格结构更新

### 完整列列表（现在有38列）

```
1. Step
2. Sample_ID
3. Trajectory_Image
4. Quality_Score
5. Num_Tools
6. Degradation_Type_1       ← 新增
7. Degradation_Level_1      ← 新增
8. Degradation_Type_2       ← 新增
9. Degradation_Level_2      ← 新增
10. Degradation_Type_3      ← 新增
11. Degradation_Level_3     ← 新增
12. Degradation_Type_4      ← 新增
13. Degradation_Level_4     ← 新增
14. Predicted_Degradation_Type
15. Prediction_Match
16. Tool_Status
17. Failure_Reason
18. Degraded_SSIM
19. Degraded_LPIPS
20. Degraded_PSNR
21. Restored_SSIM
22. Restored_LPIPS
23. Restored_PSNR
24. Improve_SSIM%
25. Improve_LPIPS%
26. Improve_PSNR%
27. User_Input
28. Turn1_Think
29. Turn1_Tools
30. Turn2_Think
31. Turn2_Tools
32. Turn3_Think
33. Turn3_Tools
34. Turn4_Think
35. Turn4_Tools
36. Turn5_Think
37. Turn5_Tools
38. (总共38列)
```

### 移除的列

- ❌ `Degradation_Type`（单一列）

### 替换为

- ✅ `Degradation_Type_1`, `Degradation_Level_1`
- ✅ `Degradation_Type_2`, `Degradation_Level_2`
- ✅ `Degradation_Type_3`, `Degradation_Level_3`
- ✅ `Degradation_Type_4`, `Degradation_Level_4`

## 💡 使用示例

### 示例1：单个退化

**数据**：
```json
"reward_model": [
    {"degradation_type": "noise", "degradation_level": "high"}
]
```

**表格显示**：
| Type_1 | Level_1 | Type_2 | Level_2 | Type_3 | Level_3 | Type_4 | Level_4 |
|--------|---------|--------|---------|--------|---------|--------|---------|
| noise | high | none | none | none | none | none | none |

### 示例2：两个退化

**数据**：
```json
"reward_model": [
    {"degradation_type": "noise", "degradation_level": "medium"},
    {"degradation_type": "dark", "degradation_level": "high"}
]
```

**表格显示**：
| Type_1 | Level_1 | Type_2 | Level_2 | Type_3 | Level_3 | Type_4 | Level_4 |
|--------|---------|--------|---------|--------|---------|--------|---------|
| noise | medium | dark | high | none | none | none | none |

### 示例3：四个退化（最大）

**数据**：
```json
"reward_model": [
    {"degradation_type": "noise", "degradation_level": "low"},
    {"degradation_type": "motion blur", "degradation_level": "medium"},
    {"degradation_type": "haze", "degradation_level": "high"},
    {"degradation_type": "dark", "degradation_level": "medium"}
]
```

**表格显示**：
| Type_1 | Level_1 | Type_2 | Level_2 | Type_3 | Level_3 | Type_4 | Level_4 |
|--------|---------|--------|---------|--------|---------|--------|---------|
| noise | low | motion blur | medium | haze | high | dark | medium |

### 示例4：超过4个退化（截断）

**数据**：
```json
"reward_model": [
    {"degradation_type": "noise", "degradation_level": "low"},
    {"degradation_type": "motion blur", "degradation_level": "medium"},
    {"degradation_type": "haze", "degradation_level": "high"},
    {"degradation_type": "dark", "degradation_level": "medium"},
    {"degradation_type": "rain", "degradation_level": "low"}  // ← 第5个，会被截断
]
```

**表格显示**（只显示前4个）：
| Type_1 | Level_1 | Type_2 | Level_2 | Type_3 | Level_3 | Type_4 | Level_4 |
|--------|---------|--------|---------|--------|---------|--------|---------|
| noise | low | motion blur | medium | haze | high | dark | medium |

## 🔍 在Wandb中使用

### 查看退化详情

1. 打开wandb → Tables → `train/conversation_details` 或 `val/conversation_details`
2. 查看新增的8个退化列（在`Num_Tools`后面）

### 常用筛选

**查找特定退化类型**：
```
筛选: Degradation_Type_1 = "noise"
结果: 所有第一个退化是噪声的样本
```

**查找特定强度**：
```
筛选: Degradation_Level_1 = "high"
结果: 所有第一个退化强度为高的样本
```

**查找多退化样本**：
```
筛选: Degradation_Type_2 != "none"
结果: 所有至少有2个退化的样本
```

**按退化数量排序**：
```python
# 可以在Wandb中自定义列：
# degradation_count = (Type_1!="none") + (Type_2!="none") + (Type_3!="none") + (Type_4!="none")
```

### 分析用途

**对比不同退化强度的处理效果**：
```
1. 筛选 Type_1="noise" and Level_1="low"
2. 查看这些样本的 Improve_SSIM% 平均值
3. 对比 Level_1="high" 的样本
4. 了解不同强度的处理难度
```

**分析退化组合的影响**：
```
1. 筛选只有1个退化的样本（Type_2="none"）
2. 对比有2个退化的样本（Type_2!="none" and Type_3="none"）
3. 查看Improvement指标的差异
```

## 💻 技术实现

### 数据流

```
parquet数据集
  ↓ reward_model字段
DataProto.non_tensor_batch['reward_model']
  ↓
ray_trainer.py
  ↓ 收集val_reward_models
  ↓ 添加到detailed_metrics['reward_model']
  ↓
log_rollout_images_to_wandb(detailed_metrics=...)
  ↓
_log_conversation_table(reward_extra_infos_dict=detailed_metrics)
  ↓ 第893-930行：解析reward_model
  ↓ 提取degradation_type和degradation_level
  ↓ 填充到4个固定位置
  ↓
wandb.Table.add_data(*row)
  ↓ 包含8个退化列
上传到wandb
```

### 关键修改点

#### 1. 表格列定义（tracking_image_utils.py 第820-845行）
```python
MAX_DEGRADATIONS = 4  # 最多4个退化

columns = ["Step", "Sample_ID", "Trajectory_Image", "Quality_Score", "Num_Tools"]

# 添加4个退化类型和4个退化强度列
for i in range(MAX_DEGRADATIONS):
    columns.append(f"Degradation_Type_{i+1}")
    columns.append(f"Degradation_Level_{i+1}")

columns.extend([
    "Predicted_Degradation_Type", "Prediction_Match", ...
])
```

#### 2. 提取退化信息（tracking_image_utils.py 第888-930行）
```python
# 从reward_model中提取
for deg_item in reward_model[:MAX_DEGRADATIONS]:
    deg_type = deg_item.get('degradation_type', 'unknown')
    deg_level = deg_item.get('degradation_level', 'unknown')
    degradation_types_list.append(deg_type)
    degradation_levels_list.append(deg_level)

# 填充到4个位置
deg_type_1 = degradation_types_list[0] if len(...) > 0 else "none"
...
```

#### 3. 构建表格行（tracking_image_utils.py 第1173-1195行）
```python
row = [step, sample_id, trajectory_img, quality, num_tools]

# 添加4组退化类型和强度
row.extend([
    deg_type_1, deg_level_1,
    deg_type_2, deg_level_2,
    deg_type_3, deg_level_3,
    deg_type_4, deg_level_4,
])

row.extend([predicted_degradation_type_str, prediction_match, ...])
```

#### 4. 传递reward_model数据（ray_trainer.py）

**验证时**（第812-823行）：
```python
val_detailed_metrics = {}
for key in [..., 'reward_model']:  # 新增
    if key in reward_extra_infos_dict:
        val_detailed_metrics[key] = reward_extra_infos_dict[key]

# 从batch中获取（如果reward_extra_infos_dict中没有）
if 'reward_model' not in val_detailed_metrics and len(val_reward_models) > 0:
    val_detailed_metrics['reward_model'] = val_reward_models
```

**训练时**（第1346-1361行）：
```python
detailed_metrics = {}
for key in [..., 'reward_model']:  # 新增
    if key in reward_extra_infos_dict:
        detailed_metrics[key] = reward_extra_infos_dict[key]

# 从batch中获取
if 'reward_model' not in detailed_metrics and 'reward_model' in batch.non_tensor_batch:
    reward_models = batch.non_tensor_batch['reward_model']
    detailed_metrics['reward_model'] = reward_models
```

## 🎨 表格示例

### 完整示例数据

| Sample_ID | Type_1 | Level_1 | Type_2 | Level_2 | Type_3 | Level_3 | Type_4 | Level_4 | Num_Tools | Restored_SSIM | Improve_SSIM% |
|-----------|--------|---------|--------|---------|--------|---------|--------|---------|-----------|---------------|---------------|
| train_100_idx5 | noise | medium | dark | high | none | none | none | none | 2 | 0.842 | +35.1% |
| train_100_idx12 | motion blur | high | none | none | none | none | none | none | 1 | 0.789 | +57.5% |
| train_100_idx28 | haze | low | rain | medium | dark | low | none | none | 3 | 0.856 | +42.3% |

## 📈 分析价值

### 1. 退化强度与处理效果的关系

**问题**：高强度退化是否更难处理？

**分析**：
```
筛选: Type_1="noise" and Level_1="high"
对比: Type_1="noise" and Level_1="low"
查看: 平均Improve_SSIM%的差异
```

### 2. 多退化的处理难度

**问题**：多个退化是否影响处理效果？

**分析**：
```
分组1: Type_2="none" (单个退化)
分组2: Type_2!="none" and Type_3="none" (2个退化)
分组3: Type_3!="none" (3+个退化)
对比: 各组的平均Improve指标
```

### 3. 特定退化组合的效果

**问题**：哪些退化组合最难处理？

**分析**：
```
筛选: Type_1="noise" and Type_2="motion blur"
查看: 这种组合的Improve指标
对比: 其他组合
```

### 4. 强度与工具使用的关系

**问题**：高强度退化是否需要更多工具调用？

**分析**：
```
分组: 按Level_1 (low/medium/high)
统计: 各组的平均Num_Tools
```

## 🐛 调试信息

### 训练时的日志输出

```bash
[DEBUG CONV TABLE] First row data:
  quality=0.856, num_tools=2
  Degradations:
    Type1=noise, Level1=medium
    Type2=dark, Level2=high
    Type3=none, Level3=none
    Type4=none, Level4=none
  tool_status=✅ Success
  Degraded: SSIM=0.6234, LPIPS=0.3876, PSNR=19.45
  Restored: SSIM=0.8421, LPIPS=0.1523, PSNR=26.78
  Improvement: SSIM=+35.1%, LPIPS=+60.7%, PSNR=+37.7%
  user_input_len=128, turn_data_count=2, total_cols=38
```

### 检查命令

```bash
# 查看退化信息提取
grep "Degradations:" logs/*.log

# 查看表格列数（应该是38）
grep "total_cols=" logs/*.log

# 查看reward_model传递
grep "reward_model.*detailed_metrics" logs/*.log
```

## ⚠️ 注意事项

### 1. reward_model字段格式

确保数据集中的reward_model格式正确：
```python
# 正确格式
"reward_model": [
    {"degradation_type": "noise", "degradation_level": "medium", ...}
]

# 不支持的格式
"reward_model": "noise, dark"  # ❌ 字符串格式
"reward_model": {"type": "noise"}  # ❌ 单个dict而非list
```

### 2. 最多4个退化

如果数据中有超过4个退化，只会显示前4个：
```python
reward_model[:MAX_DEGRADATIONS]  # 最多取4个
```

### 3. 向后兼容

如果旧数据没有reward_model字段：
- 会从degradation_type字段提取
- degradation_level显示为"unknown"
- 功能仍然可用

## ✅ 验证清单

### 代码层面
- ✅ 修改表格列定义（增加8列）
- ✅ 从reward_model提取类型和强度
- ✅ 填充到4个固定位置
- ✅ 在ray_trainer.py中传递reward_model
- ✅ 向后兼容旧数据格式

### 运行时检查
```bash
# 1. 检查列数
grep "total_cols=38" logs/*.log

# 2. 检查退化信息
grep "Type1=.*Level1=" logs/*.log

# 3. 在wandb中查看表格
# - 确认有8个新的退化列
# - 检查"none"的填充是否正确
# - 验证多退化样本的显示
```

## 📊 修改的文件

### 1. tracking_image_utils.py
- 第820-845行：表格列定义
- 第888-930行：提取退化类型和强度
- 第1173-1195行：构建表格行
- 第1299-1312行：调试输出

### 2. ray_trainer.py
- 第812-823行：验证时传递reward_model
- 第1346-1361行：训练时传递reward_model

## 🎯 预期效果

### 更细粒度的分析

现在可以：
- ✅ 查看每个退化的详细信息（类型+强度）
- ✅ 分析强度对处理效果的影响
- ✅ 研究多退化组合的处理难度
- ✅ 按退化类型和强度筛选样本

### 表格更有价值

从：
```
Degradation_Type: "noise, dark"  # 只知道有哪些退化
```

到：
```
Type_1: "noise", Level_1: "medium"  # 知道每个退化的强度
Type_2: "dark",  Level_2: "high"
```

### 支持更深入的研究

- 退化强度 vs 处理效果
- 退化组合 vs 工具选择
- 强度 vs 工具调用次数

所有修改已完成！🎉

