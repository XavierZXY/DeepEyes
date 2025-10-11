# 完整奖励配置指南

## 🎯 概述

所有奖励相关的配置参数都可以通过**环境变量**在 `IR.sh` 脚本中灵活配置，并且会**自动记录到WandB**。

---

## 📋 完整参数列表

### 1. 图像质量配置

| 环境变量 | 类型 | 默认值 | 说明 |
|---------|------|--------|------|
| `IMAGE_QUALITY_USE_NO_REFERENCE` | 布尔 | `True` | 是否使用无参考指标 |
| `IMAGE_QUALITY_DISCRETIZE_LEVELS` | 整数 | `0` | 离散化等级（0=连续） |

**指标详情**:
- `True`: 使用 NIQE + BRISQUE + CPBD + CLIP-IQA + Hyper-IQA（无参考）
- `False`: 使用 SSIM + LPIPS + PSNR（有参考，需要GT）

---

### 2. 奖励权重配置 ⭐ 核心

| 环境变量 | 类型 | 默认值 | 说明 |
|---------|------|--------|------|
| `FORMAT_REWARD_WEIGHT` | 浮点 | `0.3` | 格式奖励权重 |
| `QUALITY_REWARD_WEIGHT` | 浮点 | `0.7` | 图像质量奖励权重 |

**默认奖励结构**:
```python
total_reward = FORMAT_WEIGHT × format_score + QUALITY_WEIGHT × quality_score
```

---

### 3. 退化类型奖励配置 ⭐ 可选

| 环境变量 | 类型 | 默认值 | 说明 |
|---------|------|--------|------|
| `ENABLE_DEGRADATION_TYPE_REWARD` | 布尔 | `False` | 是否启用退化类型奖励 |
| `DEGRADATION_TYPE_REWARD_WEIGHT` | 浮点 | `1.0` | 退化类型奖励权重 |

**启用后的奖励结构**:
```python
total_reward = FORMAT_WEIGHT × format_score 
             + QUALITY_WEIGHT × quality_score 
             + DEGRADATION_TYPE_WEIGHT × degradation_type_score
```

**奖励逻辑**:
- 检查预测的退化类型集合是否匹配（**不考虑顺序**）
- 完全匹配: 1.0分，部分匹配: 按比例给分
- 作为额外奖励加到总分上

---

## 🔧 IR.sh中的配置

### 完整配置示例

```bash
# ========== Image Quality Reward Configuration ==========
export IMAGE_QUALITY_USE_NO_REFERENCE=False  # True=无参考, False=有参考
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0     # 0=连续, 10=每10%, 20=每5%
# ========================================================

# ========== Reward Weight Configuration ==========
export FORMAT_REWARD_WEIGHT=0.3              # 格式奖励权重
export QUALITY_REWARD_WEIGHT=0.7             # 图像质量奖励权重
export ENABLE_DEGRADATION_TYPE_REWARD=False  # 是否启用退化类型奖励
export DEGRADATION_TYPE_REWARD_WEIGHT=1.0    # 退化类型奖励权重
# ==================================================================
```

---

## 📊 奖励计算公式

### 完整公式

```python
# 1. 格式分数（二元）
format_score = 1.0   # 格式完美
            或 -1.0  # 格式违规

# 2. 图像质量分数（连续）
quality_score = 0.0 ~ 1.0  # 图像质量分数（SSIM/LPIPS/PSNR 或 NIQE/BRISQUE/CPBD等）

# 3. 退化类型分数（连续，可选）
degradation_type_score = 0.0 ~ 1.0  # 退化类型识别准确性（集合匹配）

# 4. 默认奖励（格式 + 图像质量）
total_reward = FORMAT_REWARD_WEIGHT × format_score 
             + QUALITY_REWARD_WEIGHT × quality_score

# 5. 启用退化类型奖励后
if ENABLE_DEGRADATION_TYPE_REWARD and format_score > 0:
    total_reward = FORMAT_REWARD_WEIGHT × format_score 
                 + QUALITY_REWARD_WEIGHT × quality_score 
                 + DEGRADATION_TYPE_REWARD_WEIGHT × degradation_type_score
```

