# 统计报告指南

## 📊 生成的统计文件

测试完成后，会在 `results/` 目录生成以下统计文件：

```
results/
├── results_<timestamp>.json           # 详细结果数据（所有样本）
├── summary_<timestamp>.txt            # 总体统计摘要 ⭐
├── detailed_stats_<timestamp>.txt     # 按退化类型的详细统计 ⭐ 新增
├── statistics_<timestamp>.csv         # CSV格式统计（便于分析）⭐ 新增
└── by_degradation_<timestamp>.csv     # 按退化类型分组的CSV ⭐ 新增
```

## 📋 summary_<timestamp>.txt - 总体统计摘要

### 内容包括

对于每种策略（random/reverse），提供：

#### 1. 平均指标（Mean）

```
Average Degraded Metrics:
  PSNR: 27.4595 (±2.3456)    # 平均值 (±标准差)
  SSIM: 0.7768 (±0.0523)
  LPIPS: 0.3501 (±0.0892)

Average Restored Metrics:
  PSNR: 26.9817 (±2.1234)
  SSIM: 0.8098 (±0.0456)
  LPIPS: 0.3055 (±0.0734)

Average Improvements:
  PSNR: -0.4778 (±1.2345)    # 平均改善 (±标准差)
  SSIM: +0.0330 (±0.0234)
  LPIPS: +0.0446 (±0.0345)
```

#### 2. 中位数（Median）

```
Median Improvements:
  PSNR: +0.2334              # 中位数改善
  SSIM: +0.0289
  LPIPS: +0.0412
```

**用途：** 中位数不受极端值影响，更能反映典型表现

#### 3. 最佳/最差改善

```
Best Improvements:
  PSNR: +5.6789              # 最好的样本改善
  SSIM: +0.1234
  LPIPS: +0.2345

Worst Improvements:
  PSNR: -3.4567              # 最差的样本改善
  SSIM: -0.0234
  LPIPS: -0.0567
```

**用途：** 了解极端情况

#### 4. 工具成功率

```
Tool Success Rate: 95.5% (42/44 steps)
```

**说明：** 有多少工具调用成功执行

## 📈 detailed_stats_<timestamp>.txt - 按退化类型的详细统计

### 内容结构

```
DETAILED STATISTICS BY DEGRADATION TYPE
================================================================================

Total Unique Degradation Types: 5
Types: ['jpeg compression artifact', 'low resolution', 'motion blur', 'noise', 'rain']

--------------------------------------------------------------------------------
Degradation Type: jpeg compression artifact
--------------------------------------------------------------------------------
Samples containing this degradation: 8

  RANDOM strategy (8 samples):
    Average improvements:
      PSNR: +2.3456
      SSIM: +0.0456
      LPIPS: +0.0567

  REVERSE strategy (8 samples):
    Average improvements:
      PSNR: +2.5678
      SSIM: +0.0489
      LPIPS: +0.0623

--------------------------------------------------------------------------------
Degradation Type: motion blur
--------------------------------------------------------------------------------
...

================================================================================
STRATEGY COMPARISON
================================================================================

RANDOM vs REVERSE:
--------------------------------------------------------------------------------

PSNR:
  random: +1.2345
  reverse: +1.5678
  Difference: +0.3333
  Better: reverse

SSIM:
  random: +0.0456
  reverse: +0.0523
  Difference: +0.0067
  Better: reverse

LPIPS:
  random: +0.0678
  reverse: +0.0734
  Difference: +0.0056
  Better: reverse
```

**用途：**
- 了解每种退化类型的修复效果
- 比较不同策略在特定退化上的表现
- 发现哪些退化类型容易修复，哪些困难

## 📊 statistics_<timestamp>.csv - CSV统计表

### 格式

```csv
strategy,metric,mean,std,median,min,max,samples
random,psnr,1.234567,0.567890,1.123456,-2.345678,5.678901,10
random,ssim,0.045678,0.012345,0.043210,-0.023456,0.123456,10
random,lpips,0.067890,0.023456,0.065432,-0.045678,0.234567,10
reverse,psnr,1.456789,0.654321,1.345678,-1.234567,6.789012,10
reverse,ssim,0.052345,0.013456,0.051234,-0.012345,0.134567,10
reverse,lpips,0.078901,0.024567,0.076543,-0.034567,0.245678,10
```

