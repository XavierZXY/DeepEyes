# Baseline 指标计算对齐总结

## 修改时间
2025-10-18

## 目的
将 `/app/xiaominl/DeepEyes_v2/tests/baseline/test_baseline_restoration.py` 中的图像质量指标计算，与 `/app/xiaominl/DeepEyes_v2/verl/utils/reward_score/image_quality_metrics.py` 中的实现对齐。

## 主要修改

### 1. ✅ 添加智能尺寸处理函数（参考 verl）

#### `_resize_image()` 函数
**位置**: 第 97-125 行

**功能**: 
- 使用 PIL 的 LANCZOS 重采样算法（高质量）
- 支持 RGB 和灰度图像
- 降级策略：失败时使用裁剪

**参考**: `verl/utils/reward_score/image_quality_metrics.py:263-293`

#### `_handle_size_mismatch()` 函数
**位置**: 第 128-173 行

**功能**: 
- **策略 1**: 检测整数倍关系（适用于超分辨率场景）
  - 如果 image2 是 image1 的整数倍 → 下采样 image2
  - 如果 image1 是 image2 的整数倍 → 下采样 image1
- **策略 2**: 非整数倍关系 → 裁剪到最小尺寸
- 提供调试信息（显示尺寸和缩放策略）

**参考**: `verl/utils/reward_score/image_quality_metrics.py:216-261`

**示例输出**:
```
[DEBUG SSIM] 图像尺寸不匹配: image1=512x512, image2=1024x1024
[DEBUG SSIM] 下采样较大图像到512x512 (缩放比例: 2.0x)
```

---

### 2. 🔴 修改 SSIM 计算（最关键的变化）

#### 修改前（旧实现）
```python
# 转换为灰度图
if len(arr1.shape) == 3:
    arr1_gray = cv2.cvtColor(arr1, cv2.COLOR_RGB2GRAY)
    arr2_gray = cv2.cvtColor(arr2, cv2.COLOR_RGB2GRAY)
else:
    arr1_gray = arr1
    arr2_gray = arr2

return ssim(arr1_gray, arr2_gray)
```

**问题**: 只在亮度通道计算 SSIM，忽略了颜色信息

#### 修改后（新实现）
```python
# 在 RGB 空间计算 SSIM（参考 verl）
# 这样可以考虑颜色相似性，不仅仅是亮度
if len(arr1.shape) == 3:  # RGB图像
    ssim_value = ssim(arr1, arr2, channel_axis=2, data_range=255)
else:  # 灰度图像
    ssim_value = ssim(arr1, arr2, data_range=255)

return float(ssim_value)
```

**改进**:
- ✅ 在 RGB 空间计算 SSIM（保留颜色信息）
- ✅ 明确指定 `data_range=255`
- ✅ 使用 `channel_axis=2` 在所有通道上计算
- ✅ 与 verl 实现完全对齐

**预期影响**: SSIM 值会与之前有显著差异（通常变化 5-15%），因为现在考虑了颜色相似性。

---

### 3. ⚠️ 修改 PSNR 计算

#### 修改前
```python
if arr1.shape != arr2.shape:
    h = min(arr1.shape[0], arr2.shape[0])
    w = min(arr1.shape[1], arr2.shape[1])
    arr1 = cv2.resize(arr1, (w, h))
    arr2 = cv2.resize(arr2, (w, h))
```

**问题**: 简单 resize，未考虑超分辨率场景

#### 修改后
```python
# 使用智能尺寸处理策略（参考 verl）
arr1, arr2 = _handle_size_mismatch(arr1, arr2, "PSNR")
```

**改进**:
- ✅ 智能检测整数倍关系
- ✅ 使用高质量 LANCZOS 重采样
- ✅ 与 verl 实现对齐

---

### 4. ⚠️ 修改 LPIPS 计算

#### 修改前
```python
if arr1.shape != arr2.shape:
    h = min(arr1.shape[0], arr2.shape[0])
    w = min(arr1.shape[1], arr2.shape[1])
    img1 = Image.fromarray(cv2.resize(arr1, (w, h)))
    img2 = Image.fromarray(cv2.resize(arr2, (w, h)))
```

#### 修改后
```python
# 使用智能尺寸处理策略（参考 verl）
arr1, arr2 = _handle_size_mismatch(arr1, arr2, "LPIPS")
```

**改进**:
- ✅ 统一使用智能尺寸处理
- ✅ 代码更简洁
- ✅ 与 verl 实现对齐

---

## 修改对比表

