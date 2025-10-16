# 格式奖励检查总结

## 📋 当前配置

### 环境变量配置（IR.sh）

```bash
# 第53-54行
export FORMAT_REWARD_WEIGHT=0.3             # 格式奖励权重（默认0.3）
export QUALITY_REWARD_WEIGHT=0.7            # 图像质量奖励权重（默认0.7）
export ENABLE_DEGRADATION_TYPE_REWARD=False # 是否启用退化类型奖励（默认False）
export DEGRADATION_TYPE_REWARD_WEIGHT=1.0   # 退化类型奖励权重（默认1.0）
```

### 奖励权重

| 奖励类型 | 权重 | 说明 |
|---------|------|------|
| **格式奖励** | 0.3 | 检查输出格式是否符合要求 |
| **图像质量奖励** | 0.7 | 评估图像修复质量 |
| **退化类型奖励** | 关闭 (0.0) | 检查预测的退化类型是否正确（当前未启用） |

## 🎯 格式奖励机制

### 使用的格式检查函数

**文件**: `verl/utils/reward_score/image_restoration.py`

**函数**: `check_multiturn_format_v2()` （第51-194行）

### 格式要求（严格模式）

所有以下要求**必须全部满足**，否则奖励为 -1.0：

#### 1. **Think块要求**
- ✅ 每轮必须有 `<think>` 块
- ✅ Think内容长度 ≥ 10个字符
- ❌ 缺少think块或内容太短 → 格式违规

#### 2. **Tool_call和Answer互斥**
- ✅ 每轮可以有 `<tool_call>` **或** `<answer>`
- ✅ 可以只有 `<think>`（思考但不执行）
- ❌ 同时有tool_call和answer → 格式违规

#### 3. **JSON格式正确**
- ✅ Tool_call必须是有效JSON数组
- ✅ Answer必须是有效JSON对象
- ❌ JSON解析失败 → 格式违规

#### 4. **工具名称合法**
- ✅ Tool名称必须在允许列表中
- ❌ 使用未允许的工具 → 格式违规

#### 5. **Answer格式正确**
- ✅ Answer必须包含 `restoration_log` 字段
- ✅ `restoration_log` 必须是列表
- ✅ Answer **只能有** `restoration_log` 这一个字段
- ❌ 缺少字段或有额外字段 → 格式违规

### 允许的工具列表

```python
allowed_tools = {
    # Dehazing（去雾）
    "dehazeformer_dehaze",
    
    # Deblurring（去模糊）
    "drbnet_defocus_deblurring",        # 散焦去模糊
    "xrestormer_motion_deblurring",     # 运动去模糊
    "mprnet_motion_deblurring",         # 运动去模糊
    "restormer_motion_deblurring",      # 运动去模糊
    "restormer_defocus_deblurring",     # 散焦去模糊
    
    # Deraining（去雨）
    "mprnet_deraining",
    "restormer_deraining",
    "xrestormer_deraining",
    
    # JPEG artifact removal（JPEG伪影去除）
    "swinir_jpeg_artifact_removal",
    "fbcnn_jpeg_artifact_removal",
    
    # Quality assessment（质量评估）
    "fbcnn_blind_quality_assessment",
    
    # Super resolution（超分辨率）
    "swinir_super_resolution",
    
    # Denoising（去噪）
    "swinir_denoising",
    "mprnet_denoising",
    
    # Basic adjustments（基础调整）
    "histogram_equalization",           # 直方图均衡化
    "gamma_correction",                 # Gamma校正
    "constant_shift",                   # 常量偏移
    
    # Visual toolboxes（视觉工具箱）
    "visual_toolbox",
    "visual_toolbox_v2",
    "visual_toolbox_v3",
    "visual_toolbox_v4",
    "visual_toolbox_v5",
    
    # Image processing（图像处理）
    "crop_image",                       # 裁剪图像
}
```

## 💯 格式分数计算

### 二值奖励

```python
format_score = check_multiturn_format_v2(response_str, is_clean_sample)

# 返回值：
#   1.0  → 所有格式要求都满足 ✅
#  -1.0  → 任何一项格式违规 ❌
```

### 总奖励计算

**文件**: `verl/utils/reward_score/image_restoration.py` 第1393-1429行

```python
# 权重
format_weight = 0.3    # FORMAT_REWARD_WEIGHT
quality_weight = 0.7   # QUALITY_REWARD_WEIGHT

# 基础奖励计算
if format_score == -1.0:
    # 格式违规：只计算格式惩罚，不给图像质量奖励
    total_score = format_weight * format_score
    # = 0.3 × (-1.0) = -0.3
else:
    # 格式正确：格式奖励 + 图像质量奖励
    total_score = format_weight * format_score + quality_weight * quality_score
    # = 0.3 × 1.0 + 0.7 × quality_score
    # = 0.3 + 0.7 × quality_score

# 退化类型奖励（可选，当前关闭）
if ENABLE_DEGRADATION_TYPE_REWARD and format_score > 0:
    total_score += DEGRADATION_TYPE_REWARD_WEIGHT * degradation_type_score
```

