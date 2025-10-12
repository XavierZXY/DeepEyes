# 指标计算示例 - 各种情况详解

## 📊 三种典型场景

### 场景1: 处理成功 ✅ （最理想）

```
Degraded: SSIM=0.600, LPIPS=0.400, PSNR=20.0
Restored: SSIM=0.850, LPIPS=0.150, PSNR=28.0

计算过程：
  SSIM:  (0.850 - 0.600) / 0.600 * 100 = +41.7% ✅ 提升
  LPIPS: (0.400 - 0.150) / 0.400 * 100 = +62.5% ✅ 改善
  PSNR:  (28.0 - 20.0) / 20.0 * 100 = +40.0% ✅ 提升

表格显示：
  Improve_SSIM%: +41.7%
  Improve_LPIPS%: +62.5%
  Improve_PSNR%: +40.0%
```

### 场景2: 处理后变差 ❌ （问题样本）

```
Degraded: SSIM=0.800, LPIPS=0.200, PSNR=25.0
Restored: SSIM=0.600, LPIPS=0.400, PSNR=18.0

计算过程：
  SSIM:  (0.600 - 0.800) / 0.800 * 100 = -25.0% ❌ 降低了
  LPIPS: (0.200 - 0.400) / 0.200 * 100 = -100.0% ❌ 恶化了
  PSNR:  (18.0 - 25.0) / 25.0 * 100 = -28.0% ❌ 降低了

表格显示：
  Improve_SSIM%: -25.0%   ← 负值，很明显
  Improve_LPIPS%: -100.0% ← 负值，很明显
  Improve_PSNR%: -28.0%   ← 负值，很明显
```

**分析**：这种情况说明：
- 可能选错了工具
- 工具参数不对
- 图像本身质量就不错，不需要处理

### 场景3: 工具未执行 ⚠️ （无处理）

```
Degraded: SSIM=0.600, LPIPS=0.400, PSNR=20.0
Restored: SSIM=0.000, LPIPS=0.000, PSNR=0.0

计算过程：
  由于 len(image_history) < 2，不计算复原图指标
  所有 restored 值保持为 0.0
  所有 improvement 保持为 0.0

表格显示：
  Improve_SSIM%: 0.0%
  Improve_LPIPS%: 0.0%
  Improve_PSNR%: 0.0%
  Tool_Status: ⚠️ Requested but Failed
```

### 场景4: 轻微改善 ⚠️ （效果不明显）

```
Degraded: SSIM=0.700, LPIPS=0.300, PSNR=22.0
Restored: SSIM=0.720, LPIPS=0.280, PSNR=22.5

计算过程：
  SSIM:  (0.720 - 0.700) / 0.700 * 100 = +2.9% ⚠️ 轻微提升
  LPIPS: (0.300 - 0.280) / 0.300 * 100 = +6.7% ⚠️ 轻微改善
  PSNR:  (22.5 - 22.0) / 22.0 * 100 = +2.3% ⚠️ 轻微提升

表格显示：
  Improve_SSIM%: +2.9%   ← 效果不明显
  Improve_LPIPS%: +6.7%
  Improve_PSNR%: +2.3%
```

**分析**：这种情况说明工具执行了，但效果很弱。

### 场景5: 混合结果 🤔 （部分改善）

```
Degraded: SSIM=0.650, LPIPS=0.350, PSNR=21.0
Restored: SSIM=0.780, LPIPS=0.380, PSNR=24.0

计算过程：
  SSIM:  (0.780 - 0.650) / 0.650 * 100 = +20.0% ✅ 提升
  LPIPS: (0.350 - 0.380) / 0.350 * 100 = -8.6% ❌ 恶化了
  PSNR:  (24.0 - 21.0) / 21.0 * 100 = +14.3% ✅ 提升

表格显示：
  Improve_SSIM%: +20.0%   ← 提升
  Improve_LPIPS%: -8.6%   ← 恶化（注意负号）
  Improve_PSNR%: +14.3%   ← 提升
```

**分析**：SSIM和PSNR提升了，但LPIPS反而恶化了。这可能意味着：
- 结构相似度提高了
- 但感知质量下降了
- 需要检查是否过度处理

