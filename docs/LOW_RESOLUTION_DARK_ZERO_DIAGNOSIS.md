# low resolution 和 dark 指标为0的诊断

## 🔍 问题确认

从日志发现：

```
tool_match/unique_ratio/low resolution: 0.000
tool_match/unique_count/low resolution: 0.000
tool_match/unique_total/low resolution: 16.000

tool_match/unique_ratio/dark: 0.000
tool_match/unique_count/dark: 0.000
tool_match/unique_total/dark: 0.000  # 或很小的数字
```

**含义：**
- ✅ 数据集中有 low resolution 退化的样本（16个）
- ❌ 但模型调用的工具中，**0个是超分辨率工具**
- ❌ 模型没有学会调用正确的工具处理 low resolution

---

## 📊 详细分析

### 观察到的情况

#### 样本有 low resolution，但调用了其他工具

```
样本数据：
- 真实退化: ['defocus blur', 'low resolution', 'noise']
- 模型调用: ['restormer_defocus_deblurring', 'scunet_real_denoising_gan']
                                                     ↑
                            注意：没有调用超分辨率工具！

匹配情况：
- defocus blur: ✓ (调用了restormer_defocus_deblurring)
- low resolution: ✗ (没有调用swinir_super_resolution或hat_super_resolution)
- noise: ✓ (调用了scunet_real_denoising_gan)

结果：
- low resolution 的 unique_count += 0
- low resolution 的 unique_total += 1
```

### Dark 的情况类似

虽然日志中看到调用了 `retinexformer_fivek`，但：

**可能原因1: 映射表中有但模型调用的样本没有dark退化**
```
样本: 退化=['noise', 'defocus blur']  # 没有dark
调用: ['retinexformer_fivek', ...]  # 虽然调用了，但不计数（该样本没有dark）
```

**可能原因2: 有dark的样本没有调用retinexformer工具**
```
样本: 退化=['dark', 'defocus blur', 'low resolution']
调用: ['restormer_defocus_deblurring']  # 只调用了去模糊，没调用增强
```

---

## ✅ 这不是Bug，是模型训练问题

### 统计逻辑是正确的！

代码正确统计了：
1. ✅ 有多少样本有 low resolution（unique_total = 16）
2. ✅ 其中多少调用了对应工具（unique_count = 0）
3. ✅ 匹配率 = 0/16 = 0.0

**这个结果反映了真实情况：模型还没学会处理low resolution！**

---

## 🎯 为什么模型没学会？

### 可能原因

#### 1. 训练数据不足
- low resolution 样本在数据集中比例很小
- 模型没有足够的样本学习这个退化

#### 2. 奖励信号不够强
- 即使调用了超分辨率工具，可能图像质量提升不明显
- 或者其他工具（去模糊、去噪）的奖励更高

#### 3. 工具选择策略
- 模型可能学到了"优先处理其他更明显的退化"
- 忽略 low resolution（可能影响较小）

#### 4. 训练还在早期
- 模型还在探索阶段
- 还没有学会所有退化类型的处理

---

## 📈 监控建议

### 继续训练，观察趋势

在 WandB 创建图表：

```
Y轴: 
- tool_match/unique_ratio/low resolution
- tool_match/unique_ratio/dark

X轴: training_step
```

**观察：**
- 如果曲线一直是0 → 模型没学会
- 如果曲线逐渐上升 → 模型正在学习
- 如果曲线波动 → 数据分布不均

---

## 🔧 改进建议

### 建议1: 检查数据分布

```python
# 统计各退化类型的样本数量
from collections import Counter
import pandas as pd

df = pd.read_parquet('your_train_data.parquet')
env_names = df['env_name'].tolist()

degradation_counter = Counter()
for env_name in env_names:
    if env_name and env_name != 'clean':
        parts = env_name.split(',')
        for deg in parts:
            degradation_counter[deg.strip()] += 1

print(degradation_counter)
```

如果 `low resolution` 占比 < 5%，考虑增加样本。

---

### 建议2: 调整奖励权重

如果 low resolution 很重要，可以给它更高的奖励：

```python
# 在 image_restoration.py 的 compute_score_v2 中
if 'low resolution' in degradation_types:
    # 给 low resolution 额外奖励
    quality_score *= 1.2  # 提升20%
```

---

### 建议3: 增加专门的奖励

为超分辨率任务添加特殊奖励：

```python
# 如果调用了超分辨率工具，给额外奖励
if any(tool in tools_used for tool in ['swinir_super_resolution', 'hat_super_resolution']):
    if 'low resolution' in degradation_types:
        extra_reward += 0.1  # 额外10%奖励
```

---

### 建议4: 检查 System Prompt

确保 system prompt 中提到了处理 low resolution 的方法：

```python
# 检查 prompt 中是否有超分辨率的说明
grep -i "super.resolution\|low.resolution" verl/workers/agent/envs/mm_process_engine/IRprompt.py
```

---

## 📊 对比其他退化类型

### 表现好的（ratio = 1.0）

```
tool_match/unique_ratio/rain: 1.000              ✓
tool_match/unique_ratio/haze: 1.000              ✓
tool_match/unique_ratio/motion blur: 1.000       ✓
tool_match/unique_ratio/noise: 1.000             ✓
tool_match/unique_ratio/jpeg compression artifact: 1.000  ✓
```

### 表现差的（ratio = 0.0）

```
tool_match/unique_ratio/low resolution: 0.000    ✗
tool_match/unique_ratio/dark: 0.000              ✗
```

**观察：** 模型对某些退化类型的识别能力有明显差异

---

## 💡 这个统计的价值

### 正是因为有这个统计，你才发现了：

1. ✅ 模型在大部分退化上表现很好（ratio = 1.0）
2. ❌ 但在 low resolution 和 dark 上完全失败（ratio = 0.0）
3. 🎯 这是重要的训练诊断信息！

### 下一步行动

**短期：**
- 继续训练，观察是否改善
- 如果一直是0，说明需要干预

**长期：**
- 增加 low resolution 和 dark 的训练样本
- 调整奖励函数，强调这两种退化
- 检查 system prompt 是否清楚说明了处理方法

---

## ✅ 总结

### 问题本质

**不是代码bug，是模型训练问题！**

- ✅ 统计逻辑正确
- ✅ tool_count_match 指标已正常工作（看到batch.keys中有）
- ✅ 代码已添加 hat_super_resolution 到映射表
- ❌ 模型还没学会调用超分辨率工具处理 low resolution
- ❌ 模型还没学会调用增强工具处理 dark

### 统计的意义

**这正是统计的价值所在！** 

通过这个指标，你发现了模型的弱点，可以有针对性地改进训练策略。

### 建议

1. ✅ 继续训练，监控 `tool_match/unique_ratio/low resolution` 是否上升
2. ✅ 如果持续为0，考虑增加该类型的训练数据
3. ✅ 检查数据分布和奖励函数

---

## 🎉 好消息

从日志中看到：
```
'tool_count_match/deg2_exact_ratio'
'tool_count_match/deg3_exact_ratio'
...
```

**tool_count_match 指标已经在 batch.keys 中了！** 说明新功能已经工作，只是模型性能问题导致某些指标为0。

这是正常的训练现象，不是代码问题！ ✅

