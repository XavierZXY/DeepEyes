# Wandb表格指标增强 - 退化图和复原图对比

## 🎯 新功能概述

为wandb表格添加了完整的图像质量指标对比功能，现在可以直观地看到：
- 退化图（Degraded）与原图的指标
- 复原图（Restored）与原图的指标  
- 处理前后的提升百分比

## 📊 新增的表格列（9列）

### 退化图指标（3列）
| 列名 | 说明 | 数值范围 |
|-----|------|---------|
| `Degraded_SSIM` | 退化图vs原图的SSIM | 0.0-1.0（越高越好）|
| `Degraded_LPIPS` | 退化图vs原图的LPIPS | 0.0-1.0（越低越好）|
| `Degraded_PSNR` | 退化图vs原图的PSNR | 0-∞ dB（越高越好）|

### 复原图指标（3列）
| 列名 | 说明 | 数值范围 |
|-----|------|---------|
| `Restored_SSIM` | 复原图vs原图的SSIM | 0.0-1.0（越高越好）|
| `Restored_LPIPS` | 复原图vs原图的LPIPS | 0.0-1.0（越低越好）|
| `Restored_PSNR` | 复原图vs原图的PSNR | 0-∞ dB（越高越好）|

### 提升百分比（3列）
| 列名 | 说明 | 数值含义 |
|-----|------|---------|
| `Improve_SSIM%` | SSIM提升率 | 正值=提升，负值=降低 |
| `Improve_LPIPS%` | LPIPS改善率 | 正值=改善，负值=恶化 |
| `Improve_PSNR%` | PSNR提升率 | 正值=提升，负值=降低 |

## 📐 计算公式

### 提升百分比计算

**SSIM和PSNR**（越高越好）：
```python
improvement = (restored - degraded) / degraded * 100
```

**LPIPS**（越低越好）：
```python
improvement = (degraded - restored) / degraded * 100
```

### 示例

**场景1：处理成功**
```
Degraded: SSIM=0.600, LPIPS=0.400, PSNR=20.0
Restored: SSIM=0.850, LPIPS=0.150, PSNR=28.0

Improvement:
  SSIM = (0.850 - 0.600) / 0.600 * 100 = +41.7% ✅ 提升
  LPIPS = (0.400 - 0.150) / 0.400 * 100 = +62.5% ✅ 改善
  PSNR = (28.0 - 20.0) / 20.0 * 100 = +40.0% ✅ 提升
```

**场景2：处理失败（未调用工具）**
```
Degraded: SSIM=0.600, LPIPS=0.400, PSNR=20.0
Restored: SSIM=0.000, LPIPS=0.000, PSNR=0.0

Improvement: SSIM=0.0%, LPIPS=0.0%, PSNR=0.0% ⚠️ 未处理
```

**场景3：处理反而变差**
```
Degraded: SSIM=0.800, LPIPS=0.200, PSNR=25.0
Restored: SSIM=0.600, LPIPS=0.400, PSNR=18.0

Improvement:
  SSIM = (0.600 - 0.800) / 0.800 * 100 = -25.0% ❌ 降低
  LPIPS = (0.200 - 0.400) / 0.200 * 100 = -100.0% ❌ 恶化
  PSNR = (18.0 - 25.0) / 25.0 * 100 = -28.0% ❌ 降低
```

## 🚀 性能优化

### 智能采样计算

**训练时**：只对上传到wandb的样本计算
```python
# 采样策略（log_rollout_images_to_wandb）
selected_indices = worst_samples + best_samples + random_samples
# 例如：[0, 5] (worst) + [28, 31] (best) + [7, 12, 19] (random) = 7个样本

# 只计算这7个样本的退化图指标
compute_degraded_and_restored_metrics_for_indices(
    batch_data=batch_data,
    indices=selected_indices  # ← 只计算7个
)
```

**验证时**：全部样本计算
```python
# 验证时所有样本都需要
indices = list(range(len(image_histories)))  # 例如：88个样本

# 计算全部88个样本
compute_degraded_and_restored_metrics_for_indices(
    batch_data=batch_data,
    indices=indices  # ← 全部计算
)
```

