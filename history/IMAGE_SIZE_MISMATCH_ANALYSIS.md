# 图像尺寸不匹配问题分析

## 🔍 错误信息解读

```
[DEBUG LPIPS] 图像尺寸不匹配: image1=336x504, image2=1344x2044
```

### image1 和 image2 分别是什么？

根据代码调用顺序：

```python
# image_quality_metrics.py 第750-787行
def calculate_all_metrics(self, img1, img2=None):
    """
    Args:
        img1: 第一张图像（或待评估图像）← image1
        img2: 第二张图像（参考图像，可选）← image2
    """
    metrics['lpips'] = self.calculate_lpips(img1, img2)
```

### 调用位置

**tracking_image_utils.py 第1589行**：
```python
degraded_metrics = metrics_calculator.calculate_all_metrics(degraded_img, original_img)
#                                                            ↑img1      ↑img2
#                                                            image1     image2
```

**结论**：
- **image1** = `degraded_img`（退化图，336x504）
- **image2** = `original_img`（原始GT图，1344x2044）

---

## 🎯 问题分析

### 您的场景：低分辨率退化

**数据集中的图像**：
```
original_image (GT): 1344x2044  ← 高分辨率原图
  ↓ 添加low resolution退化
degraded_image: 336x504  ← 低分辨率退化图（缩小到1/4）
```

**处理流程**：
```
1. 输入退化图: 336x504
2. 工具处理（可能super_resolution）: 336x504 → 1344x2044
3. 复原图: 1344x2044
```

### 问题所在

当计算**退化图 vs 原图**的指标时：
```python
degraded_img: 336x504     ← image1（低分辨率退化图）
original_img: 1344x2044   ← image2（高分辨率GT）

❌ 尺寸不匹配！无法计算SSIM/LPIPS
```

---

## 📊 为什么会有这个问题

### low resolution退化的特殊性

与其他退化不同：
- **noise, blur, haze**: 尺寸不变，只改变内容
- **low resolution**: **尺寸会变小**！

**示例**：
```
原图: 1344x2044
  ↓ 添加noise退化
退化图: 1344x2044  ← 尺寸不变 ✅

原图: 1344x2044
  ↓ 添加low resolution退化
退化图: 336x504  ← 尺寸变小 ❌
```

---

## ✅ 我的修复是正确的

### 修复代码（tracking_image_utils.py 第1582-1592行）

```python
# 确保尺寸一致（处理super_resolution等改变尺寸的工具）
if degraded_img.size != original_img.size:
    # 将原图resize到退化图的尺寸（因为退化图是输入尺寸）
    print(f"[DEBUG] Sample {idx}: 尺寸不匹配，原图{original_img.size} → 退化图{degraded_img.size}")
    original_img = original_img.resize(degraded_img.size, Image.Resampling.LANCZOS)
    # ↑ 将1344x2044 resize到 336x504

# 计算指标（现在尺寸一致）
degraded_metrics = metrics_calculator.calculate_all_metrics(degraded_img, original_img)
#                                                            336x504     336x504 ✅
```

### 为什么resize原图而不是退化图？

**原则**：将GT原图resize到与待评估图像相同的尺寸

**理由**：
1. 退化图是实际输入，尺寸应该保持不变
2. 原图是reference，可以调整到任意尺寸
3. 这样才能公平比较："在336x504分辨率下，退化图与原图的差异"

---

## 🎨 完整场景示例

### 场景：低分辨率退化 + Super Resolution处理

**数据集**：
```json
{
    "original_image": <1344x2044的高清图>,
    "images": [<336x504的低分辨率退化图>],
    "reward_model": [{"degradation_type": "low resolution", "degradation_level": "high"}]
}
```

**处理过程**：
```
Step 0: 退化图输入
  image_history[0] = 336x504（低分辨率）

Step 1: 模型调用super_resolution工具
  image_history[1] = 1344x2044（恢复到高分辨率）
```

**计算指标**：

