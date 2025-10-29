# 指标计算对比报告

## 概述

本报告对比了 `/app/xiaominl/DeepEyes_v2/tests/baseline/test_baseline_restoration.py` 和 `/app/xiaominl/DeepEyes_v2/verl/utils/reward_score/image_quality_metrics.py` 中的图像质量指标计算实现。

---

## ✅ 更新状态 (2025-10-18)

**Baseline 已完成对齐修改！**

根据此报告的分析，已对 baseline 版本进行以下修改：
1. ✅ SSIM 改为 RGB 模式（与 verl 对齐）
2. ✅ 添加智能尺寸处理函数（参考 verl 实现）
3. ✅ 统一使用 PIL LANCZOS 重采样

详细修改内容请参考: [`BASELINE_ALIGNMENT_SUMMARY.md`](./BASELINE_ALIGNMENT_SUMMARY.md)

---

## 快速对比表

### 修改前（旧版本）

| 指标 | Baseline 版本（旧） | Verl 版本 | 是否一致 | 影响程度 |
|-----|-------------|----------|---------|---------|
| **PSNR** | 手动 MSE 计算 | scikit-image psnr 函数 | ⚠️ 基本一致 | 低 |
| **SSIM** | 灰度图单通道 | RGB 三通道 | 🔴 **不一致** | **高** |
| **LPIPS** | lpips.LPIPS(net='alex') | lpips.LPIPS(net='alex') | ✅ 一致 | 无 |
| **尺寸处理** | cv2.resize 到最小尺寸 | 智能策略（整数倍/裁剪） | ⚠️ 不同策略 | 中 |
| **图像预处理** | 简单 np.array() | 鲁棒的多格式支持 | ⚠️ 不同实现 | 低 |

**🔴 关键发现**: SSIM 计算方式不同（灰度 vs RGB）会导致结果显著差异！

### ✅ 修改后（当前版本）

| 指标 | Baseline 版本（新） | Verl 版本 | 是否一致 | 对齐状态 |
|-----|-------------|----------|---------|---------|
| **PSNR** | 手动 MSE + 智能尺寸处理 | scikit-image psnr + 智能尺寸处理 | ✅ **对齐** | ✅ 完成 |
| **SSIM** | **RGB 三通道** | RGB 三通道 | ✅ **完全一致** | ✅ 完成 |
| **LPIPS** | lpips.LPIPS + 智能尺寸处理 | lpips.LPIPS + 智能尺寸处理 | ✅ **完全一致** | ✅ 完成 |
| **尺寸处理** | 智能策略（整数倍/裁剪） | 智能策略（整数倍/裁剪） | ✅ **完全一致** | ✅ 完成 |
| **图像重采样** | PIL LANCZOS | PIL LANCZOS | ✅ **完全一致** | ✅ 完成 |
| **NIQE** | ❌ 不支持 | ✅ 支持 | N/A | - |
| **BRISQUE** | ❌ 不支持 | ✅ 支持 | N/A | - |
| **CPBD** | ❌ 不支持 | ✅ 支持 | N/A | - |
| **CLIP-IQA** | ❌ 不支持 | ✅ 支持 | N/A | - |
| **Hyper-IQA** | ❌ 不支持 | ✅ 支持 | N/A | - |

**✅ 对齐完成**: 所有有参考指标（PSNR、SSIM、LPIPS）及其辅助函数已与 verl 完全对齐！

## 对比总结

### ✅ 相同点

1. **使用相同的评估指标**: PSNR、SSIM、LPIPS
2. **LPIPS 归一化**: 都使用 [-1, 1] 范围的归一化
3. **异常处理**: 两者都有异常处理机制，失败时返回默认值
4. **LPIPS 网络**: 都默认使用 'alex' 网络

### ⚠️ 关键差异

## 1. PSNR 计算差异

