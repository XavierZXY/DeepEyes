# 奖励结构完整说明

## 🎯 核心理念

**清晰的命名**，**灵活的配置**，**完整的追踪**

---

## 📐 奖励结构

### 三个独立的奖励组件

```python
┌─────────────────────────────────────────────────────────┐
│                    总奖励 (Total Reward)                 │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ 格式奖励      │  │ 图像质量奖励  │  │ 退化类型奖励  │ │
│  │ Format       │  │ Quality      │  │ Degradation  │ │
│  │ Reward       │  │ Reward       │  │ Type Reward  │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│                                                         │
│  必须            必须            可选（默认关闭）          │
│  ✅              ✅              ⚙️                       │
└─────────────────────────────────────────────────────────┘
```

---

## 1️⃣ 格式奖励 (Format Reward)

### 作用
检查模型输出是否符合规定的格式规范。

### 评分
- `1.0`: 格式完美
- `-1.0`: 格式违规

### 要求
- 必须有 `<think>` 块（≥10字符）
- `<tool_call>` 和 `<answer>` 不能同时出现
- JSON格式必须正确
- 工具名称必须在允许列表中

### 权重配置
```bash
export FORMAT_REWARD_WEIGHT=0.3  # 默认0.3
```

**推荐范围**: 0.2 ~ 0.5

---

## 2️⃣ 图像质量奖励 (Quality Reward)

### 作用
评估最终复原图像的质量。

### 评分
- `0.0 ~ 1.0`: 连续分数（可离散化）

### 两种模式

#### 有参考模式 (Reference-based)
```python
quality_score = 0.35×SSIM + 0.50×(1-LPIPS) + 0.15×PSNR
```

**配置**:
```bash
export IMAGE_QUALITY_USE_NO_REFERENCE=False
```

**需要**: 数据集中的 `original_image`（GT）

**指标**:
- SSIM: 结构相似性 [-1, 1]
- LPIPS: 感知距离 [0, 1]（越小越好）
- PSNR: 信噪比 [10, 40]dB

---

#### 无参考模式 (No-reference，默认)
```python
quality_score = 0.20×(NIQE + BRISQUE + CPBD + CLIP-IQA + Hyper-IQA)
```

**配置**:
```bash
export IMAGE_QUALITY_USE_NO_REFERENCE=True  # 默认
```

**优势**: 不需要GT，所有样本都能计算

**指标**:
- NIQE: 自然度 [2, 15]（越小越好）
- BRISQUE: 盲质量 [0, 100]（越小越好）
- CPBD: 锐度 [0, 1]（越大越好）
- CLIP-IQA: 语义质量 [0, 1]（越大越好）
- Hyper-IQA: 局部失真 [0, 1]（越大越好）

---

### 权重配置
```bash
export QUALITY_REWARD_WEIGHT=0.7  # 默认0.7
```

**推荐范围**: 0.5 ~ 0.8

---

## 3️⃣ 退化类型奖励 (Degradation Type Reward)

### 作用
评估模型是否正确识别了退化类型（**不考虑顺序**）。

### 评分
- `1.0`: 完全匹配（预测集合 = 期望集合）
- `predicted/expected`: 部分匹配
- `0.0`: 无匹配或包含无效类型

### 示例

**期望**: `{blur, noise, jpeg_artifact}`

**预测**: `{noise, blur, jpeg_artifact}` → 1.0（顺序不同但集合相同）

**预测**: `{noise, blur}` → 0.667（2/3）

**预测**: `{noise, haze}` → 0.0（包含无效类型haze）

### 权重配置
```bash
export ENABLE_DEGRADATION_TYPE_REWARD=True   # 启用
export DEGRADATION_TYPE_REWARD_WEIGHT=1.0    # 权重
```

**推荐范围**: 0.5 ~ 1.5

**默认**: 关闭（`False`）

---

## 🔢 完整计算公式

### 默认配置（退化类型奖励关闭）

```python
total_reward = FORMAT_WEIGHT × format_score 
             + QUALITY_WEIGHT × quality_score

# 默认权重
total_reward = 0.3 × format_score + 0.7 × quality_score

# 奖励范围
[-0.3, 1.0]
```

### 启用退化类型奖励

