# WandB表格添加预测退化类型列

## 🎯 功能说明

在WandB的对话详情表格中新增 `Predicted_Degradation_Type` 列，显示模型预测的退化类型（从工具调用中推断）。

---

## 📊 表格列变化

### 修改前（9个基础列）
```
1. Step
2. Sample_ID
3. Trajectory_Image
4. Quality_Score
5. Num_Tools
6. Degradation_Type               # Ground Truth (GT)
7. Tool_Status
8. Failure_Reason
9. User_Input
10-19. Turn1_Think, Turn1_Tools, ...
```

### 修改后（10个基础列）⭐
```
1. Step
2. Sample_ID
3. Trajectory_Image
4. Quality_Score
5. Num_Tools
6. Degradation_Type               # Ground Truth (GT)
7. Predicted_Degradation_Type     # 模型预测 ⭐ 新增
8. Tool_Status
9. Failure_Reason
10. User_Input
11-20. Turn1_Think, Turn1_Tools, ...
```

---

## 🔧 实现逻辑

### 1. 提取工具名称
从 `conversation_history` 中的每个turn提取 `<tool_call>` 内容：

```python
# 示例tool_call
<tool_call>
[
  {"name": "swinir_denoising", "arguments": {"noise_level": 25}},
  {"name": "constant_shift", "arguments": {"shift": 40}}
]
</tool_call>
```

提取出：`["swinir_denoising", "constant_shift"]`

### 2. 映射到退化类型
使用 `tool_to_degradation_mapping.py` 中的映射表：

```python
TOOL_TO_DEGRADATION_TYPE = {
    # 去噪
    "swinir_denoising": "noise",
    "mprnet_denoising": "noise",
    
    # 去模糊
    "restormer_motion_deblurring": "motion blur",
    "xrestormer_motion_deblurring": "motion blur",
    "restormer_defocus_deblurring": "defocus blur",
    "drbnet_defocus_deblurring": "defocus blur",
    
    # 去雨
    "restormer_deraining": "rain",
    "mprnet_deraining": "rain",
    
    # JPEG伪影
    "swinir_jpeg_artifact_removal": "jpeg compression artifact",
    "fbcnn_jpeg_artifact_removal": "jpeg compression artifact",
    
    # 超分辨率
    "swinir_super_resolution": "low resolution",
    
    # 去雾
    "dehazeformer_dehaze": "haze",
    
    # 增亮（3个工具都对应dark）⭐
    "constant_shift": "dark",
    "gamma_correction": "dark",
    "histogram_equalization": "dark",
}
```

### 3. 格式化显示
- **多个退化类型**: 用逗号分隔，如 `"noise, dark"`
- **无工具调用**: 显示 `"none"`
- **去重**: 同一个退化类型只显示一次

---

## 📝 示例

### 示例1: 单一退化类型
**工具调用**:
```json
[{"name": "swinir_denoising", "arguments": {"noise_level": 25}}]
```

**结果**:
- `Degradation_Type`: `"noise"` (GT)
- `Predicted_Degradation_Type`: `"noise"` ✅ 预测正确

---

### 示例2: 多个工具，同一退化类型
**工具调用** (多轮):
```json
Turn 1: [{"name": "constant_shift", "arguments": {"shift": 40}}]
Turn 2: [{"name": "gamma_correction", "arguments": {"gamma": 1.5}}]
```

**结果**:
- `Degradation_Type`: `"dark"` (GT)
- `Predicted_Degradation_Type`: `"dark"` ✅ 去重后只显示一次

---

### 示例3: 多个退化类型（模型识别了多种）
**工具调用**:
```json
Turn 1: [{"name": "swinir_denoising", "arguments": {}}]
Turn 2: [{"name": "histogram_equalization", "arguments": {}}]
```

**结果**:
- `Degradation_Type`: `"noise"` (GT)
- `Predicted_Degradation_Type`: `"noise, dark"` ⚠️ 识别了额外的退化

---

### 示例4: 无工具调用
**工具调用**: 无（直接给answer）

**结果**:
- `Degradation_Type`: `"noise"` (GT)
- `Predicted_Degradation_Type`: `"none"` ❌ 未识别

---

## 🎨 WandB表格显示

### 完整表格示例

| Step | Sample_ID | Quality | Num_Tools | Degradation_Type | Predicted_Degradation_Type | Tool_Status | Failure_Reason |
|------|-----------|---------|-----------|------------------|----------------------------|-------------|----------------|
| 5 | train_step5_idx0 | 0.856 | 2 | noise | **noise** | ✅ Success | - |
| 5 | train_step5_idx1 | 0.723 | 1 | dark | **dark** | ✅ Success | - |
| 5 | train_step5_idx2 | 0.0 | 0 | motion blur | **none** | ❌ No Tool Request | 直接给答案 |
| 10 | train_step10_idx0 | 0.912 | 3 | noise | **noise, dark** | ✅ Success | - |

---

## 💡 使用场景

### 1. 对比GT和预测
快速查看模型是否正确识别了退化类型：
```
Degradation_Type        vs    Predicted_Degradation_Type
"noise"                 vs    "noise"           ✅ 正确
"dark"                  vs    "none"            ❌ 未识别
"motion blur"           vs    "noise, motion blur" ⚠️ 识别了额外类型
```

