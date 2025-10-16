# 更新日志

## v1.1 (2024-10-15) - 增强统计功能 ✨

### 新增功能

#### 1. 更详细的总体统计 📊

**新增指标：**
- ✅ **标准差（Std）** - 评估结果稳定性
- ✅ **中位数（Median）** - 不受极端值影响的典型表现
- ✅ **最大值（Max）** - 最佳改善效果
- ✅ **最小值（Min）** - 最差情况
- ✅ **成功率（Success Rate）** - 工具调用成功比例

**输出示例：**
```
Average Improvements:
  PSNR: +2.34 (±1.23)      # 平均值 (±标准差)
  
Median Improvements:
  PSNR: +2.56              # 中位数

Best Improvements:
  PSNR: +5.67              # 最佳

Worst Improvements:
  PSNR: -1.23              # 最差
  
Tool Success Rate: 95.5% (42/44 steps)
```

#### 2. 按退化类型分组统计 📈

**新文件：** `detailed_stats_<timestamp>.txt`

**内容：**
- 每种退化类型的样本数量
- 每种退化类型在不同策略下的平均改善
- 哪些退化类型容易修复，哪些困难

**示例：**
```
Degradation Type: motion blur
Samples containing this degradation: 12

  RANDOM strategy (12 samples):
    Average improvements:
      PSNR: +3.45
      SSIM: +0.06
      LPIPS: +0.08

  REVERSE strategy (12 samples):
    Average improvements:
      PSNR: +3.78
      SSIM: +0.07
      LPIPS: +0.09
```

#### 3. CSV格式统计数据 📉

**新文件：**
- `statistics_<timestamp>.csv` - 总体统计
- `by_degradation_<timestamp>.csv` - 按退化类型分组

**用途：**
- 使用pandas/Excel进一步分析
- 绘制图表和可视化
- 数据挖掘和模式发现

**CSV格式：**
```csv
strategy,metric,mean,std,median,min,max,samples
random,psnr,1.234567,0.567890,1.123456,-2.345678,5.678901,10
random,ssim,0.045678,0.012345,0.043210,-0.023456,0.123456,10
...
```

#### 4. 策略对比摘要 🔄

**控制台输出和文件中都包含：**
```
STRATEGY COMPARISON SUMMARY
================================================================================

RANDOM vs REVERSE:
  PSNR: random=+1.2345, reverse=+1.5678, diff=+0.3333 → reverse wins
  SSIM: random=+0.0456, reverse=+0.0523, diff=+0.0067 → reverse wins
  LPIPS: random=+0.0678, reverse=+0.0734, diff=+0.0056 → reverse wins
```

**自动判断：** 哪个策略在哪个指标上更好

### Bug修复

#### 修复1: Random策略伪随机问题 🐛

**问题：** Random策略的shuffle结果总是逆序或相同

**原因：** 固定seed + 简单seed计算导致伪随机

**解决：** 使用哈希seed为每个样本生成独立随机序列
```python
import hashlib
seed_str = f"random_restoration_{sample_idx}_{len(degradations)}"
seed_value = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
sample_random = random.Random(seed_value)
sample_random.shuffle(degradations)
```

**效果：** 真正的多样化随机排列

## 对比 v1.0 vs v1.1

| 功能 | v1.0 | v1.1 |
|------|------|------|
| 基本统计（均值） | ✅ | ✅ |
| 标准差 | ❌ | ✅ 新增 |
| 中位数 | ❌ | ✅ 新增 |
| 最大/最小值 | ❌ | ✅ 新增 |
| 成功率统计 | ❌ | ✅ 新增 |
| 按退化类型统计 | ❌ | ✅ 新增 |
| CSV导出 | ❌ | ✅ 新增 |
| 策略对比 | ❌ | ✅ 新增 |
| Random真随机 | ❌ | ✅ 修复 |
| 代码行数 | 643行 | 951行 |

## 📦 新增文件

| 文件 | 说明 |
|------|------|
| `STATISTICS_GUIDE.md` | 统计报告使用指南 |
| `BUG_FIX_NOTES.md` | Bug修复说明 |
| `UPDATES.md` | 本文件 - 更新日志 |

## 📊 输出文件变化

### v1.0 输出

```
results/
├── results_<timestamp>.json
└── summary_<timestamp>.txt
```

### v1.1 输出

```
results/
├── results_<timestamp>.json              # 详细数据
├── summary_<timestamp>.txt               # 基本摘要
├── detailed_stats_<timestamp>.txt        # ✨ 新增：详细统计
├── statistics_<timestamp>.csv            # ✨ 新增：CSV统计
└── by_degradation_<timestamp>.csv        # ✨ 新增：分组CSV
```

## 🚀 使用新功能

### 1. 查看增强的统计

```bash
cd /app/xiaominl/DeepEyes_v2/tests/baseline

# 运行测试
./run_baseline_test.sh --num-samples 20 --strategy both

# 查看基本摘要（现在包含更多统计）
cat results/summary_*.txt

# 查看详细统计（按退化类型）
cat results/detailed_stats_*.txt

# 查看CSV（使用pandas）
python3 << 'EOF'
import pandas as pd
df = pd.read_csv('results/statistics_*.csv')
print(df)
EOF
```

### 2. 分析特定退化类型

```bash
# 查看motion blur的修复效果
grep -A 10 "motion blur" results/detailed_stats_*.txt
```

### 3. 导出数据到Excel

```bash
# CSV可以直接在Excel中打开
# 或使用pandas
python3 << 'EOF'
import pandas as pd

# 读取统计数据
stats = pd.read_csv('results/statistics_*.csv')
deg = pd.read_csv('results/by_degradation_*.csv')

# 导出到Excel
with pd.ExcelWriter('results/analysis.xlsx') as writer:
    stats.to_excel(writer, sheet_name='Overall Stats', index=False)
    deg.to_excel(writer, sheet_name='By Degradation', index=False)

print("✅ Exported to results/analysis.xlsx")
EOF
```

## 📖 相关文档

- `STATISTICS_GUIDE.md` - 详细的统计指标说明
- `BUG_FIX_NOTES.md` - Random策略bug修复说明
- `README.md` - 完整功能文档

## 🎯 后续计划

### v1.2 计划

- [ ] 添加置信区间
- [ ] 统计显著性检验（t-test）
- [ ] 自动生成可视化图表
- [ ] HTML格式的交互式报告
- [ ] 并行处理支持
- [ ] 进度条显示

---

**当前版本：** v1.1  
**代码行数：** 951行  
**功能完整度：** ⭐⭐⭐⭐⭐

