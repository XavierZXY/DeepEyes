# ⚠️ 数据质量检查报告

**数据集**: air_d1_sp9_up2_balanced/shard-test-000000.parquet  
**检查时间**: 2025-10-13  
**总样本**: 128

---

## 🔴 严重问题：Haze退化未生效

### 发现的问题
**所有17个haze样本的退化图和原图完全相同！**

```
退化类型: haze
样本数: 17
平均像素差异: 0.00 (范围: 0.00 - 0.00)
判断: ⚠️  几乎无退化（像素级完全相同）
```

### 检查结果
```
样本 1 (haze, high级别):
  平均像素差: 0.00
  完全相同像素: 100.0%
  RGB差异: [0.0, 0.0, 0.0]
  
样本 2 (haze, low级别):
  平均像素差: 0.00
  完全相同像素: 100.0%
  RGB差异: [0.0, 0.0, 0.0]

样本 3 (haze, low级别):
  平均像素差: 0.00
  完全相同像素: 100.0%
  RGB差异: [0.0, 0.0, 0.0]
```

**结论**: 退化图和原图是**完全相同的图片**，没有添加任何雾霾效果！

---

## 📊 所有退化类型的质量分析

按平均像素差异排序（0-255范围）：

| 退化类型 | 样本数 | 平均像素差 | 范围 | 状态 |
|---------|--------|-----------|------|------|
| 🔴 **haze** | 17 | **0.00** | 0.00 - 0.00 | ⚠️ **完全无退化** |
| 🟡 jpeg compression artifact | 16 | 6.48 | 3.81 - 10.72 | ✅ 有一定退化 |
| 🟡 low resolution | 13 | 6.90 | 2.64 - 12.27 | ✅ 有一定退化 |
| 🟡 rain | 18 | 7.05 | 0.54 - 13.13 | ✅ 有一定退化 |
| 🟡 defocus blur | 13 | 7.86 | 3.01 - 14.08 | ✅ 有一定退化 |
| 🟡 motion blur | 20 | 10.15 | 1.76 - 19.37 | ✅ 有一定退化 |
| 🟡 noise | 10 | 16.07 | 4.42 - 29.29 | ✅ 有一定退化 |
| 🟢 dark | 21 | 32.26 | 7.67 - 75.82 | ✅ 退化明显 |

### 像素差异解读
- **< 1.0**: 退化图和原图几乎相同（数据问题）⚠️
- **1-5**: 退化很轻微
- **5-20**: 有一定退化
- **> 20**: 退化明显 ✅

---

## 🎯 影响分析

### 1. Haze样本无法测试
由于haze样本的退化图和原图完全相同：
- ✅ baseline_psnr = inf (100.0修复后)
- ✅ 任何工具处理都会降低质量
- ❌ **无法评估DehazeFormer的真实性能**

### 2. 测试结果的可靠性

**有效样本**: 111个（128 - 17）
- 可靠测试: noise, dark, motion blur, rain, defocus blur, jpeg, low resolution
- 不可靠: haze（17个样本）

### 3. 工具评估的影响

**DehazeFormer工具**:
- 设计用途: 去雾（haze）
- 实际测试: 处理的是"完全相同的图片"
- 结果: 必然变差（引入处理伪影）
- **结论**: 无法评估其真实去雾能力 ⚠️

---

## 💡 建议

### 1. 立即建议：过滤haze样本
在分析结果时，排除haze样本：

```python
import pandas as pd

df = pd.read_csv('detailed_results.csv')

# 过滤掉haze样本
df_filtered = df[~df['degradation_types'].str.contains('haze', na=False)]

# 重新计算统计
tool_summary = df_filtered.groupby('tool_name')['psnr_improvement'].mean()
print(tool_summary.sort_values(ascending=False))
```

### 2. 数据修复建议

**检查数据生成代码**:
```python
# 查找haze退化的生成逻辑
# 可能的问题：
# 1. haze强度参数设置为0
# 2. haze退化函数没有被调用
# 3. 条件判断错误，haze分支被跳过
```

**验证方法**:
```bash
# 检查训练集是否也有同样问题
python3 << 'CHECK'
import pandas as pd
df = pd.read_parquet('shard-train-000000.parquet')
# ... 同样的检查逻辑
CHECK
```

### 3. 临时解决方案

