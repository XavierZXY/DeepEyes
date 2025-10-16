# 退化类型顺序奖励完整报告

生成时间：2025-10-11  
基于代码版本：DeepEyes (AIR项目)

---

## 📋 目录

1. [LIFO原则介绍](#lifo原则介绍)
2. [退化类型顺序奖励模式](#退化类型顺序奖励模式)
3. [数据流和顺序转换](#数据流和顺序转换)
4. [详细计算示例](#详细计算示例)
5. [与图像质量奖励的对比](#与图像质量奖励的对比)

---

## LIFO原则介绍

### 什么是LIFO原则？

**LIFO (Last In, First Out)**: 最后添加的退化，应该最先被处理。

### 为什么使用LIFO？

在图像修复任务中，退化是按照一定顺序添加的：
```
原始图像 → 添加退化1 → 添加退化2 → 添加退化3 → 最终退化图像
```

**LIFO原则**认为，恢复时应该按照**相反的顺序**处理：
```
退化图像 → 去除退化3 → 去除退化2 → 去除退化1 → 恢复原图
```

### 示例

假设图像经过以下退化过程：
```
1. 原图 (清晰)
2. + 模糊 (blur) 
3. + JPEG压缩 (jpeg_artifact)
4. + 噪声 (noise)
→ 最终退化图像
```

**正确的恢复顺序 (LIFO)**:
```
退化图像 → 去噪 (noise) → 去JPEG伪影 (jpeg_artifact) → 去模糊 (blur) → 原图
```

**错误的顺序**:
```
退化图像 → 去模糊 → 去噪 → 去JPEG伪影  ❌ 违反LIFO
```

---

## 退化类型顺序奖励模式

在 `compute_score_v2()` 函数中，`accuracy_mode` 参数控制使用哪种奖励模式：

### 模式对比表

| 模式 | 函数 | 特点 | 奖励范围 | 适用场景 |
|-----|------|------|----------|----------|
| `image_quality` | `compute_image_quality_reward_v2()` | **默认模式**，使用图像质量指标 | [0, 1] | 训练主流，关注最终复原质量 |
| `partial_credit` | `check_restoration_order_with_partial_credit_v2()` | **递进式奖励**，鼓励部分正确 | [0, 1] | 监督学习顺序，平滑梯度 |
| `order_only` | `check_restoration_order_v2()` | 原始顺序检查，位置对比 | [0, 1] | 严格顺序要求 |
| `order_with_dedup` | `check_restoration_order_v2()` + 去重 | 顺序检查，允许重复处理 | [0, 1] | 允许多次调用同一工具 |

---

## 模式1: partial_credit - 递进式奖励 (推荐)

### 核心逻辑

**函数**: `check_restoration_order_with_partial_credit_v2(predicted_log, reward_model_order)`

### 关键特性

1. ✅ **自动过滤 "clean" 标签**: 因为ground truth中没有clean
2. ✅ **合并连续重复**: 一个退化可能需要多次处理（如多次调用去噪工具）
3. ✅ **递进式奖励**: 鼓励部分正确，避免稀疏奖励
4. ✅ **必须LIFO顺序**: 顺序错误直接0分

### 递进式奖励规则

#### 1个退化

| 预测数量 | 奖励 | 说明 |
|---------|------|------|
| 0 | 0.0 | 未预测 |
| 1 (正确) | 1.0 | 完全正确 |

#### 2个退化

| 预测数量 | 奖励 | 说明 |
|---------|------|------|
| 0 | 0.0 | 未预测 |
| 1 (第1个正确) | **0.6** | 处理了最重要的（最后添加的） |
| 2 (全部正确) | **1.0** | 完全正确 |

#### 3个退化

| 预测数量 | 奖励 | 说明 |
|---------|------|------|
| 0 | 0.0 | 未预测 |
| 1 (第1个正确) | **0.5** | 处理了最重要的 |
| 2 (前2个正确) | **0.8** | 处理了大部分 |
| 3 (全部正确) | **1.0** | 完全正确 |

#### 4个或更多退化

使用**平方根奖励**（介于线性和稀疏之间）:
```python
reward = sqrt(predicted_count / expected_count)
```

示例（4个退化）:
- 1个正确: `sqrt(1/4) = 0.50`
- 2个正确: `sqrt(2/4) = 0.71`
- 3个正确: `sqrt(3/4) = 0.87`
- 4个正确: `sqrt(4/4) = 1.00`

### 处理流程

```python
原始预测: ["noise", "jpeg_artifact", "noise", "blur", "clean"]
    ↓
1. 过滤clean: ["noise", "jpeg_artifact", "noise", "blur"]
    ↓
2. 合并重复: ["noise", "jpeg_artifact", "blur"]
    ↓
3. 验证顺序: 与期望顺序["noise", "jpeg_artifact", "blur"]对比
    ↓
4. 计算奖励: 3/3正确 → 1.0分
```

### 详细示例

#### 示例1: 完全正确

```python
# Ground truth (退化添加顺序)
reward_model_order = ["blur", "jpeg_artifact", "noise"]

# 期望的恢复顺序 (LIFO，反向)
correct_restoration_order = ["noise", "jpeg_artifact", "blur"]

# 模型预测
predicted_log = ["noise", "jpeg_artifact", "blur"]

# 计算
# - 过滤clean: 无需过滤
# - 合并重复: 无重复
# - 顺序检查: 完全匹配
# 奖励 = 1.0 (3/3)
```

#### 示例2: 部分正确（2/3）

```python
# Ground truth
reward_model_order = ["blur", "jpeg_artifact", "noise"]
correct_restoration_order = ["noise", "jpeg_artifact", "blur"]

# 模型预测（只处理了前2个）
predicted_log = ["noise", "jpeg_artifact"]

# 计算
# - 过滤clean: 无需过滤
# - 合并重复: 无重复
# - 顺序检查: 前2个正确
# 奖励 = 0.8 (2/3正确，给80%奖励)
```

#### 示例3: 顺序错误

```python
# Ground truth
reward_model_order = ["blur", "jpeg_artifact", "noise"]
correct_restoration_order = ["noise", "jpeg_artifact", "blur"]

# 模型预测（顺序错误）
predicted_log = ["jpeg_artifact", "noise", "blur"]

# 计算
# - 过滤clean: 无需过滤
# - 合并重复: 无重复
# - 顺序检查: 第一个就错误（期望noise，实际jpeg_artifact）
# 奖励 = 0.0 (顺序错误，不给分)
```

#### 示例4: 重复处理

```python
# Ground truth
reward_model_order = ["blur", "noise"]
correct_restoration_order = ["noise", "blur"]

# 模型预测（多次去噪）
predicted_log = ["noise", "noise", "noise", "blur"]

# 计算
# - 过滤clean: 无需过滤
# - 合并重复: ["noise", "blur"]  ← 连续的noise合并为1个
# - 顺序检查: 完全匹配
# 奖励 = 1.0 (允许多次处理同一退化)
```

#### 示例5: 包含clean标签

```python
# Ground truth
reward_model_order = ["blur", "noise"]
correct_restoration_order = ["noise", "blur"]

# 模型预测（包含clean）
predicted_log = ["noise", "blur", "clean"]

# 计算
# - 过滤clean: ["noise", "blur"]  ← 自动过滤clean
# - 合并重复: 无重复
# - 顺序检查: 完全匹配
# 奖励 = 1.0 (自动忽略clean标签)
```

#### 示例6: 预测了额外的退化类型

```python
# Ground truth
reward_model_order = ["blur", "noise"]
correct_restoration_order = ["noise", "blur"]

# 模型预测（多余的jpeg_artifact）
predicted_log = ["noise", "jpeg_artifact", "blur"]

# 计算
# - 过滤clean: 无需过滤
# - 合并重复: 无重复
# - 验证类型: jpeg_artifact不在期望集合中
# 奖励 = 0.0 (预测了无效的退化类型)
```

---

## 模式2: order_only - 原始顺序检查

### 核心逻辑

**函数**: `check_restoration_order_v2(predicted_log, reward_model_order)`

### 计算规则

1. **完全匹配**: 预测完全等于期望顺序 → `1.0`
2. **部分匹配**: 按位置计算正确率 → `correct_positions / total_expected`
3. **集合奖励**: 即使顺序错，但所有退化类型都存在 → 至少 `0.1`

### 示例

#### 示例1: 完全匹配
```python
predicted_log = ["noise", "jpeg_artifact", "blur"]
expected_order = ["noise", "jpeg_artifact", "blur"]

# 奖励 = 1.0
```

#### 示例2: 部分位置正确
```python
predicted_log = ["noise", "blur", "jpeg_artifact"]  # 后两个顺序反了
expected_order = ["noise", "jpeg_artifact", "blur"]

# 位置0: noise = noise ✓
# 位置1: blur ≠ jpeg_artifact ✗
# 位置2: jpeg_artifact ≠ blur ✗
# 奖励 = 1/3 = 0.33
```

#### 示例3: 集合正确但顺序全错
```python
predicted_log = ["blur", "jpeg_artifact", "noise"]  # 完全反序
expected_order = ["noise", "jpeg_artifact", "blur"]

# 所有位置都错误: 0/3 = 0.0
# 但集合相同: {blur, jpeg_artifact, noise} = {noise, jpeg_artifact, blur}
# 奖励 = max(0.0, 0.1) = 0.1 (集合奖励)
```

---

## 模式3: order_with_dedup - 顺序检查+去重

### 核心逻辑

先合并连续重复的退化类型，然后进行顺序检查。

**函数组合**:
```python
merged_log = merge_consecutive_duplicates_v2(predicted_log)
score = check_restoration_order_v2(merged_log, expected_order)
```

### 示例

```python
# 原始预测
predicted_log = ["noise", "noise", "noise", "jpeg_artifact", "blur", "blur"]

# 去重后
merged_log = ["noise", "jpeg_artifact", "blur"]

# 期望顺序
expected_order = ["noise", "jpeg_artifact", "blur"]

# 匹配 → 奖励 = 1.0
```

**适用场景**: 当模型需要多次调用同一工具才能完全去除某个退化时。

---

## 数据流和顺序转换

### 完整数据流

```
数据集 (Parquet)
├── reward_model: [
│   {"degradation_type": "blur", ...},      # 第1个添加
│   {"degradation_type": "jpeg_artifact", ...},  # 第2个添加
│   {"degradation_type": "noise", ...}      # 第3个添加
│   ]
└── env_name: "blur,jpeg_artifact,noise"
         ↓
解析 (parse_reward_model_to_degradations_v2)
         ↓
degradation_addition_order = ["blur", "jpeg_artifact", "noise"]
         ↓
LIFO反转 (list(reversed(...)))
         ↓
correct_restoration_order = ["noise", "jpeg_artifact", "blur"]
         ↓
模型预测
         ↓
predicted_log = ["noise", "jpeg_artifact", "blur"]
         ↓
对比验证 → 计算奖励
```

### 关键转换

#### 从reward_model解析
```python
reward_model = [
    {"degradation_type": "blur", ...},
    {"degradation_type": "jpeg_artifact", ...},
    {"degradation_type": "noise", ...}
]

# 解析为添加顺序
degradation_addition_order = ["blur", "jpeg_artifact", "noise"]

# LIFO反转为正确恢复顺序
correct_restoration_order = ["noise", "jpeg_artifact", "blur"]
```

#### 从env_name解析
```python
env_name = "blur,jpeg_artifact,noise"

# 解析（注意：env_name已经是反序的，即LIFO顺序）
env_degradations = ["blur", "jpeg_artifact", "noise"]

# 再反转一次得到添加顺序
degradation_addition_order = list(reversed(env_degradations))
# = ["noise", "jpeg_artifact", "blur"]  # 这是添加顺序

# LIFO反转为正确恢复顺序
correct_restoration_order = list(reversed(degradation_addition_order))
# = ["blur", "jpeg_artifact", "noise"]  # 回到env_name的顺序
```

**注意**: env_name的设计有些反直觉，它实际上已经是LIFO顺序了。

---

## 详细计算示例

### 完整场景示例

#### 场景设置
```python
# Ground truth (数据集中的定义)
ground_truth = {
    "reward_model": [
        {"degradation_type": "blur", "params": {...}},      # 添加顺序1
        {"degradation_type": "jpeg_artifact", "params": {...}},  # 添加顺序2  
        {"degradation_type": "noise", "params": {...}}      # 添加顺序3
    ],
    "env_name": "blur,jpeg_artifact,noise"
}

# 解析
degradation_addition_order = ["blur", "jpeg_artifact", "noise"]
correct_restoration_order = ["noise", "jpeg_artifact", "blur"]
```

#### 案例1: 完美响应

**模型输出**:
```xml
<think>
图像存在噪声、JPEG伪影和模糊，根据LIFO原则，优先处理最后添加的噪声
</think>
<tool_call>
[{"name": "swinir_denoising", "arguments": {}}]
</tool_call>
```

然后经过多轮交互：
```xml
<!-- Turn 2 -->
<think>
噪声已去除，现在处理JPEG压缩伪影
</think>
<tool_call>
[{"name": "swinir_jpeg_artifact_removal", "arguments": {}}]
</tool_call>

<!-- Turn 3 -->
<think>
JPEG伪影已去除，最后处理模糊
</think>
<tool_call>
[{"name": "restormer_motion_deblurring", "arguments": {}}]
</tool_call>

<!-- Turn 4 -->
<think>
所有退化已处理完毕，图像恢复清晰
</think>
<answer>
{"restoration_log": ["noise", "jpeg_artifact", "blur"]}
</answer>
```

**奖励计算** (`accuracy_mode="partial_credit"`):
```python
predicted_log = ["noise", "jpeg_artifact", "blur"]
expected_order = ["noise", "jpeg_artifact", "blur"]

# 过滤clean: 无需过滤
# 合并重复: 无重复
# 顺序检查: 完全匹配
# 3个退化，全部正确 → 1.0

accuracy_score = 1.0
```

#### 案例2: 部分完成（早期终止）

**模型输出**:
```xml
<think>
图像存在噪声和JPEG伪影，先处理噪声
</think>
<tool_call>
[{"name": "swinir_denoising", "arguments": {}}]
</tool_call>

<!-- Turn 2 -->
<think>
噪声已基本去除，图像质量可接受
</think>
<answer>
{"restoration_log": ["noise"]}
</answer>
```

**奖励计算**:
```python
predicted_log = ["noise"]
expected_order = ["noise", "jpeg_artifact", "blur"]

# 3个退化，只处理了第1个（最重要的）
# 根据递进式规则: 第1个=50%
accuracy_score = 0.5
```

#### 案例3: 重复尝试

**模型输出**:
```xml
<answer>
{"restoration_log": ["noise", "noise", "noise", "jpeg_artifact", "blur"]}
</answer>
```

**奖励计算**:
```python
predicted_log = ["noise", "noise", "noise", "jpeg_artifact", "blur"]

# 过滤clean: 无需过滤
# 合并重复: ["noise", "jpeg_artifact", "blur"]
# 顺序检查: 完全匹配

accuracy_score = 1.0  # 允许重复处理
```

#### 案例4: 顺序错误

**模型输出**:
```xml
<answer>
{"restoration_log": ["blur", "noise", "jpeg_artifact"]}
</answer>
```

**奖励计算**:
```python
predicted_log = ["blur", "noise", "jpeg_artifact"]
expected_order = ["noise", "jpeg_artifact", "blur"]

# 第一个就错误: blur ≠ noise
accuracy_score = 0.0  # 违反LIFO原则
```

---

## 与图像质量奖励的对比

### 对比表

| 维度 | 退化顺序奖励 | 图像质量奖励 |
|-----|-------------|-------------|
| **关注点** | 处理顺序是否正确 | 最终复原质量 |
| **需要GT** | 需要退化类型标签 | 有参考模式需要GT图像 |
| **奖励范围** | [0, 1] | [0, 1] |
| **稀疏性** | 中等（partial_credit减少稀疏） | 连续（可调整） |
| **训练目标** | 学习LIFO策略 | 学习质量优化 |
| **可解释性** | 高（明确的顺序规则） | 中等（基于指标） |
| **计算成本** | 低（字符串对比） | 高（图像质量计算） |

### 使用建议

#### 场景1: 纯训练阶段
**推荐**: `accuracy_mode="image_quality"` (默认)
```python
# 配置
accuracy_mode = "image_quality"
use_no_reference = True
discretize_levels = 0

# 优势
# - 关注最终质量，而非中间步骤
# - 允许模型探索不同策略
# - 无参考模式适用所有样本
```

#### 场景2: 监督LIFO学习
**推荐**: `accuracy_mode="partial_credit"`
```python
# 配置
accuracy_mode = "partial_credit"

# 优势
# - 递进式奖励鼓励部分正确
# - 明确的LIFO原则引导
# - 自动处理clean和重复
```

#### 场景3: 早期训练+监督信号
**推荐**: 混合模式
```python
# 总奖励
total_reward = format_score + 0.5 * quality_score + 0.5 * order_score

# 优势
# - 同时优化质量和顺序
# - 平衡探索和引导
```

---

## 总奖励权重

### 当前配置

```python
# compute_score_v2() 中的权重
format_weight = 0.3    # 格式奖励（二元：1.0 或 -1.0）
logic_weight = 0.0     # 逻辑奖励（当前禁用）
accuracy_weight = 0.7  # 准确性奖励（退化顺序或图像质量）

# 总奖励计算
if format_score == -1.0:
    total_score = format_weight * format_score  # 格式错误不给准确性分
else:
    total_score = (format_weight * format_score + 
                   logic_weight * logic_score + 
                   accuracy_weight * accuracy_score)
```

### 奖励分布示例

#### 完美场景
```python
format_score = 1.0      # 格式完美
accuracy_score = 1.0    # 顺序完全正确

total_score = 0.3 * 1.0 + 0.7 * 1.0 = 1.0
```

#### 部分正确场景
```python
format_score = 1.0      # 格式正确
accuracy_score = 0.5    # 只处理了第1个退化（3个退化中）

total_score = 0.3 * 1.0 + 0.7 * 0.5 = 0.65
```

#### 格式错误场景
```python
format_score = -1.0     # 格式错误
accuracy_score = 1.0    # 即使顺序正确

total_score = 0.3 * (-1.0) = -0.3  # 不计算准确性分
```

---

## 关键要点总结

### ✅ LIFO原则
- **定义**: 最后添加的退化最先处理
- **原因**: 模拟真实修复过程，从表面到深层
- **表现**: 退化添加顺序 → 反转 → 正确恢复顺序

### ✅ partial_credit模式优势
1. **递进式奖励**: 50% → 80% → 100%（3个退化）
2. **自动过滤clean**: 模型可以自由使用"clean"标记
3. **合并重复**: 允许多次调用同一工具
4. **顺序严格**: 必须按LIFO顺序，否则0分

### ✅ 数据流关键点
- `reward_model`: 列表形式，按添加顺序
- `degradation_addition_order`: 解析后的添加顺序
- `correct_restoration_order`: LIFO反转后的正确恢复顺序
- `predicted_log`: 从模型的`<answer>`中提取

### ✅ 权重配置
- 格式权重: 30% (二元，格式错误直接负分)
- 准确性权重: 70% (连续，退化顺序或图像质量)

### ✅ 模式选择
- **训练主流**: `image_quality` (关注最终质量)
- **监督学习**: `partial_credit` (引导LIFO策略)
- **严格要求**: `order_only` (不允许误差)
- **灵活处理**: `order_with_dedup` (允许重复)

---

## 代码位置索引

| 功能 | 文件路径 |
|-----|----------|
| 递进式奖励 | `verl/utils/reward_score/image_restoration.py::check_restoration_order_with_partial_credit_v2()` |
| 原始顺序检查 | `check_restoration_order_v2()` |
| 合并重复 | `merge_consecutive_duplicates_v2()` |
| 解析退化类型 | `parse_reward_model_to_degradations_v2()` |
| 总奖励计算 | `compute_score_v2()` |
| 环境变量配置 | `verl/utils/reward_score/__init__.py` |

---

**生成完毕** 🎉

退化类型奖励提供了一种**可解释的监督信号**，帮助模型学习正确的LIFO处理策略。虽然当前默认使用图像质量奖励，但退化顺序奖励在某些场景下（如需要明确监督信号）非常有用。

