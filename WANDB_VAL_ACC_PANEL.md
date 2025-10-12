# WandB Validation准确率Panel (val-acc)

## 🎯 功能说明

在validation阶段自动计算退化类型预测准确率，并上传到WandB的 `val-acc` panel。

---

## 📊 指标体系

### 1. 总体准确率
```
val-acc/overall_accuracy      # 所有样本的准确率
val-acc/total_samples          # 总样本数（排除clean样本）
```

**计算方式**: 预测的退化类型集合 == GT退化类型集合的比例

---

### 2. 按退化类型统计（不考虑等级）
```
val-acc/by_type/noise                  # noise类型的准确率
val-acc/by_type/noise_samples          # noise类型的样本数
val-acc/by_type/dark                   # dark类型的准确率
val-acc/by_type/dark_samples           # dark类型的样本数
val-acc/by_type/motion_blur            # motion blur类型的准确率
val-acc/by_type/motion_blur_samples    # motion blur类型的样本数
...
```

**说明**: 
- 每种退化类型的识别准确率
- 只要预测中包含该类型就算正确（不考虑其他类型）

---

### 3. 按等级统计（汇总所有类型）
```
val-acc/by_level/low              # low等级的准确率
val-acc/by_level/low_samples      # low等级的样本数
val-acc/by_level/medium           # medium等级的准确率
val-acc/by_level/medium_samples   # medium等级的样本数
val-acc/by_level/high             # high等级的准确率
val-acc/by_level/high_samples     # high等级的样本数
```

**说明**: 
- 不同退化程度的识别准确率
- 汇总了所有退化类型

---

### 4. 按类型和等级组合统计
```
val-acc/by_level_and_type/noise_low              # noise + low的准确率
val-acc/by_level_and_type/noise_low_samples      # noise + low的样本数
val-acc/by_level_and_type/dark_high              # dark + high的准确率
val-acc/by_level_and_type/dark_high_samples      # dark + high的样本数
val-acc/by_level_and_type/motion_blur_medium     # motion blur + medium的准确率
...
```

**说明**: 
- 最细粒度的统计
- 可以看出哪些类型+等级组合更难识别

---

## 🔧 数据来源

### 1. 预测的退化类型
**来源**: `conversation_history` 中的 `<tool_call>`

```python
# 从对话中提取工具调用
<tool_call>[{"name": "swinir_denoising"}]</tool_call>
<tool_call>[{"name": "constant_shift"}]</tool_call>

# 映射到退化类型
swinir_denoising → "noise"
constant_shift → "dark"

# 结果
predicted = ["noise", "dark"]
```

### 2. GT退化类型和等级
**来源**: 数据集的 `reward_model` 字段

```python
reward_model = [
    {
        "degradation_type": "dark",
        "degradation_level": "high",
        "has_original": True
    },
    {
        "degradation_type": "noise",
        "degradation_level": "low",
        "has_original": True
    }
]

# 提取
gt_types = ["dark", "noise"]
gt_levels = ["high", "low"]
```

---

## 📝 准确率计算示例

### 示例1: 完全正确
```python
GT: ["noise"]
Predicted: ["noise"]
结果: ✅ 正确 (集合相等)
```

### 示例2: 完全错误
```python
GT: ["dark"]
Predicted: ["noise"]
结果: ❌ 错误 (集合不相等)
```

### 示例3: 未预测
```python
GT: ["motion blur"]
Predicted: []  # 没有调用工具
结果: ❌ 错误
```

### 示例4: 多退化类型 - 完全匹配
```python
GT: ["noise", "dark"]
Predicted: ["noise", "dark"]
结果: ✅ 正确 (集合相等，顺序无关)
```

### 示例5: 多退化类型 - 部分匹配
```python
GT: ["noise", "dark"]
Predicted: ["noise"]
结果: ❌ 错误 (集合不完全相等)

# 但在by_type统计中：
# - noise类型: ✅ 正确 (预测中包含noise)
# - dark类型: ❌ 错误 (预测中没有dark)
```

### 示例6: Brightening工具
```python
GT: ["dark"]
Predicted: ["dark"]  # 调用了constant_shift或gamma_correction或histogram_equalization

结果: ✅ 正确 (3个brightening工具都映射到"dark")
```

---

## 🎨 WandB Panel显示

### 在WandB中查看

#### 方法1: 搜索
在WandB搜索框输入：
```
val-acc
```
会显示所有准确率指标。

#### 方法2: 创建Panel

**Panel 1: 总体准确率趋势**
```yaml
Panel Type: Line Chart
Title: Overall Degradation Type Accuracy
X轴: Step
Y轴: val-acc/overall_accuracy
```

**Panel 2: 按类型对比**
```yaml
Panel Type: Line Chart
Title: Accuracy by Degradation Type
X轴: Step
Y轴:
  - val-acc/by_type/noise
  - val-acc/by_type/dark
  - val-acc/by_type/motion_blur
  - val-acc/by_type/rain
  - val-acc/by_type/haze
  - val-acc/by_type/low_resolution
  - val-acc/by_type/defocus_blur
  - val-acc/by_type/jpeg_compression_artifact
```

**Panel 3: 按等级对比**
```yaml
Panel Type: Line Chart
Title: Accuracy by Degradation Level
X轴: Step
Y轴:
  - val-acc/by_level/low
  - val-acc/by_level/medium
  - val-acc/by_level/high
```

**Panel 4: 细粒度热力图**
```yaml
Panel Type: Bar Chart
Title: Accuracy by Type and Level
X轴: 不同的type_level组合
Y轴: 准确率
```

---

## 📊 数据分析示例