### 性能对比

假设训练batch_size=32，验证batch_size=88：

| 场景 | 旧方法 | 新方法 | 节省 |
|-----|-------|-------|-----|
| 训练（采样） | 计算0个 | 计算9个（2+2+5） | ✅ 只计算需要的 |
| 验证（全部） | 计算0个 | 计算88个 | ✅ 全部计算 |

**估算时间**：
- 每个样本计算2组指标（退化+复原）：~0.1秒
- 训练：0.9秒/batch（9个样本）
- 验证：8.8秒/batch（88个样本）

## 💻 技术实现

### 新增函数

**`compute_degraded_and_restored_metrics_for_indices()`**

位置：`verl/utils/tracking_image_utils.py` 第1346-1494行

```python
def compute_degraded_and_restored_metrics_for_indices(
    batch_data: Dict,
    indices: List[int],
) -> Dict[str, List]:
    """
    仅为指定indices的样本计算退化图和复原图的有参考指标
    
    Args:
        batch_data: 包含image_history和original_images
        indices: 需要计算的样本索引列表
        
    Returns:
        Dict包含9个key:
        - degraded_ssim, degraded_lpips, degraded_psnr
        - restored_ssim, restored_lpips, restored_psnr
        - improvement_ssim, improvement_lpips, improvement_psnr
    """
```

### 调用流程

```
log_rollout_images_to_wandb()
  ↓ 确定indices（训练采样/验证全部）
  ↓
_log_conversation_table()
  ↓ 第847-856行：调用compute_degraded_and_restored_metrics_for_indices
  ↓
  ↓ 对每个样本：
  ↓   - 提取degraded_img（image_history[0]）
  ↓   - 提取restored_img（image_history[-1]）
  ↓   - 提取original_img（original_images[idx]）
  ↓   - 计算degraded vs original的SSIM/LPIPS/PSNR
  ↓   - 计算restored vs original的SSIM/LPIPS/PSNR
  ↓   - 计算improvement百分比
  ↓
  ↓ 第1092-1133行：构建表格行，添加9个指标列
  ↓
wandb.Table.add_data(*row)
  ↓
上传到wandb
```

## 📊 表格总览

### 完整列结构（现在有30列）

```
1. Step
2. Sample_ID
3. Trajectory_Image
4. Quality_Score
5. Num_Tools
6. Degradation_Type
7. Predicted_Degradation_Type
8. Prediction_Match
9. Tool_Status
10. Failure_Reason
11. Degraded_SSIM       ← 新增
12. Degraded_LPIPS      ← 新增
13. Degraded_PSNR       ← 新增
14. Restored_SSIM       ← 新增
15. Restored_LPIPS      ← 新增
16. Restored_PSNR       ← 新增
17. Improve_SSIM%       ← 新增
18. Improve_LPIPS%      ← 新增
19. Improve_PSNR%       ← 新增
20. User_Input
21. Turn1_Think
22. Turn1_Tools
23. Turn2_Think
24. Turn2_Tools
25. Turn3_Think
26. Turn3_Tools
27. Turn4_Think
28. Turn4_Tools
29. Turn5_Think
30. Turn5_Tools
```

## 🔍 使用指南

### 在Wandb中查看

1. 打开wandb run页面
2. 导航到 **Tables** → `train/conversation_details` 或 `val/conversation_details`
3. 查看新增的指标列

### 常用筛选和排序

**查找提升最大的样本**：
```
排序：点击 "Improve_SSIM%" 列标题，降序
结果：看到提升最多的样本（例如+50%）
```

**查找处理失败的样本**：
```
筛选：Tool_Status = "⚠️ Requested but Failed"
查看：这些样本的Restored指标应该全是0.0
```

**查找处理反而变差的样本**：
```
筛选：Improve_SSIM% < 0
结果：看到处理后质量反而下降的样本
```

**对比退化图和复原图**：
```
排序：按Degraded_SSIM升序（最差的退化图）
对比：查看这些样本的Restored_SSIM是否有显著提升
```

## 📈 分析价值

