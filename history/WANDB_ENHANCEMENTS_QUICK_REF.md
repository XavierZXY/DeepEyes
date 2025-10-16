# WandB增强功能 - 快速参考

## 📊 WandB表格新增列（21列）

| 列号 | 列名 | 说明 | 状态 |
|-----|------|------|------|
| 1 | Step | 训练步数 | 原有 |
| 2 | Sample_ID | 样本ID | 原有 |
| 3 | Trajectory_Image | 图像轨迹 | 原有 |
| 4 | Quality_Score | 质量分数 | 原有 |
| 5 | Num_Tools | 工具数量 | 原有 |
| 6 | Degradation_Type | GT退化类型 | 原有 |
| 7 | Predicted_Degradation_Type | 预测退化类型 | ⭐ 新增 |
| 8 | Prediction_Match | 匹配状态 (✅⚠️❌❓) | ⭐ 新增 |
| 9 | Tool_Status | 工具状态 | 原有 |
| 10 | Failure_Reason | 失败原因 | 原有 |
| 11 | User_Input | 用户输入 | 原有 |
| 12-21 | Turn1_Think ~ Turn5_Tools | 对话内容 | 原有 |

---

## 📈 WandB新增指标

### 1. 有参考图像质量指标
```
reward/ssim_mean/max/min/std           # 训练
val/reward/ssim_mean/max/min/std       # 验证

reward/lpips_mean/max/min/std          # 训练
val/reward/lpips_mean/max/min/std      # 验证

reward/psnr_mean/max/min/std           # 训练
val/reward/psnr_mean/max/min/std       # 验证
```

### 2. 退化类型准确率指标
```
val-acc/overall_accuracy                    # 总体准确率
val-acc/total_samples                       # 总样本数

val-acc/by_type/noise                       # noise类型准确率
val-acc/by_type/dark                        # dark类型准确率
val-acc/by_type/motion_blur                 # 等...

val-acc/by_level/low                        # low等级准确率
val-acc/by_level/medium                     # medium等级准确率
val-acc/by_level/high                       # high等级准确率

val-acc/by_level_and_type/noise_low         # 组合准确率
val-acc/by_level_and_type/dark_high         # 等...
```

---

## 🔍 Prediction_Match Emoji说明

| Emoji | 含义 | 条件 | 示例 |
|-------|------|------|------|
| ✅ | 完全正确 | 预测集合 == GT集合 | GT: noise, Pred: noise |
| ⚠️ | 部分正确 | 有交集但不完全相等 | GT: noise,dark, Pred: noise |
| ❌ | 完全错误 | 无交集或未预测 | GT: noise, Pred: dark 或 none |
| ❓ | 未知 | GT为unknown | GT: unknown, Pred: noise |

---

## 🛠️ Brightening工具映射

**3个工具都映射到 "dark"**:
```
constant_shift          → "dark"
gamma_correction        → "dark"
histogram_equalization  → "dark"
```

示例：
```
工具调用: constant_shift, gamma_correction
预测结果: "dark" (去重)
```

---

## 📂 关键文件

### 新增文件 (1个)
- `verl/utils/degradation_accuracy_utils.py` - 准确率计算

### 修改文件 (3个)
- `verl/trainer/ppo/metric_utils.py` - 添加有参考指标统计
- `verl/trainer/ppo/ray_trainer.py` - 调整计算顺序，添加准确率计算
- `verl/utils/tracking_image_utils.py` - 添加2个新列

### 文档文件 (7个)
- `WANDB_REFERENCE_METRICS_FIX.md`
- `COMPLETE_VERIFICATION_CHECKLIST.md`
- `WANDB_TABLE_PREDICTED_DEGRADATION.md`
- `WANDB_TABLE_PREDICTION_MATCH.md`
- `WANDB_VAL_ACC_PANEL.md`
- `COMPLETE_WANDB_ENHANCEMENTS_SUMMARY.md`
- `WANDB_ENHANCEMENTS_QUICK_REF.md` (本文档)

---

## ✅ 验证清单

- ✅ 无linter错误
- ✅ 单元测试通过
- ✅ 不影响原有功能
- ✅ 使用单例模式（性能优化）
- ✅ 完整异常处理
- ✅ 详细日志输出

---

## 🚀 使用指南

### 查看有参考指标
```
WandB → Charts → 搜索 "val/reward/ssim"
```

### 查看表格
```
WandB → Tables → val/conversation_details
列: Degradation_Type | Predicted_Degradation_Type | Prediction_Match
```

### 查看准确率
```
WandB → Charts → 搜索 "val-acc"
看到: overall_accuracy, by_type/*, by_level/*
```

### 筛选错误样本
```
Tables → val/conversation_details
Filter: Prediction_Match == "❌"
分析: 为什么预测错误
```

---

**快速参考完成！** 🎯

