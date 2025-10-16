# air_v5_dev_v2 最终更新总结

**分支**: air_v5_dev_v2  
**日期**: 2025-10-13  
**基于**: air_v5_dev

---

## 🎯 本次更新内容

### 核心改动：支持单轮对话的退化类型提取

**问题背景**：
- 你的模型现在是单轮对话（`max_turns=1`）
- 新的输出格式在 `tool_call` 中包含 `degradation` 字段
- 需要从 `tool_call` 而不是 `<answer>` 提取退化类型

**解决方案**：
- ✅ 所有退化类型提取优先从 `tool_call.degradation` 获取
- ✅ 退化类型奖励计算优先从 `tool_call` 提取
- ✅ 避免依赖 `<answer>` 块

---

## 📝 修改的文件（3个核心文件）

### 1. verl/utils/degradation_accuracy_utils.py

**函数**: `extract_predicted_degradation_types_from_conversation()`

**改动**:
```python
# 优先使用 degradation 字段（新格式）
if 'degradation' in tool_dict:
    deg_type = tool_dict['degradation']  # 直接提取
    predicted_types.append(deg_type)
else:
    # 兼容旧格式：通过工具名称映射
    tool_name = tool_dict.get('name', '')
    deg_type = tool_to_degradation.get(tool_name)
    if deg_type:
        predicted_types.append(deg_type)
```

