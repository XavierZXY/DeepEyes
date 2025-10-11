# WandB有参考指标显示修复

## 🎯 问题描述

在WandB的validation指标中，没有看到PSNR、SSIM、LPIPS等有参考指标，只能看到 `val/reward/quality_score_std` 等无参考指标。

## 🔍 根本原因

代码执行顺序问题：

```python
# 原代码顺序（错误）
1. 统计指标: compute_reward_component_metrics(reward_extra_infos_dict)  # 第738-744行
2. 计算有参考指标: _compute_reference_metrics_for_batch(...)          # 第770-776行
3. 添加到字典: reward_extra_infos_dict.update(val_ref_metrics)         # 第776行
```

**问题**: 统计时 `reward_extra_infos_dict` 还没有包含有参考指标数据！

## ✅ 修复方案

调整代码执行顺序：

```python
# 修复后的顺序（正确）
1. 计算有参考指标: _compute_reference_metrics_for_batch(...)          # 第751-757行
2. 添加到字典: reward_extra_infos_dict.update(val_ref_metrics)         # 第757行
3. 统计指标: compute_reward_component_metrics(reward_extra_infos_dict)  # 第763-768行
```

## 📝 修改的文件

### 1. `verl/trainer/ppo/metric_utils.py`

**添加有参考指标的统计** (288-328行)

```python
# SSIM统计 (0.0 - 1.0, 越高越好)
if 'ssim_score_ref' in reward_extra_infos_dict:
    valid_ssim = [s for s in ssim_scores if s > 0.0]
    if len(valid_ssim) > 0:
        metrics['reward/ssim_mean'] = np.mean(valid_ssim)
        metrics['reward/ssim_max'] = np.max(valid_ssim)
        metrics['reward/ssim_min'] = np.min(valid_ssim)
        metrics['reward/ssim_std'] = np.std(valid_ssim)
        metrics['reward/ssim_valid_samples'] = len(valid_ssim)

# LPIPS统计 (0.0 - 1.0, 越低越好)
if 'lpips_score_ref' in reward_extra_infos_dict:
    valid_lpips = [s for s in lpips_scores if s > 0.0]
    if len(valid_lpips) > 0:
        metrics['reward/lpips_mean'] = np.mean(valid_lpips)
        metrics['reward/lpips_max'] = np.max(valid_lpips)
        metrics['reward/lpips_min'] = np.min(valid_lpips)
        metrics['reward/lpips_std'] = np.std(valid_lpips)
        metrics['reward/lpips_valid_samples'] = len(valid_lpips)

# PSNR统计 (通常10-50, 越高越好)
if 'psnr_score_ref' in reward_extra_infos_dict:
    valid_psnr = [s for s in psnr_scores if s > 0.0]
    if len(valid_psnr) > 0:
        metrics['reward/psnr_mean'] = np.mean(valid_psnr)
        metrics['reward/psnr_max'] = np.max(valid_psnr)
        metrics['reward/psnr_min'] = np.min(valid_psnr)
        metrics['reward/psnr_std'] = np.std(valid_psnr)
        metrics['reward/psnr_valid_samples'] = len(valid_psnr)
```

### 2. `verl/trainer/ppo/ray_trainer.py`

**Training阶段** (1278-1285行)
```python
# 有参考指标按需计算（用于wandb展示和统计）
ref_metrics = _compute_reference_metrics_for_batch(
    batch_data=batch_data,
    reward_extra_infos_dict=reward_extra_infos_dict
)
detailed_metrics.update(ref_metrics)
# 同时将有参考指标添加到reward_extra_infos_dict，以便统计
reward_extra_infos_dict.update(ref_metrics)
```

**Validation阶段** (738-768行)
```python
# 在统计之前，先计算有参考指标
if len(val_image_histories) > 0:
    try:
        val_batch_data = {
            'image_history': val_image_histories,
            'raw_prompt': val_raw_prompts,
            'responses': val_responses,
            'original_images': val_original_images,
            'conversation_history': val_conversation_histories,
        }
        
        # 有参考指标按需计算
        val_ref_metrics = _compute_reference_metrics_for_batch(
            batch_data=val_batch_data,
            reward_extra_infos_dict=reward_extra_infos_dict
        )
        # 将有参考指标添加到reward_extra_infos_dict
        reward_extra_infos_dict.update(val_ref_metrics)
    except Exception as e:
        print(f"[WARNING] Failed to compute reference metrics: {e}")

# 收集验证集的奖励组成部分统计指标（现在包含有参考指标）
if reward_extra_infos_dict:
    val_reward_component_metrics = compute_reward_component_metrics(reward_extra_infos_dict)
    # 添加val前缀
    for key, value in val_reward_component_metrics.items():
        metric_dict[f"val/{key}"] = value
```

## 📊 现在WandB会显示的指标

### 训练阶段 (train)
```
reward/format_correct_ratio          # 格式正确率
reward/quality_score_mean/max/min/std  # 图像质量（无参考）
reward/degradation_type_score_mean   # 退化类型识别
reward/ssim_mean/max/min/std         # SSIM（有参考）⭐
reward/lpips_mean/max/min/std        # LPIPS（有参考）⭐
reward/psnr_mean/max/min/std         # PSNR（有参考）⭐
reward/ssim_valid_samples            # 有效样本数
reward/lpips_valid_samples           # 有效样本数
reward/psnr_valid_samples            # 有效样本数
```

### 验证阶段 (val)
```
val/reward/format_correct_ratio
val/reward/quality_score_mean/max/min/std
val/reward/degradation_type_score_mean
val/reward/ssim_mean/max/min/std     # SSIM（有参考）⭐
val/reward/lpips_mean/max/min/std    # LPIPS（有参考）⭐
val/reward/psnr_mean/max/min/std     # PSNR（有参考）⭐
val/reward/ssim_valid_samples
val/reward/lpips_valid_samples
val/reward/psnr_valid_samples
```

## 🎯 关键点

1. **计算顺序很重要**: 必须先计算有参考指标，再统计
2. **单例模式**: 使用 `get_image_quality_metrics()` 避免重复初始化模型
3. **只统计有效样本**: 过滤掉分数为0的样本（工具未执行）
4. **与无参考指标同级**: 所有指标都在 `reward/` 或 `val/reward/` 下

## ✅ 验证方法

运行训练后，在WandB中搜索：
```
val/reward/ssim
val/reward/psnr
val/reward/lpips
```

应该能看到完整的统计指标曲线。

## 📝 注意事项

1. **有效样本数**: `ssim_valid_samples` 可能小于batch_size，因为只统计执行了工具的样本
2. **LPIPS方向**: LPIPS值越低越好（与SSIM/PSNR相反）
3. **需要GT**: 有参考指标只在有original_image且工具执行后才计算

---

**修复日期**: 2025-10-11
**状态**: ✅ 完成，无linter错误

