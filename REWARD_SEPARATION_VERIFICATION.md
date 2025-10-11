# 奖励分离验证报告

## ✅ 验证结论

**图像质量奖励和退化类型奖励完全独立，没有混淆！**

---

## 📐 三个独立的奖励组件

### 组件1: 格式奖励 (Format Reward)
```python
功能: 检查输出格式
计算: check_multiturn_format_v2() 或 check_response_format_v2()
输入: solution_str (模型输出文本)
输出: format_score (1.0 或 -1.0)
字段: result_dict['format_score']
WandB: reward/format_score_mean
```

### 组件2: 图像质量奖励 (Quality Reward) ⭐
```python
功能: 评估复原后的图像质量
计算: compute_image_quality_reward_v2()
输入: 
  - extra_info['image_history'] (图像历史)
  - extra_info['original_image'] (GT，有参考模式需要)
方法:
  - 有参考: SSIM + LPIPS + PSNR
  - 无参考: NIQE + BRISQUE + CPBD + CLIP-IQA + Hyper-IQA
输出: quality_score (0.0 ~ 1.0)
字段: result_dict['quality_score']
WandB: reward/quality_score_mean
```

### 组件3: 退化类型奖励 (Degradation Type Reward) ⭐
```python
功能: 评估退化类型识别准确性（不考虑顺序）
计算: check_degradation_type_match_v2()
输入:
  - predicted_log (从<answer>的restoration_log提取)
  - reward_model_order (从ground_truth提取)
方法:
  - 提取restoration_log列表
  - 转换为集合
  - 集合匹配（无序）
输出: degradation_type_score (0.0 ~ 1.0)
字段: result_dict['degradation_type_score']
WandB: reward/degradation_type_score_mean
```

---

## 🔍 代码流程验证

### compute_score_v2() 完整流程

```python
def compute_score_v2(...):
    # ========== 步骤1: 解析Ground Truth ==========
    reward_model = ground_truth.get('reward_model', [])
    env_name = ground_truth.get('env_name', '')
    degradation_addition_order = parse_reward_model_to_degradations_v2(reward_model)
    predicted_log = extract_restoration_log_from_response_v2(solution_str)
    
    # ========== 步骤2: 计算格式分数 ==========
    format_score = check_multiturn_format_v2(solution_str)
    # → format_score = 1.0 或 -1.0
    
    # ========== 步骤3: 计算图像质量分数 ⭐ ==========
    if accuracy_mode == "image_quality":
        # 调用图像质量计算函数
        quality_result = compute_image_quality_reward_v2(
            solution_str, 
            extra_info,  # 包含image_history
            discretize_levels=discretize_levels,
            use_no_reference=use_no_reference
        )
        accuracy_score = quality_result["image_quality_reward"]
        # → accuracy_score = 0.85 (来自图像质量指标)
    
    # 重命名为quality_score（语义更清晰）
    quality_score = accuracy_score
    # → quality_score = 0.85
    
    # ========== 步骤4: 计算基础奖励（格式+质量）==========
    if format_score == -1.0:
        total_score = format_weight * format_score
    else:
        total_score = format_weight * format_score + quality_weight * quality_score
    # → total_score = 0.3 × 1.0 + 0.7 × 0.85 = 0.895
    
    # ========== 步骤5: 计算退化类型奖励（独立！）⭐ ==========
    degradation_type_score = 0.0
    if enable_degradation_type_reward and not is_clean_sample:
        # 调用退化类型匹配函数（完全独立的计算）
        degradation_type_score = check_degradation_type_match_v2(
            predicted_log,           # 从restoration_log提取
            degradation_addition_order
        )
        # → degradation_type_score = 1.0 (来自集合匹配)
        
        if format_score > 0:
            total_score += degradation_type_reward_weight * degradation_type_score
            # → total_score = 0.895 + 1.0 × 1.0 = 1.895
    
    # ========== 步骤6: 返回结果字典 ==========
    result_dict = {
        "score": total_score,                        # 1.895 (总分)
        "quality_score": quality_score,              # 0.85 (图像质量) ⭐
        "degradation_type_score": degradation_type_score,  # 1.0 (退化类型) ⭐
        "format_score": format_score,                # 1.0 (格式)
    }
    
    return result_dict
```

---

## 🎯 关键区分点

### 图像质量 vs 退化类型