```python
total_reward = FORMAT_WEIGHT × format_score 
             + QUALITY_WEIGHT × quality_score 
             + DEGRADATION_TYPE_WEIGHT × degradation_type_score

# 示例权重
total_reward = 0.3 × format_score + 0.7 × quality_score + 1.0 × degradation_type_score

# 奖励范围
[-0.3, 2.0]
```

---

## 📊 完整示例

### 示例1: 默认配置（格式+质量）

**配置**:
```bash
FORMAT_REWARD_WEIGHT=0.3
QUALITY_REWARD_WEIGHT=0.7
ENABLE_DEGRADATION_TYPE_REWARD=False  # 关闭
```

**计算**:
```python
format_score = 1.0      # 格式完美
quality_score = 0.85    # 图像质量优秀

total_reward = 0.3 × 1.0 + 0.7 × 0.85
             = 0.3 + 0.595
             = 0.895
```

**奖励组成**:
- 格式贡献: 0.300
- 质量贡献: 0.595
- 退化类型贡献: 0（未启用）
- **总分: 0.895**

---

### 示例2: 启用退化类型奖励

**配置**:
```bash
FORMAT_REWARD_WEIGHT=0.3
QUALITY_REWARD_WEIGHT=0.7
ENABLE_DEGRADATION_TYPE_REWARD=True
DEGRADATION_TYPE_REWARD_WEIGHT=1.0
```

**计算**:
```python
format_score = 1.0              # 格式完美
quality_score = 0.85            # 图像质量优秀
degradation_type_score = 1.0    # 退化类型完全匹配

total_reward = 0.3 × 1.0 + 0.7 × 0.85 + 1.0 × 1.0
             = 0.3 + 0.595 + 1.0
             = 1.895
```

**奖励组成**:
- 格式贡献: 0.300
- 质量贡献: 0.595
- 退化类型贡献: 1.000
- **总分: 1.895**

---

### 示例3: 部分退化类型匹配

**配置**:
```bash
FORMAT_REWARD_WEIGHT=0.3
QUALITY_REWARD_WEIGHT=0.7
ENABLE_DEGRADATION_TYPE_REWARD=True
DEGRADATION_TYPE_REWARD_WEIGHT=1.0
```

**计算**:
```python
format_score = 1.0              # 格式完美
quality_score = 0.75            # 图像质量良好
degradation_type_score = 0.667  # 识别了2/3的退化类型

total_reward = 0.3 × 1.0 + 0.7 × 0.75 + 1.0 × 0.667
             = 0.3 + 0.525 + 0.667
             = 1.492
```

**奖励组成**:
- 格式贡献: 0.300
- 质量贡献: 0.525
- 退化类型贡献: 0.667
- **总分: 1.492**

---

### 示例4: 格式错误

**配置**:
```bash
FORMAT_REWARD_WEIGHT=0.3
QUALITY_REWARD_WEIGHT=0.7
ENABLE_DEGRADATION_TYPE_REWARD=True
DEGRADATION_TYPE_REWARD_WEIGHT=1.0
```

**计算**:
```python
format_score = -1.0     # 格式违规（think内容太短）
quality_score = 0.9     # 即使质量很好
degradation_type_score = 1.0  # 即使类型完全匹配

# 格式错误时不给质量和退化类型奖励
total_reward = 0.3 × (-1.0)
             = -0.3
```

**奖励组成**:
- 格式贡献: -0.300（惩罚）
- 质量贡献: 0（不计算）
- 退化类型贡献: 0（不计算）
- **总分: -0.3**

---

## 🎨 命名对应关系

### 旧命名 vs 新命名

| 旧命名 | 新命名 | 说明 |
|-------|--------|------|
| `accuracy_score` | `quality_score` | 实际是图像质量分数，重命名更清晰 |
| `degradation_type_bonus` | `degradation_type_score` | 不是bonus，是独立的奖励组件 |
| `ENABLE_DEGRADATION_TYPE_BONUS` | `ENABLE_DEGRADATION_TYPE_REWARD` | 统一命名为reward |
| `DEGRADATION_TYPE_BONUS_WEIGHT` | `DEGRADATION_TYPE_REWARD_WEIGHT` | 统一命名为reward |
| `ACCURACY_REWARD_WEIGHT` | `QUALITY_REWARD_WEIGHT` | 更准确地反映实际含义 |

