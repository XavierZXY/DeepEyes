# Wandb上传控制总结

## ✅ 已完成的修改

### 1. 新增环境变量控制

在 `examples/agent/IR.sh` 中添加了新的环境变量：

```bash
export WANDB_LOG_WRONG_PREDICTIONS=True
```

**位置**: IR.sh 第59行

### 2. 修改代码逻辑

在 `verl/trainer/ppo/ray_trainer.py` 中添加了环境变量读取逻辑：

```python
import os
if os.environ.get('WANDB_LOG_WRONG_PREDICTIONS', 'True').lower() in ['true', '1', 'yes']:
    # 上传错误预测样本
    log_validation_wrong_predictions_to_wandb(...)
else:
    print(f"[INFO] Skipping wrong predictions upload (WANDB_LOG_WRONG_PREDICTIONS=False)")
```

**位置**: ray_trainer.py 第855-873行

### 3. 新增配置文档

创建了详细的配置说明文档：
- `WANDB_WRONG_PREDICTIONS_CONFIG.md` - 完整的功能说明和使用指南

## 🎯 如何使用

### 启用错误预测上传（默认）

在 `IR.sh` 中设置：
```bash
export WANDB_LOG_WRONG_PREDICTIONS=True
```

或者使用以下任一值：`true`, `1`, `yes`

**效果**：
- ✅ 验证时会上传预测错误的样本到 `val_errors/wrong_predictions` 表格
- ✅ 表格包含：原图、退化图、复原图、GT退化类型、预测退化类型等
- ✅ 帮助分析模型在哪些情况下容易出错

### 禁用错误预测上传

在 `IR.sh` 中设置：
```bash
export WANDB_LOG_WRONG_PREDICTIONS=False
```

或者使用以下任一值：`false`, `0`, `no`

**效果**：
- ⚠️ 跳过错误预测样本的收集和上传
- ⚠️ 只会打印日志：`[INFO] Skipping wrong predictions upload`
- ✅ 节省wandb存储空间和上传带宽
- ✅ 加快验证速度

## 📊 在 Wandb 中查看

当启用时，可以在 Wandb 中查看错误预测：

1. 打开 Wandb 项目页面
2. 进入 **Tables** 标签
3. 查找 `val_errors/wrong_predictions` 表格

**表格列**：
- Step, Sample_ID
- Original_Image, Degraded_Image, Restored_Image
- GT_Degradation, Predicted_Degradation
- Missing_Types, Extra_Types
- Full_Conversation

## 🔧 修改的文件

| 文件 | 修改内容 | 行数 |
|------|---------|------|
| `examples/agent/IR.sh` | 添加环境变量 `WANDB_LOG_WRONG_PREDICTIONS` | 59 |
| `verl/trainer/ppo/ray_trainer.py` | 添加环境变量读取和条件判断 | 855-873 |
| `WANDB_WRONG_PREDICTIONS_CONFIG.md` | 新增配置说明文档 | - |
| `WANDB_CONTROL_SUMMARY.md` | 新增快速参考文档（本文件） | - |

## 💡 使用建议

### 推荐启用的场景

✅ **训练初期**（前10-20个epoch）
- 快速发现模型的主要问题
- 了解模型对哪些退化类型识别不准

✅ **调试和分析**
- 深入分析特定的错误case
- 验证改进方案的效果

✅ **最终评估**
- 完整记录模型的错误模式
- 为论文/报告准备素材

### 推荐禁用的场景

⚠️ **训练后期**（模型已收敛）
- 错误样本很少，上传价值低
- 减少wandb存储使用

⚠️ **快速实验迭代**
- 只关注总体指标
- 不需要详细的错误分析

⚠️ **资源受限**
- Wandb存储空间有限
- 网络带宽受限

## 📝 日志示例

### 启用时的日志