## 📊 奖励范围

### 可能的总奖励值

| 情况 | 格式分数 | 质量分数 | 总奖励计算 | 总奖励范围 |
|------|---------|---------|-----------|-----------|
| **格式违规** | -1.0 | 0.0~1.0 | `0.3 × (-1.0)` | **-0.3** |
| **格式正确，质量差** | 1.0 | 0.0 | `0.3 × 1.0 + 0.7 × 0.0` | **0.3** |
| **格式正确，质量中等** | 1.0 | 0.5 | `0.3 × 1.0 + 0.7 × 0.5` | **0.65** |
| **格式正确，质量优秀** | 1.0 | 1.0 | `0.3 × 1.0 + 0.7 × 1.0` | **1.0** |

### 关键观察

1. **格式违规是致命的**
   - 无论图像质量多好，格式违规都会得到负奖励（-0.3）
   - 这鼓励模型首先学会正确的输出格式

2. **格式正确是基础**
   - 格式正确可以获得0.3的基础分
   - 再根据图像质量获得0~0.7的额外分

3. **图像质量是主要优化目标**
   - 权重0.7远大于格式权重0.3
   - 但必须在格式正确的前提下

## 🔍 格式检查示例

### ✅ 正确格式示例1（使用工具）

```xml
<think>图像存在明显的运动模糊，需要使用运动去模糊工具进行处理</think>
<tool_call>[{"name": "restormer_motion_deblurring", "arguments": {}}]</tool_call>
```

**检查结果**:
- ✅ 有think块，内容≥10字符
- ✅ 有tool_call，没有answer
- ✅ JSON格式正确
- ✅ 工具名在允许列表中
- **格式分数**: 1.0

### ✅ 正确格式示例2（Clean图像）

```xml
<think>经过分析，图像质量良好，没有明显的退化问题，无需修复</think>
<answer>{"restoration_log": []}</answer>
```

**检查结果**:
- ✅ 有think块，内容≥10字符
- ✅ 有answer，没有tool_call
- ✅ JSON格式正确
- ✅ Answer只有restoration_log字段
- **格式分数**: 1.0

### ✅ 正确格式示例3（多轮对话）

```xml
<think>图像存在噪声，先使用去噪工具</think>
<tool_call>[{"name": "swinir_denoising", "arguments": {}}]</tool_call>

<think>去噪后观察到有运动模糊，继续使用去模糊工具</think>
<tool_call>[{"name": "restormer_motion_deblurring", "arguments": {}}]</tool_call>

<think>处理完成，记录修复过程</think>
<answer>{"restoration_log": ["noise", "motion blur"]}</answer>
```

**检查结果**:
- ✅ 每轮都有think块
- ✅ 没有tool_call和answer同时出现
- ✅ 所有JSON格式正确
- ✅ 所有工具名合法
- ✅ Answer格式正确
- **格式分数**: 1.0

### ❌ 错误格式示例1（同时有tool_call和answer）

```xml
<think>图像有模糊</think>
<tool_call>[{"name": "restormer_motion_deblurring", "arguments": {}}]</tool_call>
<answer>{"restoration_log": ["motion blur"]}</answer>
```

**检查结果**:
- ❌ 同一轮同时有tool_call和answer
- **格式分数**: -1.0
- **总奖励**: -0.3

### ❌ 错误格式示例2（Think内容太短）

```xml
<think>ok</think>
<tool_call>[{"name": "swinir_denoising", "arguments": {}}]</tool_call>
```

**检查结果**:
- ❌ Think内容只有2个字符（<10）
- **格式分数**: -1.0
- **总奖励**: -0.3

### ❌ 错误格式示例3（使用未允许的工具）

```xml
<think>图像需要增强对比度</think>
<tool_call>[{"name": "contrast_enhancement", "arguments": {}}]</tool_call>
```

**检查结果**:
- ❌ 工具"contrast_enhancement"不在允许列表中
- **格式分数**: -1.0
- **总奖励**: -0.3

### ❌ 错误格式示例4（Answer有额外字段）

```xml
<think>图像已处理完成</think>
<answer>{"restoration_log": ["noise"], "quality": "good"}</answer>
```

**检查结果**:
- ❌ Answer有额外字段"quality"（应该只有restoration_log）
- **格式分数**: -1.0
- **总奖励**: -0.3

## 🛠️ 调试格式奖励

### 查看格式检查日志

训练时会输出详细的格式检查信息：

```bash
# 运行训练
bash examples/agent/IR.sh 2>&1 | tee logs/format_check.log

# 查看格式检查日志
grep "STRICT FORMAT" logs/format_check.log
```