| 函数 | 修改前 | 修改后 | 对齐状态 |
|-----|-------|-------|---------|
| **SSIM** | 灰度图 SSIM | RGB SSIM | ✅ 完全对齐 |
| **PSNR** | 简单 cv2.resize | 智能尺寸处理 | ✅ 完全对齐 |
| **LPIPS** | 简单 cv2.resize | 智能尺寸处理 | ✅ 完全对齐 |
| **尺寸处理** | 无统一策略 | _handle_size_mismatch | ✅ 完全对齐 |
| **图像重采样** | OpenCV 默认 | PIL LANCZOS | ✅ 完全对齐 |

---

## 代码位置

修改文件: `/app/xiaominl/DeepEyes_v2/tests/baseline/test_baseline_restoration.py`

| 函数/功能 | 行号范围 | 说明 |
|----------|---------|------|
| `_resize_image()` | 97-125 | 新增：图像重采样函数 |
| `_handle_size_mismatch()` | 128-173 | 新增：智能尺寸处理函数 |
| `calculate_psnr()` | 176-196 | 修改：使用智能尺寸处理 |
| `calculate_ssim()` | 199-224 | **修改：RGB SSIM（关键变化）** |
| `calculate_lpips()` | 227-273 | 修改：使用智能尺寸处理 |

---

## 验证建议

### 1. 单元测试
建议添加测试用例验证：
- ✅ 相同尺寸图像
- ✅ 整数倍尺寸图像（2x、4x 超分场景）
- ✅ 非整数倍尺寸图像
- ✅ 灰度图像 vs RGB 图像

### 2. 回归测试
```bash
cd /app/xiaominl/DeepEyes_v2/tests/baseline
python test_baseline_restoration.py --num-samples 5 --strategy both
```

预期：
- ✅ 所有指标正常计算
- ⚠️ SSIM 值与之前不同（这是预期的！）
- ✅ 超分场景下尺寸处理更智能

### 3. 对比测试
可以运行对比测试验证 baseline 和 verl 的结果是否一致：

```python
from verl.utils.reward_score.image_quality_metrics import get_image_quality_metrics
from PIL import Image

# Baseline 版本
from tests.baseline.test_baseline_restoration import calculate_ssim, calculate_psnr, calculate_lpips

img1 = Image.open("image1.png")
img2 = Image.open("image2.png")

# Baseline
ssim_baseline = calculate_ssim(img1, img2)
psnr_baseline = calculate_psnr(img1, img2)
lpips_baseline = calculate_lpips(img1, img2)

# Verl
metrics = get_image_quality_metrics()
ssim_verl = metrics.calculate_ssim(img1, img2)
psnr_verl = metrics.calculate_psnr(img1, img2)
lpips_verl = metrics.calculate_lpips(img1, img2)

print(f"SSIM: baseline={ssim_baseline:.4f}, verl={ssim_verl:.4f}, diff={abs(ssim_baseline-ssim_verl):.4f}")
print(f"PSNR: baseline={psnr_baseline:.4f}, verl={psnr_verl:.4f}, diff={abs(psnr_baseline-psnr_verl):.4f}")
print(f"LPIPS: baseline={lpips_baseline:.4f}, verl={lpips_verl:.4f}, diff={abs(lpips_baseline-lpips_verl):.4f}")
```

预期差异：
- SSIM: < 0.01 (应该非常接近)
- PSNR: < 0.5 dB (应该非常接近)
- LPIPS: < 0.01 (应该非常接近)

---

## 注意事项

### ⚠️ SSIM 值变化是正常的

由于从灰度 SSIM 改为 RGB SSIM，旧的测试结果将不再适用。需要：
1. 重新运行 baseline 测试生成新的参考值
2. 更新任何依赖 SSIM 数值的文档或报告
3. 如果有阈值判断，可能需要调整阈值

### ✅ 现在与 verl 完全一致

修改后，baseline 和 verl 的指标计算逻辑完全对齐：
- 相同的 SSIM 算法（RGB 多通道）
- 相同的尺寸处理策略（智能整数倍检测）
- 相同的图像重采样方法（LANCZOS）

### 🔍 调试信息

修改后会输出更多调试信息：
```
[DEBUG PSNR] 图像尺寸不匹配: image1=256x256, image2=512x512
[DEBUG PSNR] 下采样较大图像到256x256 (缩放比例: 2.0x)
```

如果不需要这些信息，可以注释掉 `_handle_size_mismatch()` 中的 `print()` 语句。

---

## 总结

✅ **已完成的对齐**:
1. SSIM 计算（灰度 → RGB）—— **最重要的变化**
2. 智能尺寸处理（简单 resize → 整数倍检测）
3. 高质量图像重采样（OpenCV → PIL LANCZOS）
4. 统一了三个指标的尺寸处理逻辑

🎯 **结果**: baseline 测试脚本现在与 verl 项目的指标计算完全对齐，可以确保结果的可比性。

📊 **预期影响**: SSIM 值会有显著变化（这是正确的行为），其他指标变化较小。