## 🎯 如何在Wandb中找到问题样本

### 查找处理后变差的样本

**方法1：按SSIM提升率排序**
```
1. 点击 "Improve_SSIM%" 列标题
2. 升序排序（最小值在前）
3. 负值样本会出现在最前面
```

**方法2：使用筛选器**
```
筛选条件：Improve_SSIM% < 0
结果：所有SSIM降低的样本
```

**方法3：组合筛选**
```
筛选条件：
  - Tool_Status = "✅ Success"  （工具成功执行了）
  - Improve_SSIM% < 0           （但SSIM反而降低了）

结果：找到"执行成功但效果变差"的问题样本
```

### 查找不同程度的改善

**大幅提升**（>30%）：
```
筛选：Improve_SSIM% > 30
结果：效果很好的样本
```

**轻微提升**（0-10%）：
```
筛选：Improve_SSIM% > 0 AND Improve_SSIM% < 10
结果：效果不明显的样本
```

**无变化**（=0%）：
```
筛选：Improve_SSIM% = 0
结果：工具未执行或计算失败的样本
```

**降低**（<0%）：
```
筛选：Improve_SSIM% < 0
结果：处理后反而变差的样本
```

## 📊 代码实现验证

### 格式化输出确保显示负号

```python
# tracking_image_utils.py 第1472行
print(f"  Improvement: SSIM={impr_ssim:+.1f}%, LPIPS={impr_lpips:+.1f}%, PSNR={impr_psnr:+.1f}%")
```

`:+.1f` 格式说明：
- `+` 强制显示正负号
- `.1f` 保留1位小数
- `%` 百分号

输出示例：
```
Improvement: SSIM=+35.1%, LPIPS=+60.7%, PSNR=+37.7%  ← 全部提升
Improvement: SSIM=-25.0%, LPIPS=-100.0%, PSNR=-28.0% ← 全部降低
Improvement: SSIM=+20.0%, LPIPS=-8.6%, PSNR=+14.3%   ← 混合情况
```

### 表格显示验证

wandb.Table会原样显示数值：
- 正数显示为正（可能带+号，取决于wandb）
- **负数一定显示负号** ✅
- 零显示为 0.0

## 🔍 实际调试日志示例

```bash
[DEBUG DEGRADED METRICS] Sample 5:
  Degraded: SSIM=0.8123, LPIPS=0.2341, PSNR=24.56
  Restored: SSIM=0.6234, LPIPS=0.4521, PSNR=18.23
  Improvement: SSIM=-23.3%, LPIPS=-93.1%, PSNR=-25.8%
                     ↑ 负值      ↑ 负值      ↑ 负值

[DEBUG CONV TABLE] First row data (if idx=5):
  Degraded: SSIM=0.8123, LPIPS=0.2341, PSNR=24.56
  Restored: SSIM=0.6234, LPIPS=0.4521, PSNR=18.23
  Improvement: SSIM=-23.3%, LPIPS=-93.1%, PSNR=-25.8%
```

## ✅ 总结

### 所有情况都能正确显示

| 情况 | Improvement值 | 表格显示 | 说明 |
|-----|--------------|---------|------|
| 大幅提升 | +30% ~ +100% | +30.0% ~ +100.0% | ✅ 非常好 |
| 轻微提升 | +1% ~ +10% | +1.0% ~ +10.0% | ⚠️ 效果弱 |
| 无变化 | 0% | 0.0% | ⚠️ 未处理 |
| 轻微降低 | -1% ~ -10% | -1.0% ~ -10.0% | ❌ 略差 |
| 大幅降低 | -20% ~ -100% | -20.0% ~ -100.0% | ❌ 很差 |

### 关键点

1. ✅ **负值会自动计算**：公式本身就支持
2. ✅ **负号会显示**：`:+.1f` 格式强制显示
3. ✅ **易于筛选**：可以用 `< 0` 筛选出所有降低的样本
4. ✅ **日志清晰**：调试日志也会显示负值

所以您完全不用担心，**降低的情况会清晰地显示为负值**！🎯