### 使用pandas分析

```python
import pandas as pd

# 读取CSV
df = pd.read_csv('results/statistics_20251015_123456.csv')

# 查看random策略的统计
random_stats = df[df['strategy'] == 'random']
print(random_stats)

# 比较两种策略
pivot = df.pivot_table(index='metric', columns='strategy', values='mean')
print(pivot)

# 绘图
import matplotlib.pyplot as plt
pivot.plot(kind='bar')
plt.title('Strategy Comparison')
plt.ylabel('Mean Improvement')
plt.show()
```

## 📉 by_degradation_<timestamp>.csv - 按退化类型分组

### 格式

```csv
degradation_type,strategy,metric,mean_improvement,sample_count
jpeg compression artifact,random,psnr,2.345678,8
jpeg compression artifact,random,ssim,0.045678,8
jpeg compression artifact,random,lpips,0.056789,8
jpeg compression artifact,reverse,psnr,2.567890,8
jpeg compression artifact,reverse,ssim,0.048901,8
jpeg compression artifact,reverse,lpips,0.062345,8
motion blur,random,psnr,1.234567,6
...
```

### 使用pandas分析

```python
import pandas as pd

# 读取CSV
df = pd.read_csv('results/by_degradation_20251015_123456.csv')

# 查看特定退化类型的表现
motion_blur = df[df['degradation_type'] == 'motion blur']
print(motion_blur)

# 比较哪种退化类型最难修复
degradation_avg = df.groupby('degradation_type')['mean_improvement'].mean()
print(degradation_avg.sort_values())

# 对比不同策略在各退化类型上的表现
pivot = df.pivot_table(
    index='degradation_type', 
    columns='strategy', 
    values='mean_improvement',
    aggfunc='mean'
)
print(pivot)
```

## 📊 完整的统计指标说明

### 1. Mean（平均值）

**含义：** 所有样本改善的算术平均  
**用途：** 反映总体趋势  
**注意：** 会受极端值影响

### 2. Std（标准差）

**含义：** 改善值的离散程度  
**用途：** 
- 标准差大 → 结果不稳定，有些样本改善很多，有些很少
- 标准差小 → 结果稳定，所有样本改善程度接近

### 3. Median（中位数）

**含义：** 排序后位于中间的改善值  
**用途：** 
- 不受极端值影响
- 反映"典型"样本的表现
- 如果median > mean，说明有少数样本拖后腿

### 4. Min/Max（最小/最大）

**含义：** 最差和最好的改善  
**用途：**
- 了解极端情况
- Min为负表示有样本变差了
- Max显示最佳可能效果

### 5. Success Rate（成功率）

**含义：** 工具调用成功的比例  
**用途：**
- 100% → 所有工具都正常工作
- <100% → 有些工具调用失败
- 低成功率需要检查工具服务

## 📖 统计报告使用示例

### 示例1: 查看总体表现

```bash
# 运行测试
./run_baseline_test.sh --num-samples 20 --strategy both

# 查看摘要
cat results/summary_*.txt
```

**输出解读：**
```
RANDOM Strategy:
  Average Improvements:
    PSNR: +2.34 (±1.23)  # 平均提升2.34 dB，但波动较大
    SSIM: +0.05 (±0.02)  # 平均提升0.05，比较稳定
    LPIPS: +0.06 (±0.03) # 平均降低0.06（越小越好）

  Median Improvements:
    PSNR: +2.56          # 中位数高于均值，说明少数样本拖后腿
    
  Best/Worst:
    PSNR: +5.67 / -1.23  # 最好提升5.67，最差降低1.23
```

### 示例2: 分析特定退化类型

```bash
# 查看按退化类型的统计
cat results/detailed_stats_*.txt | grep -A 10 "motion blur"
```