| 维度 | 图像质量奖励 | 退化类型奖励 |
|-----|-------------|-------------|
| **检查对象** | 图像像素 | 文本标签 |
| **输入数据** | `image_history`（图像） | `restoration_log`（文本列表） |
| **计算函数** | `compute_image_quality_reward_v2()` | `check_degradation_type_match_v2()` |
| **计算方法** | 图像指标（SSIM/LPIPS等） | 集合匹配 |
| **代码行数** | 677-924行 | 1080-1147行 |
| **返回字段** | `quality_score` | `degradation_type_score` |
| **WandB指标** | `reward/quality_score_*` | `reward/degradation_type_score_*` |
| **作用** | 主要准确性奖励 | 可选额外奖励 |
| **默认启用** | ✅ 是 | ❌ 否 |

---

## 🔍 可能混淆的地方检查

### 混淆点1: accuracy_mode 参数名 ✅

**代码**:
```python
if accuracy_mode == "image_quality":
    quality_result = compute_image_quality_reward_v2(...)
```

**说明**:
- `accuracy_mode` 是选择"准确性评估方式"的参数
- `"image_quality"` 模式表示用图像质量来评估准确性
- 这里没有混淆，质量就是准确性的一种评估方式

---

### 混淆点2: accuracy_score 临时变量名 ✅

**代码**:
```python
accuracy_score = quality_result["image_quality_reward"]  # Line 1298
quality_score = accuracy_score  # Line 1344
```

**说明**:
- `accuracy_score` 是临时变量名（历史遗留）
- Line 1344 明确重命名为 `quality_score`
- 返回字典用的是 `quality_score` 字段
- 没有混淆，只是命名过渡

---

### 混淆点3: degradation_order_score vs degradation_type_score ✅

**两个不同的概念**:

**degradation_order_score** (退化顺序):
```python
# 当 accuracy_mode = "partial_credit" 时
accuracy_score = check_restoration_order_with_partial_credit_v2(...)
# → 检查LIFO顺序，顺序错误不给分
```

**degradation_type_score** (退化类型):
```python
# 独立计算，可选
degradation_type_score = check_degradation_type_match_v2(...)
# → 检查集合匹配，不考虑顺序
```

**返回字典**:
```python
result_dict = {
    "degradation_order_score": quality_score,  # 兼容字段，实际是quality_score
    "degradation_type_score": degradation_type_score,  # 真正的退化类型分数
}
```

**说明**: 这两个字段不同！
- `degradation_order_score`: 旧字段，实际保存的是 `quality_score`
- `degradation_type_score`: 新字段，保存的是真正的退化类型分数

---

## 📊 完整示例验证

### 场景：所有奖励都启用

**配置**:
```bash
IMAGE_QUALITY_USE_NO_REFERENCE=True
QUALITY_REWARD_WEIGHT=0.7
ENABLE_DEGRADATION_TYPE_REWARD=True
DEGRADATION_TYPE_REWARD_WEIGHT=1.0
```

**输入**:
```python
# Ground truth
expected_degradations = ["blur", "noise", "jpeg_artifact"]

# 模型输出
solution_str = """
<think>检测到模糊、噪声和JPEG伪影</think>
<answer>
{"restoration_log": ["noise", "blur", "jpeg_artifact"]}
</answer>
"""

# 图像数据
extra_info = {
    "image_history": [退化图, 复原图],  # 长度=2，有处理
    "original_image": GT图像
}
```

**计算过程**:

```python
# 1. 格式检查
format_score = check_multiturn_format_v2(solution_str)
# → format_score = 1.0 ✅ (格式完美)

# 2. 图像质量计算（独立）⭐
quality_result = compute_image_quality_reward_v2(
    solution_str,
    extra_info,  # 使用image_history计算质量
    use_no_reference=True
)
# → 内部计算：
#   - 提取 image_history[-1] (复原图)
#   - 计算 NIQE, BRISQUE, CPBD, CLIP-IQA, Hyper-IQA
#   - 综合评分
# → quality_result = {"image_quality_reward": 0.85}

accuracy_score = 0.85
quality_score = 0.85  # 重命名

# 3. 基础奖励
base = 0.3 × 1.0 + 0.7 × 0.85 = 0.895

# 4. 退化类型计算（独立）⭐
predicted_log = extract_restoration_log_from_response_v2(solution_str)
# → predicted_log = ["noise", "blur", "jpeg_artifact"]

degradation_type_score = check_degradation_type_match_v2(
    predicted_log,  # 从restoration_log提取
    expected_degradations
)
# → 内部计算：
#   - 转换为集合: {"noise", "blur", "jpeg_artifact"}
#   - 与期望集合比较
# → degradation_type_score = 1.0 (完全匹配)

# 5. 总分
total = 0.895 + 1.0 × 1.0 = 1.895
```

