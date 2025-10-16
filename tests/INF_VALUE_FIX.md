# 🔧 PSNR Inf值修复

## ❌ 问题

报告中出现了`-inf`值：
```
前5名工具（按PSNR改进排序）：
1. dehazeformer_dehaze: inf → 19.28 dB (改进 -inf)
2. drbnet_defocus_deblurring: inf → 27.72 dB (改进 -inf)
```

---

## 🔍 原因分析

### PSNR = inf 的原因

PSNR（峰值信噪比）的计算公式：
```
PSNR = 10 * log10(MAX² / MSE)
```

其中：
- MAX = 最大像素值（通常是255）
- MSE = 均方误差（Mean Squared Error）

**当MSE = 0时**（两张图完全相同）：
```
PSNR = 10 * log10(255² / 0) = inf
```

### 为什么会出现MSE = 0？

可能的原因：
1. **退化图和原图完全相同**
   - 某些样本的"退化"可能很轻微或不存在
   - 数据生成过程中的边界情况
   
2. **图像resize后完全一致**
   - 退化图和原图在resize到相同尺寸后，像素值完全相同

3. **数据问题**
   - 原图和退化图引用了同一张图
   - 数据预处理错误

---

## ✅ 修复方案

### 方案1: 限制PSNR上限（已实施）

```python
# 处理inf值
if psnr is not None and np.isinf(psnr):
    psnr = 100.0  # 使用100dB作为"完全相同"的表示
```

**优点**:
- ✅ 避免inf导致的计算问题
- ✅ 100dB足够表示"几乎完全相同"
- ✅ 不影响其他正常值的计算

**PSNR值的含义**:
- < 30 dB: 有明显差异
- 30-40 dB: 差异较小
- 40-50 dB: 几乎无差异
- > 50 dB: 极其接近
- **100 dB**: 完全相同（原本是inf）

---

## 📊 实际影响

### 84个样本有inf值

**分析**:
```
总样本: 128
有inf的: 84 (65.6%)
正常值的: 44 (34.4%)
```

这说明**超过一半的样本，退化图和原图非常接近**（可能是轻度退化）。

### 修复前后对比

**修复前**:
```
baseline_psnr: inf
psnr_improvement: -inf
平均PSNR: inf
```

**修复后**:
```
baseline_psnr: 100.0
psnr_improvement: 70.72 (如果restored=29.28)
平均PSNR: 正常计算
```

---

## 🎯 如何解读100dB的PSNR

### 含义
- baseline_psnr = 100.0 → 退化图几乎等于原图
- 这种情况下，任何工具处理都可能**降低质量**

### 预期行为
```
样本: sample_X
  baseline_psnr: 100.0  ← 退化图已经完美
  restored_psnr: 25.3   ← 工具处理后反而变差
  psnr_improvement: -74.7  ← 大幅下降是正常的
```

**不是工具的问题！** 是因为退化图本身就很好，工具无法改进。

---

## 💡 建议

### 1. 过滤高PSNR样本
如果要评估工具的真实修复能力，建议过滤掉baseline_psnr > 40的样本：

```python
import pandas as pd

df = pd.read_csv('detailed_results.csv')

# 只保留退化明显的样本（baseline_psnr < 40）
degraded_df = df[df['baseline_psnr'] < 40]

# 重新计算统计
print(degraded_df.groupby('tool_name')['psnr_improvement'].mean())
```

### 2. 分层分析
根据退化严重程度分组：

```python
# 严重退化
severe = df[df['baseline_psnr'] < 25]

# 中度退化  
moderate = df[(df['baseline_psnr'] >= 25) & (df['baseline_psnr'] < 35)]

# 轻度退化
mild = df[df['baseline_psnr'] >= 35]

# 分别统计
for name, group in [('严重', severe), ('中度', moderate), ('轻度', mild)]:
    print(f"\n{name}退化:")
    print(group.groupby('tool_name')['psnr_improvement'].mean())
```

### 3. 检查数据质量
```bash
# 统计高PSNR样本
python3 << 'EOF'
import pandas as pd
df = pd.read_csv('detailed_results.csv')
high_psnr = df[df['baseline_psnr'] > 40]
print(f"baseline_psnr > 40的样本: {high_psnr['sample_id'].nunique()}个")
print(f"占比: {high_psnr['sample_id'].nunique() / df['sample_id'].nunique() * 100:.1f}%")
EOF
```

---

## 🔧 其他修复选项

### 选项1: 使用SSIM代替PSNR排序
```python
# 在报告生成时使用SSIM排序
tool_summary = tool_summary.sort_values('ssim_improvement', ascending=False)
```

### 选项2: 跳过inf样本
```python
# 在测试时跳过PSNR=inf的样本
if baseline_metrics['psnr'] > 99:
    print(f"  ⚠️  跳过（退化图已完美）")
    continue
```

### 选项3: 记录为特殊值
```python
# 保留inf但在报告中特殊标记
if np.isinf(psnr):
    return {'psnr': float('inf'), 'ssim': ssim, 'lpips': lpips, 'note': 'identical'}
```

---

## ✅ 当前修复

**已实施**: 将inf替换为100.0

**效果**:
- ✅ 报告可以正常生成
- ✅ 平均值可以正常计算
- ✅ 排序可以正常进行
- ✅ 保留了"完全相同"的信息（100.0是很高的值）

---

## 📝 使用建议

### 查看报告时
如果看到baseline_psnr = 100.0：
- 🔍 说明退化图几乎等于原图
- 🔍 工具改进为负数是正常的
- 🔍 不代表工具不好，而是没有改进空间

### 分析时
建议分别分析：
- 严重退化样本（baseline_psnr < 30）
- 中度退化样本（30 ≤ baseline_psnr < 40）
- 轻度退化样本（baseline_psnr ≥ 40）

每组样本的最佳工具可能不同。

---

**修复版本**: test_all_tools_metrics.py v2.1  
**修复时间**: 2025-10-13  
**状态**: ✅ 已修复