### 字段兼容性

为了向后兼容，返回的字典包含新旧字段：

```python
result_dict = {
    # 新字段（推荐使用）
    "score": total_score,                      # 总分
    "format_score": format_score,              # 格式分数
    "quality_score": quality_score,            # 图像质量分数
    "degradation_type_score": degradation_type_score,  # 退化类型分数
    
    # 旧字段（兼容）
    "accuracy_score": quality_score,           # = quality_score
    "degradation_order_score": quality_score,  # = quality_score
}
```

---

## 🔍 WandB中的显示

### Config部分

```yaml
reward_config:
  # 图像质量配置
  IMAGE_QUALITY_USE_NO_REFERENCE: "True"
  IMAGE_QUALITY_DISCRETIZE_LEVELS: "0"
  
  # 奖励权重配置
  FORMAT_REWARD_WEIGHT: "0.3"
  QUALITY_REWARD_WEIGHT: "0.7"
  
  # 退化类型奖励配置
  ENABLE_DEGRADATION_TYPE_REWARD: "False"
  DEGRADATION_TYPE_REWARD_WEIGHT: "1.0"
```

### Metrics部分

```python
# 训练过程中记录的指标
{
    "score": 1.895,                      # 总分
    "format_score": 1.0,                 # 格式分数
    "quality_score": 0.85,               # 图像质量分数 ⭐ 新命名
    "degradation_type_score": 1.0,       # 退化类型分数 ⭐ 新命名
    
    # 兼容旧字段
    "accuracy_score": 0.85,              # = quality_score
}
```

---

## 🚀 使用示例

### 场景1: 默认训练（格式+质量）

```bash
# IR.sh配置
export IMAGE_QUALITY_USE_NO_REFERENCE=True
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0
export FORMAT_REWARD_WEIGHT=0.3
export QUALITY_REWARD_WEIGHT=0.7
export ENABLE_DEGRADATION_TYPE_REWARD=False  # 关闭退化类型奖励
```

**奖励公式**:
```python
total = 0.3 × format_score + 0.7 × quality_score
```

**监控指标**:
- `score`: 总分 [-0.3, 1.0]
- `format_score`: 1.0 或 -1.0
- `quality_score`: 0.0 ~ 1.0

---

### 场景2: 强化退化类型识别

```bash
# IR.sh配置
export IMAGE_QUALITY_USE_NO_REFERENCE=True
export IMAGE_QUALITY_DISCRETIZE_LEVELS=10
export FORMAT_REWARD_WEIGHT=0.3
export QUALITY_REWARD_WEIGHT=0.7
export ENABLE_DEGRADATION_TYPE_REWARD=True   # 启用退化类型奖励
export DEGRADATION_TYPE_REWARD_WEIGHT=1.0
```

**奖励公式**:
```python
total = 0.3 × format_score + 0.7 × quality_score + 1.0 × degradation_type_score
```

**监控指标**:
- `score`: 总分 [-0.3, 2.0]
- `format_score`: 1.0 或 -1.0
- `quality_score`: 0.0 ~ 1.0
- `degradation_type_score`: 0.0 ~ 1.0

---

### 场景3: 自定义权重

```bash
# IR.sh配置
export IMAGE_QUALITY_USE_NO_REFERENCE=True
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0
export FORMAT_REWARD_WEIGHT=0.4              # 提高格式权重
export QUALITY_REWARD_WEIGHT=0.6             # 降低质量权重
export ENABLE_DEGRADATION_TYPE_REWARD=True
export DEGRADATION_TYPE_REWARD_WEIGHT=0.5    # 适度的退化类型奖励
```

**奖励公式**:
```python
total = 0.4 × format_score + 0.6 × quality_score + 0.5 × degradation_type_score
```

**奖励范围**: [-0.4, 1.5]

---

## 📈 权重调整建议

### FORMAT_REWARD_WEIGHT（格式奖励权重）

| 值 | 场景 | 效果 |
|----|------|------|
| 0.1 | 格式已稳定 | 轻微约束 |
| **0.3** | **默认** | **平衡** |
| 0.5 | 格式问题严重 | 强约束 |
| 0.7 | 极度重视格式 | 强惩罚 |

