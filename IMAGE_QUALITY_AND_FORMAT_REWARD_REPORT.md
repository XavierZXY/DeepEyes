# 图像质量奖励与格式奖励完整报告

生成时间：2025-10-11  
基于代码版本：DeepEyes (AIR项目)

---

## 📋 目录

1. [总体奖励架构](#总体奖励架构)
2. [图像质量奖励详解](#图像质量奖励详解)
3. [格式奖励详解](#格式奖励详解)
4. [配置参数说明](#配置参数说明)
5. [奖励计算示例](#奖励计算示例)

---

## 总体奖励架构

### 奖励组成公式

```python
总奖励 = 格式分数 + 准确性分数

其中准确性分数可以是：
- 图像质量奖励 (image_quality模式，默认)
- 退化顺序奖励 (partial_credit模式)
```

### 核心函数调用链

```
compute_score_v2()  # 主奖励函数
├── check_multiturn_format_v2()  # 格式检查（严格模式）
│   └── 返回 1.0 或 -1.0
├── check_response_format_v2()   # 格式检查（渐进模式）
│   └── 返回 0.0 ~ 1.0
└── compute_image_quality_reward_v2()  # 图像质量奖励
    ├── compute_image_restoration_reward()        # 有参考模式
    │   └── SSIM + LPIPS + PSNR
    └── compute_no_reference_image_restoration_reward()  # 无参考模式
        └── NIQE + BRISQUE + CPBD + CLIP-IQA + Hyper-IQA
```

---

## 图像质量奖励详解

### 两种计算模式

#### 模式1：有参考指标 (Reference-based)

**配置**: `IMAGE_QUALITY_USE_NO_REFERENCE=False`

**需要数据**: 原始GT图像（从数据集的`original_image`字段获取）

**使用指标**:

| 指标 | 权重 | 数值范围 | 归一化范围 | 方向 | 作用 |
|-----|------|----------|-----------|------|------|
| **SSIM** | **α=0.35** | [-1, 1] | [0, 1] | 越大越好 | **结构相似性**，衡量纹理和边缘的相似度 |
| **LPIPS** | **β=0.50** | [0, 1] | [0, 1] | 越小越好 | **感知相似性**（最重要），基于深度学习特征，最接近人类视觉感知 |
| **PSNR** | **γ=0.15** | [10, 40] dB | [0, 1] | 越大越好 | **峰值信噪比**，像素级误差，辅助指标 |

**奖励公式**:
```python
reward = α × SSIM_norm + β × (1 - LPIPS_norm) + γ × PSNR_norm
       = 0.35 × SSIM_norm + 0.50 × (1 - LPIPS_norm) + 0.15 × PSNR_norm
```

**归一化策略**:
- SSIM: 线性归一化 `(x - (-1)) / 2`
- LPIPS: 线性归一化，取反（因为越小越好）
- PSNR: **非线性归一化**，使用平方根函数增强低质量区分度
  ```python
  linear_norm = (psnr - 10) / (40 - 10)
  psnr_norm = sqrt(linear_norm)
  ```

**质量等级参考**:

| 等级 | SSIM | LPIPS | PSNR (dB) | 奖励分数 | 说明 |
|------|------|-------|-----------|----------|------|
| 完美复原 | 1.00 | 0.00 | 40 | 0.95+ | 几乎与GT完全一致 |
| 优秀质量 | 0.95 | 0.05 | 35 | 0.87 | 结构完整，感知优秀 |
| 良好质量 | 0.90 | 0.10 | 30 | 0.75 | 结构良好，感知可接受 |
| 中等质量 | 0.80 | 0.20 | 25 | 0.58 | 可识别，有明显失真 |
| 可接受质量 | 0.70 | 0.30 | 20 | 0.42 | 基本可用 |
| 较差质量 | 0.60 | 0.45 | 15 | 0.28 | 严重失真 |

**为什么LPIPS权重最高 (50%)?**
1. 基于深度学习特征（VGG/AlexNet），更接近人类视觉系统
2. 对细节恢复和感知质量最敏感
3. 能够有效区分不同复原质量
4. 比像素级指标(PSNR)和结构指标(SSIM)更符合人类主观评价

---

#### 模式2：无参考指标 (No-reference)

**配置**: `IMAGE_QUALITY_USE_NO_REFERENCE=True` (默认)

**优势**: 不需要GT，所有样本都能计算奖励（训练更稳定）

**使用指标**:

| 指标 | 权重 | 数值范围 | 归一化范围 | 方向 | 作用 |
|-----|------|----------|-----------|------|------|
| **NIQE** | **α=0.20** | [2, 15] | [0, 1] | 越小越好 | **自然度评估**，关注自然场景统计特征 |
| **BRISQUE** | **β=0.20** | [0, 100] | [0, 1] | 越小越好 | **盲质量评估**，结合亮度和结构信息 |
| **CPBD** | **γ=0.20** | [0, 1] | [0, 1] | 越大越好 | **锐度评估**，常用于评估模糊和压缩失真 |
| **CLIP-IQA** | **δ=0.20** | [0, 1] | [0, 1] | 越大越好 | **语义质量**，强调图像的语义信息（基于CLIP） |
| **Hyper-IQA** | **ε=0.20** | [0, 1] | [0, 1] | 越大越好 | **局部失真检测**，能够检测局部失真 |

**奖励公式**:
```python
reward = α × NIQE_norm + β × BRISQUE_norm + γ × CPBD_norm 
         + δ × CLIP-IQA_norm + ε × Hyper-IQA_norm
       = 0.20 × (所有5个指标的均等加权)
```

**归一化策略**:
- NIQE & BRISQUE: **反向归一化**（值越小越好）
  ```python
  norm = 1.0 - (value - min) / (max - min)
  ```
- CPBD, CLIP-IQA, Hyper-IQA: 线性归一化（值越大越好）

**为什么采用均等权重?**
1. 各指标关注不同的图像质量维度，均等权重确保全面评估
2. 避免偏向某一类指标，保持评估的平衡性
3. 可根据具体应用场景调整权重

**各指标详细说明**:

- **NIQE** (Natural Image Quality Evaluator):
  - 基于自然场景统计 (NSS) 模型
  - 典型好图像: < 5
  - 典型差图像: > 10
  
- **BRISQUE** (Blind/Referenceless Image Spatial QE):
  - 分析MSCN系数的统计特征
  - 典型好图像: < 40
  - 典型差图像: > 60
  
- **CPBD** (Cumulative Probability of Blur Detection):
  - 基于边缘检测和局部对比度
  - 高清晰度: > 0.8
  - 模糊图像: < 0.4
  
- **CLIP-IQA**:
  - 使用CLIP模型提取图像语义特征
  - 评估图像的高层语义质量
  
- **Hyper-IQA**:
  - 深度学习模型，能捕捉局部失真模式
  - 对局部伪影敏感

---

### 离散化选项

**配置**: `IMAGE_QUALITY_DISCRETIZE_LEVELS`

```python
discretize_levels = 0   # 不离散化，保持连续（默认）
discretize_levels = 10  # 每10%一档 (0.0, 0.1, 0.2, ..., 1.0)
discretize_levels = 20  # 每5%一档  (0.0, 0.05, 0.10, ..., 1.0)
```

**离散化效果**:
```python
连续值: 0.8234 
discretize_levels=10  → 0.8
discretize_levels=20  → 0.8
discretize_levels=0   → 0.8234 (不变)
```

**为什么需要离散化?**
1. **减少奖励噪声**: 小的质量波动不会影响奖励
2. **加速早期收敛**: 离散化梯度更明确
3. **避免过拟合**: 防止模型过度关注细微质量差异

**推荐配置**:
- 训练早期: `discretize_levels=10` (稳定训练)
- 训练后期: `discretize_levels=0` (精细优化)

---

### 图像数据流

```
数据集 (Parquet)
├── original_image (GT，未退化的原图) → 用于有参考指标计算
├── 输入prompt
└── env_name (退化类型)
         ↓
Agent Rollout
├── image_history[0]: 退化后的输入图像
├── image_history[1]: 工具1处理后的图像
├── image_history[2]: 工具2处理后的图像
└── image_history[-1]: 最终复原图像 ← 用于质量评估
         ↓
质量奖励计算
├── 有参考: compare(image_history[-1], original_image)
└── 无参考: evaluate(image_history[-1])
```

**关键点**:
- `original_image` 来自数据集，是未退化的真实原图（GT）
- `image_history[0]` 是退化后的输入图像（不用于质量评估）
- `image_history[-1]` 是最后一个被工具处理的图像（复原结果）
- 如果 `len(image_history) < 2`，说明没有执行工具，返回0分

---

## 格式奖励详解

### 格式要求

模型输出必须遵循以下格式：

```xml
<think>
推理内容（至少10个字符，描述退化检测和处理策略）
</think>

<!-- 二选一，不能同时出现 -->

<!-- 选项1: 使用工具 -->
<tool_call>
[
  {
    "name": "工具名称",
    "arguments": {参数}
  }
]
</tool_call>

<!-- 选项2: 给出最终答案 -->
<answer>
{
  "restoration_log": ["退化类型1", "退化类型2", ...]
}
</answer>
```

### 格式检查模式

#### 模式1: 严格格式检查 (strict_format=True, 默认)

**函数**: `check_multiturn_format_v2()`

**返回值**: 
- `1.0`: 完美格式，所有规则满足
- `-1.0`: 任何格式违规

**检查规则** (ALL must be satisfied):

1. ✅ **必须有`<think>`块**，内容 ≥ 10字符
2. ✅ **`<tool_call>`和`<answer>`不能同时出现**
3. ✅ **可以只有`<think>`**（纯思考，无行动也是允许的）
4. ✅ **`<tool_call>`格式必须正确**:
   - 必须是有效的JSON列表
   - 每个元素必须有`name`和`arguments`字段
   - `name`必须在允许的工具列表中
5. ✅ **`<answer>`格式必须正确**:
   - 必须是有效的JSON对象
   - 必须有`restoration_log`字段（列表类型）
   - **只能有`restoration_log`字段，不能有其他字段**

**允许的工具列表**:
```python
# 去雾
"dehazeformer_dehaze"

# 去模糊
"drbnet_defocus_deblurring", "xrestormer_motion_deblurring", 
"mprnet_motion_deblurring", "restormer_motion_deblurring",
"restormer_defocus_deblurring"

# 去雨
"mprnet_deraining", "restormer_deraining", "xrestormer_deraining"

# JPEG伪影去除
"swinir_jpeg_artifact_removal", "fbcnn_jpeg_artifact_removal"

# 质量评估
"fbcnn_blind_quality_assessment"

# 超分辨率
"swinir_super_resolution"

# 去噪
"swinir_denoising", "mprnet_denoising"

# 基础调整
"histogram_equalization", "gamma_correction", "constant_shift"

# 视觉工具箱
"visual_toolbox", "visual_toolbox_v2", "visual_toolbox_v3", 
"visual_toolbox_v4", "visual_toolbox_v5"

# 图像处理
"crop_image"
```

**示例 - 完美格式**:
```xml
<think>
图像存在JPEG压缩伪影和模糊，根据LIFO原则，应该先处理压缩伪影（最后添加的退化）
</think>
<tool_call>
[
  {"name": "swinir_jpeg_artifact_removal", "arguments": {}}
]
</tool_call>
```

**示例 - 格式错误（-1.0分）**:
```xml
<!-- 错误1: think内容太短 -->
<think>OK</think>
<tool_call>[...]</tool_call>

<!-- 错误2: tool_call和answer同时出现 -->
<think>...</think>
<tool_call>[...]</tool_call>
<answer>{...}</answer>

<!-- 错误3: answer有额外字段 -->
<think>...</think>
<answer>
{
  "restoration_log": [...],
  "confidence": 0.9  <!-- 不允许！ -->
}
</answer>

<!-- 错误4: 使用未注册的工具 -->
<think>...</think>
<tool_call>
[
  {"name": "my_custom_tool", "arguments": {}}  <!-- 不在允许列表 -->
]
</tool_call>
```

---

#### 模式2: 渐进格式检查 (strict_format=False)

**函数**: `check_response_format_v2()`

**返回值**: `0.0 ~ 1.0` (渐进式部分分数)

**评分细则**:

| 项目 | 满分 | 评分标准 |
|-----|------|----------|
| **Think块** | 0.4 | • 有内容 ≥10字符: +0.3<br>• 包含质量推理关键词: +0.1<br>• 只有少量内容: +0.1 |
| **格式冲突** | -0.8 | • tool_call和answer同时出现: -0.8 (严重惩罚) |
| **Tool Call** | 0.4 | • 存在tool_call块: +0.2<br>• 有效JSON列表: +0.1<br>• 工具名称和参数合法: +0.1<br>• JSON解析失败: -0.2 |
| **Answer** | 0.6 | • 存在answer块: +0.2<br>• 有效JSON: +0.1<br>• 有restoration_log字段: +0.1<br>• restoration_log是列表: +0.1<br>• 只有restoration_log字段: +0.1<br>• 有额外字段: -0.1<br>• JSON解析失败: -0.2 |

**质量推理关键词**:
```python
keywords = [
    "artifact", "blur", "noise", "haze", "rain", "dark", "compression",
    "clean", "priority", "lifo", "degradation", "highest", "fix"
]
```

**示例 - 部分分数**:
```xml
<!-- 0.4分: 只有think -->
<think>图像质量不错</think>

<!-- 0.5分: think + 质量关键词 -->
<think>图像有JPEG压缩伪影，需要处理</think>

<!-- 0.9分: think + tool_call完整 -->
<think>检测到JPEG伪影，使用SwinIR处理</think>
<tool_call>
[{"name": "swinir_jpeg_artifact_removal", "arguments": {}}]
</tool_call>

<!-- 1.0分: think + answer完美 -->
<think>图像已完全清晰，无需进一步处理</think>
<answer>
{"restoration_log": ["jpeg_artifact", "blur"]}
</answer>
```

---

### 特殊场景：Clean样本

**识别**: `env_name == "clean"`

**格式要求**: 必须给出`<answer>`，且`restoration_log`为空列表或只包含`["clean"]`

**示例 - 正确响应**:
```xml
<think>
图像质量很好，没有检测到明显退化，无需处理
</think>
<answer>
{"restoration_log": []}
</answer>
```

或：
```xml
<think>
经过检查，图像清晰无伪影
</think>
<answer>
{"restoration_log": ["clean"]}
</answer>
```

**示例 - 错误响应**:
```xml
<!-- 错误：clean样本使用了工具 -->
<think>...</think>
<tool_call>[...]</tool_call>

<!-- 错误：restoration_log包含退化类型 -->
<answer>
{"restoration_log": ["clean", "jpeg_artifact"]}
</answer>
```

---

## 配置参数说明

### 环境变量配置

```bash
# IR.sh 中的配置
export IMAGE_QUALITY_USE_NO_REFERENCE=False
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0
```

### 参数详解

#### IMAGE_QUALITY_USE_NO_REFERENCE

| 值 | 模式 | 指标 | 需要GT | 适用场景 |
|----|------|------|--------|----------|
| `True` | 无参考 | NIQE + BRISQUE + CPBD + CLIP-IQA + Hyper-IQA | ❌ | **训练阶段**（所有样本都能计算） |
| `False` | 有参考 | SSIM + LPIPS + PSNR | ✅ | **有GT数据**（评估更准确） |

**推荐配置**:
- 训练: `True` (无参考，适用于所有样本)
- 评估/微调: `False` (有参考，如果数据集有GT)

---

#### IMAGE_QUALITY_DISCRETIZE_LEVELS

| 值 | 档位 | 示例 | 适用场景 |
|----|------|------|----------|
| `0` | 连续 | 0.8234 | **训练后期**（精细优化） |
| `10` | 11档 (10%) | 0.0, 0.1, 0.2, ..., 1.0 | **训练早期**（稳定训练） |
| `20` | 21档 (5%) | 0.0, 0.05, 0.10, ..., 1.0 | **训练中期**（平衡） |

**效果对比**:
```python
continuous_reward = 0.8234

discretize_levels=0  → 0.8234  # 保留完整精度
discretize_levels=10 → 0.8000  # 四舍五入到0.1
discretize_levels=20 → 0.8000  # 四舍五入到0.05
```

---

### 推荐训练策略

#### 阶段1: 训练早期 (Epoch 1-10)
```bash
export IMAGE_QUALITY_USE_NO_REFERENCE=True   # 无参考，所有样本可用
export IMAGE_QUALITY_DISCRETIZE_LEVELS=10    # 离散化，减少噪声
```
**目标**: 快速收敛，学习基本格式

---

#### 阶段2: 训练中期 (Epoch 10-25)
```bash
export IMAGE_QUALITY_USE_NO_REFERENCE=True   # 保持无参考
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0     # 切换到连续
```
**目标**: 精细调整，优化质量

---

#### 阶段3: 微调 (可选，如果有GT)
```bash
export IMAGE_QUALITY_USE_NO_REFERENCE=False  # 切换到有参考
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0     # 保持连续
```
**目标**: 最大化与GT的相似度

---

## 奖励计算示例

### 示例1: 完美工具调用 (有GT)

**模型输出**:
```xml
<think>
图像存在JPEG压缩伪影和轻微模糊，根据LIFO原则先处理压缩伪影
</think>
<tool_call>
[{"name": "swinir_jpeg_artifact_removal", "arguments": {}}]
</tool_call>
```

**计算过程**:
```python
# 格式分数 (严格模式)
format_score = 1.0  # 完美格式

# 图像质量分数 (有参考模式)
# 假设复原后: SSIM=0.92, LPIPS=0.08, PSNR=32dB
norm_ssim = 0.96    # (0.92 - (-1)) / 2
norm_lpips = 0.08   # 已在[0,1]
norm_psnr = 0.77    # sqrt((32-10)/(40-10))

quality_reward = 0.35 × 0.96 + 0.50 × (1-0.08) + 0.15 × 0.77
               = 0.336 + 0.460 + 0.116
               = 0.912

# 总奖励
total_reward = format_score + quality_reward
             = 1.0 + 0.912
             = 1.912
```

**结论**: 格式完美 + 质量优秀 = 高奖励

---

### 示例2: 格式错误

**模型输出**:
```xml
<think>OK</think>  <!-- 内容太短 -->
<tool_call>
[{"name": "swinir_jpeg_artifact_removal", "arguments": {}}]
</tool_call>
```

**计算过程**:
```python
# 格式分数 (严格模式)
format_score = -1.0  # think内容 < 10字符

# 图像质量分数
# 工具可能正常执行，假设质量=0.85

# 总奖励
total_reward = -1.0 + 0.85 = -0.15
```

**结论**: 格式错误导致负奖励，即使质量好也会被惩罚

---

### 示例3: 无工具执行 (Clean样本)

**模型输出**:
```xml
<think>
图像质量优秀，无明显退化，无需处理
</think>
<answer>
{"restoration_log": []}
</answer>
```

**计算过程**:
```python
# 格式分数
format_score = 1.0  # 格式正确

# Clean样本特殊处理
# 检测到restoration_log为空 → 正确识别clean
clean_detection_reward = 0.5  # 降低clean奖励（避免过度倾向）

# 总奖励
total_reward = format_score + clean_detection_reward
             = 1.0 + 0.5
             = 1.5
```

**结论**: Clean样本奖励被降低（0.5 vs 1.0），鼓励模型更多使用工具恢复

---

### 示例4: 无参考模式 (训练中)

**模型输出**:
```xml
<think>
检测到模糊和噪声，优先处理模糊
</think>
<tool_call>
[{"name": "restormer_motion_deblurring", "arguments": {}}]
</tool_call>
```

**计算过程**:
```python
# 格式分数
format_score = 1.0  # 完美格式

# 图像质量分数 (无参考模式)
# 假设复原后: NIQE=4.2, BRISQUE=28, CPBD=0.82, CLIP-IQA=0.71, Hyper-IQA=0.68

# 归一化 (反向归一化用于NIQE和BRISQUE)
norm_niqe = 1.0 - (4.2 - 2.0) / (15.0 - 2.0) = 0.831
norm_brisque = 1.0 - (28 - 0) / (100 - 0) = 0.720
norm_cpbd = 0.82
norm_clip_iqa = 0.71
norm_hyper_iqa = 0.68

quality_reward = 0.20 × (0.831 + 0.720 + 0.82 + 0.71 + 0.68)
               = 0.20 × 3.761
               = 0.752

# 应用离散化 (假设discretize_levels=10)
discrete_reward = round(0.752 × 10) / 10 = 0.8

# 总奖励
total_reward = format_score + discrete_reward
             = 1.0 + 0.8
             = 1.8
```

**结论**: 无参考模式可以为所有样本计算奖励，离散化减少噪声

---

## 关键要点总结

### ✅ 格式奖励
1. **严格格式至关重要**: 格式错误直接 -1.0 分
2. **Think块必须有实质内容**: 至少10字符
3. **Tool call和Answer互斥**: 不能同时出现
4. **Clean样本特殊处理**: 必须输出空的restoration_log

### ✅ 图像质量奖励
1. **有参考模式更准确**: LPIPS权重最高 (50%)，最接近人类感知
2. **无参考模式更通用**: 适用于所有样本，训练更稳定
3. **PSNR非线性归一化**: 增强低质量到中等质量的区分度
4. **离散化减少噪声**: 早期训练推荐使用

### ✅ 配置建议
- **训练阶段**: `use_no_reference=True`, `discretize_levels=10` (早期) → `0` (后期)
- **评估阶段**: `use_no_reference=False` (如果有GT)
- **Clean样本**: 奖励降低至0.5，鼓励模型更多使用工具

### ✅ 数据流关键点
- `original_image`: 从数据集获取（GT）
- `image_history[0]`: 退化输入
- `image_history[-1]`: 最终复原结果（用于质量评估）
- 如果 `len(image_history) < 2`: 没有执行工具，返回0分

---

## 代码位置索引

| 功能 | 文件路径 |
|-----|----------|
| 图像质量指标计算 | `verl/utils/reward_score/image_quality_metrics.py` |
| 有参考奖励计算 | `compute_image_restoration_reward()` |
| 无参考奖励计算 | `compute_no_reference_image_restoration_reward()` |
| 格式检查（严格） | `verl/utils/reward_score/image_restoration.py::check_multiturn_format_v2()` |
| 格式检查（渐进） | `check_response_format_v2()` |
| 总奖励计算 | `compute_score_v2()` |
| 配置读取 | `verl/utils/reward_score/__init__.py` (环境变量) |
| 训练脚本 | `examples/agent/IR.sh` |

---

**生成完毕** 🎉

如需更多细节或有疑问，请参考代码或联系维护者。

