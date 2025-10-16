# 正确的尺寸对齐策略

## ✅ 正确的对齐逻辑

### 核心原则

**原图GT是参考标准，应该保持不变**  
**待评估的图像（退化图/复原图）应该resize到GT的尺寸**

---

## 📊 正确的实现

### 1. 退化图 vs 原图

```python
# tracking_image_utils.py 第1582-1589行
# 确保尺寸一致（处理low resolution等改变尺寸的退化）
# 原则：将退化图resize到原图尺寸（GT是标准，待评估图像需要对齐）
if degraded_img.size != original_img.size:
    print(f"退化图{degraded_img.size} → 原图{original_img.size}")
    degraded_img = degraded_img.resize(original_img.size, Image.Resampling.LANCZOS)
    # ↑ resize 退化图，不是原图！

degraded_metrics = calculate_all_metrics(degraded_img, original_img)
```

### 2. 复原图 vs 原图

```python
# tracking_image_utils.py 第1613-1619行
# 确保尺寸一致（处理super_resolution等改变尺寸的工具）
# 原则：将复原图resize到原图尺寸（GT是标准，待评估图像需要对齐）
if restored_img.size != original_img.size:
    print(f"复原图{restored_img.size} → 原图{original_img.size}")
    restored_img = restored_img.resize(original_img.size, Image.Resampling.LANCZOS)
    # ↑ resize 复原图，不是原图！

restored_metrics = calculate_all_metrics(restored_img, original_img)
```

### 3. 奖励计算

```python
# image_restoration.py 第893-905行
# 确保尺寸一致
# 原则：将复原图resize到原图尺寸（GT是参考标准）
if restored_image.size != original_image.size:
    print(f"尺寸不匹配: restored={restored_image.size} vs original={original_image.size}")
    restored_image = restored_image.resize(original_image.size, Image.Resampling.LANCZOS)
    # ↑ resize 复原图，不是原图！
    print(f"复原图已resize到: {restored_image.size}")

metrics = calculate_all_metrics(restored_image, original_image)
```

---

## 🎯 为什么这样是正确的

### 原理

**Ground Truth是评估标准**：
- 原图GT定义了"应该是什么样子"
- 所有评估都应该在GT的分辨率下进行
- 这样才能公平比较

### 场景示例

**Low Resolution退化**：
```
原图GT: 1344x2044（高分辨率）← 标准
退化图: 336x504（低分辨率）  ← 需要upscale到1344x2044
复原图: 可能336x504或1344x2044  ← 需要对齐到1344x2044

比较标准：都在1344x2044分辨率下比较
```

**Super Resolution处理**：
```
原图GT: 336x504（原始分辨率）← 标准
退化图: 336x504（低分辨率）  ← 已对齐
复原图: 1344x2044（super_resolution 4x）← 需要downscale到336x504

比较标准：都在336x504分辨率下比较（GT的分辨率）
```

---

## 📈 具体例子

### 场景：Low Resolution退化

**数据集**：
```
original_image: 1344x2044（高清GT）
degraded_image: 336x504（低分辨率退化）
```

**处理**：
```
Step 0: 输入退化图 336x504
Step 1: 模型可能使用super_resolution → 1344x2044
       或者不处理 → 336x504
```

**计算指标（正确方式）**：

```python
# 1. 退化图 vs 原图
degraded_img = 336x504  ← 从image_history[0]
original_img = 1344x2044  ← 从original_images

# resize退化图到GT尺寸
degraded_img_resized = degraded_img.resize((1344, 2044))  # ✅ 正确！

# 在1344x2044分辨率下比较
degraded_ssim = calculate_ssim(degraded_img_resized, original_img)
#                               1344x2044             1344x2044 ✅
结果: SSIM=0.45（低分辨率图upscale后与GT的相似度）


# 2. 复原图 vs 原图
restored_img = 1344x2044 或 336x504  ← 取决于是否用了super_resolution
original_img = 1344x2044  ← GT

# 如果复原图是336x504，resize到GT尺寸
if restored_img.size == (336, 504):
    restored_img_resized = restored_img.resize((1344, 2044))  # ✅ 正确！
else:
    restored_img_resized = restored_img  # 已经是1344x2044

# 在1344x2044分辨率下比较
restored_ssim = calculate_ssim(restored_img_resized, original_img)
#                               1344x2044              1344x2044 ✅
结果: SSIM=0.88（复原图与GT的相似度）


# 3. 提升计算
improvement = (0.88 - 0.45) / 0.45 * 100 = +95.6% ✅
```