### 1. 评估模型性能
- 看Improvement%的分布，了解模型平均提升幅度
- 正值占比高 = 模型效果好
- 负值较多 = 模型可能存在问题

### 2. 识别问题样本
- Improvement%为负 = 处理后反而变差，需要分析原因
- Restored指标为0 = 工具未执行或执行失败

### 3. 对比不同工具效果
- 筛选不同的Predicted_Degradation_Type
- 对比各类型的平均Improvement%
- 了解哪些工具效果最好

### 4. 训练监控
- 追踪Improvement%随训练step的变化
- 观察模型是否在学习选择正确的工具

## 🐛 调试信息

训练时会打印详细的调试日志：

```bash
[DEBUG DEGRADED METRICS] Computing metrics for 9 samples (indices: [0, 5, 28, 31, 7]...)
[DEBUG DEGRADED METRICS] Sample 0:
  Degraded: SSIM=0.6234, LPIPS=0.3876, PSNR=19.45
  Restored: SSIM=0.8421, LPIPS=0.1523, PSNR=26.78
  Improvement: SSIM=+35.1%, LPIPS=+60.7%, PSNR=+37.7%
[DEBUG DEGRADED METRICS] ========== Summary ==========
[DEBUG DEGRADED METRICS] Requested: 9, Calculated: 9, Skipped: 0
[DEBUG DEGRADED METRICS] ================================

[DEBUG CONV TABLE] First row data:
  quality=0.856, num_tools=2
  degradation=motion blur, tool_status=✅ Success
  Degraded: SSIM=0.6234, LPIPS=0.3876, PSNR=19.45
  Restored: SSIM=0.8421, LPIPS=0.1523, PSNR=26.78
  Improvement: SSIM=+35.1%, LPIPS=+60.7%, PSNR=+37.7%
```

## ✅ 验证清单

完成修改后，检查：

### 代码层面
- ✅ 新增函数 `compute_degraded_and_restored_metrics_for_indices()`
- ✅ 修改表格列定义（增加9列）
- ✅ 在`_log_conversation_table()`中调用计算函数
- ✅ 在构建row时添加9个指标值
- ✅ 更新调试输出

### 运行时检查
```bash
# 1. 检查日志中的计算过程
grep "DEBUG DEGRADED METRICS" logs/*.log

# 2. 检查表格列数
grep "total_cols=" logs/*.log
# 应该显示：total_cols=30（之前是21列）

# 3. 在wandb中查看表格
# - 确认有9个新列
# - 检查数值是否合理
# - 验证Improvement%的正负号
```

## 🎯 预期效果

### 表格示例数据

| Sample_ID | Degraded_SSIM | Restored_SSIM | Improve_SSIM% | Tool_Status |
|-----------|---------------|---------------|---------------|-------------|
| train_step100_idx5 | 0.623 | 0.842 | +35.1% | ✅ Success |
| train_step100_idx12 | 0.501 | 0.789 | +57.5% | ✅ Success |
| train_step100_idx28 | 0.720 | 0.000 | 0.0% | ⚠️ Requested but Failed |
| train_step100_idx31 | 0.650 | 0.580 | -10.8% | ✅ Success ❌ 处理变差 |

### 分析洞察

从上表可以看出：
1. ✅ idx5和idx12：处理效果好，SSIM提升35-57%
2. ⚠️ idx28：工具未执行，无提升
3. ❌ idx31：处理后反而变差，需要调查原因（可能选错了工具）

## 📝 总结

### 核心改进
1. ✅ 添加9个新的指标列到wandb表格
2. ✅ 只对需要上传的样本计算（性能优化）
3. ✅ 提供退化图、复原图、提升百分比的完整对比
4. ✅ 帮助评估模型性能和识别问题样本

### 关键文件
- `verl/utils/tracking_image_utils.py`
  - 第1346-1494行：新增计算函数
  - 第823-830行：修改表格列定义
  - 第847-856行：调用计算函数
  - 第1092-1133行：构建表格行

### 性能特点
- 训练时：只计算~9个样本（采样）
- 验证时：计算全部样本
- 每个样本计算时间：~0.1秒

所有修改已完成并优化！🎉