### 默认配置下的奖励范围

```python
# 默认配置（退化类型奖励关闭）
total_reward = 0.3 × format_score + 0.7 × quality_score
范围: [-0.3, 1.0]

# 启用退化类型奖励（weight=1.0）
total_reward = 0.3 × format_score + 0.7 × quality_score + 1.0 × degradation_type_score
范围: [-0.3, 2.0]
```

---

## 🎯 推荐配置方案

### 方案1: 默认配置（纯质量优化）

```bash
# 图像质量
export IMAGE_QUALITY_USE_NO_REFERENCE=True
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0

# 权重（默认：格式+质量）
export FORMAT_REWARD_WEIGHT=0.3
export QUALITY_REWARD_WEIGHT=0.7

# 退化类型奖励（关闭）
export ENABLE_DEGRADATION_TYPE_REWARD=False
```

**适用**: 常规训练，关注最终复原质量

**奖励结构**: 格式奖励 + 图像质量奖励

**奖励范围**: [-0.3, 1.0]

---

### 方案2: 强化类型识别

```bash
# 图像质量
export IMAGE_QUALITY_USE_NO_REFERENCE=True
export IMAGE_QUALITY_DISCRETIZE_LEVELS=10

# 权重（默认）
export FORMAT_REWARD_WEIGHT=0.3
export QUALITY_REWARD_WEIGHT=0.7

# 退化类型奖励（开启）
export ENABLE_DEGRADATION_TYPE_REWARD=True
export DEGRADATION_TYPE_REWARD_WEIGHT=1.0
```

**适用**: 早期训练，需要引导模型学习退化类型识别

**奖励结构**: 格式奖励 + 图像质量奖励 + 退化类型奖励

**奖励范围**: [-0.3, 2.0]

---

### 方案3: 平衡格式和质量

```bash
# 图像质量
export IMAGE_QUALITY_USE_NO_REFERENCE=False
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0

# 权重（加大格式权重）
export FORMAT_REWARD_WEIGHT=0.5
export QUALITY_REWARD_WEIGHT=0.5

# 退化类型奖励（关闭）
export ENABLE_DEGRADATION_TYPE_REWARD=False
```

**适用**: 格式问题严重时，加大格式奖励权重

**奖励结构**: 格式奖励 + 图像质量奖励（格式权重提高）

**奖励范围**: [-0.5, 1.0]

---

### 方案4: 全面监督

```bash
# 图像质量
export IMAGE_QUALITY_USE_NO_REFERENCE=True
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0

# 权重（默认）
export FORMAT_REWARD_WEIGHT=0.3
export QUALITY_REWARD_WEIGHT=0.7

# 退化类型奖励（高权重）
export ENABLE_DEGRADATION_TYPE_REWARD=True
export DEGRADATION_TYPE_REWARD_WEIGHT=1.5
```

**适用**: 需要强监督信号，快速收敛

**奖励结构**: 格式奖励 + 图像质量奖励 + 退化类型奖励（高权重）

**奖励范围**: [-0.3, 2.5]

---

## 📈 配置对比表

| 配置项 | 方案1<br>(默认) | 方案2<br>(强化类型) | 方案3<br>(平衡) | 方案4<br>(全面监督) |
|-------|----------------|-------------------|----------------|-------------------|
| **无参考指标** | ✅ | ✅ | ❌ | ✅ |
| **离散化** | 0 | 10 | 0 | 0 |
| **类型Bonus** | ❌ | ✅ (1.0) | ❌ | ✅ (1.5) |
| **格式权重** | 0.3 | 0.3 | 0.5 | 0.3 |
| **准确性权重** | 0.7 | 0.7 | 0.5 | 0.7 |
| **最高奖励** | 1.0 | 2.0 | 1.0 | 2.5 |
| **训练阶段** | 常规 | 早期 | 格式问题 | 快速收敛 |

---

## 🔍 在WandB中查看配置

