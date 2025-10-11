# Wandb奖励组成部分统计指标

## 概述

现在wandb会分别统计**格式奖励**和**图像质量奖励**两个核心组成部分，而不是只显示总的奖励分数。

## 新增指标列表（精简版）

### 1️⃣ **格式奖励指标** (`reward/format_*`)

#### `reward/format_correct_ratio`
- **含义**: 格式完全正确的样本比例
- **计算**: format_score = 1.0 的样本数 / 总样本数
- **范围**: 0.0 - 1.0
- **期望**: 越高越好（理想值 1.0）

#### `reward/format_violation_ratio`
- **含义**: 格式违规的样本比例
- **计算**: format_score = -1.0 的样本数 / 总样本数
- **范围**: 0.0 - 1.0
- **期望**: 越低越好（理想值 0.0）

#### `reward/format_score_mean`
- **含义**: 格式分数的平均值
- **范围**: -1.0 - 1.0
- **说明**: 
  - 1.0 = 完美格式
  - -1.0 = 格式违规
  - 0.0 附近 = 部分正确

---

### 2️⃣ **图像质量奖励指标** (`reward/quality_*`)

#### `reward/quality_score_mean`
- **含义**: 图像质量分数的平均值
- **范围**: 0.0 - 1.0
- **说明**: 基于NIQE、BRISQUE、CPBD等无参考指标计算

#### `reward/quality_score_max`
- **含义**: 图像质量分数的最大值
- **用途**: 看模型能达到的最好质量

#### `reward/quality_score_min`
- **含义**: 图像质量分数的最小值
- **用途**: 看模型最差的表现

#### `reward/quality_score_std`
- **含义**: 图像质量分数的标准差
- **用途**: 评估模型稳定性

#### `reward/quality_continuous_mean`
- **含义**: 连续图像质量分数的平均值
- **说明**: 离散化之前的原始值（如果启用了离散化）

---

## 训练 vs 验证指标

### 训练指标（`reward/...`）
- 实时反映当前batch的表现
- 每个训练step更新
- 显示路径：`reward/format_correct_ratio`, `reward/quality_score_mean`, 等

### 验证指标（`val/reward/...`）
- 在整个验证集上计算
- 按test_freq频率更新
- 显示路径：`val/reward/format_correct_ratio`, `val/reward/quality_score_mean`, 等

---

## Wandb面板组织建议

### 面板1: 奖励总览
```
- critic/rewards/mean (总奖励)
- reward/format_score_mean (格式分数)
- reward/quality_score_mean (质量分数)
```

### 面板2: 格式监控
```
- reward/format_correct_ratio ↑
- reward/format_violation_ratio ↓
- val/reward/format_correct_ratio
```

### 面板3: 图像质量监控
```
- reward/quality_score_mean
- reward/quality_score_max
- reward/quality_score_min
- reward/quality_score_std
```

---

## 指标解读示例

### 训练良好的模型
```
reward/format_correct_ratio: 0.95  ✅ (95%样本格式正确)
reward/format_violation_ratio: 0.02  ✅ (2%样本格式违规)
reward/format_score_mean: 0.85  ✅ (格式分数高)
reward/quality_score_mean: 0.78  ✅ (图像质量好)
reward/quality_score_std: 0.12  ✅ (稳定性好)
```

### 需要改进的模型
```
reward/format_correct_ratio: 0.45  ❌ (格式问题严重)
reward/format_violation_ratio: 0.35  ❌ (35%违规)
reward/format_score_mean: -0.10  ❌ (格式分数低)
reward/quality_score_mean: 0.35  ❌ (图像质量不足)
reward/quality_score_std: 0.28  ❌ (不稳定)
```

---

## 与原有指标的关系

### 总奖励分解
```
critic/rewards/mean (总奖励)
  = reward/format_score_mean * 0.3
  + reward/quality_score_mean * 0.7
```

### 质量分数分解（image_quality模式）
```
reward/quality_score_mean
  ≈ 加权组合(NIQE, BRISQUE, CPBD, CLIP-IQA, Hyper-IQA)  # 无参考模式
  或
  ≈ 0.35*SSIM + 0.50*(1-LPIPS) + 0.15*PSNR  # 有参考模式
```

---

## 调试和验证

### 查看收集的指标数量
```bash
grep "DEBUG REWARD METRICS" logs/debug_*.log | tail -20
```

应该看到：
```
[DEBUG REWARD METRICS] Collected 15 reward component metrics
[DEBUG VAL REWARD METRICS] Collected 15 validation reward component metrics
```

### 查看具体指标值
在wandb中查找以下路径：
- Charts → `reward/*`
- Charts → `val/reward/*`