**输出：**
```
Degradation Type: motion blur
Samples: 12

  RANDOM strategy:
    PSNR: +3.45
    SSIM: +0.06
    LPIPS: +0.08

  REVERSE strategy:
    PSNR: +3.78
    SSIM: +0.07
    LPIPS: +0.09
```

**结论：** motion blur在reverse策略下修复效果更好

### 示例3: 使用CSV进行深入分析

```python
import pandas as pd
import matplotlib.pyplot as plt

# 读取统计数据
stats = pd.read_csv('results/statistics_20251015_123456.csv')

# 创建对比图
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
metrics = ['psnr', 'ssim', 'lpips']

for i, metric in enumerate(metrics):
    data = stats[stats['metric'] == metric]
    
    # 绘制柱状图
    strategies = data['strategy'].values
    means = data['mean'].values
    stds = data['std'].values
    
    axes[i].bar(strategies, means, yerr=stds, capsize=5)
    axes[i].set_title(f'{metric.upper()} Improvements')
    axes[i].set_ylabel('Improvement')
    axes[i].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('results/comparison.png')
print("Saved comparison plot!")
```

### 示例4: 找出最需要改进的退化类型

```python
import pandas as pd

# 读取按退化类型的统计
df = pd.read_csv('results/by_degradation_20251015_123456.csv')

# 计算每种退化的平均改善（跨所有策略和指标）
degradation_perf = df.groupby('degradation_type')['mean_improvement'].mean()

# 排序（找出表现最差的）
worst = degradation_perf.sort_values()
print("需要重点改进的退化类型：")
print(worst.head(3))

# 排序（找出表现最好的）
best = degradation_perf.sort_values(ascending=False)
print("\n修复效果最好的退化类型：")
print(best.head(3))
```

## 🎯 关键统计指标解读

### 成功的修复应该满足：

✅ **平均改善为正**
```
PSNR: +2.00 以上（显著改善）
SSIM: +0.05 以上（明显改善）
LPIPS: +0.05 以上（感知提升）
```

✅ **标准差适中**
```
过小 → 所有样本表现相似（好）
过大 → 结果不稳定（需要调查）
```

✅ **中位数接近平均值**
```
median ≈ mean → 分布对称
median > mean → 有少数极差样本
median < mean → 有少数极好样本
```

✅ **最差改善不要太负**
```
Min > -1.0 → 可接受
Min < -3.0 → 有严重恶化的样本，需要检查
```

✅ **成功率高**
```
>95% → 工具很稳定
<90% → 需要检查工具服务
```

## 📈 策略对比分析

### 对比指标

测试报告会自动比较两种策略：

```
STRATEGY COMPARISON SUMMARY
================================================================================

RANDOM vs REVERSE:
  PSNR: random=+1.2345, reverse=+1.5678, diff=+0.3333 → reverse wins
  SSIM: random=+0.0456, reverse=+0.0523, diff=+0.0067 → reverse wins
  LPIPS: random=+0.0678, reverse=+0.0734, diff=+0.0056 → reverse wins
```

**解读：**
- `diff > 0.5` (PSNR) → 策略差异显著
- `diff > 0.01` (SSIM/LPIPS) → 策略差异明显
- `diff < 0.01` → 策略差异不大

### 统计显著性

对于大样本（>20个）：
```python
from scipy import stats

# t检验判断差异是否显著
random_psnr = [r['improvements']['psnr'] for r in random_results]
reverse_psnr = [r['improvements']['psnr'] for r in reverse_results]

t_stat, p_value = stats.ttest_ind(random_psnr, reverse_psnr)

if p_value < 0.05:
    print("✅ 两种策略的差异统计显著")
else:
    print("⚠️  差异不显著，可能是偶然")
```

## 🔍 快速查看命令

```bash
# 查看总体摘要
cat results/summary_*.txt

# 查看详细统计
cat results/detailed_stats_*.txt

# 查看最新的CSV
ls -lt results/*.csv | head -1

# 使用pandas快速查看
python3 << 'EOF'
import pandas as pd
df = pd.read_csv('results/statistics_*.csv')
print(df)
EOF

# 比较两种策略
python3 << 'EOF'
import pandas as pd
df = pd.read_csv('results/statistics_*.csv')
pivot = df.pivot_table(index='metric', columns='strategy', values='mean')
print(pivot)
print("\n✅ 数值越大越好（除了LPIPS）")
EOF
```