### Overview页面

所有6个参数都会记录在 `config.reward_config`:

```yaml
reward_config:
  IMAGE_QUALITY_USE_NO_REFERENCE: "True"
  IMAGE_QUALITY_DISCRETIZE_LEVELS: "0"
  ENABLE_DEGRADATION_TYPE_BONUS: "False"
  DEGRADATION_TYPE_BONUS_WEIGHT: "1.0"
  FORMAT_REWARD_WEIGHT: "0.3"          # ⭐ 新增
  ACCURACY_REWARD_WEIGHT: "0.7"        # ⭐ 新增
```

### 对比不同Run的配置

在WandB Table中添加列：
- `config.reward_config.FORMAT_REWARD_WEIGHT`
- `config.reward_config.ACCURACY_REWARD_WEIGHT`
- `config.reward_config.ENABLE_DEGRADATION_TYPE_BONUS`
- 等...

---

## 💡 权重调整建议

### 格式权重 (FORMAT_REWARD_WEIGHT)

| 值 | 适用场景 | 效果 |
|----|---------|------|
| `0.1` | 格式已经很好，不需要强调 | 弱化格式要求 |
| `0.3` | **默认**，平衡格式和质量 | 适中约束 |
| `0.5` | 格式问题严重，需要强化 | 强化格式 |
| `0.7` | 极度重视格式规范 | 强约束 |

**注意**: 格式违规会导致负分，权重越高，惩罚越重。

---

### 准确性权重 (ACCURACY_REWARD_WEIGHT)

| 值 | 适用场景 | 效果 |
|----|---------|------|
| `0.3` | 弱化质量，强化格式 | 关注规范性 |
| `0.5` | 平衡格式和质量 | 均衡 |
| `0.7` | **默认**，重视质量优化 | 关注结果 |
| `0.9` | 几乎只看质量 | 最大化质量 |

**注意**: 通常建议 `FORMAT_WEIGHT + ACCURACY_WEIGHT = 1.0` 以保持奖励范围一致。

---

### 退化类型Bonus权重 (DEGRADATION_TYPE_BONUS_WEIGHT)

| 值 | 适用场景 | 效果 |
|----|---------|------|
| `0.3` | 轻微引导 | 辅助信号 |
| `0.5` | 适度引导 | 平衡bonus |
| `1.0` | **默认**，明显引导 | 显著鼓励 |
| `1.5` | 强引导 | 强监督 |

**注意**: Bonus是额外奖励，会增加总奖励的上限。

---

## 📊 奖励分解示例

### 示例1: 默认配置

**配置**:
```bash
FORMAT_REWARD_WEIGHT=0.3
ACCURACY_REWARD_WEIGHT=0.7
ENABLE_DEGRADATION_TYPE_BONUS=False
```

**计算**:
```python
format_score = 1.0      # 格式完美
accuracy_score = 0.85   # 图像质量优秀

total_reward = 0.3 × 1.0 + 0.7 × 0.85 + 0
             = 0.3 + 0.595 + 0
             = 0.895
```

---

### 示例2: 启用Bonus

**配置**:
```bash
FORMAT_REWARD_WEIGHT=0.3
ACCURACY_REWARD_WEIGHT=0.7
ENABLE_DEGRADATION_TYPE_BONUS=True
DEGRADATION_TYPE_BONUS_WEIGHT=1.0
```

**计算**:
```python
format_score = 1.0      # 格式完美
accuracy_score = 0.85   # 图像质量优秀
bonus_score = 1.0       # 退化类型完全匹配

base_reward = 0.3 × 1.0 + 0.7 × 0.85 = 0.895
bonus_contribution = 1.0 × 1.0 = 1.0
total_reward = 0.895 + 1.0 = 1.895
```

---

### 示例3: 调整权重

**配置**:
```bash
FORMAT_REWARD_WEIGHT=0.5    # 增加格式权重
ACCURACY_REWARD_WEIGHT=0.5  # 降低准确性权重
ENABLE_DEGRADATION_TYPE_BONUS=True
DEGRADATION_TYPE_BONUS_WEIGHT=0.5  # 适度bonus
```

