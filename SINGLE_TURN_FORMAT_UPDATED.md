# 单轮格式检查 - 已添加工具数量约束 ✅

## 🎯 更新内容

已为单轮格式检查添加"**工具调用数量>=退化数量**"的约束，以支持一轮预测多个工具的场景。

---

## 📋 完整格式检查规则

### **单轮格式检查 (check_single_turn_format)**

**文件**: `verl/utils/reward_score/image_restoration.py` 第108-208行

#### ✅ **必须满足的条件**

1. **有 `<think>` 块**，且内容 >= 10字符
2. **不能同时有** `<tool_call>` 和 `<answer>`
3. 如果有 `<tool_call>`：
   - JSON格式正确
   - 是非空列表
   - 每个元素有 `name` 和 `arguments` 字段
   - 工具名在 `ALLOWED_TOOLS` 中
4. 如果有 `<answer>`：
   - JSON格式正确
   - 有且仅有 `restoration_log` 字段
   - `restoration_log` 是列表
5. **⭐ 对于非clean样本**：工具调用数量 >= 退化数量

#### 代码实现

```python
def check_single_turn_format(response_str: str, degradation_count: int = 0, is_clean_sample: bool = False) -> float:
    # ... 其他检查 ...
    
    # 统计工具调用数量
    total_tool_call_count = 0
    if tool_call_match:
        tool_calls = json.loads(tool_call_match.group(1))
        for tool_call in tool_calls:
            # 验证每个工具调用
            # ...
            total_tool_call_count += 1
    
    # 检查工具数量是否足够（非clean样本）
    if not is_clean_sample and degradation_count > 0:
        if total_tool_call_count < degradation_count:
            print(f' [SINGLE FORMAT] 工具调用数量不足: {total_tool_call_count} < {degradation_count}')
            return -1.0
    
    return 1.0
```

---

## 📊 使用场景示例

### **场景1: 单退化图像**

**图像信息**：
- 退化类型: `["noise"]`
- 退化数量: 1

**✅ 正确响应**：
```
<think>
图像存在明显的噪声，需要使用去噪工具处理。
</think>
<tool_call>
[{"name": "swinir_denoising", "arguments": {}}]
</tool_call>
```
**结果**: `+1.0` ✅ (1个工具 >= 1个退化)

---

### **场景2: 双退化图像**

**图像信息**：
- 退化类型: `["noise", "blur"]`
- 退化数量: 2

**✅ 正确响应**：
```
<think>
图像同时存在噪声和模糊，需要先去噪再去模糊。
</think>
<tool_call>
[
  {"name": "swinir_denoising", "arguments": {}},
  {"name": "restormer_motion_deblurring", "arguments": {}}
]
</tool_call>
```
**结果**: `+1.0` ✅ (2个工具 >= 2个退化)

---

### **场景3: 三退化图像 - 预测更多工具也可以**

**图像信息**：
- 退化类型: `["noise", "blur", "jpeg"]`
- 退化数量: 3

**✅ 正确响应（预测了4个工具）**：
```
<think>
图像有噪声、模糊和JPEG压缩伪影，我先去噪、再去模糊、然后处理JPEG伪影，最后可能需要超分辨率增强。
</think>
<tool_call>
[
  {"name": "swinir_denoising", "arguments": {}},
  {"name": "restormer_motion_deblurring", "arguments": {}},
  {"name": "fbcnn_jpeg_artifact_removal", "arguments": {}},
  {"name": "swinir_super_resolution", "arguments": {}}
]
</tool_call>
```
**结果**: `+1.0` ✅ (4个工具 >= 3个退化，允许预测更多)

---

### **❌ 场景4: 工具数量不足**

**图像信息**：
- 退化类型: `["noise", "blur"]`
- 退化数量: 2

**❌ 错误响应（只预测1个工具）**：
```
<think>
图像有噪声和模糊，我先去噪声。
</think>
<tool_call>
[{"name": "swinir_denoising", "arguments": {}}]
</tool_call>
```
**结果**: `-1.0` ❌ (1个工具 < 2个退化)

**错误信息**: 
```
[SINGLE FORMAT] 工具调用数量不足: 1 < 2 (需要至少2个工具调用)
```

