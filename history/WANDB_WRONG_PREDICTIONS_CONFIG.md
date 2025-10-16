# Wandb错误预测上传配置说明

## 🎯 功能说明

在验证阶段，系统可以自动识别预测错误的样本（退化类型识别不准确的样本），并上传到wandb的独立表格中，方便分析模型在哪些情况下容易出错。

## ⚙️ 配置方式

### 在 IR.sh 中设置环境变量

```bash
# ========== Wandb Upload Configuration ==========
# 控制wandb上传行为
export WANDB_LOG_WRONG_PREDICTIONS=True     # 是否上传错误预测的验证样本到wandb（默认True）
```

### 配置选项

| 配置值 | 说明 |
|--------|------|
| `True` / `true` / `1` / `yes` | **启用**错误预测上传（默认） |
| `False` / `false` / `0` / `no` | **禁用**错误预测上传 |

## 📊 上传的内容

当启用时，验证阶段会上传以下内容到 `val_errors/wrong_predictions` 表格：

### 表格列

1. **Step** - 训练步数
2. **Sample_ID** - 样本ID
3. **Original_Image** - 原图（Ground Truth）
4. **Degraded_Image** - 退化图（输入）
5. **Restored_Image** - 复原图（输出）
6. **GT_Degradation** - 真实退化类型
7. **Predicted_Degradation** - 预测的退化类型
8. **Missing_Types** - 漏检的退化类型
9. **Extra_Types** - 误检的退化类型
10. **Full_Conversation** - 完整对话内容

### 错误判定标准

样本被认为是"错误预测"的条件：
```python
predicted_set = set(predicted_types)  # 模型预测的退化类型集合
gt_set = set(gt_types)                # 真实的退化类型集合

is_wrong = (predicted_set != gt_set)  # 集合不完全匹配即为错误
```

**示例**：

| Ground Truth | 模型预测 | 是否错误 | 原因 |
|-------------|---------|---------|------|
| `["noise", "motion_blur"]` | `["noise", "motion_blur"]` | ❌ 正确 | 完全匹配 |
| `["noise", "motion_blur"]` | `["noise"]` | ✅ **错误** | 漏检了motion_blur |
| `["noise", "motion_blur"]` | `["noise", "haze"]` | ✅ **错误** | 误检了haze，漏检了motion_blur |
| `["noise"]` | `["clean"]` | ✅ **错误** | 完全错误 |

## 🔍 在 Wandb 中查看

### 位置

1. 打开 Wandb 项目页面
2. 进入 **Tables** 标签
3. 查找 `val_errors/wrong_predictions` 表格

### 使用场景

1. **分析错误模式**
   - 查看哪些退化类型组合容易被误判
   - 统计漏检和误检的频率

2. **追踪改进**
   - 按Step列排序，查看训练过程中错误率的变化
   - 对比不同checkpoint的错误样本

3. **Case Study**
   - 查看具体错误样本的图像和对话
   - 分析模型的推理过程

## 📝 日志输出

### 启用时的日志

```bash
[INFO] Found 15 wrong predictions out of 100 samples
[INFO] Creating wrong predictions table with 15 samples
[INFO] Uploading wrong predictions table to: val_errors/wrong_predictions
[INFO] Wrong predictions table columns: ['Step', 'Sample_ID', ...]
[INFO] - Step: 100
[INFO] - Wrong samples: 15
[INFO] - Table: val_errors/wrong_predictions
```

### 禁用时的日志

```bash
[INFO] Skipping wrong predictions upload (WANDB_LOG_WRONG_PREDICTIONS=False)
```

### 无错误预测时的日志

```bash
[INFO] No wrong predictions found at step 100
```

## 💡 使用建议

### 何时启用（`True`）

✅ **训练早期**（前几个epoch）
- 帮助快速发现模型的主要问题
- 了解模型对哪些退化类型不敏感

✅ **调试阶段**
- 深入分析特定的错误case
- 验证修复方案的效果

✅ **最终评估**
- 完整记录模型的错误模式
- 为论文/报告提供素材

### 何时禁用（`False`）

⚠️ **训练后期**（稳定阶段）
- 错误样本数量减少，上传价值降低
- 减少wandb存储空间使用

⚠️ **快速迭代**
- 只关注总体指标，不需要详细分析
- 加快验证速度（跳过表格创建和上传）

⚠️ **资源受限**
- Wandb存储空间有限
- 网络带宽受限

## 🔧 代码实现位置

### 环境变量配置
- **文件**: `examples/agent/IR.sh`
- **行数**: 第59行

### 环境变量读取
- **文件**: `verl/trainer/ppo/ray_trainer.py`
- **行数**: 第856行
- **逻辑**:
  ```python
  import os
  if os.environ.get('WANDB_LOG_WRONG_PREDICTIONS', 'True').lower() in ['true', '1', 'yes']:
      # 调用上传函数
      log_validation_wrong_predictions_to_wandb(...)
  else:
      print("[INFO] Skipping wrong predictions upload")
  ```

### 上传函数
- **文件**: `verl/utils/tracking_image_utils.py`
- **函数**: `log_validation_wrong_predictions_to_wandb()`
- **行数**: 第1897-2192行

## 📊 性能影响

### 启用时的额外开销

1. **计算开销**：
   - 提取预测退化类型：~5ms/sample
   - 对比GT和预测：~1ms/sample
   - 创建表格：~10ms/sample
   - **总计**: ~16ms/sample × 错误样本数

2. **存储开销**：
   - 每个错误样本 ≈ 500KB（3张图片 + 文本）
   - 100个错误样本 ≈ 50MB/step

3. **网络开销**：
   - 取决于错误样本数量和网络带宽
   - 通常 < 30秒/step（如果有错误样本）

### 优化建议

如果错误样本过多（>50个/step），可以考虑：
- 设置最大上传数量限制
- 只上传quality_score最低的N个错误样本
- 降低上传频率（每N个step上传一次）

## 🔄 更新历史

| 日期 | 版本 | 更新内容 |
|------|------|---------|
| 2025-10-14 | v1.0 | 初始版本，添加环境变量控制 |

## ❓ 常见问题

### Q1: 为什么我看不到错误预测表格？

**A**: 可能的原因：
1. 当前step没有错误预测（模型表现完美）
2. `WANDB_LOG_WRONG_PREDICTIONS=False`（被禁用）
3. 数据集中没有退化类型标签（无法判断对错）
4. 所有样本都是clean（会被跳过）

### Q2: 表格中的图片是什么？

**A**: 
- **Original_Image**: 未退化的原图（Ground Truth）
- **Degraded_Image**: 退化后的输入图（模型看到的）
- **Restored_Image**: 模型修复后的输出图

### Q3: Missing_Types 和 Extra_Types 是什么？

**A**: 
- **Missing_Types**: 真实存在但模型漏检的退化类型
  - 例如：GT有`motion_blur`，但模型没预测出来
- **Extra_Types**: 模型误检的退化类型
  - 例如：GT没有`haze`，但模型预测了`haze`

### Q4: 如何减少上传的数据量？

**A**: 
1. 设置 `WANDB_LOG_WRONG_PREDICTIONS=False` 完全禁用
2. 增加验证频率 `trainer.test_freq`（减少验证次数）
3. 修改代码限制最大上传数量（需要改源码）

---

**维护者**: DeepEyes Team  
**最后更新**: 2025-10-14

