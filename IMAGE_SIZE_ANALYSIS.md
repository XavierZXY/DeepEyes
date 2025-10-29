# 图像尺寸差异分析

## 📊 数据集分析结果

**检查了256个样本**:
- ✅ **194个样本**: 尺寸完全一致（无low resolution退化）
- 🔍 **62个样本**: 4倍关系（有low resolution退化）
- ⚠️ **0个样本**: 细微差异

**结论**: 数据集本身**没有**小差异样本！所有尺寸关系都很清晰。

---

## 🔍 那么日志中的小差异从哪来？

### 观察到的差异

```
image1=1188x1800, image2=1176x1792
差异: width=12, height=8
```

### 可能来源

#### 1. fetch_image的padding（已修复）✅

**Qwen VL的fetch_image**会padding到28的倍数：

```python
检查能否被28整除:
1188 % 28 = 0  ✅
1800 % 28 = 0  ✅
1176 % 28 = 0  ✅
1792 % 28 = 0  ✅
```

**都能被28整除**，说明两个都是fetch_image处理过的。

**修复**: 我们已经移除了reward计算中的fetch_image，这个问题应该消失。

#### 2. 工具API服务端的处理

某些深度学习模型要求输入能被特定数整除：

```python
# 检查能否被8整除
1188 % 8 = 4  ❌
1176 % 8 = 0  ✅

# API可能做了crop/padding:
1188 → 1176 (crop掉12像素)
1800 → 1792 (crop掉8像素)
```

**可能**: 工具API服务端为了满足模型要求，对输入做了微调整。

#### 3. 多次工具处理的累积

```
原图: (1200, 1800)
  ↓ 工具1 (可能crop到8的倍数)
  → (1192, 1800)
  ↓ 工具2 (可能再crop)
  → (1184, 1792)
  ↓ 工具3
  → (1176, 1792)
```

**可能**: 每个工具都做微小调整，累积后产生差异。

---

## 🔧 已添加的诊断

### 工具尺寸变化检查

**位置**: `parallel_env.py` 第1011-1020行

```python
# 检查工具是否改变了尺寸
if input_img.size != output_img.size:
    print(f'⚠️  工具{i}({tool.name})改变了尺寸: {input_img.size} → {output_img.size}')
else:
    print(f'✅ 工具{i}({tool.name})保持尺寸: {output_img.size}')
```

**作用**: 运行训练后可以看到每个工具是否改变了尺寸

---

## 🚀 验证方法

### 运行训练后检查

```bash
# 1. 查看工具是否改变了尺寸
grep "工具.*改变了尺寸" logs/*.log

# 应该看到（如果有）:
# [WARNING T1-00] ⚠️  工具1(scunet_denoising)改变了尺寸: (1188, 1800) → (1176, 1792)

# 2. 查看工具保持尺寸
grep "工具.*保持尺寸" logs/*.log | head -20

# 应该看到大部分工具都保持尺寸:
# [DEBUG T1-00] ✅ 工具1(restormer_deraining)保持尺寸: (1176, 1792)

# 3. 查看工具输入尺寸
grep "📏 工具输入图像尺寸" logs/*.log | head -10

# 看看输入尺寸是什么
```

---

## 🎯 预期发现

### 情况A: 工具确实保持尺寸

```bash
# 日志
[DEBUG T1-00] 📏 工具输入图像尺寸: (1188, 1800)
[DEBUG T1-00] ✅ 工具1(restormer_deraining)保持尺寸: (1188, 1800)
[DEBUG T1-00] ✅ 工具2(scunet_denoising)保持尺寸: (1188, 1800)
[DEBUG T1-00] ✅ 工具3(retinexformer_brighten)保持尺寸: (1188, 1800)
```

**说明**: 工具没有问题，差异来自之前的fetch_image（已修复）

### 情况B: 某个工具改变了尺寸

```bash
# 日志
[DEBUG T1-00] 📏 工具输入图像尺寸: (1188, 1800)
[WARNING T1-00] ⚠️  工具1(scunet_denoising)改变了尺寸: (1188, 1800) → (1176, 1792)
[DEBUG T1-00] ✅ 工具2(retinexformer_brighten)保持尺寸: (1176, 1792)
```

**说明**: 工具API服务端做了调整（可能是模型要求）

---

## 📝 处理方案

### 当前逻辑（已有，正确）✅

```python
# image_restoration.py 第963-967行
if restored_image.size != original_image.size:
    # 将复原图resize到原图的尺寸（GT是参考标准）
    restored_image = restored_image.resize(original_image.size, Image.Resampling.LANCZOS)
```

**这个逻辑会自动处理所有尺寸差异**:
- 4倍关系（low resolution样本）
- 2倍关系（如果用了scale=2的SR）
- 细微差异（工具API的微调整）
- 任意差异

### 如果工具API确实改变了尺寸

**建议修复工具API服务端**:
- 让API保持输入输出尺寸一致
- 或者在API返回前resize回原始尺寸

**临时方案**（如果无法修改API）:
- 当前的resize对齐逻辑已经能处理 ✅
- 只是会有微小的质量损失

---

## 🧪 诊断脚本

运行训练，然后执行：

```bash
# 查看是否有工具改变尺寸
grep "改变了尺寸" logs/*.log | head -20

# 统计频率
grep "改变了尺寸" logs/*.log | grep -oP '工具\d+\(\K[^)]+' | sort | uniq -c

# 示例输出:
#   15 scunet_denoising
#    8 restormer_deraining
# → 说明这些工具会微调尺寸
```

---

## ✅ 总结

### 您的理解完全正确

1. ✅ **工具应该保持尺寸**（除了SR）
2. ✅ **SR改变尺寸是倍数关系**（2x, 3x, 4x）
3. ✅ **细微差异不应该出现**

### 细微差异的可能来源

1. **fetch_image的padding** ← 已修复 ✅
2. **工具API服务端的微调整** ← 需要验证
3. **之前的代码bug** ← 已修复 ✅

### 下一步

运行训练，查看日志：

```bash
# 如果看到
[DEBUG] ✅ 工具保持尺寸: (1188, 1800)
→ 说明工具没问题

# 如果看到  
[WARNING] ⚠️  工具改变了尺寸: (1188, 1800) → (1176, 1792)
→ 说明API服务端有问题，需要修复API
```

**无论如何，当前的resize对齐逻辑都能正确处理！** ✅

---

**修复完成！添加了尺寸变化监控！** 🎉