### 格式违规日志示例

```
[STRICT FORMAT] 第1轮缺少think块
[STRICT FORMAT] 第2轮think内容太短 (< 10字符)
[STRICT FORMAT] 第1轮同时包含tool_call和answer
[STRICT FORMAT] 第1轮tool_call JSON解析失败
[STRICT FORMAT] 第1轮使用了未允许的工具: unknown_tool
[STRICT FORMAT] 第1轮answer缺少restoration_log字段
[STRICT FORMAT] 第1轮answer包含额外字段（应该只有restoration_log）
```

### 查看奖励计算日志

```bash
# 查看奖励计算详情
grep "DEBUG image_restoration_v2" logs/format_check.log

# 示例输出：
# [DEBUG image_restoration_v2] format_score=1.000, logic_score=0.000, quality_score=0.856
# [DEBUG image_restoration_v2] weights: format=0.3, quality=0.7, logic=0.0
# [DEBUG image_restoration_v2] base_reward=0.899 (format + quality)
```

## 📈 格式奖励在Wandb中的显示

### 相关指标

| Wandb指标 | 含义 | 取值范围 |
|----------|------|---------|
| `reward/format_score_mean` | 平均格式分数 | -1.0 ~ 1.0 |
| `reward/format_correct_ratio` | 格式正确率 | 0.0 ~ 1.0 |
| `reward/format_violation_ratio` | 格式违规率 | 0.0 ~ 1.0 |
| `critic/score/mean` | 总奖励平均值 | -0.3 ~ 1.0 |
| `critic/score/max` | 最大总奖励 | -0.3 ~ 1.0 |

### 监控建议

#### 训练早期（前100步）
- 🎯 **目标**: `format_correct_ratio` > 0.7
- 📊 **观察**: 格式违规率应该快速下降
- ⚠️ **警告**: 如果format_correct_ratio < 0.5，可能需要调整system prompt

#### 训练中期（100-1000步）
- 🎯 **目标**: `format_correct_ratio` > 0.9
- 📊 **观察**: 总奖励应该稳步上升
- ⚠️ **警告**: 如果format_violation_ratio > 0.1，需要分析违规原因

#### 训练后期（>1000步）
- 🎯 **目标**: `format_correct_ratio` > 0.95
- 📊 **观察**: 重点关注图像质量指标
- ⚠️ **警告**: 如果格式违规率反弹，可能是过拟合或分布变化

## 🔧 调整格式奖励权重

### 何时增加格式权重

**情况**: 格式违规率一直很高（>20%）

```bash
# IR.sh
export FORMAT_REWARD_WEIGHT=0.5  # 从0.3增加到0.5
export QUALITY_REWARD_WEIGHT=0.5  # 相应减少
```

**效果**: 
- ✅ 更强的格式学习信号
- ⚠️ 可能影响图像质量优化速度

### 何时减少格式权重

**情况**: 格式已经很好（>95%），想要更关注质量

```bash
# IR.sh
export FORMAT_REWARD_WEIGHT=0.2  # 从0.3减少到0.2
export QUALITY_REWARD_WEIGHT=0.8  # 相应增加
```

**效果**:
- ✅ 更强的质量优化信号
- ⚠️ 可能导致偶尔的格式违规

### 推荐配置

| 训练阶段 | 格式权重 | 质量权重 | 说明 |
|---------|---------|---------|------|
| **早期** | 0.4 | 0.6 | 优先学习格式 |
| **中期** | 0.3 | 0.7 | 平衡格式和质量（默认）|
| **后期** | 0.2 | 0.8 | 优先优化质量 |

## 📝 当前配置总结

### ✅ 已配置项

1. **格式检查函数**: `check_multiturn_format_v2()` （严格模式）
2. **格式权重**: 0.3
3. **质量权重**: 0.7
4. **退化类型奖励**: 关闭
5. **允许的工具**: 27个（已完整列出）

### 🎯 预期行为

1. **格式违规** → 总奖励 = -0.3（惩罚）
2. **格式正确，未使用工具** → 总奖励 = 0.3（只有格式分）
3. **格式正确，图像质量好** → 总奖励 = 0.3 + 0.7 × quality_score

### 💡 优化建议

1. **监控格式正确率**
   - 目标：训练100步后 > 90%
   - 如果达不到，考虑：
     - 增加格式权重
     - 优化system prompt
     - 检查训练数据质量

2. **分析格式违规原因**
   - 使用 `grep "STRICT FORMAT" logs/*.log` 查看具体违规类型
   - 针对性优化（如：think太短、工具名错误等）

3. **平衡格式和质量**
   - 格式稳定后，可以适当降低格式权重
   - 重点优化图像质量奖励

---

**检查时间**: 2025-10-14  
**配置文件**: `examples/agent/IR.sh`  
**实现文件**: `verl/utils/reward_score/image_restoration.py`