### 1. 查看哪些类型最难识别
```python
# 在WandB中比较
val-acc/by_type/noise          # 0.95 ✅ 容易
val-acc/by_type/dark           # 0.92 ✅ 容易
val-acc/by_type/haze           # 0.65 ⚠️ 中等
val-acc/by_type/defocus_blur   # 0.45 ❌ 困难
```

**结论**: defocus_blur最难识别

### 2. 查看退化等级的影响
```python
val-acc/by_level/low     # 0.85
val-acc/by_level/medium  # 0.75
val-acc/by_level/high    # 0.90
```

**结论**: medium等级识别率最低（可能因为退化不明显导致模型犹豫）

### 3. 查看特定组合
```python
val-acc/by_level_and_type/noise_low     # 0.90
val-acc/by_level_and_type/noise_high    # 0.95
val-acc/by_level_and_type/dark_low      # 0.85
val-acc/by_level_and_type/dark_high     # 0.93
```

**结论**: 低等级的退化类型识别率普遍较低

---

## 🔍 特殊处理

### 1. Clean样本过滤
```python
# clean样本会被排除在准确率计算之外
if env_name.strip().lower() == "clean":
    continue  # 跳过
```

**原因**: clean样本没有退化类型，无法计算准确率

### 2. Brightening工具映射
```python
# 3个工具都映射到"dark"
"constant_shift": "dark"
"gamma_correction": "dark"
"histogram_equalization": "dark"
```

**说明**: 这3个工具都用于处理暗图

### 3. 去重处理
```python
# 同一个退化类型只计算一次
Predicted: ["noise"] (来自swinir_denoising和mprnet_denoising)
→ 去重后: {"noise"}
```

### 4. 集合匹配
```python
# 使用集合匹配，顺序无关
GT: ["noise", "dark"]
Predicted: ["dark", "noise"]  # 顺序不同
→ 结果: ✅ 正确 (集合相等)
```

---

## 📂 实现文件

### 1. `verl/utils/degradation_accuracy_utils.py` (新增)
**核心函数**:
```python
compute_degradation_accuracy(
    conversation_histories: List,
    reward_models: List,
    env_names: List
) -> Dict[str, float]
```

**功能**:
- 提取预测的退化类型
- 提取GT退化类型和等级
- 计算各种维度的准确率

### 2. `verl/trainer/ppo/ray_trainer.py` (修改)
**修改位置**:
- 第587-588行: 添加列表收集reward_model和env_name
- 第709-723行: 收集reward_model和env_name数据
- 第786-801行: 计算准确率并添加到metrics

---

## 🧪 测试验证

### 测试数据
```python
conversation_histories = [
    [{'response': '<tool_call>[{"name": "swinir_denoising"}]</tool_call>'}],
    [{'response': '<tool_call>[{"name": "constant_shift"}]</tool_call>'}],
    [{'response': '<answer>{"restoration_log": []}</answer>'}],  # 未预测
]

reward_models = [
    [{"degradation_type": "noise", "degradation_level": "high"}],
    [{"degradation_type": "dark", "degradation_level": "low"}],
    [{"degradation_type": "motion blur", "degradation_level": "medium"}],
]

env_names = ["", "", ""]
```

### 预期结果
```python
{
    'val-acc/overall_accuracy': 0.667,  # 2/3正确
    'val-acc/total_samples': 3,
    'val-acc/by_type/noise': 1.0,       # 1/1
    'val-acc/by_type/dark': 1.0,        # 1/1
    'val-acc/by_type/motion_blur': 0.0, # 0/1
    'val-acc/by_level/high': 1.0,       # noise_high正确
    'val-acc/by_level/low': 1.0,        # dark_low正确
    'val-acc/by_level/medium': 0.0,     # motion_blur_medium错误
    ...
}
```

---

## ✅ 关键要点

1. ✅ **自动计算**: validation结束后自动计算，无需手动触发
2. ✅ **多维度**: 总体、按类型、按等级、按组合
3. ✅ **排除clean**: 自动过滤clean样本
4. ✅ **集合匹配**: 顺序无关，只看类型是否完全匹配
5. ✅ **容错处理**: 计算失败不影响validation流程
6. ✅ **详细日志**: 打印每个类型的准确率和样本数

---

## 📈 预期效果

### 训练初期 (Epoch 1-5)
```
val-acc/overall_accuracy: 0.3 → 0.5
val-acc/by_type/noise: 0.6
val-acc/by_type/dark: 0.4
val-acc/by_type/motion_blur: 0.2  # 较难
```

### 训练中期 (Epoch 5-15)
```
val-acc/overall_accuracy: 0.5 → 0.75
val-acc/by_type/noise: 0.85
val-acc/by_type/dark: 0.75
val-acc/by_type/motion_blur: 0.55  # 逐渐提升
```

### 训练后期 (Epoch 15-32)
```
val-acc/overall_accuracy: 0.75 → 0.90
val-acc/by_type/noise: 0.95
val-acc/by_type/dark: 0.92
val-acc/by_type/motion_blur: 0.80  # 显著提升
```

---

## 🎯 使用建议

### 1. 监控训练进度
观察 `val-acc/overall_accuracy` 是否持续提升

### 2. 识别弱项
找到准确率最低的退化类型，针对性改进：
- 增加该类型的训练数据
- 调整该类型的奖励权重
- 检查工具是否正确注册

### 3. 分析等级影响
对比不同等级的准确率，判断：
- 是否低等级退化难以识别？
- 是否高等级退化识别更容易？

### 4. 对比实验
使用不同配置训练多个实验，对比：
- 不同奖励权重对准确率的影响
- 不同max_turns对准确率的影响
- 启用/禁用退化类型奖励的效果

---

**功能完成日期**: 2025-10-12  
**状态**: ✅ 已实现并测试  
**Panel名称**: `val-acc/*`