**影响**:
- val-acc/* 准确率统计
- train/val_conversation_details 表格
- val_errors/wrong_predictions 表格

### 2. verl/utils/tracking_image_utils.py

**函数**: `_log_conversation_table()`

**改动**:
```python
# 使用统一的提取函数
from verl.utils.degradation_accuracy_utils import extract_predicted_degradation_types_from_conversation
predicted_degradation_types = extract_predicted_degradation_types_from_conversation(conv_hist)
```

**影响**:
- train/conversation_details 表格的 Predicted_Degradation_Type 列
- val/conversation_details 表格的 Predicted_Degradation_Type 列

### 3. verl/utils/reward_score/image_restoration.py

**函数**: `compute_score_v2()`

**改动**:
```python
# 优先从 <tool_call> 提取（单轮对话）
predicted_log = []
tool_call_matches = re.finditer(r'<tool_call>\s*(\[.*?\])\s*</tool_call>', solution_str, re.DOTALL)
for tool_call_match in tool_call_matches:
    tools = json.loads(tool_call_match.group(1))
    for tool_dict in tools:
        if 'degradation' in tool_dict:
            deg_type = tool_dict['degradation']
            if deg_type and deg_type not in predicted_log:
                predicted_log.append(deg_type)

# 如果没提取到，兼容从 <answer> 提取
if not predicted_log:
    predicted_log = extract_restoration_log_from_response_v2(solution_str)
```

**影响**:
- 退化类型奖励计算
- reward/degradation_type_score_* 统计

---

## 📊 Wandb 统计指标

### 启用退化类型奖励后（ENABLE_DEGRADATION_TYPE_REWARD=True）

**Charts 指标**:
```
reward/degradation_type_score_mean         平均分
reward/degradation_type_score_max          最高分
reward/degradation_type_score_min          最低分
reward/degradation_type_score_std          标准差
reward/degradation_type_valid_samples      有效样本数
reward/degradation_type_valid_ratio        有效样本比例
```

**准确率指标**（一直存在）:
```
val-acc/overall_accuracy                   总体准确率
val-acc/by_type/noise                      按类型统计
val-acc/by_type/jpeg_compression_artifact  
val-acc/by_level/high                      按等级统计
val-acc/by_level/medium
```

**表格显示**:
```
train/conversation_details                 Predicted_Degradation_Type 列
val/conversation_details                   Predicted_Degradation_Type 列
val_errors/wrong_predictions               Predicted_Types, Missing_Types, Extra_Types 列
```

---

## 🔄 提取优先级

### 路径 1: 奖励计算（compute_score_v2）

```
1. 优先：从所有 <tool_call>.degradation 提取  ← 单轮对话
2. 兼容：从 <answer>.restoration_log 提取    ← 多轮对话
```

### 路径 2: 准确率统计（extract_predicted_degradation_types_from_conversation）

```
1. 优先：<tool_call>.degradation  ← 新格式
2. 兼容：工具名称映射            ← 旧格式
```

---

## ✅ 测试验证

### 单轮对话测试

**输入**:
```xml
<think>JPEG artifacts detected.</think>
<tool_call>
[
    {"name":"fbcnn_jpeg_artifact_removal", "degradation":"jpeg compression artifact", "arguments":{"jpeg":40}}
]
</tool_call>
```

**结果**:
- ✅ 提取: `["jpeg compression artifact"]`
- ✅ 退化类型分数: 1.0（完全匹配）
- ✅ 总分: 1.3（format 0.3 + quality 0.0 + degradation_type 1.0）

### 多退化类型测试

**输入**:
```xml
<tool_call>
[
    {"name":"fbcnn_jpeg_artifact_removal", "degradation":"jpeg compression artifact", "arguments":{"jpeg":40}},
    {"name":"swinir_denoising", "degradation":"noise", "arguments":{"noise_level":15}}
]
</tool_call>
```

**结果**:
- ✅ 提取: `["jpeg compression artifact", "noise"]`
- ✅ 退化类型分数: 1.0（完全匹配）

### 部分匹配测试

**场景**: GT 有 2 个退化，模型只识别 1 个

**结果**:
- ✅ 退化类型分数: 0.5（1/2 部分匹配）

---

## 🎯 使用方式

### 配置启用

在 `IR.sh` 中设置：
```bash
export ENABLE_DEGRADATION_TYPE_REWARD=True   # 启用退化类型奖励
export DEGRADATION_TYPE_REWARD_WEIGHT=1.0    # 权重
```

### 模型输出格式

**必须包含 `degradation` 字段**:
```json
{
    "name": "tool_name",
    "degradation": "degradation_type",  ← 必须有这个字段
    "arguments": {...}
}
```

**示例**:
```json
{"name":"fbcnn_jpeg_artifact_removal", "degradation":"jpeg compression artifact", "arguments":{"jpeg":40}}
{"name":"swinir_denoising", "degradation":"noise", "arguments":{"noise_level":15}}
{"name":"restormer_motion_deblurring", "degradation":"motion blur", "arguments":{}}
```

---

## 📈 预期效果

### 奖励计算

```
total_reward = FORMAT_WEIGHT × format_score
             + QUALITY_WEIGHT × quality_score  
             + DEGRADATION_TYPE_WEIGHT × degradation_type_score

示例（完全匹配）:
  = 0.3 × 1.0 + 0.7 × 0.8 + 1.0 × 1.0
  = 0.3 + 0.56 + 1.0
  = 1.86
```

### Wandb 显示

**Charts**:
- `reward/degradation_type_score_mean`: 显示平均匹配分数
- `val-acc/overall_accuracy`: 显示预测准确率

**Tables**:
- `train/conversation_details`: Predicted_Degradation_Type 列显示模型预测
- `val_errors/wrong_predictions`: 显示漏检和误检的类型

---

## ⚠️ 重要说明

### 必须在 tool_call 中包含 degradation 字段

❌ **不支持**（没有 degradation 字段）:
```json
{"name":"fbcnn_jpeg_artifact_removal", "arguments":{"jpeg":40}}
```
→ 退化类型奖励 = 0（无法提取）

✅ **支持**（有 degradation 字段）:
```json
{"name":"fbcnn_jpeg_artifact_removal", "degradation":"jpeg compression artifact", "arguments":{"jpeg":40}}
```
→ 可以正确计算退化类型奖励

### System Prompt 建议

在 system prompt 中明确说明格式：
```
When calling tools, you MUST include the "degradation" field:

<tool_call>
[
    {
        "name": "tool_name",
        "degradation": "degradation_type",  ← Required
        "arguments": {...}
    }
]
</tool_call>
```

---

## 🔍 技术细节

### 提取流程（compute_score_v2）

```python
# Step 1: 从 tool_call 提取（优先）
for tool_call in all_tool_calls:
    for tool in tools:
        if 'degradation' in tool:
            predicted_log.append(tool['degradation'])

# Step 2: 如果没提取到，从 answer 提取（兼容）
if not predicted_log:
    predicted_log = extract_restoration_log_from_response_v2(solution_str)

# Step 3: 与 GT 比对
degradation_type_score = check_degradation_type_match_v2(predicted_log, gt_types)
```

### 匹配逻辑

**集合匹配**（顺序无关）:
```python
predicted_set = set(predicted_log)
gt_set = set(gt_types)

if predicted_set == gt_set:
    score = 1.0  # 完全匹配
elif len(predicted_set) > 0:
    score = len(predicted_set) / len(gt_set)  # 部分匹配
else:
    score = 0.0  # 无匹配
```

---

## 📚 相关文档

- `AIR_V5_DEV_CHANGELOG.md` - 完整分支改动日志
- `CHANGES_SUMMARY.md` - 改动摘要
- `VALIDATION_ERROR_LOGGING.md` - 错误样本上传功能
- `GPU_ACCELERATION_SUMMARY.md` - GPU 加速优化

---

## ✅ 总结

### 更新的功能

1. ✅ 退化类型奖励计算：优先从 `tool_call` 提取
2. ✅ 准确率统计：从 `tool_call.degradation` 提取
3. ✅ Wandb 表格：从 `tool_call.degradation` 提取
4. ✅ 单轮对话友好：不依赖 `<answer>` 块

### 向后兼容

- ✅ 仍支持从 `restoration_log` 提取（多轮对话）
- ✅ 仍支持工具名称映射（无 degradation 字段时）
- ✅ 自动适配新旧格式

### 使用建议

1. **新模型训练**: 在 system prompt 中要求包含 `degradation` 字段
2. **启用奖励**: 设置 `ENABLE_DEGRADATION_TYPE_REWARD=True`
3. **监控效果**: 查看 wandb 的 `reward/degradation_type_score_mean`

---

**修改文件**:
- verl/utils/degradation_accuracy_utils.py
- verl/utils/tracking_image_utils.py  
- verl/utils/reward_score/image_restoration.py

**测试状态**: ✅ 全部通过