---

## ❌ 错误的方式（之前的实现）

```python
# ❌ 错误：将GT resize到退化图尺寸
if degraded_img.size != original_img.size:
    original_img = original_img.resize(degraded_img.size)  # ❌
    # 1344x2044 → 336x504（降低了GT的分辨率！）

# 在336x504分辨率下比较
degraded_ssim = calculate_ssim(degraded_img, original_img_resized)
#                               336x504      336x504
# 问题：GT被降低分辨率，失去了细节信息
```

---

## ✅ 正确的方式（现在的实现）

```python
# ✅ 正确：将退化图resize到GT尺寸
if degraded_img.size != original_img.size:
    degraded_img = degraded_img.resize(original_img.size)  # ✅
    # 336x504 → 1344x2044（将退化图upscale）

# 在1344x2044分辨率下比较
degraded_ssim = calculate_ssim(degraded_img_resized, original_img)
#                               1344x2044              1344x2044 ✅
# 优势：在GT的原始分辨率下评估，保留所有细节
```

---

## 🎯 优势

### 为什么resize退化图/复原图更合理

1. **保留GT的完整信息**
   - GT是1344x2044，包含所有细节
   - 如果resize GT到336x504，会丢失75%的像素信息
   - resize退化图到1344x2044，虽然是插值，但GT保持完整

2. **公平的评估基准**
   - 所有评估都在GT的分辨率下进行
   - 统一的评估标准

3. **符合图像复原的目标**
   - 目标是将图像恢复到GT的质量
   - 在GT的分辨率下评估更合理

---

## 📝 修改总结

### 修改的逻辑

**之前（错误）**：
```
退化图(小) vs 原图GT(大) → resize 原图到小 ❌
复原图(大) vs 原图GT(大) → resize 原图到大 ❌
```

**现在（正确）**：
```
退化图(小) vs 原图GT(大) → resize 退化图到大 ✅
复原图(任意) vs 原图GT(大) → resize 复原图到大 ✅
```

### 修改的文件

- ✅ `verl/utils/tracking_image_utils.py`（第1582-1619行）
- ✅ `verl/utils/reward_score/image_restoration.py`（第893-905行）

### 关键改变

**之前**：
```python
original_img = original_img.resize(degraded_img.size)  # ❌ resize GT
```

**现在**：
```python
degraded_img = degraded_img.resize(original_img.size)  # ✅ resize 待评估图像
```

---

## ✅ 验证

### 运行后应该看到

```bash
[DEBUG DEGRADED METRICS] Sample 0: 尺寸不匹配，退化图(336, 504) → 原图(1344, 2044)
[DEBUG DEGRADED METRICS] Sample 0:
  Degraded: SSIM=0.4523, LPIPS=0.5234, PSNR=18.45
  # ↑ 退化图upscale到1344x2044后与GT的相似度

[DEBUG DEGRADED METRICS] Sample 0: 尺寸不匹配，复原图(1344, 2044) → 原图(1344, 2044)
# ↑ 如果已经一致，不会resize

[DEBUG] ✓ 所有指标计算成功，无尺寸错误
```

---

## 🎉 总结

### 您的纠正完全正确！

- ✅ **原图GT**：保持不变（标准分辨率）
- ✅ **退化图**：resize到GT尺寸
- ✅ **复原图**：resize到GT尺寸
- ✅ 所有比较在GT分辨率下进行

感谢您的细心审查！这个逻辑现在完全正确了。🎉

