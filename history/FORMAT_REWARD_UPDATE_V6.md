# 格式奖励更新 - v6版本

## 📋 修改内容

### ✅ 修改的函数

#### 1. `check_multiturn_format_v2()` - 多轮严格格式检查
**位置**: `verl/utils/reward_score/image_restoration.py:51`

**修改前**:
- ❌ 允许只有 `<think>` 块（无action也可以）

**修改后**:
- ✅ **必须有 `<think>` + action 的组合**
- ✅ action = `<tool_call>` 或 `<answer>` (至少一个)
- ✅ 新增检查代码:
```python
# 4. Must have either tool_call or answer (at least one is REQUIRED)
if not tool_call_match and not answer_match:
    print(f' [STRICT FORMAT] 第{i+1}轮既没有tool_call也没有answer（必须至少有一个）')
    return -1.0
```

---

#### 2. `check_response_format_strict_v2()` - 单轮严格格式检查
**位置**: `verl/utils/reward_score/image_restoration.py:200`

**修改前**:
- ❌ 不要求必须有tool_call或answer，只有think也是可以的

**修改后**:
- ✅ **必须有 `<think>` + action 的组合**
- ✅ 新增检查代码:
```python
# 4. Must have either tool_call or answer (at least one is REQUIRED)
if not tool_call_match and not answer_match:
    return 0.0
```

---

#### 3. `check_response_format_v2()` - 渐进式格式检查
**位置**: `verl/utils/reward_score/image_restoration.py:325`

**修改前**:
- ❌ 3. Can have only `<think>` (neither tool_call nor answer)

**修改后**:
- ✅ 2. Must have either `<tool_call>` OR `<answer>` (at least one is REQUIRED)
- ✅ 3. `<tool_call>` and `<answer>` cannot coexist in same response
- ✅ 新增惩罚代码:
```python
# 4. Must have either tool_call or answer (at least one is REQUIRED)
if not tool_call_match and not answer_match:
    format_score -= 0.6  # Major penalty for missing action
    return max(format_score, 0.0)
```

---

## 📊 新的格式要求

### ✅ 合法格式示例

#### 示例1: Think + Tool Call
```xml
<think>
图像存在噪声退化，需要使用去噪工具处理
</think>
<tool_call>
[
    {
        "name": "swinir_denoising",
        "degradation": "noise",
        "arguments": {"noise_level": 15}
    }
]
</tool_call>
```

#### 示例2: Think + Answer
```xml
<think>
图像已完全复原，没有明显的退化
</think>
<answer>
{
    "restoration_log": ["noise", "motion blur"]
}
</answer>
```

---

### ❌ 非法格式示例

#### 错误1: 只有Think，没有Action ❌
```xml
<think>
图像可能有噪声
</think>
<!-- 缺少 tool_call 或 answer -->
```
**结果**: 
- 严格模式: `format_score = -1.0`
- 渐进模式: `format_score -= 0.6`

#### 错误2: Think + Tool Call + Answer 同时存在 ❌
```xml
<think>推理内容</think>
<tool_call>[...]</tool_call>
<answer>{...}</answer>
```
**结果**: `format_score = -1.0` 或 `-0.8`

#### 错误3: 没有Think块 ❌
```xml
<tool_call>[...]</tool_call>
```
**结果**: `format_score = -1.0` 或 `0.0`

---

## 🎯 格式检查流程

### 严格模式 (`check_multiturn_format_v2`)

```python
for each turn:
    ✓ 1. 检查 <think> 块存在且内容 >= 10字符
    ✓ 2. 检查 <tool_call> 和 <answer> 不能同时存在
    ✓ 3. 检查至少有一个 action（tool_call 或 answer）⭐ 新增
    ✓ 4. 验证 tool_call 的 JSON 格式和工具名称
    ✓ 5. 验证 answer 的 JSON 格式和 restoration_log 字段

if all_checks_passed:
    return 1.0  # 完美格式
else:
    return -1.0  # 任何违规
```

### 渐进模式 (`check_response_format_v2`)

