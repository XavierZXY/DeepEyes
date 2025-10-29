# low resolution 和 dark 为0 - 完整诊断报告

## 📊 问题确认

### WandB 显示

```
tool_match/unique_count/low resolution = 0  (total = 16)
tool_match/unique_count/dark = 0  (total = 0 或很小)
```

---

## 🔍 诊断结果

### 1. 数据集检查 ✅

```
数据集: /app/xiaominl/air_v15_dm3_update_tool/shards

统计结果:
- dark: 44-72个样本/shard (约10-14%)
- low resolution: 220-248个样本/shard (约43-48%，接近一半！)

示例:
- 'low resolution, motion blur, dark'
- 'jpeg compression artifact, noise, low resolution'
- 'defocus blur, dark'
```

**结论：数据集中有大量这两种退化！** ✅

---

### 2. 工具映射检查 ✅

#### parallel_env.py 中的映射表

```python
DEGRADATION_TO_TOOLS = {
    'low resolution': ['swinir_super_resolution', 'hat_super_resolution'],  ✅
    'dark': ['retinexformer_enhance', 'retinexformer_lol_v1', ..., 'retinexformer_fivek'],  ✅
}
```

#### image_restoration.py 中的格式检查

```python
ALLOWED_TOOLS = {
    "hat_super_resolution",  ✅ 已添加
    "retinexformer_enhance",  ✅
    "retinexformer_fivek",  ✅
    # ... 所有 retinexformer 系列
}
```

**结论：映射和格式检查都已正确配置！** ✅

---

### 3. 工具调用实际情况 ❌

#### 从日志分析（最新训练）

```bash
调用的工具列表（前30个样本）:
✓ restormer_motion_deblurring
✓ scunet_real_denoising_gan
✓ restormer_defocus_deblurring
✓ fbcnn_jpeg_artifact_removal
✓ dehazeformer_dehaze
✓ restormer_deraining
✓ retinexformer_fivek  ← 有调用（但可能不在有dark的样本中）

❌ 没有看到: hat_super_resolution
❌ 没有看到: swinir_super_resolution
```

**结论：模型确实没有调用超分辨率工具！** ❌

---

## 🎯 根本原因分析

### 问题核心

**模型还没有学会识别和处理 low resolution 退化！**

虽然数据集中有大量 low resolution 样本（~45%），但模型从不调用超分辨率工具。

### 可能的原因

#### 原因1: 格式检查曾经惩罚了HAT工具

**之前的情况：**
```
模型尝试调用: ['hat_super_resolution']
→ 格式检查: ❌ (不在 ALLOWED_TOOLS)
→ format_score = -1.0
→ 总奖励很低（甚至负数）
→ 模型学会了：调用HAT会被惩罚，不要调用！
```

**现在已修复：**
```python
ALLOWED_TOOLS = {
    "hat_super_resolution",  # ✅ 已添加
}
```

但模型需要**重新训练**才能"忘记"之前的惩罚经验。

---

#### 原因2: low resolution 的图像质量奖励信号弱

**假设：**
- 超分辨率处理比较困难
- 即使调用了工具，图像质量提升不明显
- 奖励信号弱，模型倾向于忽略

**验证方法：**
```bash
# 查看有low resolution样本的奖励分布
grep -B 5 "low resolution" logs/*.log | grep "quality_score"
```

**可能的解决方案：**
- 增加 low resolution 的奖励权重
- 使用更宽松的质量评估标准

---

#### 原因3: 训练策略问题

模型可能学到了：
- "只处理容易的退化（rain, haze, noise）"
- "忽略困难的退化（low resolution, dark）"
- 因为容易的退化奖励更高、更稳定

---

## 🔧 解决方案

### 立即行动：清理缓存并重新训练

```bash
# 1. 停止当前训练
pkill -f main_ppo

# 2. 清理缓存（重要！）
ray stop
find /app/xiaominl/DeepEyes_v2 -name "*.pyc" -delete
find /app/xiaominl/DeepEyes_v2 -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null

# 3. 重新训练
cd /app/xiaominl/DeepEyes_v2
bash examples/agent/IRv2.sh
```

**原因：** HAT工具的格式检查已修复，需要让模型重新学习

---

### 中期改进：调整训练策略

如果重新训练后还是0，考虑：

#### 方案1: 增加 low resolution 的奖励权重

修改 `image_restoration.py` 的 `compute_score_v2` 函数：

```python
# 在计算quality_score后
if 'low resolution' in degradation_types:
    quality_score *= 1.3  # 提升30%奖励
```

#### 方案2: 添加专门的工具选择奖励

```python
# 如果调用了超分辨率工具且有low resolution退化
if 'low resolution' in degradation_types:
    sr_tools = ['hat_super_resolution', 'swinir_super_resolution']
    if any(tool in predicted_tools for tool in sr_tools):
        extra_reward += 0.2  # 额外20%奖励
```

#### 方案3: 检查System Prompt

确保提示词中明确说明了如何处理 low resolution：

```bash
grep -i "low.resolution\|super.resolution" verl/workers/agent/envs/mm_process_engine/IRprompt.py
```

---

## 📈 监控指标

### 重新训练后观察

在 WandB 创建图表，监控这两个指标的变化：

```
Y轴: 
- tool_match/unique_ratio/low resolution
- tool_match/unique_ratio/dark

X轴: training_step
```

**预期趋势：**

#### 情况A: 格式修复生效
```
Step 0-100:   0.00 → 0.00  (旧经验影响)
Step 100-500: 0.00 → 0.30  (开始探索)
Step 500+:    0.30 → 0.80  (逐步学习)
```

#### 情况B: 还需要干预
```
Step 0-1000: 0.00 → 0.05  (几乎不变)
→ 需要调整奖励或增加数据
```

---

## 🎯 关键数据

### 当前batch的统计（从日志）

```
Step 69:
- low resolution total: 16个样本
- low resolution matched: 0个
- ratio: 0.000

- dark total: 0个样本（这个batch恰好没有）
- dark matched: 0个
```

### 数据集总体分布

```
每个shard (512样本):
- dark: ~50-70个 (10-14%)
- low resolution: ~220-248个 (43-48%)

7个训练shards:
- dark: ~350-490个
- low resolution: ~1540-1736个
```

**low resolution 占比接近一半，数据非常充足！**

---

## ✅ 总结

### 问题定位

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 数据集有这两种退化 | ✅ | dark ~10%, low resolution ~45% |
| 工具映射配置正确 | ✅ | 已包含HAT和retinexformer系列 |
| 格式检查允许工具 | ✅ | 刚修复，已添加HAT |
| 统计逻辑正确 | ✅ | 指标已上传到WandB |
| 模型调用对应工具 | ❌ | **模型没有学会调用！** |

### 根本原因

**模型训练问题，不是代码问题！**

可能之前HAT工具被格式检查惩罚，模型学会了不调用。

### 解决方案

1. **立即：** 清理缓存重新训练（应用格式修复）
2. **观察：** 监控指标是否从0上升
3. **调整：** 如果持续为0，增加这两种退化的奖励权重

---

## 🚀 下一步行动

```bash
# 清理并重启
ray stop
find /app/xiaominl/DeepEyes_v2 -name "*.pyc" -delete
bash /app/xiaominl/DeepEyes_v2/examples/agent/IRv2.sh

# 然后在WandB观察
# tool_match/unique_ratio/low resolution
# tool_match/unique_ratio/dark
```

应该会看到从0开始逐渐上升！🎯

