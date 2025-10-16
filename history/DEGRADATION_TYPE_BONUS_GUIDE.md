# 退化类型匹配奖励（Degradation Type Bonus）使用指南

## 🎯 功能概述

**退化类型匹配奖励**是一个额外的bonus奖励，用于鼓励模型识别并预测正确的退化类型，**不考虑处理顺序**，只看集合匹配。

### 关键特性

- ✅ **只看集合匹配**: 不考虑顺序，只要预测的退化类型集合与期望集合匹配即可
- ✅ **额外bonus**: 作为额外奖励加到总分上，不替代现有奖励
- ✅ **可配置权重**: 默认权重为1.0，可通过环境变量调整
- ✅ **脚本控制**: 可在IR.sh中轻松开启/关闭
- ✅ **自动过滤clean**: 自动忽略预测中的"clean"标签
- ✅ **允许重复**: 自动合并连续重复的退化类型

---

## 🚀 快速开始

### 1. 在IR.sh中启用

```bash
# 编辑 examples/agent/IR.sh

# ========== Degradation Type Bonus Reward Configuration ==========
export ENABLE_DEGRADATION_TYPE_BONUS=True   # 启用退化类型奖励
export DEGRADATION_TYPE_BONUS_WEIGHT=1.0    # 权重系数
# ==================================================================
```

### 2. 运行训练

```bash
bash examples/agent/IR.sh
```

### 3. 检查日志

训练时会看到：
```
[INFO] Degradation Type Bonus Config: enable=True, weight=1.0
[DEBUG degradation_type_match] 预测集合: {'noise', 'blur'}
[DEBUG degradation_type_match] 期望集合: {'blur', 'noise'}
[DEBUG degradation_type_match] 完全匹配，奖励=1.0
[DEBUG degradation_type_bonus] enabled, bonus_score=1.0, weight=1.0, contribution=1.0
```

---

## 📊 奖励计算逻辑

### 基本规则

```python
# 1. 提取预测的退化类型
predicted_log = ["noise", "blur", "jpeg_artifact"]

# 2. 自动过滤clean
filtered = ["noise", "blur", "jpeg_artifact"]  # 如果有"clean"会被移除

# 3. 合并连续重复
merged = ["noise", "blur", "jpeg_artifact"]  # ["noise", "noise", "blur"] → ["noise", "blur"]

# 4. 转换为集合
predicted_set = {"noise", "blur", "jpeg_artifact"}
expected_set = {"blur", "noise", "jpeg_artifact"}

# 5. 计算奖励
if predicted_set == expected_set:
    bonus_score = 1.0  # 完全匹配
elif predicted_set.issubset(expected_set):
    bonus_score = len(predicted_set) / len(expected_set)  # 部分匹配
else:
    bonus_score = 0.0  # 包含无效类型
```

### 得分规则

| 场景 | 奖励 | 说明 |
|-----|------|------|
| **完全匹配** | 1.0 | 预测集合 = 期望集合 |
| **部分匹配** | predicted/expected | 预测了部分正确的退化类型 |
| **无效类型** | 0.0 | 预测了不在期望集合中的类型 |
| **空预测** | 0.0 | 没有预测任何退化类型 |
| **格式错误** | 0.0 | 不给bonus（格式必须正确） |
| **Clean样本** | 0.0 | Clean样本不计算bonus |

---

## 💡 详细示例

### 示例1: 完全匹配 ✅

**Ground Truth**:
```python
expected = ["blur", "noise", "jpeg_artifact"]
```

**模型预测**（顺序不同，但集合相同）:
```xml
<answer>
{"restoration_log": ["noise", "jpeg_artifact", "blur"]}
</answer>
```

**计算**:
```python
predicted_set = {"noise", "jpeg_artifact", "blur"}
expected_set = {"blur", "noise", "jpeg_artifact"}

# 集合相同 → 完全匹配
bonus_score = 1.0
bonus_contribution = 1.0 × 1.0 = 1.0
```

---

### 示例2: 部分匹配 📊

**Ground Truth**:
```python
expected = ["blur", "noise", "jpeg_artifact"]  # 3个退化
```

**模型预测**（只识别了2个）:
```xml
<answer>
{"restoration_log": ["noise", "blur"]}
</answer>
```

**计算**:
```python
predicted_set = {"noise", "blur"}
expected_set = {"blur", "noise", "jpeg_artifact"}

# 部分匹配：2/3
bonus_score = 2 / 3 = 0.667
bonus_contribution = 1.0 × 0.667 = 0.667
```

---

### 示例3: 自动过滤clean 🧹

**Ground Truth**:
```python
expected = ["blur", "noise"]
```

**模型预测**（包含clean）:
```xml
<answer>
{"restoration_log": ["noise", "blur", "clean"]}
</answer>
```

**计算**:
```python
# 过滤clean
filtered = ["noise", "blur"]
predicted_set = {"noise", "blur"}
expected_set = {"blur", "noise"}

# 完全匹配
bonus_score = 1.0
bonus_contribution = 1.0 × 1.0 = 1.0
```

---

### 示例4: 允许重复 🔄

