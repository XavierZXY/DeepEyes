# 图像质量奖励机制详解

## 📋 概述

图像质量奖励是训练系统中的核心奖励组件，用于评估模型处理后的图像质量。系统支持两种评估模式：**有参考模式**和**无参考模式**。

## 🎯 当前配置（IRv2.sh）

```bash
export IMAGE_QUALITY_USE_NO_REFERENCE=False  # 使用有参考指标
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0     # 连续奖励（不离散化）
```

## 📊 两种评估模式

### 模式1：有参考模式（Reference-Based）

**配置**: `IMAGE_QUALITY_USE_NO_REFERENCE=False`

#### 使用的指标

| 指标 | 全称 | 范围 | 含义 | 权重 |
|------|------|------|------|------|
| **SSIM** | Structural Similarity | [-1, 1] | 结构相似性，越接近1越好 | 35% (α=0.35) |
| **LPIPS** | Learned Perceptual Image Patch Similarity | [0, 1] | 感知相似性，越接近0越好 | 50% (β=0.50) |
| **PSNR** | Peak Signal-to-Noise Ratio | [10, 40]dB | 峰值信噪比，越大越好 | 15% (γ=0.15) |

#### 奖励计算公式

```python
# 1. 归一化各指标到[0, 1]
norm_ssim = (ssim - (-1)) / (1 - (-1))          # SSIM归一化
norm_lpips = lpips                               # LPIPS已在[0,1]
norm_psnr = (psnr - 10) / (40 - 10)             # PSNR归一化

# 2. 计算综合奖励
reward = 0.35 × norm_ssim + 0.50 × (1 - norm_lpips) + 0.15 × norm_psnr
reward = clip(reward, 0.0, 1.0)  # 限制在[0, 1]范围
```

#### 权重设计理由

- **LPIPS权重最高(50%)**: 
  - 基于深度特征，最接近人类感知
  - 能捕捉高层语义信息
  - 对纹理、颜色、结构变化敏感

- **SSIM权重中等(35%)**:
  - 结构相似性指标
  - 对纹理和边缘敏感
  - 计算简单高效

- **PSNR权重较低(15%)**:
  - 像素级误差指标
  - 作为辅助参考
  - 不完全反映人类感知

#### 指标归一化规则

**SSIM归一化**:
```python
# 线性映射 [-1, 1] → [0, 1]
norm_ssim = (ssim + 1.0) / 2.0
```

**LPIPS归一化**:
```python
# 反向映射（值越小越好）
norm_lpips_inverted = 1.0 - lpips
# 因为LPIPS越小表示越相似，所以取反
```

**PSNR归一化**:
```python
# 线性映射 [10dB, 40dB] → [0, 1]
norm_psnr = (psnr - 10.0) / (40.0 - 10.0)
# 10dB: 质量很差 → 0.0
# 20dB: 可接受   → 0.33
# 30dB: 良好     → 0.67
# 40dB: 优秀     → 1.0
```

#### 优点

✅ 准确度高，直接与Ground Truth对比  
✅ 多维度评估（结构、感知、像素）  
✅ 权重优化，更接近人类感知  

#### 缺点

❌ 需要原始图像（Ground Truth）  
❌ 只能评估执行了工具的样本  
❌ 对于Clean样本或未执行工具的样本返回0.0  

---

### 模式2：无参考模式（No-Reference）

**配置**: `IMAGE_QUALITY_USE_NO_REFERENCE=True`

#### 使用的指标

| 指标 | 全称 | 范围 | 含义 | 权重 |
|------|------|------|------|------|
| **NIQE** | Natural Image Quality Evaluator | [2, 15] | 自然场景统计特征，越小越好 | 20% (α=0.20) |
| **BRISQUE** | Blind/Referenceless Image Spatial Quality Evaluator | [0, 100] | 亮度结构信息，越小越好 | 20% (β=0.20) |
| **CPBD** | Cumulative Probability of Blur Detection | [0, 1] | 清晰度评估，越大越好 | 20% (γ=0.20) |
| **CLIP-IQA** | CLIP-based Image Quality Assessment | [0, 1] | 语义质量评估，越大越好 | 20% (δ=0.20) |
| **Hyper-IQA** | Hypernetwork-based IQA | [0, 1] | 局部失真检测，越大越好 | 20% (ε=0.20) |

#### 奖励计算公式

```python
# 1. 归一化各指标到[0, 1]
norm_niqe = 1.0 - (niqe - 2.0) / (15.0 - 2.0)        # 反向归一化
norm_brisque = 1.0 - (brisque - 0.0) / (100.0 - 0.0) # 反向归一化
norm_cpbd = cpbd                                      # 直接使用
norm_clip_iqa = clip_iqa                             # 直接使用
norm_hyper_iqa = hyper_iqa                           # 直接使用

# 2. 计算综合奖励（均等权重）
reward = 0.20 × norm_niqe 
       + 0.20 × norm_brisque 
       + 0.20 × norm_cpbd 
       + 0.20 × norm_clip_iqa 
       + 0.20 × norm_hyper_iqa
reward = clip(reward, 0.0, 1.0)
```

