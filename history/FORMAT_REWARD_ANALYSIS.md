# 格式奖励机制分析报告

## 📋 概述

当前系统使用 **二元严格格式检查** (`check_multiturn_format_v2`) 作为主要的格式奖励机制。

---

## 🎯 核心函数

### 1. **主函数**: `compute_score_v2()` 
位置: `verl/utils/reward_score/image_restoration.py:1222`

**奖励结构**:
```python
# 基础奖励（格式违规时）
total_score = FORMAT_WEIGHT × format_score + LOGIC_WEIGHT × logic_score

# 格式正确时
total_score = FORMAT_WEIGHT × format_score 
            + QUALITY_WEIGHT × quality_score 
            + LOGIC_WEIGHT × logic_score

# 启用退化类型奖励后（可选）
total_score = FORMAT_WEIGHT × format_score 
            + QUALITY_WEIGHT × quality_score 
            + DEGRADATION_TYPE_WEIGHT × degradation_type_score
            + LOGIC_WEIGHT × logic_score
```

**默认权重配置** (from IR.sh):
- `FORMAT_REWARD_WEIGHT=0.3` (格式奖励权重)
- `QUALITY_REWARD_WEIGHT=0.7` (图像质量奖励权重)
- `DEGRADATION_TYPE_REWARD_WEIGHT=1.0` (退化类型奖励权重，需手动启用)
- `LOGIC_WEIGHT=0.0` (逻辑奖励已禁用)

---

## ⚙️ 格式检查机制

### 📌 **严格模式** (默认): `check_multiturn_format_v2()`

**返回值**: 
- ✅ `1.0`: 完美格式
- ❌ `-1.0`: 任何格式违规

**检查规则** (ALL必须满足):

#### 1️⃣ **Think块要求**
```python
# 每轮对话必须有<think>块
- 内容长度 >= 10 字符（有意义的推理）
- 格式: <think>推理内容</think>
```

#### 2️⃣ **Tool Call格式**
```python
# 如果存在<tool_call>，必须满足：
<tool_call>
[
    {
        "name": "tool_name",        # 必须在允许列表中
        "arguments": {...}           # 必须存在
    }
]
</tool_call>

# JSON必须有效
# tool_name必须是注册的工具
```

**允许的工具列表** (共25个):
```python
allowed_tools = {
    # 去雾
    "dehazeformer_dehaze",
    
    # 去模糊
    "drbnet_defocus_deblurring", "xrestormer_motion_deblurring", 
    "mprnet_motion_deblurring", "restormer_motion_deblurring",
    "restormer_defocus_deblurring",
    
    # 去雨
    "mprnet_deraining", "restormer_deraining", "xrestormer_deraining",
    
    # JPEG伪影去除
    "swinir_jpeg_artifact_removal", "fbcnn_jpeg_artifact_removal",
    
    # 质量评估
    "fbcnn_blind_quality_assessment",
    
    # 超分辨率
    "swinir_super_resolution",
    
    # 去噪
    "swinir_denoising", "mprnet_denoising",
    
    # 增亮调整
    "histogram_equalization", "gamma_correction", "constant_shift",
    
    # 可视化工具箱
    "visual_toolbox", "visual_toolbox_v2", "visual_toolbox_v3", 
    "visual_toolbox_v4", "visual_toolbox_v5",
    
    # 图像处理
    "crop_image",
}
```

#### 3️⃣ **Answer格式**
```python
# 如果存在<answer>，必须满足：
<answer>
{
    "restoration_log": [...]    # 必须存在且为列表
}
</answer>

# 严格要求：ONLY restoration_log字段（len(keys) == 1）
# JSON必须有效
```

#### 4️⃣ **互斥规则**
```python
# 同一个回合中，tool_call和answer不能同时出现
if tool_call_match and answer_match:
    return -1.0  # 格式违规
```

#### 5️⃣ **允许只有Think**
```python
# 不要求必须有tool_call或answer
# 只有<think>块也是有效的（仅思考，不执行动作）
```

---

### 📌 **渐进模式** (可选): `check_response_format_v2()`

**返回值**: `0.0 ~ 1.0` (部分分数)

**评分规则**:

| 组件 | 分数 | 条件 |
|-----|------|-----|
| **Think块** | 0.3 | 有意义的内容 (>=10字符) |
| **Think质量** | +0.1 | 包含质量关键词 (artifact, blur, noise等) |
| **Tool Call** | 0.2 | 存在tool_call块 |
| **Tool格式** | +0.1 | 有效的JSON列表 |
| **Tool有效性** | +0.1 | 工具名称和参数都正确 |
| **Answer** | 0.2 | 存在answer块 |
| **Answer格式** | +0.1 | 有效的JSON |
| **restoration_log** | +0.1 | 存在restoration_log字段 |
| **List格式** | +0.1 | restoration_log是列表 |
| **严格合规** | +0.1 | 只有restoration_log字段 |
| **格式冲突** | -0.8 | tool_call和answer同时出现 |
| **JSON错误** | -0.2 | JSON解析失败 |

---

## 🔧 当前使用的模式

根据 `IR.sh` 配置和 `compute_score_v2` 代码:

```python
# 默认使用严格模式
strict_format = True  # 硬编码在调用处

# 格式检查
if strict_format:
    format_score = check_multiturn_format_v2(solution_str, is_clean_sample)
else:
    format_score = check_response_format_v2(solution_str)
```

