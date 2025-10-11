# 图像尺寸对齐修复

## 🔴 问题

```
[DEBUG LPIPS] 图像尺寸不匹配: image1=1092x1932, image2=1080x1920
[DEBUG SSIM] 图像尺寸不匹配: image1=1092x1932, image2=1080x1920
[DEBUG PSNR] 图像尺寸不匹配: image1=1092x1932, image2=1080x1920
```

## 📊 根本原因

### 数据处理流程差异

**复原图** (image_history[-1]):
```python
# 在训练过程中
multi_modal_data = {"image": degraded_image}
processed_img = fetch_image(multi_modal_data)  # qwen2.5-vl预处理，resize到1080x1920
# 工具处理后返回
restored_img = fetch_image(tool_output)  # 也经过fetch_image，1080x1920
```

**原图** (original_image):
```python
# 从数据集读取
original_image = parquet['extra_info']['original_image']  # bytes格式，原始尺寸1092x1932
# 直接使用，没有经过fetch_image
```

**结果**: 尺寸不匹配 → 无法计算PSNR/SSIM/LPIPS

## ✅ 解决方案

### 对原图应用相同的fetch_image处理

```python
# compute_reference_metrics_for_batch中

# 1. 提取原图
original_img_raw = extract_image_from_multimodal_data(original_images[idx])
# → PIL Image, 原始尺寸 1092x1932

# 2. 应用fetch_image（与复原图相同的预处理）
from qwen_vl_utils import fetch_image

original_dict = {"image": original_img_raw}
original_img = fetch_image(original_dict)
# → 处理后的PIL Image, 1080x1920

# 3. 提取复原图（已经是fetch_image处理过的）
restored_img = extract_image_from_multimodal_data(img_hist[-1])
# → 1080x1920

# 4. 计算指标（尺寸匹配）
metrics = metrics_calculator.calculate_all_metrics(restored_img, original_img)
# ✓ 1080x1920 vs 1080x1920 → 成功！
```

## 🔍 fetch_image的作用

**Qwen2.5-VL的预处理**:
```python
def fetch_image(image_dict):
    # 1. 读取图像
    # 2. Resize到合适尺寸（保持长宽比）
    # 3. 可能的padding或crop
    # 4. 返回处理后的PIL Image
```

**为什么需要**:
- Qwen2.5-VL对输入图像尺寸有要求
- 训练中所有图像都经过fetch_image
- 计算指标时必须用相同处理后的图像

## 📊 完整数据流

```
数据集
  ↓ original_image: 原始bytes (1092x1932)
  ↓ images: 退化bytes (1092x1932)
  
数据加载
  ↓ origin_images = process_raw_image(original_image) → PIL Image (1092x1932)
  ↓ images = process_image(images) → fetch_image处理 (1080x1920)
  
训练过程
  ↓ multi_modal_data = fetch_image(images) → 1080x1920
  ↓ 工具处理
  ↓ image_history[-1] = fetch_image(tool_output) → 1080x1920
  
计算有参考指标（修复后）
  ↓ original = fetch_image(origin_images) → 1080x1920 ✓
  ↓ restored = image_history[-1] → 1080x1920 ✓
  ↓ PSNR/SSIM/LPIPS(restored, original) → 成功！
```

## ✅ 修复位置

**文件**: `verl/utils/tracking_image_utils.py` 第1172-1192行

**关键代码**:
```python
# 对原图应用fetch_image处理（与复原图相同的预处理）
from qwen_vl_utils import fetch_image

if isinstance(original_img_raw, Image.Image):
    original_dict = {"image": original_img_raw}
    original_img = fetch_image(original_dict)  # ← 应用相同预处理
elif isinstance(original_img_raw, bytes):
    pil_img = Image.open(io.BytesIO(original_img_raw))
    original_dict = {"image": pil_img}
    original_img = fetch_image(original_dict)  # ← 应用相同预处理
```

## 🎯 预期结果

修复后应该看到：
```
[DEBUG REF METRICS] Sample 0: original_img size after fetch_image: (1080, 1920)
[DEBUG REF METRICS] Sample 1: original_img size after fetch_image: (1080, 1920)
...
[DEBUG REF METRICS] Calculated reference metrics for 37/100 samples
```

**不再有尺寸不匹配的警告！**

## 📝 总结

**问题**: 原图和复原图尺寸不匹配  
**原因**: 原图未经过fetch_image预处理  
**修复**: 对原图应用相同的fetch_image处理  
**结果**: 尺寸对齐 → PSNR/SSIM/LPIPS计算正确

现在应该完全正常了！🎯