**返回结果**:
```python
{
    "score": 1.895,                    # 总分
    "format_score": 1.0,               # 格式分数
    "quality_score": 0.85,             # 图像质量分数 ← 从图像计算
    "degradation_type_score": 1.0,     # 退化类型分数 ← 从文本匹配
}
```

**WandB记录**:
```python
# 格式指标
reward/format_score_mean = 1.0

# 图像质量指标 ⭐
reward/quality_score_mean = 0.85
reward/quality_score_max = 0.92
reward/quality_score_min = 0.78
reward/quality_score_std = 0.05

# 退化类型指标 ⭐
reward/degradation_type_score_mean = 1.0
reward/degradation_type_score_max = 1.0
reward/degradation_type_score_min = 0.667
reward/degradation_type_score_std = 0.15

# 总分
critic/rewards/mean = 1.895
```

---

## ⚠️ 容易混淆的概念澄清

### 概念1: 图像质量奖励
- **评估什么**: 复原图像的质量好不好
- **数据来源**: `image_history[-1]`（复原后的图像）
- **计算方法**: SSIM/LPIPS/PSNR 或 NIQE/BRISQUE/CPBD等图像指标
- **字段名**: `quality_score`

### 概念2: 退化类型奖励
- **评估什么**: 是否正确识别了退化类型
- **数据来源**: `restoration_log`（文本列表）
- **计算方法**: 集合匹配（不考虑顺序）
- **字段名**: `degradation_type_score`

### 概念3: 退化顺序奖励（另一个模式）
- **评估什么**: 是否按LIFO顺序处理
- **数据来源**: `restoration_log`（文本列表）
- **计算方法**: 顺序匹配（严格LIFO）
- **使用场景**: 当 `accuracy_mode="partial_credit"` 时
- **字段名**: 也会保存在 `accuracy_score` 中（但这时不是图像质量了）

---

## 🎯 当前默认配置的逻辑

### IR.sh配置
```bash
# 默认使用图像质量模式
accuracy_mode="image_quality"  # 在代码中默认

# 启用退化类型奖励
ENABLE_DEGRADATION_TYPE_REWARD=True
```

### 奖励计算流程

```python
# 1. 格式奖励
format_score = 1.0

# 2. 图像质量奖励（主要准确性评估）
quality_score = compute_image_quality_reward_v2(...)
# → 0.85 (从图像指标计算)

# 3. 基础奖励
base = 0.3 × 1.0 + 0.7 × 0.85 = 0.895

# 4. 退化类型奖励（额外bonus）
degradation_type_score = check_degradation_type_match_v2(...)
# → 1.0 (从文本标签匹配)

# 5. 总分
total = 0.895 + 1.0 × 1.0 = 1.895
```

---

## 📊 数据源对比

### 图像质量奖励的数据源

```python
# 来自 extra_info（运行时动态生成）
extra_info = {
    "image_history": [
        退化图（PIL Image），
        工具1处理后（PIL Image），
        工具2处理后（PIL Image）
    ],
    "original_image": GT图像（PIL Image，来自数据集）
}

# 使用最后一张图
restored_image = image_history[-1]

# 计算图像质量
quality_score = calculate_ssim(restored_image, original_image)
```

### 退化类型奖励的数据源

```python
# 来自 ground_truth（数据集预定义）
ground_truth = {
    "reward_model": [
        {"degradation_type": "blur"},
        {"degradation_type": "noise"},
        {"degradation_type": "jpeg_artifact"}
    ]
}

# 提取期望的退化类型
expected_set = {"blur", "noise", "jpeg_artifact"}

# 来自 solution_str（模型输出）
solution_str = '<answer>{"restoration_log": ["noise", "blur", "jpeg_artifact"]}</answer>'

# 提取预测的退化类型
predicted_set = {"noise", "blur", "jpeg_artifact"}

# 集合匹配
degradation_type_score = 1.0 if predicted_set == expected_set else ...
```

---

## ✅ 验证检查表