#### 均等权重设计理由

- **各指标关注不同维度**：确保全面评估
- **避免偏向某一类指标**：保持评估平衡性
- **适应多种图像类型**：不同图像类型的最优指标不同

#### 各指标特点

**NIQE (Natural Image Quality Evaluator)**:
- 基于自然场景统计 (NSS)
- 评估图像是否符合自然图像分布
- 无需训练，计算高效

**BRISQUE (Blind/Referenceless)**:
- 结合空间域统计特征
- 对噪声、模糊、压缩失真敏感
- 需要预训练模型

**CPBD (Cumulative Probability of Blur Detection)**:
- 专注于模糊检测
- 基于边缘锐度分析
- 对去模糊任务特别有效

**CLIP-IQA**:
- 基于CLIP视觉编码器
- 评估语义层面的图像质量
- 对内容完整性敏感

**Hyper-IQA**:
- 基于超网络架构
- 检测局部失真和伪影
- 泛化能力强

#### 优点

✅ 不需要Ground Truth原图  
✅ 所有样本都能计算（包括Clean样本）  
✅ 适合训练阶段使用  
✅ 多维度综合评估  

#### 缺点

❌ 准确度相对较低  
❌ 计算开销较大（5个指标）  
❌ 可能与人类感知有偏差  

---

## 🔄 离散化选项

**配置**: `IMAGE_QUALITY_DISCRETIZE_LEVELS`

### 离散化等级

| 等级值 | 效果 | 示例 |
|--------|------|------|
| **0** | 连续奖励（默认） | 0.8234 → 0.8234 |
| **10** | 每10%一档 | 0.8234 → 0.8000 |
| **20** | 每5%一档 | 0.8234 → 0.8000 |

### 离散化公式

```python
if discretize_levels > 0:
    discrete_reward = round(continuous_reward × discretize_levels) / discretize_levels
else:
    discrete_reward = continuous_reward
```

### 使用场景

| 场景 | 推荐配置 | 理由 |
|------|---------|------|
| 训练稳定阶段 | `discretize_levels=0` | 保留梯度信息，精细调优 |
| 训练早期 | `discretize_levels=10` | 减少奖励波动，加速收敛 |
| 极端噪声环境 | `discretize_levels=20` | 更粗粒度，抗噪声 |

---

## 📈 奖励范围和含义

### 奖励分数解释

| 分数范围 | 质量等级 | 含义 |
|---------|---------|------|
| 0.9 - 1.0 | 优秀 | 复原效果接近完美 |
| 0.8 - 0.9 | 良好 | 复原效果明显，轻微瑕疵 |
| 0.7 - 0.8 | 中等 | 有一定改善，仍有明显问题 |
| 0.5 - 0.7 | 较差 | 改善有限 |
| 0.0 - 0.5 | 很差 | 几乎没有改善或变差 |

### 特殊情况

| 情况 | 返回值 | 说明 |
|------|--------|------|
| 未执行工具 | 0.0 | 没有image_history |
| 计算失败 | 0.0 | 异常情况 |
| Clean样本（有参考模式） | 不计算 | 使用clean检测奖励 |
| Clean样本（无参考模式） | 正常计算 | 评估原始图像质量 |

---

## 🔧 推荐配置

### 配置1：训练阶段（推荐）

```bash
export IMAGE_QUALITY_USE_NO_REFERENCE=True   # 无参考指标
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0     # 连续奖励
```

**优点**:
- ✅ 所有样本都能计算
- ✅ 不需要Ground Truth
- ✅ 精细的梯度信息

**适用于**: 常规训练、没有原图的场景

---

### 配置2：训练早期（稳定性优先）

```bash
export IMAGE_QUALITY_USE_NO_REFERENCE=True   # 无参考指标
export IMAGE_QUALITY_DISCRETIZE_LEVELS=10    # 离散化
```

**优点**:
- ✅ 减少奖励波动
- ✅ 加速早期收敛
- ✅ 对噪声鲁棒

**适用于**: 训练不稳定、奖励波动大

---

### 配置3：有Ground Truth（精确度优先）

```bash
export IMAGE_QUALITY_USE_NO_REFERENCE=False  # 有参考指标
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0     # 连续奖励
```

**优点**:
- ✅ 最准确的评估
- ✅ 更接近人类感知
- ✅ 多维度综合

**适用于**: 有原图、精确评估场景

**注意**: Clean样本和未执行工具的样本会返回0.0

---

### 配置4：您当前的配置 ✅

```bash
export IMAGE_QUALITY_USE_NO_REFERENCE=False  # 有参考指标
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0     # 连续奖励
```

**特点**:
- 使用SSIM、LPIPS、PSNR三个有参考指标
- 权重: LPIPS(50%) + SSIM(35%) + PSNR(15%)
- 连续奖励，保留完整梯度信息
- 需要原始Ground Truth图像

**适合**: 数据集包含原图，追求最高准确度

---

## 🎨 实际示例

### 示例1：有参考模式评估

**输入**:
- 复原图: 去噪后的图像
- 原图: Ground Truth