### Baseline 版本 (test_baseline_restoration.py:96-117)
```python
def calculate_psnr(img1: Image.Image, img2: Image.Image) -> float:
    """计算PSNR"""
    import cv2
    arr1 = np.array(img1)
    arr2 = np.array(img2)
    
    # 确保尺寸一致 - 使用 cv2.resize
    if arr1.shape != arr2.shape:
        h = min(arr1.shape[0], arr2.shape[0])
        w = min(arr1.shape[1], arr2.shape[1])
        arr1 = cv2.resize(arr1, (w, h))
        arr2 = cv2.resize(arr2, (w, h))
    
    # 手动计算 MSE 和 PSNR
    mse = np.mean((arr1.astype(float) - arr2.astype(float)) ** 2)
    if mse == 0:
        return 100.0
    return 10 * np.log10(255.0 ** 2 / mse)
```

**特点:**
- ✅ 手动实现 MSE 和 PSNR 计算
- ✅ 使用 OpenCV 的 cv2.resize 调整尺寸
- ✅ MSE=0 时返回 100.0

### Verl 版本 (image_quality_metrics.py:355-382)
```python
def calculate_psnr(self, img1, img2) -> float:
    """计算PSNR (Peak Signal-to-Noise Ratio)"""
    image1 = self._prepare_image(img1)
    image2 = self._prepare_image(img2)
    
    # 使用更复杂的尺寸处理策略
    image1, image2 = self._handle_size_mismatch(image1, image2, "PSNR")
    
    # 使用 scikit-image 的 PSNR 函数
    psnr_value = psnr(image1, image2, data_range=255)
    return float(psnr_value)
```

**特点:**
- ✅ 使用 scikit-image 的标准 psnr 函数
- ✅ 更鲁棒的图像预处理 (_prepare_image)
- ✅ 智能尺寸匹配处理 (_handle_size_mismatch)

**差异影响:** 
- scikit-image 的 psnr 函数可能与手动实现有细微数值差异
- 尺寸调整方法不同可能导致结果略有差异

---

## 2. SSIM 计算差异

### Baseline 版本 (test_baseline_restoration.py:120-147)
```python
def calculate_ssim(img1: Image.Image, img2: Image.Image) -> float:
    """计算SSIM"""
    from skimage.metrics import structural_similarity as ssim
    import cv2
    
    arr1 = np.array(img1)
    arr2 = np.array(img2)
    
    # 确保尺寸一致
    if arr1.shape != arr2.shape:
        h = min(arr1.shape[0], arr2.shape[0])
        w = min(arr1.shape[1], arr2.shape[1])
        arr1 = cv2.resize(arr1, (w, h))
        arr2 = cv2.resize(arr2, (w, h))
    
    # 转换为灰度图再计算 SSIM
    if len(arr1.shape) == 3:
        arr1_gray = cv2.cvtColor(arr1, cv2.COLOR_RGB2GRAY)
        arr2_gray = cv2.cvtColor(arr2, cv2.COLOR_RGB2GRAY)
    else:
        arr1_gray = arr1
        arr2_gray = arr2
    
    return ssim(arr1_gray, arr2_gray)
```

**特点:**
- ⚠️ **强制转换为灰度图**再计算 SSIM
- ✅ 使用 cv2.cvtColor 转换
- ✅ 未指定 data_range (默认值)

### Verl 版本 (image_quality_metrics.py:322-353)
```python
def calculate_ssim(self, img1, img2) -> float:
    """计算SSIM (Structural Similarity Index)"""
    image1 = self._prepare_image(img1)
    image2 = self._prepare_image(img2)
    
    # 处理尺寸不匹配
    image1, image2 = self._handle_size_mismatch(image1, image2, "SSIM")
    
    # 根据图像类型计算 SSIM
    if len(image1.shape) == 3:  # RGB图像
        ssim_value = ssim(image1, image2, channel_axis=2, data_range=255)
    else:  # 灰度图像
        ssim_value = ssim(image1, image2, data_range=255)
        
    return float(ssim_value)
```

**特点:**
- ✅ **在 RGB 空间计算 SSIM** (使用 channel_axis=2)
- ✅ 明确指定 data_range=255
- ✅ 保留颜色信息