**Ground Truth**:
```python
expected = ["blur", "noise"]
```

**模型预测**（多次处理同一退化）:
```xml
<answer>
{"restoration_log": ["noise", "noise", "noise", "blur"]}
</answer>
```

**计算**:
```python
# 合并重复
merged = ["noise", "blur"]
predicted_set = {"noise", "blur"}
expected_set = {"blur", "noise"}

# 完全匹配
bonus_score = 1.0
bonus_contribution = 1.0 × 1.0 = 1.0
```

---

### 示例5: 无效类型 ❌

**Ground Truth**:
```python
expected = ["blur", "noise"]
```

**模型预测**（包含不存在的退化）:
```xml
<answer>
{"restoration_log": ["noise", "blur", "haze"]}
</answer>
```

**计算**:
```python
predicted_set = {"noise", "blur", "haze"}
expected_set = {"blur", "noise"}

# "haze" 不在期望集合中
bonus_score = 0.0  # 无效类型，不给分
bonus_contribution = 0.0
```

---

## 🔧 总奖励计算

### 完整奖励公式

```python
# 基础奖励
base_reward = 0.3 × format_score + 0.7 × accuracy_score

# 如果启用退化类型bonus
if enable_degradation_type_bonus:
    degradation_type_bonus = bonus_weight × bonus_score
    total_reward = base_reward + degradation_type_bonus
else:
    total_reward = base_reward
```

### 奖励范围

| 配置 | 最小值 | 最大值 | 说明 |
|-----|--------|--------|------|
| **Bonus关闭** | -0.3 | 1.0 | 格式错误可能导致负分 |
| **Bonus开启(weight=1.0)** | -0.3 | 2.0 | 最高可达2.0分 |
| **Bonus开启(weight=0.5)** | -0.3 | 1.5 | 根据权重调整 |

### 示例计算

#### 场景1: 完美场景（bonus开启）

```python
format_score = 1.0          # 格式完美
accuracy_score = 0.85       # 图像质量优秀
bonus_score = 1.0           # 完全匹配退化类型
bonus_weight = 1.0

base_reward = 0.3 × 1.0 + 0.7 × 0.85 = 0.895
bonus_contribution = 1.0 × 1.0 = 1.0
total_reward = 0.895 + 1.0 = 1.895
```

#### 场景2: 部分识别（bonus开启）

```python
format_score = 1.0          # 格式正确
accuracy_score = 0.75       # 图像质量良好
bonus_score = 0.667         # 识别了2/3的退化类型
bonus_weight = 1.0

base_reward = 0.3 × 1.0 + 0.7 × 0.75 = 0.825
bonus_contribution = 1.0 × 0.667 = 0.667
total_reward = 0.825 + 0.667 = 1.492
```

#### 场景3: 格式错误（不给bonus）

```python
format_score = -1.0         # 格式错误
accuracy_score = 0.9        # 即使质量很好
bonus_score = 1.0           # 即使类型完全匹配

# 格式错误时不计算准确性和bonus
total_reward = 0.3 × (-1.0) = -0.3
```

---

## ⚙️ 配置参数详解

### ENABLE_DEGRADATION_TYPE_BONUS

**类型**: 布尔值 (True/False)  
**默认值**: `False` (关闭)

**说明**:
- `True`: 启用退化类型匹配奖励
- `False`: 关闭此功能（使用默认奖励机制）

**推荐**:
- 需要强化退化类型识别能力时: `True`
- 只关注最终复原质量时: `False`

---

### DEGRADATION_TYPE_BONUS_WEIGHT

**类型**: 浮点数 (≥0)  
**默认值**: `1.0`

**说明**: 控制bonus奖励的权重系数

**推荐配置**:

| 场景 | 推荐权重 | 效果 |
|-----|----------|------|
| 强化类型识别 | 1.0 ~ 1.5 | 显著鼓励正确识别退化类型 |
| 平衡引导 | 0.5 ~ 1.0 | 适度引导，不过度影响 |
| 轻微提示 | 0.1 ~ 0.5 | 轻微bonus，主要靠质量 |

**示例**:
```bash
# 强引导
export DEGRADATION_TYPE_BONUS_WEIGHT=1.5

# 适中引导
export DEGRADATION_TYPE_BONUS_WEIGHT=1.0

# 轻微引导
export DEGRADATION_TYPE_BONUS_WEIGHT=0.3
```

---

## 🎯 使用场景建议

### 场景1: 早期训练

**目标**: 帮助模型快速学习识别退化类型

**配置**:
```bash
export ENABLE_DEGRADATION_TYPE_BONUS=True
export DEGRADATION_TYPE_BONUS_WEIGHT=1.0
export IMAGE_QUALITY_USE_NO_REFERENCE=True
export IMAGE_QUALITY_DISCRETIZE_LEVELS=10
```

**理由**: 
- 退化类型bonus提供明确的监督信号
- 配合离散化的质量奖励，稳定训练

---

### 场景2: 中后期训练

**目标**: 微调质量，减少对类型识别的依赖