**计算过程**:
```python
# 原始指标
ssim_val = 0.85      # 结构相似性
lpips_val = 0.12     # 感知距离
psnr_val = 28.5      # 峰值信噪比

# 归一化
norm_ssim = (0.85 + 1.0) / 2.0 = 0.925
norm_lpips = 1.0 - 0.12 = 0.88
norm_psnr = (28.5 - 10.0) / 30.0 = 0.617

# 综合奖励
reward = 0.35 × 0.925 + 0.50 × 0.88 + 0.15 × 0.617
       = 0.324 + 0.440 + 0.093
       = 0.857

# 结果: 0.857 → 良好质量
```

---

### 示例2：无参考模式评估

**输入**:
- 复原图: 去雨后的图像

**计算过程**:
```python
# 原始指标
niqe_val = 4.2          # 越小越好
brisque_val = 25.0      # 越小越好
cpbd_val = 0.72         # 越大越好
clip_iqa_val = 0.68     # 越大越好
hyper_iqa_val = 0.75    # 越大越好

# 归一化
norm_niqe = 1.0 - (4.2 - 2.0) / 13.0 = 0.831
norm_brisque = 1.0 - 25.0 / 100.0 = 0.75
norm_cpbd = 0.72
norm_clip_iqa = 0.68
norm_hyper_iqa = 0.75

# 综合奖励（均等权重）
reward = 0.20 × (0.831 + 0.75 + 0.72 + 0.68 + 0.75)
       = 0.20 × 3.731
       = 0.746

# 结果: 0.746 → 中等质量
```

---

## 💡 最佳实践

### 1. 模式选择

| 场景 | 推荐模式 |
|------|---------|
| 有原图数据集 | 有参考模式 |
| 无原图或在线训练 | 无参考模式 |
| 早期探索 | 无参考模式 |
| 精确调优 | 有参考模式 |

### 2. 离散化选择

| 训练阶段 | 推荐设置 |
|---------|---------|
| 早期（不稳定） | `discretize_levels=10` |
| 中期（较稳定） | `discretize_levels=0` |
| 后期（精调） | `discretize_levels=0` |

### 3. 权重调整

**有参考模式** (可在代码中修改):
```python
# image_restoration.py 第1020行
alpha, beta, gamma = 0.35, 0.50, 0.15  # SSIM, LPIPS, PSNR
```

**无参考模式** (可在代码中修改):
```python
# image_quality_metrics.py 第1004-1008行
alpha = 0.20    # NIQE
beta = 0.20     # BRISQUE
gamma = 0.20    # CPBD
delta = 0.20    # CLIP-IQA
epsilon = 0.20  # Hyper-IQA
```

---

## 📊 与其他奖励的关系

### 总奖励结构

```python
总奖励 = 格式奖励权重 × 格式分数 + 质量奖励权重 × 图像质量分数

# 当前配置
格式奖励权重 = 0.3
质量奖励权重 = 0.7
```

### 示例计算

```python
# 格式正确，图像质量良好
format_score = 1.0          # 格式完美
quality_score = 0.857       # 图像质量良好

total_reward = 0.3 × 1.0 + 0.7 × 0.857
             = 0.3 + 0.600
             = 0.900

# 最终奖励: 0.900（优秀）
```

---

## 🔍 调试和监控

### 日志输出

**有参考模式**:
```
[DEBUG image_quality] ssim=0.85(norm=0.925), 
                      lpips=0.12(norm=0.88), 
                      psnr=28.5(norm=0.617)
[DEBUG image_quality] weights: α=0.35(SSIM), β=0.50(LPIPS), γ=0.15(PSNR)
[DEBUG image_quality] reward=0.857 (越接近1表示复原质量越好)
```

**无参考模式**:
```
[DEBUG no_ref_image_quality] niqe=4.2(norm=0.831), 
                             brisque=25.0(norm=0.75), 
                             cpbd=0.72(norm=0.72)
[DEBUG no_ref_image_quality] clip_iqa=0.68(norm=0.68), 
                             hyper_iqa=0.75(norm=0.75)
[DEBUG no_ref_image_quality] reward=0.746 (越接近1表示复原质量越好)
```

---

## 📝 总结

### 当前配置总结 (IRv2.sh)

```bash
模式: 有参考模式
指标: SSIM(35%) + LPIPS(50%) + PSNR(15%)
离散化: 关闭（连续奖励）
适用: 有Ground Truth的精确评估场景
```

### 关键要点

1. ✅ **有参考模式**最准确，但需要原图
2. ✅ **无参考模式**更灵活，适合训练阶段
3. ✅ **离散化**可以减少波动，但会损失精度
4. ✅ **权重设计**考虑了人类感知特性
5. ✅ **多指标融合**提供全面的质量评估

### 快速切换

```bash
# 切换到无参考模式
export IMAGE_QUALITY_USE_NO_REFERENCE=True

# 启用离散化
export IMAGE_QUALITY_DISCRETIZE_LEVELS=10
```

---

**文档版本**: v1.0  
**最后更新**: 2025-10-31  
**适用版本**: AIR v9