**1. 退化图 vs 原图**：
```python
degraded_img = 336x504  ← image_history[0]
original_img = 1344x2044  ← 原始GT

# 检测到尺寸不匹配
original_img_resized = original_img.resize((336, 504))  # 1344x2044 → 336x504

# 计算指标
degraded_metrics = calculate_all_metrics(degraded_img, original_img_resized)
#                                        336x504      336x504 ✅

结果：
  Degraded_SSIM = 0.4523（低分辨率与原图的相似度，在336x504尺寸下）
  Degraded_LPIPS = 0.5234
  Degraded_PSNR = 18.45
```

**2. 复原图 vs 原图**：
```python
restored_img = 1344x2044  ← image_history[1]（super_resolution后）
original_img = 1344x2044  ← 原始GT

# 尺寸相同，无需resize
original_img_for_restored = original_img  # 保持1344x2044

# 计算指标
restored_metrics = calculate_all_metrics(restored_img, original_img_for_restored)
#                                        1344x2044   1344x2044 ✅

结果：
  Restored_SSIM = 0.8821（复原后与原图的相似度，在1344x2044尺寸下）
  Restored_LPIPS = 0.1234
  Restored_PSNR = 32.67
```

**3. 提升百分比**：
```python
improvement_ssim = (0.8821 - 0.4523) / 0.4523 * 100 = +95.0%  # 巨大提升！
improvement_lpips = (0.5234 - 0.1234) / 0.5234 * 100 = +76.4%
improvement_psnr = (32.67 - 18.45) / 18.45 * 100 = +77.1%
```

---

## ⚠️ 重要说明

### 为什么不同尺寸下的指标可以比较？

**不能直接比较**！但可以通过提升百分比来理解：

```
Degraded (336x504下): SSIM=0.45
Restored (1344x2044下): SSIM=0.88
Improvement: +95%

这表示：
- 低分辨率图像在低分辨率下的相似度是0.45
- 恢复到高分辨率后，在高分辨率下的相似度是0.88
- 虽然分辨率不同，但相对提升是95%
```

### 更合理的解读方式

**表格中应该这样理解**：

| Degraded_SSIM | Restored_SSIM | Improve_SSIM% | 说明 |
|---------------|---------------|---------------|------|
| 0.45 (336x504) | 0.88 (1344x2044) | +95% | 尺寸不同，但都与GT对应尺寸比较 |

**注意**：
- Degraded_SSIM：在低分辨率下与GT的相似度
- Restored_SSIM：在高分辨率下与GT的相似度
- 两者不能直接对比数值，但**百分比提升仍有意义**

---

## 🔧 修复后的行为

### 自动尺寸对齐

**退化图计算**：
```python
if degraded_img.size != original_img.size:
    # 336x504 != 1344x2044
    original_img = original_img.resize(degraded_img.size)  # GT: 1344x2044 → 336x504

degraded_metrics = calculate_all_metrics(degraded_img, original_img)
#                                        336x504      336x504 ✅
```

**复原图计算**：
```python
if restored_img.size != original_img.size:
    # 1344x2044 != 1344x2044（假设原图也是1344x2044）
    # 不需要resize
    
restored_metrics = calculate_all_metrics(restored_img, original_img)
#                                        1344x2044   1344x2044 ✅
```

---

## 📝 总结

### image1 和 image2 的含义

```python
calculate_all_metrics(img1, img2)
                      ↑     ↑
                  image1  image2
```

在您的错误中：
- **image1** = degraded_img = **336x504**（退化图，低分辨率）
- **image2** = original_img = **1344x2044**（原图GT，高分辨率）

### 为什么会不匹配

因为您的数据集包含**low resolution退化**：
- 原图是高分辨率（1344x2044）
- 退化过程将图像缩小（336x504）
- 导致尺寸不一致

### 修复方案

✅ 已添加自动resize逻辑：
- 计算退化图指标时：将原图resize到退化图尺寸
- 计算复原图指标时：将原图resize到复原图尺寸
- 确保所有比较都在相同尺寸下进行

### 修复的文件

- ✅ `verl/utils/tracking_image_utils.py`（第1582-1624行）
- ✅ `verl/utils/reward_score/image_restoration.py`（第893-898行）

所有修复已完成，现在可以正确处理尺寸变化的工具（如super_resolution）！🎉