- [x] 图像质量奖励计算函数独立 (`compute_image_quality_reward_v2`)
- [x] 退化类型奖励计算函数独立 (`check_degradation_type_match_v2`)
- [x] 数据源完全不同（图像 vs 文本）
- [x] 返回字段名不同（`quality_score` vs `degradation_type_score`）
- [x] WandB指标名不同（`reward/quality_*` vs `reward/degradation_type_*`）
- [x] 计算逻辑完全独立（图像指标 vs 集合匹配）
- [x] 奖励权重独立配置（`QUALITY_REWARD_WEIGHT` vs `DEGRADATION_TYPE_REWARD_WEIGHT`）
- [x] 可以独立开启/关闭（quality总是开启，degradation_type可选）

---

## 📝 代码位置索引

| 组件 | 函数 | 代码行 | 输入 | 输出 |
|-----|------|--------|------|------|
| **格式奖励** | `check_multiturn_format_v2()` | 51-194 | solution_str | format_score |
| **图像质量** | `compute_image_quality_reward_v2()` | 677-924 | image_history | quality_score |
| **退化类型** | `check_degradation_type_match_v2()` | 1080-1147 | restoration_log | degradation_type_score |
| **总奖励** | `compute_score_v2()` | 1191-1417 | 所有 | result_dict |

---

## 🧪 完整测试用例

### 测试：两个奖励独立变化

```python
# 场景1: 质量高，类型识别低
quality_score = 0.95          # 图像质量很好
degradation_type_score = 0.5  # 只识别了一半退化类型

total = 0.3 × 1.0 + 0.7 × 0.95 + 1.0 × 0.5
      = 0.3 + 0.665 + 0.5
      = 1.465

# 场景2: 质量低，类型识别高
quality_score = 0.6           # 图像质量一般
degradation_type_score = 1.0  # 完全识别退化类型

total = 0.3 × 1.0 + 0.7 × 0.6 + 1.0 × 1.0
      = 0.3 + 0.42 + 1.0
      = 1.72

# 场景3: 都很高
quality_score = 0.95
degradation_type_score = 1.0

total = 0.3 × 1.0 + 0.7 × 0.95 + 1.0 × 1.0
      = 1.965

# 场景4: 都很低
quality_score = 0.5
degradation_type_score = 0.3

total = 0.3 × 1.0 + 0.7 × 0.5 + 1.0 × 0.3
      = 0.95
```

**结论**: 两个分数独立变化，互不影响！

---

## 🎨 WandB监控建议

### 创建对比图

**Panel 1: 奖励分解**
```yaml
Title: Reward Components Breakdown
X轴: Step
Y轴:
  - critic/rewards/mean (总分)
  - reward/format_score_mean × 0.3 (格式贡献)
  - reward/quality_score_mean × 0.7 (质量贡献) ⭐
  - reward/degradation_type_score_mean × 1.0 (类型贡献) ⭐
```

**Panel 2: 质量 vs 类型**
```yaml
Title: Quality vs Degradation Type
X轴: Step
Y轴（双Y轴）:
  - reward/quality_score_mean (左Y轴，图像质量) ⭐
  - reward/degradation_type_score_mean (右Y轴，退化类型) ⭐
```

通过这个图可以看到两个奖励的独立趋势。

---

## ✅ 最终验证结论

**图像质量奖励和退化类型奖励完全独立，没有任何混淆！**

### 独立性证明

1. ✅ **计算函数不同**
   - 质量: `compute_image_quality_reward_v2()`（247行代码）
   - 类型: `check_degradation_type_match_v2()`（67行代码）

2. ✅ **数据源不同**
   - 质量: 图像数据（`image_history`）
   - 类型: 文本数据（`restoration_log`）

3. ✅ **计算方法不同**
   - 质量: 图像质量指标（SSIM/LPIPS/PSNR等）
   - 类型: 集合匹配（`set() == set()`）

4. ✅ **返回字段不同**
   - 质量: `result_dict['quality_score']`
   - 类型: `result_dict['degradation_type_score']`

5. ✅ **WandB指标不同**
   - 质量: `reward/quality_score_mean`
   - 类型: `reward/degradation_type_score_mean`

6. ✅ **可以独立变化**
   - 质量高 + 类型低 ✓
   - 质量低 + 类型高 ✓
   - 两者独立波动 ✓

---

**验证完成，结构清晰，没有混淆！** 🎉