---

### QUALITY_REWARD_WEIGHT（图像质量权重）

| 值 | 场景 | 效果 |
|----|------|------|
| 0.3 | 弱化质量 | 更关注格式 |
| 0.5 | 平衡 | 均衡优化 |
| **0.7** | **默认** | **关注质量** |
| 0.9 | 纯质量优化 | 最大化质量 |

**建议**: `FORMAT_WEIGHT + QUALITY_WEIGHT = 1.0` 保持奖励范围一致

---

### DEGRADATION_TYPE_REWARD_WEIGHT（退化类型权重）

| 值 | 场景 | 效果 |
|----|------|------|
| 0.3 | 轻微引导 | 辅助信号 |
| 0.5 | 适度引导 | 平衡 |
| **1.0** | **默认** | **显著鼓励** |
| 1.5 | 强引导 | 强监督 |

**注意**: 这是额外奖励，会增加总分上限

---

## 🎯 完整配置对照表

| 配置方案 | FORMAT | QUALITY | DEGRADATION_TYPE<br>(启用/权重) | 总分范围 | 适用阶段 |
|---------|--------|---------|------------------------------|---------|---------|
| **默认** | 0.3 | 0.7 | ❌ / - | [-0.3, 1.0] | 常规训练 |
| **早期训练** | 0.3 | 0.7 | ✅ / 1.0 | [-0.3, 2.0] | Epoch 1-10 |
| **中期训练** | 0.3 | 0.7 | ✅ / 0.5 | [-0.3, 1.5] | Epoch 10-20 |
| **后期训练** | 0.3 | 0.7 | ❌ / - | [-0.3, 1.0] | Epoch 20-32 |
| **强格式** | 0.5 | 0.5 | ❌ / - | [-0.5, 1.0] | 格式问题严重 |
| **强监督** | 0.3 | 0.7 | ✅ / 1.5 | [-0.3, 2.5] | 快速收敛 |

---

## ✅ WandB追踪验证

### 检查清单

训练开始后，验证以下内容：

- [ ] 控制台显示:
  ```
  [INFO] Image Quality Reward Config: use_no_reference=True, discretize_levels=0
  [INFO] Reward Weights: format=0.3, quality=0.7
  [INFO] Degradation Type Reward Config: enable=False, weight=1.0
  [INFO] Added reward config to wandb: {...}
  ```

- [ ] WandB Overview → Config → `reward_config` 包含所有6个参数

- [ ] Metrics中有:
  - `score` (总分)
  - `format_score` (格式分)
  - `quality_score` (质量分)
  - `degradation_type_score` (退化类型分，启用时)

---

## 📚 快速参考

### 命令行测试

```bash
# 测试配置记录
python test_wandb_config.py

# 查看当前配置
echo "FORMAT_WEIGHT: $FORMAT_REWARD_WEIGHT"
echo "QUALITY_WEIGHT: $QUALITY_REWARD_WEIGHT"
echo "DEGRADATION_TYPE: $ENABLE_DEGRADATION_TYPE_REWARD ($DEGRADATION_TYPE_REWARD_WEIGHT)"
```

### 修改配置

1. 编辑 `examples/agent/IR.sh`
2. 修改相应的 `export` 语句
3. 运行训练: `bash examples/agent/IR.sh`
4. 检查WandB中的 `config.reward_config`

---

## 🔑 核心要点

1. **默认奖励 = 格式 + 图像质量** ✅
   - 简单清晰，适合大部分场景
   
2. **退化类型奖励是可选的** ⚙️
   - 需要时启用，提供额外监督信号
   - 不替代主奖励，而是叠加

3. **权重灵活可调** 🔧
   - 所有权重都可以通过环境变量配置
   - 建议 FORMAT + QUALITY = 1.0

4. **自动记录到WandB** 📊
   - 所有配置参数都会记录
   - 方便实验对比和复现

---

**更新完成** 🎉

奖励结构现在更加清晰：
- **格式奖励**: 检查输出规范
- **图像质量奖励**: 评估复原质量（主要优化目标）
- **退化类型奖励**: 识别退化类型（可选的额外监督）

