# Validation Error Logging - 验证错误样本上传功能

## 📝 功能概述

在验证阶段，自动识别并上传**预测错误的样本**到 wandb 的独立表格中，方便分析模型的错误类型。

## 🎯 新增功能

### 1. **独立的wandb命名空间**
- 使用 `val_errors/` 命名空间
- 不与原有的 `val/` 混淆
- 包含以下指标：
  - `val_errors/wrong_predictions` - 错误样本表格
  - `val_errors/wrong_count` - 错误样本数量
  - `val_errors/total_samples` - 总样本数量
  - `val_errors/error_rate` - 错误率

### 2. **详细的错误分析表格**

表格包含以下列：

| 列名 | 说明 |
|------|------|
| `Step` | 训练步数 |
| `Sample_ID` | 样本标识符 |
| `Original_Image` | 原图（GT，未退化的真实图像） |
| `Degraded_Image` | 退化图（模型输入） |
| `Restored_Image` | 复原图（模型输出） |
| `Ground_Truth_Types` | 真实退化类型 |
| `Ground_Truth_Levels` | 真实退化等级 |
| `Predicted_Types` | 预测的退化类型 |
| `Missing_Types` | 漏检的类型（应该检测但未检测到） |
| `Extra_Types` | 误检的类型（不应检测但检测到了） |
| `Quality_Score` | 图像质量分数 (0-1) |
| `SSIM` | 结构相似性指标 |
| `LPIPS` | 感知损失指标 |
| `PSNR` | 峰值信噪比 |

### 3. **图像分开显示**
- 原图、退化图、复原图分别存储在不同列
- **不拼接**，方便单独查看和对比
- 支持wandb原生的图像查看功能（缩放、下载等）

## 📊 在Wandb中查看

### 1. 查看错误率曲线
- 导航到：`Charts` → `val_errors/error_rate`
- 查看随训练进行，错误率的变化趋势

### 2. 查看错误样本表格
- 导航到：`Tables` → `val_errors/wrong_predictions`
- 表格结构：
  ```
  Step | Sample_ID | Original_Image | Degraded_Image | Restored_Image | GT_Types | Predicted_Types | ...
  -----|-----------|----------------|----------------|----------------|----------|-----------------|-----
   5   | step5_s3  | [Image]        | [Image]        | [Image]        | noise    | blur            | ...
   10  | step10_s7 | [Image]        | [Image]        | [Image]        | rain,blur| rain            | ...
  ```

### 3. 分析错误类型
- **漏检 (Missing_Types)**: 真实存在但模型未检测到的退化
- **误检 (Extra_Types)**: 模型检测到但实际不存在的退化
- 通过筛选表格快速找到特定类型的错误

## 🔧 实现原理

### 判断标准
```python
# 预测正确的条件：预测的退化类型集合 == 真实退化类型集合
predicted_set = set(predicted_types)  # 从tool_call中提取
gt_set = set(gt_types)                # 从reward_model中提取

is_correct = (predicted_set == gt_set)  # 集合匹配，不考虑顺序
```

### 退化类型提取
```python
# 从conversation_history中提取工具调用
# 例如：<tool_call>[{"name": "swinir_denoising", "arguments": {...}}]</tool_call>
# 映射到退化类型：swinir_denoising → "noise"

tool_to_degradation = {
    "swinir_denoising": "noise",
    "restormer_motion_deblurring": "motion blur",
    "swinir_jpeg_artifact_removal": "jpeg compression artifact",
    "dehazeformer_dehaze": "haze",
    # ... 更多映射
}
```

## 📈 使用场景

### 1. 错误模式分析
- 查看哪些退化类型容易被漏检
- 查看哪些退化类型容易被误检
- 分析复杂退化组合的识别难度

### 2. 模型调试
- 比对原图、退化图、复原图
- 查看图像质量指标（SSIM/LPIPS/PSNR）
- 定位模型在哪些样本上效果不佳

### 3. 训练监控
- 观察错误率随训练的变化
- 评估模型是否在过拟合或欠拟合
- 判断是否需要调整训练策略

## 🎨 示例

### 示例1：漏检错误
```
Ground_Truth_Types: noise, blur
Predicted_Types: blur
Missing_Types: noise  ← 漏检了noise
Extra_Types: None
```

### 示例2：误检错误
```
Ground_Truth_Types: rain
Predicted_Types: rain, haze
Missing_Types: None
Extra_Types: haze  ← 误检了haze
```

### 示例3：完全错误
```
Ground_Truth_Types: jpeg compression artifact
Predicted_Types: noise
Missing_Types: jpeg compression artifact
Extra_Types: noise
```

## ⚙️ 配置

该功能默认启用，随validation一起运行。如果需要关闭：

```bash
# 在训练脚本中设置
trainer.log_images_to_wandb=False  # 同时关闭所有wandb图像上传
```

或在代码中：

```python
# 在 ray_trainer.py 的 validate() 方法中
# 注释掉 log_validation_wrong_predictions_to_wandb() 调用
```

## 📝 技术细节

### 文件修改
1. `verl/utils/tracking_image_utils.py`
   - 新增 `log_validation_wrong_predictions_to_wandb()` 函数

2. `verl/trainer/ppo/ray_trainer.py`
   - 在 `validate()` 方法中调用新函数
   - 在validation图像上传后执行

### 数据流
```
Validation Loop
    ↓
Collect: conversation_histories, reward_models, env_names
    ↓
For each sample:
    - Extract predicted_types (from conversation)
    - Extract gt_types (from reward_model)
    - Compare sets → is_correct?
    ↓
If incorrect:
    - Collect image data (original, degraded, restored)
    - Collect metrics (quality, SSIM, LPIPS, PSNR)
    - Add to table
    ↓
Upload to wandb: val_errors/wrong_predictions
```

## 🚀 优势

1. **不影响原有功能**：使用独立命名空间，不与 `val/` 混淆
2. **图像分开显示**：原图、退化图、复原图分列显示，方便对比
3. **详细的错误信息**：漏检、误检一目了然
4. **完整的质量指标**：SSIM/LPIPS/PSNR帮助分析图像质量
5. **自动化**：无需手动筛选，自动识别错误样本

## 🔍 常见问题

**Q: 如何判断预测是否正确？**
A: 使用集合匹配，不考虑顺序。例如 `{noise, blur}` == `{blur, noise}` 是正确的。

**Q: Clean样本会被记录吗？**
A: 不会。Clean样本会被自动跳过，只记录有真实退化的样本。

**Q: 表格会一直累积吗？**
A: 是的。每次validation都会添加新的错误样本到表格中，可以查看历史趋势。

**Q: 如果没有错误样本会怎样？**
A: 会打印 `[INFO] No wrong predictions found at step X`，不会创建空表格。

---

**实现完成日期**: 2025-10-13
**版本**: v1.0
**作者**: AI Assistant