---

## 实现细节

### 代码位置
- **统计函数**: `/app/xiaominl/AIR/verl/trainer/ppo/metric_utils.py` 第219-299行
  - `compute_reward_component_metrics()`
  
- **训练调用**: `/app/xiaominl/AIR/verl/trainer/ppo/ray_trainer.py` 第1233-1237行
  - 在收集metrics时调用

- **验证调用**: `/app/xiaominl/AIR/verl/trainer/ppo/ray_trainer.py` 第738-744行
  - 在validation结束时调用

### 数据来源
指标数据来自：
- `reward_extra_infos_dict` - reward_fn返回的详细信息
- 由`compute_score_v2()`函数在`image_restoration.py`中计算

---

## 使用建议

### 监控训练进度
1. **格式收敛**: 观察`reward/format_correct_ratio`是否逐步提升到>0.9
2. **质量提升**: 观察`reward/quality_score_mean`是否持续增长
3. **稳定性**: 观察`reward/quality_score_std`是否逐渐减小

### 对比实验
- 使用不同的奖励权重（format_weight vs accuracy_weight）
- 对比有参考vs无参考模式的效果
- 分析哪些指标对总奖励影响最大

### 问题诊断
- 如果`format_violation_ratio`很高 → 调整格式奖励权重或改进提示词
- 如果`quality_score`不增长 → 检查工具是否正确执行
- 如果`ssim_samples`很少 → 很多样本没有执行工具（可能直接给answer）

---

## 配置选项

这些统计是自动启用的，无需额外配置。如果要禁用：

```yaml
# 在训练配置中（不推荐禁用）
trainer:
  log_reward_components: false  # 默认true
```

---

## 注意事项

1. **有参考指标的样本数**: `reward/ssim_samples` 可能小于batch_size，因为只统计执行了工具的样本
2. **验证指标前缀**: 验证集指标都带`val/`前缀，如`val/reward/format_correct_ratio`
3. **数值范围**: 不同指标有不同的范围和含义，注意区分
4. **LPIPS特殊性**: 值越小越好（与其他指标相反）

---

## 完整指标列表

### 训练阶段
```
reward/format_correct_ratio         # 格式正确率
reward/format_violation_ratio       # 格式违规率
reward/format_score_mean            # 格式分数均值
reward/quality_score_mean           # 图像质量分数均值
reward/quality_score_max            # 图像质量分数最大值
reward/quality_score_min            # 图像质量分数最小值
reward/quality_score_std            # 图像质量分数标准差
```

### 验证阶段（加val/前缀）
```
val/reward/format_correct_ratio
val/reward/format_violation_ratio
val/reward/format_score_mean
val/reward/quality_score_mean
val/reward/quality_score_max
val/reward/quality_score_min
val/reward/quality_score_std
```

---

## 可视化示例

在wandb中创建自定义图表：

### Chart 1: 奖励分解
```python
# X轴: Step
# Y轴: 
#   - critic/rewards/mean (总奖励)
#   - reward/format_score_mean * 0.3 (格式部分)
#   - reward/quality_score_mean * 0.7 (质量部分)
```

### Chart 2: 格式收敛
```python
# X轴: Step
# Y轴:
#   - reward/format_correct_ratio (正确率)
#   - reward/format_violation_ratio (违规率)
```

### Chart 3: 质量提升
```python
# X轴: Step
# Y轴:
#   - reward/quality_score_mean
#   - reward/ssim_mean
#   - 1.0 - reward/lpips_mean (转换为越大越好)
```

---

## 故障排查

### 问题1: 指标未显示
**检查**: 
```bash
grep "DEBUG REWARD METRICS" logs/*.log
```

应该看到：
```
[DEBUG REWARD METRICS] Collected 15 reward component metrics
```

### 问题2: 某些指标为空
**原因**: reward_extra_infos_dict中没有对应的key

**检查**: 查看reward_fn是否返回了相应的字段

### 问题3: 有参考指标samples数=0
**原因**: 没有样本执行工具（全部直接给answer）

**检查**: 
- 查看`agent/tool_call_mean`是否 > 0
- 查看`reward/clean_sample_ratio`是否接近1.0

---

## 更新日志

### v1.0 (2025-10-11)
- ✅ 添加格式奖励统计（正确率、违规率、平均分）
- ✅ 添加图像质量奖励统计（均值、最值、标准差）
- ✅ 添加退化顺序奖励统计
- ✅ 添加clean样本准确率统计
- ✅ 添加有参考指标统计（SSIM、LPIPS、PSNR）
- ✅ 添加无参考指标统计（NIQE、BRISQUE等）
- ✅ 训练和验证分别统计