**差异影响:** 🔴 **这是最重要的差异！**
- Baseline: 只在亮度通道 (灰度图) 上计算 SSIM
- Verl: 在所有 RGB 通道上计算 SSIM，然后平均
- **结果会有显著差异**，Verl 版本考虑了颜色相似性

---

## 3. LPIPS 计算差异

### Baseline 版本 (test_baseline_restoration.py:150-192)
```python
def calculate_lpips(img1: Image.Image, img2: Image.Image) -> float:
    """计算LPIPS"""
    import torch
    import lpips
    
    # 使用函数属性存储模型（单例模式）
    if not hasattr(calculate_lpips, 'loss_fn'):
        calculate_lpips.loss_fn = lpips.LPIPS(net='alex').cuda() \
            if torch.cuda.is_available() else lpips.LPIPS(net='alex')
    
    # 转换图像为 tensor
    def img_to_tensor(img):
        arr = np.array(img).astype(np.float32) / 255.0
        if len(arr.shape) == 2:
            arr = np.stack([arr, arr, arr], axis=2)
        tensor = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)
        return tensor * 2.0 - 1.0  # 归一化到[-1, 1]
    
    # 尺寸处理
    arr1 = np.array(img1)
    arr2 = np.array(img2)
    if arr1.shape != arr2.shape:
        h = min(arr1.shape[0], arr2.shape[0])
        w = min(arr1.shape[1], arr2.shape[1])
        img1 = Image.fromarray(cv2.resize(arr1, (w, h)))
        img2 = Image.fromarray(cv2.resize(arr2, (w, h)))
    
    tensor1 = img_to_tensor(img1)
    tensor2 = img_to_tensor(img2)
    
    if torch.cuda.is_available():
        tensor1 = tensor1.cuda()
        tensor2 = tensor2.cuda()
    
    with torch.no_grad():
        distance = calculate_lpips.loss_fn(tensor1, tensor2)
    
    return distance.item()
```

**特点:**
- ✅ 使用函数属性实现单例模式
- ✅ 简单的 GPU 判断和移动
- ✅ 灰度图转换为 3 通道

### Verl 版本 (image_quality_metrics.py:384-437)
```python
def calculate_lpips(self, img1, img2) -> float:
    """计算LPIPS (Learned Perceptual Image Patch Similarity)"""
    if not HAS_LPIPS or self._lpips_model is None:
        print("[WARNING] LPIPS model not available, returning 0.0")
        return 0.0
    
    image1 = self._prepare_image(img1)
    image2 = self._prepare_image(img2)
    
    # 处理尺寸不匹配
    image1, image2 = self._handle_size_mismatch(image1, image2, "LPIPS")
    
    # 转换为LPIPS所需的张量格式
    tensor1 = self._normalize_image_for_lpips(image1)
    tensor2 = self._normalize_image_for_lpips(image2)
    
    # 使用 GPU 加速计算（模型保持在 GPU）
    with torch.no_grad():
        if self._lpips_model is not None:
            model_device = next(self._lpips_model.parameters()).device
            
            # 将输入数据移动到模型所在设备
            tensor1 = tensor1.to(model_device)
            tensor2 = tensor2.to(model_device)
            
            # 计算LPIPS
            lpips_value = self._lpips_model(tensor1, tensor2)
            result = float(lpips_value.item())
            
            # 清理输入tensor（模型保持在GPU）
            del tensor1, tensor2, lpips_value
            
            # 只在 GPU 上清理缓存（不移动模型）
            if model_device.type == 'cuda':
                torch.cuda.empty_cache()
        else:
            result = 0.0
        
    return result
```

**特点:**
- ✅ 使用类实例变量存储模型
- ✅ 智能设备管理（自动检测模型设备）
- ✅ 显式的内存管理和清理
- ✅ 更健壮的错误处理

**差异影响:** 
- 归一化逻辑基本相同
- 设备管理更智能，但计算结果应该相同

---

## 4. 尺寸不匹配处理差异