### 2. 分析识别错误
筛选 `Predicted_Degradation_Type != Degradation_Type` 的样本，查看：
- 为什么模型识别错了？
- 图像是否有歧义？
- 工具选择是否合理？

### 3. 统计识别准确率
导出表格数据，计算：
- 完全匹配率：预测==GT的比例
- 部分匹配率：预测包含GT的比例
- 无识别率：预测=="none"的比例

---

## 🔍 特殊情况处理

### 1. Brightening工具的映射 ⭐
**3个工具都映射到 "dark"**:
- `constant_shift` → `"dark"`
- `gamma_correction` → `"dark"`
- `histogram_equalization` → `"dark"`

**原因**: 这三个都是用于处理暗图的工具

### 2. 通用工具（不映射）
以下工具**不对应具体退化类型**，不会出现在预测中：
- `visual_toolbox` 系列
- `fbcnn_blind_quality_assessment`（只评估不修复）
- `crop_image`

### 3. 未知工具
如果模型调用了映射表中不存在的工具：
- 忽略该工具
- 不影响其他工具的映射

### 4. 多轮调用去重
如果模型在不同turn中多次调用同一退化类型的工具：
```python
Turn 1: swinir_denoising  → "noise"
Turn 2: mprnet_denoising  → "noise"
结果: "noise" (去重)
```

---

## 🧪 测试示例

### 测试1: 标准场景
```python
# 输入
conversation_history = [
    {
        "response": '<tool_call>[{"name": "swinir_denoising"}]</tool_call>'
    }
]

# 输出
predicted_degradation_type = "noise"
```

### 测试2: Brightening工具
```python
# 输入
conversation_history = [
    {
        "response": '<tool_call>[{"name": "constant_shift", "arguments": {"shift": 40}}]</tool_call>'
    },
    {
        "response": '<tool_call>[{"name": "gamma_correction", "arguments": {"gamma": 1.5}}]</tool_call>'
    }
]

# 输出
predicted_degradation_type = "dark"  # 去重，只显示一次
```

### 测试3: 多种退化
```python
# 输入
conversation_history = [
    {
        "response": '<tool_call>[{"name": "swinir_denoising"}]</tool_call>'
    },
    {
        "response": '<tool_call>[{"name": "restormer_deraining"}]</tool_call>'
    }
]

# 输出
predicted_degradation_type = "noise, rain"
```

### 测试4: 无工具
```python
# 输入
conversation_history = [
    {
        "response": '<answer>{"restoration_log": []}</answer>'
    }
]

# 输出
predicted_degradation_type = "none"
```

---

## 📂 修改的文件

### `verl/utils/tracking_image_utils.py`

**1. 修改列定义** (第823-828行)
```python
columns = ["Step", "Sample_ID", "Trajectory_Image", "Quality_Score", "Num_Tools", 
           "Degradation_Type", "Predicted_Degradation_Type", ...]  # 新增列
```

**2. 添加提取逻辑** (第866-918行)
```python
# 提取预测的退化类型（从conversation_history中的tool_call）
predicted_degradation_types = []
for turn in conv_hist:
    # 提取tool_call
    # 映射工具名到退化类型
    # 去重
predicted_degradation_type_str = ", ".join(predicted_degradation_types) or "none"
```

**3. 添加到行数据** (第1048-1049行)
```python
row = [step, f"{mode}_step{step}_idx{idx}", ..., 
       degradation_type, predicted_degradation_type_str, ...]  # 新增
```

---

## 🎯 关键要点

1. ✅ **GT vs 预测**: 两列并排显示，方便对比
2. ✅ **去重**: 同一退化类型只显示一次
3. ✅ **Brightening统一**: 3个工具都映射到"dark"
4. ✅ **容错处理**: JSON解析失败不影响其他数据
5. ✅ **无工具情况**: 显示"none"而不是空字符串
6. ✅ **多退化支持**: 用逗号分隔多个类型

---

## 📊 数据分析建议

### 在WandB中筛选
1. **完全匹配**: `Degradation_Type == Predicted_Degradation_Type`
2. **部分匹配**: `Predicted_Degradation_Type` 包含 `Degradation_Type`
3. **识别错误**: 两列不匹配
4. **未识别**: `Predicted_Degradation_Type == "none"`

### 导出分析
导出表格到CSV，使用pandas分析：
```python
import pandas as pd

df = pd.read_csv("wandb_table.csv")

# 完全匹配率
exact_match = (df['Degradation_Type'] == df['Predicted_Degradation_Type']).mean()
print(f"完全匹配率: {exact_match:.2%}")

# 未识别率
no_prediction = (df['Predicted_Degradation_Type'] == 'none').mean()
print(f"未识别率: {no_prediction:.2%}")

# 按退化类型分组统计
by_degradation = df.groupby('Degradation_Type').apply(
    lambda x: (x['Degradation_Type'] == x['Predicted_Degradation_Type']).mean()
)
print("各退化类型识别准确率:")
print(by_degradation)
```

---

**功能完成日期**: 2025-10-12  
**状态**: ✅ 已实现并测试