**计算**:
```python
format_score = 1.0
accuracy_score = 0.85
bonus_score = 1.0

base_reward = 0.5 × 1.0 + 0.5 × 0.85 = 0.925
bonus_contribution = 0.5 × 1.0 = 0.5
total_reward = 0.925 + 0.5 = 1.425
```

---

### 示例4: 格式错误（不给bonus）

**配置**:
```bash
FORMAT_REWARD_WEIGHT=0.3
ACCURACY_REWARD_WEIGHT=0.7
ENABLE_DEGRADATION_TYPE_BONUS=True
DEGRADATION_TYPE_BONUS_WEIGHT=1.0
```

**计算**:
```python
format_score = -1.0     # 格式违规
accuracy_score = 0.9    # 质量很好
bonus_score = 1.0       # 类型匹配

# 格式错误时不给准确性奖励和bonus
total_reward = 0.3 × (-1.0) = -0.3
```

---

## 🎨 配置策略

### 训练阶段策略

#### 第1阶段: 早期训练 (Epoch 1-10)

**目标**: 快速学习格式和基本退化识别

**配置**:
```bash
export IMAGE_QUALITY_USE_NO_REFERENCE=True   # 无参考，所有样本可用
export IMAGE_QUALITY_DISCRETIZE_LEVELS=10    # 离散化，减少噪声
export ENABLE_DEGRADATION_TYPE_BONUS=True    # 启用bonus引导
export DEGRADATION_TYPE_BONUS_WEIGHT=1.0     # 标准权重
export FORMAT_REWARD_WEIGHT=0.4              # 稍微提高格式权重
export ACCURACY_REWARD_WEIGHT=0.6            # 稍微降低准确性权重
```

**预期效果**: 快速收敛格式，学习退化类型识别

---

#### 第2阶段: 中期训练 (Epoch 10-20)

**目标**: 优化质量，保持类型识别能力

**配置**:
```bash
export IMAGE_QUALITY_USE_NO_REFERENCE=True   # 保持无参考
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0     # 切换到连续
export ENABLE_DEGRADATION_TYPE_BONUS=True    # 保持bonus
export DEGRADATION_TYPE_BONUS_WEIGHT=0.5     # 降低bonus权重
export FORMAT_REWARD_WEIGHT=0.3              # 恢复默认
export ACCURACY_REWARD_WEIGHT=0.7            # 恢复默认
```

**预期效果**: 平滑过渡，质量优化为主

---

#### 第3阶段: 后期训练 (Epoch 20-32)

**目标**: 最大化复原质量

**配置**:
```bash
export IMAGE_QUALITY_USE_NO_REFERENCE=False  # 切换到有参考（如果有GT）
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0     # 连续奖励
export ENABLE_DEGRADATION_TYPE_BONUS=False   # 关闭bonus
export DEGRADATION_TYPE_BONUS_WEIGHT=1.0     # （不生效）
export FORMAT_REWARD_WEIGHT=0.3              # 默认
export ACCURACY_REWARD_WEIGHT=0.7            # 默认
```

**预期效果**: 纯质量优化，达到最佳复原效果

---

## 📈 监控指标

### WandB中记录的指标

```python
# 奖励分数
{
    "score": 1.895,                      # 总分（基础+bonus）
    "format_score": 1.0,                 # 格式分（1.0或-1.0）
    "accuracy_score": 0.85,              # 准确性分（0.0~1.0）
    "degradation_type_bonus": 1.0,       # Bonus分（0.0~1.0）
}

# 配置参数（config.reward_config）
{
    "IMAGE_QUALITY_USE_NO_REFERENCE": "True",
    "IMAGE_QUALITY_DISCRETIZE_LEVELS": "0",
    "ENABLE_DEGRADATION_TYPE_BONUS": "True",
    "DEGRADATION_TYPE_BONUS_WEIGHT": "1.0",
    "FORMAT_REWARD_WEIGHT": "0.3",       # ⭐ 新增
    "ACCURACY_REWARD_WEIGHT": "0.7",     # ⭐ 新增
}
```