### Baseline 版本
```python
# 简单策略：resize 到最小尺寸
if arr1.shape != arr2.shape:
    h = min(arr1.shape[0], arr2.shape[0])
    w = min(arr1.shape[1], arr2.shape[1])
    arr1 = cv2.resize(arr1, (w, h))
    arr2 = cv2.resize(arr2, (w, h))
```

### Verl 版本 (image_quality_metrics.py:216-261)
```python
def _handle_size_mismatch(self, image1, image2, metric_name=""):
    """处理图像尺寸不匹配，特别针对超分辨率场景"""
    if image1.shape == image2.shape:
        return image1, image2
        
    h1, w1 = image1.shape[:2]
    h2, w2 = image2.shape[:2]
    
    # 策略1：如果一个图像是另一个的整数倍（常见于超分场景）
    scale_h1_to_h2 = h2 / h1 if h1 > 0 else 0
    scale_w1_to_w2 = w2 / w1 if w1 > 0 else 0
    
    # 检查是否是整数倍关系
    def is_integer_scale(scale):
        return abs(scale - round(scale)) < 0.01 and scale >= 1.0
    
    if (is_integer_scale(scale_h1_to_h2) and is_integer_scale(scale_w1_to_w2)):
        # image2是image1的整数倍，下采样image2
        image2 = self._resize_image(image2, (h1, w1))
    elif (is_integer_scale(scale_h2_to_h1) and is_integer_scale(scale_w2_to_w1)):
        # image1是image2的整数倍，下采样image1
        image1 = self._resize_image(image1, (h2, w2))
    else:
        # 策略2：非整数倍关系，裁剪到相同尺寸
        min_h = min(h1, h2)
        min_w = min(w1, w2)
        image1 = image1[:min_h, :min_w]
        image2 = image2[:min_h, :min_w]
```

**差异影响:**
- Verl 版本对超分辨率场景优化（检测整数倍关系）
- Verl 使用 PIL LANCZOS 重采样（更高质量）
- Baseline 使用 OpenCV 默认重采样

---

## 5. 图像预处理差异

### Baseline 版本
```python
# 直接转换为 numpy 数组
arr1 = np.array(img1)
arr2 = np.array(img2)
```

### Verl 版本 (image_quality_metrics.py:185-214)
```python
def _prepare_image(self, image_data):
    """准备图像数据，支持多种输入格式"""
    if isinstance(image_data, str):
        # 路径或base64字符串
        if image_data.startswith('data:image'):
            # base64
            image_data = base64.b64decode(image_data.split(',')[1])
        else:
            # 文件路径
            image = Image.open(image_data)
            
    elif isinstance(image_data, bytes):
        # 字节数据
        image = Image.open(io.BytesIO(image_data))
        
    elif isinstance(image_data, Image.Image):
        # PIL 图像
        image = image_data
        
    elif isinstance(image_data, np.ndarray):
        # numpy 数组
        if image_data.dtype in [np.float32, np.float64]:
            if image_data.max() <= 1.0:
                # [0,1] 范围转换到 [0,255]
                image_data = (image_data * 255).astype(np.uint8)
        return image_data
    
    # 转换PIL图像到numpy数组
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    return np.array(image)
```

**差异影响:**
- Verl 支持更多输入格式（路径、bytes、base64）
- Verl 处理浮点数范围归一化
- Baseline 假设输入已经是 PIL Image

---

## 6. 额外的指标支持

### Verl 版本额外支持的无参考指标

Verl 版本还实现了以下无参考（no-reference）图像质量评估指标，这些在 Baseline 版本中**不存在**:

1. **NIQE** (Natural Image Quality Evaluator) - 行 441-511
2. **BRISQUE** (Blind/Referenceless Image Spatial Quality Evaluator) - 行 513-582
3. **CPBD** (Cumulative Probability of Blur Detection) - 行 584-651
4. **CLIP-IQA** (CLIP-based Image Quality Assessment) - 行 653-687
5. **Hyper-IQA** - 行 689-722

还有两个聚合方法:
- `calculate_all_no_reference_metrics()` - 行 724-766
- `calculate_all_metrics()` - 行 768-828