```python
format_score = 0.0

# Think块评分
if has_think and len(content) >= 10:
    format_score += 0.3
    if has_quality_keywords:
        format_score += 0.1

# Action检查 ⭐ 新增
if tool_call and answer (同时存在):
    format_score -= 0.8
    return max(format_score, 0.0)

if not tool_call and not answer (都没有):
    format_score -= 0.6  ⭐ 新增惩罚
    return max(format_score, 0.0)

# Tool Call评分
if has_tool_call:
    format_score += 0.2 (存在)
    format_score += 0.1 (有效JSON)
    format_score += 0.1 (工具名称正确)

# Answer评分
if has_answer:
    format_score += 0.2 (存在)
    format_score += 0.1 (有效JSON)
    format_score += 0.1 (有restoration_log)
    format_score += 0.1 (是列表)
    format_score += 0.1 (只有restoration_log字段)

return min(format_score, 1.0)
```

---

## 📈 影响分析

### 对训练的影响

#### 正面影响 ✅
1. **强制执行动作**: 模型必须做出决策（使用工具或给出答案）
2. **避免空响应**: 杜绝只思考不行动的情况
3. **提高决策质量**: 促使模型明确判断图像状态

#### 需要注意 ⚠️
1. **训练早期**: 可能会有更多格式违规（因为要求更严格）
2. **惩罚力度**: 
   - 严格模式: `-1.0` (总分为负)
   - 渐进模式: `-0.6` (仍有机会通过think得分)
3. **建议**: 训练初期使用渐进模式，稳定后切换严格模式

---

## 🔧 配置建议

### 训练早期（前25%）
```python
strict_format = False  # 使用渐进模式
format_reward_weight = 0.2  # 降低格式权重
quality_reward_weight = 0.8  # 提高质量权重
```

### 训练中期（25%-75%）
```python
strict_format = False  # 继续渐进模式
format_reward_weight = 0.3  # 标准权重
quality_reward_weight = 0.7
```

### 训练后期（75%-100%）
```python
strict_format = True   # 切换严格模式
format_reward_weight = 0.3
quality_reward_weight = 0.7
```

---

## 📝 文档更新

### 需要同步更新的文档
- [ ] `FORMAT_REWARD_ANALYSIS.md` - 分析报告
- [x] `FORMAT_REWARD_UPDATE_V6.md` - 本更新文档
- [ ] System Prompt - 告知模型格式要求
- [ ] 训练脚本注释 - 更新格式说明

---

## 🧪 测试用例

### 测试1: 合法格式 - Think + Tool Call
```python
response = """
<think>检测到运动模糊，需要去模糊处理</think>
<tool_call>[{"name": "restormer_motion_deblurring", "arguments": {}}]</tool_call>
"""
# 期望: format_score = 1.0 (严格) 或 ~0.7 (渐进)
```

### 测试2: 合法格式 - Think + Answer
```python
response = """
<think>图像已完全复原，输出结果</think>
<answer>{"restoration_log": ["noise"]}</answer>
"""
# 期望: format_score = 1.0 (严格) 或 ~0.9 (渐进)
```

### 测试3: 非法格式 - 只有Think ❌
```python
response = """
<think>图像可能有问题</think>
"""
# 期望: format_score = -1.0 (严格) 或 <= 0.0 (渐进)
```

### 测试4: 非法格式 - Tool Call + Answer ❌
```python
response = """
<think>处理图像</think>
<tool_call>[...]</tool_call>
<answer>{...}</answer>
"""
# 期望: format_score = -1.0 (严格) 或 <= 0.0 (渐进)
```

---

## ✅ 完成状态

- [x] 修改 `check_multiturn_format_v2()`
- [x] 修改 `check_response_format_strict_v2()`
- [x] 修改 `check_response_format_v2()`
- [x] 更新函数文档字符串
- [x] 生成更新文档
- [ ] 运行测试验证
- [ ] 更新System Prompt

---

**修改时间**: 2025-10-14  
**分支**: `air_v6_degradation_tool_planning`  
**修改人**: AI Assistant  
**审核状态**: 待用户确认

