# 有参考指标计算说明

## 🎯 为什么单独计算有参考指标

### 问题背景

**之前的错误实现**:
```python
# 在reward function中计算并返回
res['ssim_score_ref'] = 0.923 或 None
# → 添加到 reward_extra_infos_dict
# → process_validation_metrics 尝试计算 np.mean([0.923, None, ...])
# → TypeError: unsupported operand type(s) for +: 'NoneType' and 'NoneType'
```

### 根本原因

1. **有参考指标只对工具执行的样本有意义**
   - 工具执行（37个样本）: 有复原图 → 可以计算PSNR/SSIM/LPIPS
   - 工具未执行（63个样本）: 没有复原图 → 无法计算

2. **reward_extra_infos_dict会被process_validation_metrics统计**
   - 计算mean, std, max, min等
   - 需要所有值都是数值
   - None会导致np.mean()失败

3. **有参考指标不是训练目标**
   - 训练使用无参考指标（灵活，不需要GT）
   - 有参考指标只用于wandb展示和分析
   - 不需要参与validation metrics统计

## ✅ 正确的实现

### 数据流分离

```
奖励计算流程（reward function）:
  ↓ 计算无参考指标
  ↓ 返回到 reward_extra_infos_dict
  ↓ process_validation_metrics 统计
  ↓ 用于训练优化

Wandb展示流程（logging时）:
  ↓ 从 batch_data 直接计算有参考指标
  ↓ 只用于 detailed_metrics
  ↓ 不加入 reward_extra_infos_dict
  ↓ 只用于wandb可视化
```

### 计算逻辑

**在wandb logging前调用** (`ray_trainer.py` 第1238-1244行):
```python
# 从reward_extra_infos_dict提取无参考指标
detailed_metrics = {
    'niqe_score': [...],  # 来自reward计算
    'brisque_score': [...],
    ...
}

# 额外计算有参考指标（只用于wandb）
ref_metrics = _compute_reference_metrics_for_batch(
    batch_data=batch_data,  # 包含original_images和image_history
    reward_extra_infos_dict=reward_extra_infos_dict
)
# 返回: {'ssim_score_ref': [0.923, 0.0, ...], ...}

detailed_metrics.update(ref_metrics)
```

### 为什么设为0.0而不是None

**选择0.0**:
- ✓ np.mean可以正常计算
- ✓ 在wandb中显示为0（清楚表示"无效"）
- ✓ 不会导致TypeError

**不用None**:
- ✗ np.mean([None, ...])会失败
- ✗ 即使不进入reward_extra_infos_dict，后续处理也可能有问题

## 📊 数据结构

### reward_extra_infos_dict（用于统计）
```python
{
    # 无参考指标（所有样本，100个值）
    'niqe_score': [5.71, 12.5, ...],
    'brisque_score': [43.31, ...],
    'score': [0.856, 0.300, ...],
    
    # 不包含有参考指标！
}
```

### detailed_metrics（用于wandb）
```python
{
    # 从reward_extra_infos_dict复制的无参考指标
    'niqe_score': [5.71, 12.5, ...],
    'brisque_score': [43.31, ...],
    
    # 额外计算的有参考指标（100个值，工具未执行的为0.0）
    'ssim_score_ref': [0.923, 0.0, 0.812, 0.0, ...],  # 37个真实值 + 63个0.0
    'lpips_score_ref': [0.145, 0.0, 0.234, 0.0, ...],
    'psnr_score_ref': [28.4, 0.0, 24.1, 0.0, ...],
}
```

## 🎯 计算内容

**在`compute_reference_metrics_for_batch`中**:

```python
# 对每个样本
for idx in range(num_samples):
    if img_hist[idx] 长度 < 2:
        # 工具未执行，设为0.0
        ssim_scores[idx] = 0.0
        continue
    
    # 工具已执行，计算真实值
    original = extract_image(original_images[idx])  # GT
    restored = extract_image(img_hist[idx][-1])     # 复原图
    
    # 直接调用metrics_calculator
    metrics = metrics_calculator.calculate_all_metrics(restored, original)
    
    ssim_scores[idx] = metrics['ssim']  # 如 0.923
    lpips_scores[idx] = metrics['lpips']  # 如 0.145
    psnr_scores[idx] = metrics['psnr']  # 如 28.4
```

**不需要np.mean**，因为：
- 每个样本计算一个SSIM/LPIPS/PSNR值
- 直接保存到列表中
- 只是数值提取，不做统计

**np.mean是在validation metrics中计算的**:
- 那是对reward_extra_infos_dict中的字段做统计
- 有参考指标不在那里，所以不会被统计
- 只用于wandb展示

## ✅ 总结

- ✓ 有参考指标**不进入** reward_extra_infos_dict
- ✓ 只在wandb logging时计算
- ✓ 工具未执行设为0.0（不影响统计）
- ✓ 单独的数据流，不干扰训练

完全正确的实现！🎯