这些指标不需要参考图像，可以直接评估单张图像的质量。

---

## 总体评估

### 🔴 关键问题

**SSIM 计算的本质差异最严重:**
- **Baseline**: 灰度图 SSIM (单通道)
- **Verl**: RGB SSIM (三通道)
- **影响**: SSIM 值可能相差 5-15%

### 建议

#### 如果需要结果一致性:

1. **修改 Baseline 版本，使用 RGB SSIM:**
```python
def calculate_ssim(img1: Image.Image, img2: Image.Image) -> float:
    from skimage.metrics import structural_similarity as ssim
    import cv2
    
    arr1 = np.array(img1)
    arr2 = np.array(img2)
    
    if arr1.shape != arr2.shape:
        h = min(arr1.shape[0], arr2.shape[0])
        w = min(arr1.shape[1], arr2.shape[1])
        arr1 = cv2.resize(arr1, (w, h))
        arr2 = cv2.resize(arr2, (w, h))
    
    # 修改这里：在RGB空间计算
    if len(arr1.shape) == 3:
        return ssim(arr1, arr2, channel_axis=2, data_range=255)
    else:
        return ssim(arr1, arr2, data_range=255)
```

2. **或修改 Verl 版本，使用灰度 SSIM:**
```python
def calculate_ssim(self, img1, img2) -> float:
    image1 = self._prepare_image(img1)
    image2 = self._prepare_image(img2)
    image1, image2 = self._handle_size_mismatch(image1, image2, "SSIM")
    
    # 修改这里：转换为灰度
    if len(image1.shape) == 3:
        import cv2
        image1 = cv2.cvtColor(image1, cv2.COLOR_RGB2GRAY)
        image2 = cv2.cvtColor(image2, cv2.COLOR_RGB2GRAY)
    
    return ssim(image1, image2, data_range=255)
```

3. **统一 PSNR 实现:**
   - 建议都使用 scikit-image 的 psnr 函数
   - 或都使用手动实现（需要确保公式一致）

4. **统一尺寸调整策略:**
   - 如果关心超分辨率场景，使用 Verl 的策略
   - 如果只需简单比较，使用 Baseline 的简单策略即可

---

## 代码位置

- **Baseline 版本**: `/app/xiaominl/DeepEyes_v2/tests/baseline/test_baseline_restoration.py`
  - PSNR: 行 96-117
  - SSIM: 行 120-147  
  - LPIPS: 行 150-192

- **Verl 版本**: `/app/xiaominl/DeepEyes_v2/verl/utils/reward_score/image_quality_metrics.py`
  - PSNR: 行 355-382
  - SSIM: 行 322-353
  - LPIPS: 行 384-437
  - 辅助方法: 行 185-319

---

## 结论

两个版本的指标计算**不完全相同**，主要差异在于:

1. 🔴 **SSIM**: Baseline 使用灰度，Verl 使用 RGB（**影响最大**）
2. ⚠️ **PSNR**: 实现方式不同（手动 vs scikit-image）
3. ✅ **LPIPS**: 逻辑基本相同，只是代码组织不同
4. ⚠️ **尺寸处理**: Verl 更智能，但可能导致不同结果
5. ➕ **额外指标**: Verl 支持 NIQE、BRISQUE、CPBD、CLIP-IQA、Hyper-IQA 等无参考指标

### 相同的有参考指标
- ✅ PSNR (虽然实现不同，但原理相同)
- ⚠️ SSIM (实现不同：灰度 vs RGB)
- ✅ LPIPS (基本相同)

### Verl 独有的无参考指标
- NIQE
- BRISQUE
- CPBD
- CLIP-IQA
- Hyper-IQA

**建议采取行动**: 
1. **必须**: 统一 SSIM 的计算方式（选择 RGB 或灰度），以确保结果的可比性
2. **建议**: 统一 PSNR 实现（都用 scikit-image 或都手动计算）
3. **可选**: Baseline 版本可以考虑添加无参考指标以增强评估能力