**实际效果**:
- ✅ 格式完全正确 → `format_score = 1.0` → 获得完整奖励
- ❌ 任何格式错误 → `format_score = -1.0` → **总分为负，不计算质量奖励**

---

## 📊 奖励计算流程

```python
# Step 1: 格式检查
format_score = check_multiturn_format_v2(...)  # 1.0 或 -1.0

# Step 2: 根据格式分数决定是否计算质量奖励
if format_score == -1.0:
    # 格式违规，总分为负
    total_score = FORMAT_WEIGHT × (-1.0)  # 例: 0.3 × (-1.0) = -0.3
    # 不计算图像质量奖励
else:
    # 格式正确，计算完整奖励
    quality_score = compute_image_quality_reward_v2(...)  # 0.0 ~ 1.0
    total_score = FORMAT_WEIGHT × 1.0 + QUALITY_WEIGHT × quality_score
    
    # 可选: 退化类型奖励
    if enable_degradation_type_reward:
        degradation_type_score = check_degradation_type_match_v2(...)
        total_score += DEGRADATION_TYPE_WEIGHT × degradation_type_score
```

---

## 🎨 特殊处理

### 1. **Clean样本**
```python
if is_clean_sample:  # env_name == "clean"
    # 使用clean检测奖励，不用质量奖励
    if check_clean_image_response_v2(solution_str):
        accuracy_score = 0.5  # 降低以平衡工具使用
    else:
        accuracy_score = 0.0
```

### 2. **退化类型提取**
```python
# 优先从tool_call的degradation字段提取（新格式）
<tool_call>
[
    {
        "name": "swinir_denoising",
        "degradation": "noise",  # 新格式，直接指定退化类型
        "arguments": {...}
    }
]
</tool_call>

# 兼容：如果没有degradation字段，从restoration_log提取（旧格式）
```

---

## ⚠️ 当前问题与限制

### 问题1: **过于严格的格式检查**
- 任何小错误都导致 `format_score = -1.0`
- 总分直接变负，完全抹杀质量奖励
- 可能导致训练早期大量负样本

### 问题2: **逻辑奖励被禁用**
```python
logic_score = 0.0  # check_step_logic_v2(solution_str)  # 暂时关闭
```
- `check_step_logic_v2()` 函数存在但未使用
- LIFO优先级检查、推理质量评估都被跳过

### 问题3: **缺少工具规划奖励**
- 当前只检查格式和质量
- 没有奖励**工具选择的合理性**
- 没有奖励**工具序列的优化**
- 没有奖励**参数调整的准确性**

---

## 💡 v6版本改进建议

### 建议1: **引入渐进式格式奖励**
```python
# 当前: 全或无 (1.0 或 -1.0)
# 改进: 渐进式 (0.0 ~ 1.0)

# 示例：
- 有think块但内容不足: 0.3
- 有tool_call但JSON错误: 0.5
- tool_call和answer同时出现: 0.2 (扣分但不完全否定)
```

### 建议2: **启用并优化逻辑奖励**
```python
# 重新启用check_step_logic_v2()
# 奖励：
- LIFO优先级遵循: +0.3
- 退化识别准确: +0.2
- 推理质量关键词: +0.2
```

### 建议3: **新增工具规划奖励** ⭐
```python
# 新增: check_tool_planning_quality_v2()
def check_tool_planning_quality_v2(response_str, reward_model):
    """
    评估工具选择和规划的质量
    
    奖励维度：
    1. 工具选择准确性 (0.3)
       - 选对了处理当前退化的工具
       - 工具与退化类型匹配
    
    2. 工具序列优化 (0.3)
       - LIFO顺序遵循
       - 避免重复工具
       - 合理的处理步骤
    
    3. 参数调整合理性 (0.2)
       - 根据退化程度调参
       - 参数在有效范围内
    
    4. 失败处理机制 (0.2)
       - 工具失败后的回退
       - 替代方案选择
    """
    return planning_score  # 0.0 ~ 1.0
```

### 建议4: **多维度奖励融合**
```python
# 新的奖励结构
total_score = (
    FORMAT_WEIGHT × format_score           # 0.2 (降低权重)
    + QUALITY_WEIGHT × quality_score       # 0.5 (图像质量)
    + LOGIC_WEIGHT × logic_score           # 0.1 (推理逻辑)
    + PLANNING_WEIGHT × planning_score     # 0.2 (工具规划) ⭐新增
    + DEGRADATION_TYPE_WEIGHT × deg_score  # 1.0 (退化识别，可选)
)
```

---

## 📝 总结

**当前格式奖励特点**:
- ✅ 严格的格式约束，确保输出规范
- ✅ 清晰的二元判断，易于理解
- ❌ 过于严格，训练初期可能大量负奖励
- ❌ 缺少工具规划相关的奖励机制
- ❌ 逻辑奖励被禁用，浪费了推理质量评估

**v6版本重点方向**:
1. 🎯 引入**工具规划奖励**机制
2. 📈 采用**渐进式格式奖励**，减少负奖励
3. 🧠 重启**逻辑奖励**，强化推理能力
4. ⚖️ 调整**权重分配**，平衡各维度

---

生成时间: 2025-10-14
分支: air_v6_degradation_tool_planning