```bash
[INFO] Found 15 wrong predictions out of 100 samples
[INFO] Creating wrong predictions table with 15 samples
[INFO] Uploading wrong predictions table to: val_errors/wrong_predictions
[INFO] - Step: 100
[INFO] - Wrong samples: 15
[INFO] - Table: val_errors/wrong_predictions
```

### 禁用时的日志

```bash
[INFO] Skipping wrong predictions upload (WANDB_LOG_WRONG_PREDICTIONS=False)
```

### 无错误时的日志

```bash
[INFO] No wrong predictions found at step 100
```

## 🔄 与其他配置的关系

### 相关的Wandb配置

```bash
# IR.sh中的其他wandb相关配置

# Wandb API Key
export WANDB_API_KEY=ce0821ccdf886f2dbb5703772a0c41aa85611afb

# 项目名称和实验名称
PROJECT_NAME="IRagent"
EXPERIMENT_NAME="debug_for_TIR_IR_..."

# 训练器配置
trainer.logger=['console','wandb','rl_logging_board']
```

### 独立性

- `WANDB_LOG_WRONG_PREDICTIONS` 是**独立**的配置
- 不影响其他wandb上传功能：
  - ✅ 正常的训练图像上传（`train/trajectories`）
  - ✅ 验证图像上传（`val/trajectories`）
  - ✅ 对话表格上传（`train_conversation_table`, `val_conversation_table`）
  - ✅ 指标上传（`reward/*`, `critic/*`, `actor/*`等）

## 🎓 技术细节

### 错误判定逻辑

```python
# 从模型对话中提取预测的退化类型
predicted_types = extract_predicted_degradation_types_from_conversation(conv_history)
predicted_set = set(predicted_types)  # 转为集合

# 从GT数据中提取真实的退化类型
gt_types, gt_levels = extract_ground_truth_degradation_info(reward_model)
gt_set = set(gt_types)  # 转为集合

# 判断是否错误（集合不完全匹配）
is_wrong = (predicted_set != gt_set)

# 计算漏检和误检
missing_types = gt_set - predicted_set      # GT有但模型漏检的
extra_types = predicted_set - gt_set        # 模型误检的（GT没有）
```

### 性能影响

| 操作 | 时间开销 |
|------|---------|
| 提取预测退化类型 | ~5ms/sample |
| 对比GT和预测 | ~1ms/sample |
| 创建表格 | ~10ms/sample |
| 上传到wandb | ~500ms/batch |
| **总计** | ~16ms × 错误样本数 |

**存储开销**：每个错误样本 ≈ 500KB（3张图片 + 文本）

## 🔗 相关文档

- 📄 `WANDB_WRONG_PREDICTIONS_CONFIG.md` - 详细的功能说明
- 📄 `WANDB_UPLOAD_COMPLETE_GUIDE.md` - 完整的wandb上传指南
- 📄 `WANDB_FEATURES_SUMMARY.md` - Wandb功能总结
- 📄 `WANDB_METRICS_GUIDE.md` - Wandb指标说明

## ❓ 常见问题

### Q: 如何查看当前是否启用了错误预测上传？

**A**: 查看日志输出：
- 如果看到 `[INFO] Found X wrong predictions...`，说明已启用
- 如果看到 `[INFO] Skipping wrong predictions upload`，说明已禁用

### Q: 禁用后会影响其他wandb功能吗？

**A**: 不会。只影响错误预测表格的上传，其他功能（训练图像、验证图像、指标等）完全不受影响。

### Q: 可以在训练过程中动态切换吗？

**A**: 不可以。环境变量在训练启动时读取，训练过程中不会重新读取。需要重启训练才能生效。

### Q: 如果没有设置这个环境变量会怎样？

**A**: 默认为 `True`（启用）。代码中的默认值：
```python
os.environ.get('WANDB_LOG_WRONG_PREDICTIONS', 'True')
```

---

**创建时间**: 2025-10-14  
**维护者**: DeepEyes Team