**测试时排除haze**:
```bash
python3 tests/test_all_tools_metrics.py \
    --parquet /path/to/data.parquet \
    --output_dir ./results \
    --tools \
        swinir_denoising \
        swinir_jpeg_artifact_removal \
        swinir_super_resolution \
        restormer_motion_deblurring \
        restormer_defocus_deblurring \
        restormer_deraining \
        xrestormer_motion_deblurring \
        xrestormer_deraining \
        mprnet_denoising \
        mprnet_motion_deblurring \
        mprnet_deraining \
        fbcnn_jpeg_artifact_removal \
        drbnet_defocus_deblurring
        # 跳过 dehazeformer_dehaze
```

---

## 📋 详细检查结果

### Haze样本详情

| 样本 | 退化等级 | 原图尺寸 | 退化图尺寸 | 像素差异 | 结论 |
|------|---------|---------|-----------|---------|------|
| 样本1 | high | 2040×1344 | 2040×1344 | 0.00 | ❌ 完全相同 |
| 样本2 | low | 2040×1356 | 2040×1356 | 0.00 | ❌ 完全相同 |
| 样本3 | low | 2040×1620 | 2040×1620 | 0.00 | ❌ 完全相同 |
| ... | ... | ... | ... | 0.00 | ❌ 完全相同 |

**所有17个样本**: 像素差异 = 0.00

### 其他退化类型状态

| 退化类型 | 样本数 | 平均差异 | 状态 |
|---------|--------|---------|------|
| dark | 21 | 32.26 | ✅ 退化明显 |
| noise | 10 | 16.07 | ✅ 退化明显 |
| motion blur | 20 | 10.15 | ✅ 有退化 |
| defocus blur | 13 | 7.86 | ✅ 有退化 |
| rain | 18 | 7.05 | ✅ 有退化 |
| low resolution | 13 | 6.90 | ✅ 有退化 |
| jpeg compression artifact | 16 | 6.48 | ✅ 有退化 |
| **haze** | 17 | **0.00** | ❌ **无退化** |

---

## 🔍 可能的原因

### 原因1: 数据生成代码问题
```python
# 可能的错误代码
if degradation_type == 'haze':
    # 应该添加haze效果
    degraded_image = add_haze(original_image, level=haze_level)
    # 但可能：
    # - 函数没被调用
    # - haze_level = 0
    # - 函数返回了原图
```

### 原因2: 条件分支错误
```python
# 可能的错误
if degradation_type == 'noise':
    apply_noise()
elif degradation_type == 'blur':
    apply_blur()
# ... 但缺少 haze 分支
```

### 原因3: 文件混淆
```python
# 可能错误地使用了原图
degraded_image = original_image  # 应该是 apply_degradation(original_image)
```

---

## 📝 修复步骤

### 1. 找到数据生成代码
查找生成 `air_d1_sp9_up2_balanced` 数据集的脚本

### 2. 检查haze退化逻辑
```python
# 查找类似的代码
def add_haze(image, level):
    # 检查这里的实现
    pass
```

### 3. 重新生成haze样本
```bash
# 重新生成只包含haze的数据
python generate_data.py \
    --degradation_types haze \
    --output haze_fixed.parquet
```

### 4. 验证修复
```python
# 验证新数据
import pandas as pd
df = pd.read_parquet('haze_fixed.parquet')
# 检查像素差异 > 0
```

---

## 📊 对测试结果的影响

### 当前状态
- ✅ **111个样本**（非haze）: 测试结果可靠
- ❌ **17个样本**（haze）: 测试结果不可靠

### DehazeFormer工具
- ❌ 无法评估真实性能
- ❌ 当前结果必然是负改进（因为输入已经是原图）
- ⚠️ 需要重新测试（修复数据后）

### 其他工具
- ✅ 测试结果可靠
- ✅ 不受haze数据问题影响

---

## 🛠️ 临时解决方案

### 方案1: 在分析时过滤haze
```python
df_valid = df[df['degradation_types'] != 'haze']
```

### 方案2: 标记haze样本
```python
df['valid'] = ~df['degradation_types'].str.contains('haze')
df_valid = df[df['valid']]
```

### 方案3: 分开报告
- 报告A: 所有样本（包括有问题的haze）
- 报告B: 只包含有效样本（排除haze）

---

## ✅ 下一步行动

1. **立即**: 使用过滤后的数据分析结果
2. **短期**: 检查并修复数据生成代码
3. **中期**: 重新生成haze样本
4. **长期**: 添加数据质量检查到pipeline中

---

**发现**: 🔴 Haze样本数据质量问题  
**影响**: 17/128样本（13.3%）不可靠  
**建议**: 过滤haze样本，重新分析  
**状态**: 已识别，待修复