---

### **✅ 场景5: Clean样本（不受约束）**

**图像信息**：
- 退化类型: `[]` (clean)
- 退化数量: 0
- is_clean_sample: True

**✅ 正确响应（无需工具）**：
```
<think>
图像质量良好，无需任何处理。
</think>
<answer>
{"restoration_log": ["clean"]}
</answer>
```
**结果**: `+1.0` ✅ (clean样本不检查工具数量)

**✅ 也可以只有think**：
```
<think>
图像质量良好，无需任何处理。
</think>
```
**结果**: `+1.0` ✅ (clean样本灵活)

---

## 🔄 与多轮格式的对比

| 检查项 | 单轮格式 | 增强多轮 (v3) |
|--------|---------|--------------|
| **<think>必须** | ✅ | ✅（每轮） |
| **<tool_call>或<answer>二选一必须** | ❌ 都可选 | ✅ |
| **不能同时有两者** | ✅ | ✅ |
| **tool_call数>=退化数** | ✅ **新增** | ✅ |
| **answer必须在最后一轮** | - | ✅ |
| **多轮对话支持** | ❌ 单轮 | ✅ |

---

## 💡 设计思想

### **为什么需要工具数量约束？**

1. **确保充分处理**：有N个退化，至少要调用N个工具
2. **避免遗漏**：防止模型只处理部分退化
3. **支持多步推理**：允许模型预测处理顺序和工具组合
4. **灵活性**：可以预测多于退化数的工具（如额外的增强步骤）

### **为什么Clean样本不受限？**

- Clean样本没有退化，不需要工具处理
- 可以直接返回 `<answer>` 说明是clean
- 也可以只有 `<think>` 进行分析

---

## 📝 实际训练效果

### **好处**

1. **强制完整处理**：模型必须考虑所有退化类型
2. **减少格式错误**：明确的数量要求
3. **提高覆盖率**：不会遗漏退化

### **潜在问题和解决**

**问题1**: 模型可能重复调用同一工具凑数？
- **解决**: 通过图像质量奖励（70%权重）引导，重复调用不会提高质量

**问题2**: 模型可能调用不相关的工具？
- **解决**: 工具名必须在白名单，且图像质量会体现真实效果

**问题3**: 退化数量统计不准确？
- **解决**: 从ground_truth的degradation_addition_order准确获取

---

## 🚀 配置和使用

### **环境变量**

```bash
export USE_SINGLE_TURN_FORMAT=True   # 启用单轮格式
export USE_ENHANCED_FORMAT=False     # 不使用多轮格式
```

### **自动传递退化数量**

在 `compute_score_v2` 中自动处理：

```python
if use_single_turn_format:
    degradation_count = len(degradation_addition_order)  # 自动计算
    format_score = check_single_turn_format(
        solution_str, 
        degradation_count=degradation_count,
        is_clean_sample=is_clean_sample
    )
```

**您不需要手动配置**，系统会自动从ground_truth中提取退化数量！

---

## ✅ 修改的文件

1. ✅ `verl/utils/reward_score/image_restoration.py`
   - 修改 `check_single_turn_format()` 添加 `degradation_count` 参数（第108行）
   - 添加工具数量统计逻辑（第158-177行）
   - 添加工具数量验证逻辑（第200-205行）
   - 修改调用处传递 `degradation_count`（第1500-1506行）

2. ✅ `examples/agent/IRv2.sh`
   - 更新格式检查说明（第88-92行）

---

## 🎯 总结

**单轮格式检查现在的完整逻辑**：

```
对于非clean样本：
1. ✅ 必须有<think>（>=10字符）
2. ✅ 可选<tool_call>或<answer>（不能同时有）
3. ✅ 如果有<tool_call>，数量必须 >= 退化数量  ← 新增
4. ✅ 工具名必须合法，JSON格式正确

对于clean样本：
1. ✅ 必须有<think>（>=10字符）
2. ✅ 可选<tool_call>或<answer>（不能同时有）
3. ⭕ 无工具数量限制（因为不需要处理）
```

**完美适配您的场景**: 一轮预测多个工具来执行！🎉