**配置**:
```bash
export ENABLE_DEGRADATION_TYPE_BONUS=True
export DEGRADATION_TYPE_BONUS_WEIGHT=0.5   # 降低权重
export IMAGE_QUALITY_USE_NO_REFERENCE=True
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0   # 连续奖励
```

**理由**:
- 降低bonus权重，让质量奖励主导
- 类型bonus作为辅助信号

---

### 场景3: 纯质量优化

**目标**: 只关注最终复原质量，不限制中间步骤

**配置**:
```bash
export ENABLE_DEGRADATION_TYPE_BONUS=False  # 关闭bonus
export IMAGE_QUALITY_USE_NO_REFERENCE=False # 有参考指标
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0
```

**理由**:
- 完全依赖图像质量指标
- 允许模型自由探索

---

## 📊 监控和调试

### WandB指标

启用bonus后，可以在WandB中看到以下指标：

```python
metrics = {
    "score": 1.895,                    # 总分
    "format_score": 1.0,               # 格式分
    "accuracy_score": 0.85,            # 准确性分（图像质量）
    "degradation_type_bonus": 1.0,     # Bonus分
    "degradation_order_score": 0.85,   # 顺序分（如果使用）
}
```

### 日志输出

训练时会看到详细日志：

```
[INFO] Degradation Type Bonus Config: enable=True, weight=1.0
[DEBUG degradation_type_match] 原始log: ['noise', 'blur', 'clean']
[DEBUG degradation_type_match] 过滤clean: ['noise', 'blur']
[DEBUG degradation_type_match] 合并重复: ['noise', 'blur']
[DEBUG degradation_type_match] 预测集合: {'noise', 'blur'}
[DEBUG degradation_type_match] 期望集合: {'blur', 'noise'}
[DEBUG degradation_type_match] 完全匹配，奖励=1.0
[DEBUG degradation_type_bonus] enabled, bonus_score=1.0, weight=1.0, contribution=1.0
[DEBUG image_restoration_v2] total_score=1.895
```

---

## 🆚 对比其他奖励模式

### vs. 图像质量奖励 (image_quality)

| 维度 | 退化类型Bonus | 图像质量奖励 |
|-----|--------------|-------------|
| **关注点** | 退化类型识别 | 最终复原质量 |
| **计算成本** | 低（字符串比较） | 高（图像指标计算） |
| **监督信号** | 明确（集合匹配） | 间接（质量评分） |
| **探索空间** | 受限（必须预测类型） | 自由（只看结果） |
| **训练作用** | 辅助引导 | 主要优化目标 |

---

### vs. 顺序奖励 (partial_credit)

| 维度 | 退化类型Bonus | 顺序奖励 |
|-----|--------------|---------|
| **顺序要求** | ❌ 不考虑顺序 | ✅ 严格LIFO |
| **部分分数** | ✅ 支持 | ✅ 支持（递进式） |
| **训练目标** | 识别退化类型 | 学习LIFO策略 |
| **灵活性** | 高（集合匹配） | 中（顺序约束） |

---

## 🔍 常见问题

### Q1: Bonus奖励会替代图像质量奖励吗？

**A**: 不会。Bonus是**额外奖励**，加在基础奖励之上。

```python
total = base_reward + bonus_contribution
```

---

### Q2: 为什么格式错误时不给bonus？

**A**: 格式错误说明模型输出不符合规范，此时即使识别了正确的退化类型也不应该奖励，避免强化错误行为。

---

### Q3: Clean样本会计算bonus吗？

**A**: 不会。Clean样本没有退化类型，不适用于退化类型匹配奖励。

---

### Q4: 预测顺序错误会影响bonus吗？

**A**: 不会。Bonus只看集合匹配，不考虑顺序。

例如：
- 期望: `[blur, noise]`
- 预测: `[noise, blur]`
- Bonus: 1.0 (完全匹配)

---

### Q5: 如何调整bonus权重？

**A**: 根据训练目标：
- 强化类型识别: `1.0 ~ 1.5`
- 平衡引导: `0.5 ~ 1.0`
- 轻微提示: `0.1 ~ 0.5`

---

### Q6: Bonus分数会超过1.0吗？

**A**: 单个bonus分数最高1.0，但加上基础奖励后，总分可以超过1.0（最高约2.0）。

---

## ✅ 验证清单

启用bonus后，检查以下内容：

- [ ] 日志中显示 `[INFO] Degradation Type Bonus Config: enable=True`
- [ ] 训练过程中看到 `[DEBUG degradation_type_match]` 日志
- [ ] WandB中有 `degradation_type_bonus` 指标
- [ ] 总分可能超过1.0（说明bonus生效）
- [ ] 格式错误的样本不会获得bonus

---

## 📚 相关文档

- `IMAGE_QUALITY_AND_FORMAT_REWARD_REPORT.md` - 图像质量+格式奖励详解
- `DEGRADATION_ORDER_REWARD_REPORT.md` - 退化顺序奖励详解
- `docs/IMAGE_QUALITY_REWARD_CONFIG.md` - 图像质量配置指南

---

**生成完毕** 🎉

退化类型匹配奖励提供了一种**灵活的辅助监督信号**，帮助模型学习识别退化类型，同时不限制处理顺序，允许自由探索。

