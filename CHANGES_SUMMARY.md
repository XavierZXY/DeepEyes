# air_v5_dev 分支改动摘要

**分支**: air_v5_dev ← air_v5  
**日期**: 2025-10-13

---

## 🎯 主要改动

### 1️⃣ 验证错误样本自动上传 Wandb

**功能**: 自动识别并上传预测错误的验证样本

**查看位置**:
- 📊 表格: `Tables → val_errors/wrong_predictions`
- 🖼️ 图片: `Media → val_error_images/`
- 📈 统计: `Charts → val_errors/error_rate`

**包含内容**:
- 原图、退化图、复原图（纯净PNG，可下载）
- 真实标签 vs 预测标签
- 漏检、误检分析
- SSIM/LPIPS/PSNR 质量指标
- 图片路径（方便后处理）

**用途**:
- 快速定位模型预测错误的样本
- 分析哪些退化类型容易被漏检/误检
- 导出错误案例用于分析或报告
- 监控训练过程中错误率的变化


### 2️⃣ LPIPS GPU 加速优化

**优化**: 修复 GPU 使用错误，性能提升 50 倍

**性能提升**:
- 单图: 1088ms → 22ms (**50x**)
- 批量: 10,884ms → 32ms (**340x**)

**优化内容**:
- ✅ LPIPS 模型保持在 GPU
- ✅ CLIP 模型移到 GPU
- ✅ PyIQA 模型（NIQE/BRISQUE/CLIP-IQA/Hyper-IQA）在 GPU 初始化

**影响**:
- 大幅缩短验证时间
- 解决了之前 GPU 使用报错的问题
- 自动检测 GPU，不可用时回退到 CPU

---

## 📁 修改的文件

### 核心代码 (3个)

```
modified:   verl/utils/tracking_image_utils.py
    → 新增 log_validation_wrong_predictions_to_wandb() 函数

modified:   verl/trainer/ppo/ray_trainer.py
    → 在验证流程中调用错误样本上传

modified:   verl/utils/reward_score/image_quality_metrics.py
    → LPIPS/CLIP/PyIQA GPU 加速优化
```

### 文档 (3个)

```
new file:   AIR_V5_DEV_CHANGELOG.md          (详细改动说明)
new file:   VALIDATION_ERROR_LOGGING.md      (错误样本上传功能文档)
new file:   GPU_ACCELERATION_SUMMARY.md      (GPU加速性能报告)
```

---

## 🚀 使用方式

**自动启用**: 运行训练即可，无需额外配置

```bash
bash examples/agent/IR.sh
```

**查看结果**: 在 wandb 网页查看

```
Tables → val_errors/wrong_predictions     (表格)
Media → val_error_images/                 (图片)
Charts → val_errors/error_rate            (统计)
```

---

## ✅ 兼容性

- ✅ 完全向后兼容
- ✅ 不影响现有功能
- ✅ 不改变计算结果
- ✅ GPU 不可用时自动回退

---

## 📊 预期效果

### 错误样本记录

每次 validation 会自动记录：
- 错误样本数量和比例
- 漏检最多的退化类型
- 误检最多的退化类型
- 随训练的改进趋势

### 性能提升

对于 100 样本的 validation batch:
- 节省时间: ~107 秒
- 总加速比: ~50x (LPIPS部分)

---

## 📝 快速参考

### 表格列说明

| 重要列 | 说明 |
|--------|------|
| `Sample_ID` | 样本标识 |
| `Image_Path_*` | 图片路径（后处理用） |
| `Ground_Truth_Types` | 真实标签 |
| `Predicted_Types` | 预测标签 |
| `Missing_Types` | 漏检 ⚠️ |
| `Extra_Types` | 误检 ⚠️ |

### GPU 模型状态

初始化时会显示：
```
[INFO] LPIPS model initialized on GPU: cuda:0
[INFO] CLIP model initialized on GPU
[INFO] PyIQA模型初始化完成（device=cuda）
```

---

**详细文档**: 见 `AIR_V5_DEV_CHANGELOG.md`