## 📊 完整示例：分析测试结果

```python
#!/usr/bin/env python3
"""
分析baseline测试结果
"""
import pandas as pd
import numpy as np
import json

# 1. 读取所有数据
with open('results/results_20251015_123456.json') as f:
    results = json.load(f)

stats_df = pd.read_csv('results/statistics_20251015_123456.csv')
deg_df = pd.read_csv('results/by_degradation_20251015_123456.csv')

# 2. 总体表现
print("="*80)
print("总体表现")
print("="*80)
print(stats_df)

# 3. 策略对比
print("\n" + "="*80)
print("策略对比")
print("="*80)
pivot = stats_df.pivot_table(index='metric', columns='strategy', values='mean')
print(pivot)

# 计算哪个策略更好
better_count = 0
total_metrics = 0
for metric in ['psnr', 'ssim', 'lpips']:
    metric_data = stats_df[stats_df['metric'] == metric]
    random_val = metric_data[metric_data['strategy'] == 'random']['mean'].values[0]
    reverse_val = metric_data[metric_data['strategy'] == 'reverse']['mean'].values[0]
    
    total_metrics += 1
    if metric == 'lpips':
        if reverse_val < random_val:  # LPIPS越小越好
            better_count += 1
    else:
        if reverse_val > random_val:  # PSNR/SSIM越大越好
            better_count += 1

print(f"\nReverse策略在 {better_count}/{total_metrics} 个指标上更好")

# 4. 按退化类型分析
print("\n" + "="*80)
print("各退化类型的修复难度（按PSNR改善排序）")
print("="*80)
deg_psnr = deg_df[deg_df['metric'] == 'psnr'].groupby('degradation_type')['mean_improvement'].mean()
print(deg_psnr.sort_values(ascending=False))

# 5. 找出问题样本
print("\n" + "="*80)
print("需要关注的样本（改善为负）")
print("="*80)
problem_samples = [r for r in results if r['improvements']['psnr'] < 0]
print(f"发现 {len(problem_samples)} 个问题样本")
for r in problem_samples[:3]:
    print(f"  Sample {r['sample_idx']}: PSNR {r['improvements']['psnr']:.2f}, 退化类型: {r['degradation_types']}")
```

## 📋 统计指标参考值

### PSNR改善

| 改善程度 | 数值 | 评价 |
|---------|------|------|
| 优秀 | >+3.0 dB | 显著提升 |
| 良好 | +1.5 ~ +3.0 dB | 明显改善 |
| 一般 | +0.5 ~ +1.5 dB | 有所改善 |
| 较差 | 0 ~ +0.5 dB | 轻微改善 |
| 失败 | <0 dB | 变差了 |

### SSIM改善

| 改善程度 | 数值 | 评价 |
|---------|------|------|
| 优秀 | >+0.10 | 显著提升 |
| 良好 | +0.05 ~ +0.10 | 明显改善 |
| 一般 | +0.02 ~ +0.05 | 有所改善 |
| 较差 | 0 ~ +0.02 | 轻微改善 |
| 失败 | <0 | 变差了 |

### LPIPS改善（注意：越小越好）

| 改善程度 | 数值 | 评价 |
|---------|------|------|
| 优秀 | >+0.10 | 显著降低 |
| 良好 | +0.05 ~ +0.10 | 明显降低 |
| 一般 | +0.02 ~ +0.05 | 有所降低 |
| 较差 | 0 ~ +0.02 | 轻微降低 |
| 失败 | <0 | 升高了（变差） |

## 🎯 使用建议

1. **先看summary** - 了解总体表现
2. **看detailed_stats** - 了解每种退化的表现
3. **用CSV分析** - 深入数据挖掘
4. **关注标准差** - 评估稳定性
5. **比较策略** - 选择最佳方案

---

*所有统计文件会自动生成，无需手动配置*