### 关键指标监控

1. **score** (总分)
   - 观察范围变化
   - Bonus开启后会超过1.0

2. **format_score** (格式分)
   - 应该接近1.0
   - 如果经常-1.0，需要调整prompt或模型

3. **accuracy_score** (准确性分)
   - 图像质量或退化顺序分数
   - 应该随训练逐渐提升

4. **degradation_type_bonus** (类型bonus)
   - 仅在启用时有值
   - 接近1.0表示类型识别良好

---

## ⚠️ 重要注意事项

### 1. 权重总和建议

**推荐**: `FORMAT_WEIGHT + ACCURACY_WEIGHT = 1.0`

**原因**: 
- 保持基础奖励范围为[-0.3, 1.0]
- 便于不同实验对比
- 避免奖励尺度变化影响训练

**例外**: 
- 如果需要强化某一项，可以打破这个规则
- 例如: `FORMAT_WEIGHT=0.5, ACCURACY_WEIGHT=0.7` (总和1.2)

---

### 2. Bonus作为额外奖励

Bonus不会替代基础奖励，而是**叠加**：
```python
total = base + bonus  # 叠加，不替代
```

这意味着启用bonus会提高奖励上限，可能影响训练动态。

---

### 3. 格式错误的特殊处理

格式错误时：
- ❌ 不给准确性奖励
- ❌ 不给bonus奖励
- ✅ 只给格式惩罚

```python
if format_score == -1.0:
    total = FORMAT_WEIGHT × (-1.0)  # 负分
```

---

### 4. Clean样本不计算Bonus

Clean样本没有退化类型，即使预测了也不给bonus。

---

## 🧪 测试验证

### 运行测试脚本

```bash
python test_wandb_config.py
```

### 预期输出

```
1. 当前环境变量:
   IMAGE_QUALITY_USE_NO_REFERENCE = False
   IMAGE_QUALITY_DISCRETIZE_LEVELS = 10
   ENABLE_DEGRADATION_TYPE_BONUS = True
   DEGRADATION_TYPE_BONUS_WEIGHT = 1.5
   FORMAT_REWARD_WEIGHT = 0.4           # ⭐ 新增
   ACCURACY_REWARD_WEIGHT = 0.6         # ⭐ 新增

3. 添加到config后的reward_config:
   {
     'FORMAT_REWARD_WEIGHT': '0.4',
     'ACCURACY_REWARD_WEIGHT': '0.6',
     ...
   }

✅ 配置记录测试完成
```

---

## 📚 相关文档

1. **奖励机制详解**
   - `IMAGE_QUALITY_AND_FORMAT_REWARD_REPORT.md` - 图像质量+格式奖励
   - `DEGRADATION_ORDER_REWARD_REPORT.md` - 退化顺序奖励
   - `DEGRADATION_TYPE_BONUS_GUIDE.md` - 退化类型bonus指南

2. **配置说明**
   - `WANDB_CONFIG_TRACKING.md` - WandB配置追踪
   - `docs/IMAGE_QUALITY_REWARD_CONFIG.md` - 图像质量配置
   - `REWARD_CONFIG_IMPLEMENTATION_SUMMARY.md` - 实现总结

3. **快速开始**
   - `QUICK_START.md` - 快速开始指南
   - `README.md` - 项目README

---

## ✅ 完整清单

现在所有奖励相关的配置都可以通过环境变量控制：

- [x] 图像质量模式（有参考/无参考）
- [x] 图像质量离散化等级
- [x] 退化类型bonus开关
- [x] 退化类型bonus权重
- [x] 格式奖励权重 ⭐ 新增
- [x] 准确性奖励权重 ⭐ 新增
- [x] 所有参数自动记录到WandB
- [x] 完整的文档和示例

---

**配置系统完成** 🎉

现在你可以灵活调整所有奖励参数，所有配置都会自动记录到WandB，方便实验追踪和结果复现！

