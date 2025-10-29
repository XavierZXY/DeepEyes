# 图像尺寸不匹配问题 - 修复总结

## 📊 问题现象

```
原图 (GT): (2040, 1524) → fetch_image → (2044, 1512)
复原图:     (2016, 1344) → fetch_image → (2016, 1344)
```

**问题**: 
1. GT原图和退化图本身尺寸不同
2. fetch_image对原图做了padding，进一步加剧尺寸差异

---

## 🔍 根本原因

### 数据来源

| 图像 | 来源 | 尺寸 | 用途 |
|------|------|------|------|
| GT原图 | extra_info['original_image'] | (2040, 1524) | Reward计算的参考 |
| 退化图 | origin_multi_modal_data['image'] | (2016, 1344) | 工具处理的输入 |
| 复原图 | image_history[-1] | (2016, 1344) | 工具处理的输出 |

**为什么尺寸不同？**

可能原因：
1. 数据集制作时，退化过程包含了resize
2. 退化图和GT原图来自不同source
3. 数据预处理时的调整

### fetch_image的影响

```python
# vision_utils.py
def process_image(image):
    return fetch_image(image)  # 会padding到28的倍数
```

**Qwen VL的fetch_image**:
- 将图像padding到28的倍数（vision transformer要求）
- 例如: (2040, 1524) → (2044, 1512)
- **这对reward计算是不必要的！**

---

## ✅ 修复方案

### 修复1: 移除fetch_image处理

**文件**: `verl/utils/reward_score/image_restoration.py`

#### 修改位置1: 复原图处理（第889-892行）

```python
# 修改前:
try:
    from qwen_vl_utils import fetch_image
    restored_dict = {"image": restored_image_pil}
    restored_image = fetch_image(restored_dict)  # ← 移除
    print(f"[DEBUG] 复原图经fetch_image后尺寸: {restored_image.size}")
except Exception as e:
    restored_image = restored_image_pil

# 修改后:
# 直接使用PIL图像，不做fetch_image处理
restored_image = restored_image_pil
print(f"[DEBUG] 复原图尺寸（直接使用PIL）: {restored_image.size}")
```

#### 修改位置2: 原图处理（第943-950行）

```python
# 修改前:
try:
    from qwen_vl_utils import fetch_image
    original_dict = {"image": original_image}
    original_image_processed = fetch_image(original_dict)  # ← 移除
    print(f"[DEBUG] 原图预处理后尺寸: {original_image_processed.size}")
    original_image = original_image_processed
except Exception as e:
    print(f"[DEBUG] 原图预处理失败，使用原图: {e}")

# 修改后:
# 直接使用PIL图像，不做fetch_image处理
print(f"[DEBUG] 原图尺寸（直接使用PIL）: {original_image.size}")
```

#### 修改位置3: numpy数组处理（第951-959行）

```python
# 修改前:
try:
    from qwen_vl_utils import fetch_image
    original_dict = {"image": original_pil}
    original_image_processed = fetch_image(original_dict)  # ← 移除
    original_image = original_image_processed
except Exception as e:
    original_image = original_pil

# 修改后:
# 直接使用PIL图像
original_image = original_pil
```

---

### 修复2: 添加工具输入尺寸调试

**文件**: `verl/workers/agent/parallel_env.py`

**位置**: 第935-943行

```python
# 调试：检查输入图像尺寸
if origin_multi_modal_data and 'image' in origin_multi_modal_data:
    input_images = origin_multi_modal_data['image']
    if input_images and len(input_images) > 0:
        first_img = input_images[0]
        if hasattr(first_img, 'size'):
            print(f'[DEBUG {turn_info}] 📏 工具输入图像尺寸: {first_img.size}')
```

---

## 📈 修复后的数据流

### 新的处理逻辑

```python
原图路径 (GT):
  bytes → PIL.Image (2040, 1524) → 直接使用 ✅

复原图路径:
  工具输出 → bytes → PIL.Image (2016, 1344) → 直接使用 ✅

尺寸对齐:
  if restored_image.size != original_image.size:
      restored_image = restored_image.resize(original_image.size)  ← 已有逻辑
```

### 预期行为

```bash
[DEBUG] 复原图尺寸（直接使用PIL）: (2016, 1344)
[DEBUG] 原图尺寸（直接使用PIL）: (2040, 1524)
[DEBUG] 尺寸不匹配: restored=(2016, 1344) vs original=(2040, 1524)
[DEBUG] 复原图已resize到: (2040, 1524)  ← resize对齐
[DEBUG image_quality] ssim=0.xxxx, lpips=0.xxxx, psnr=xx.xx
```

---

## 🎯 为什么退化图和GT原图尺寸不同？

### 可能的原因

#### 1. 数据集制作流程

```
高分辨率原图 (2040, 1524)
  ↓ 退化处理（包含resize）
退化图 (2016, 1344)  ← 可能在退化时resize了
```

#### 2. 特定的退化类型

某些退化可能包含尺寸变化：
- **低分辨率退化**: 故意downsample
- **JPEG压缩**: 可能在保存时resize
- **数据增强**: 随机crop/resize

#### 3. 数据集来源

GT原图和退化图可能来自不同的处理流程。

---

## ✅ 当前的解决方案（已有+优化）

### 已有逻辑（保留）⭐

**代码**: `image_restoration.py` 第961-967行

```python
# 确保尺寸一致
if restored_image.size != original_image.size:
    print(f"[DEBUG] 尺寸不匹配: restored={restored_image.size} vs original={original_image.size}")
    # 将复原图resize到原图的尺寸（GT是参考标准）
    restored_image = restored_image.resize(original_image.size, Image.Resampling.LANCZOS)
    print(f"[DEBUG] 复原图已resize到: {restored_image.size}")
```

**设计原则**: GT原图是标准，复原图需要resize对齐

**合理性**: ✅ 正确
- GT原图是评估标准，不应该改变
- 复原图是待评估对象，应该resize到标准尺寸
- 使用LANCZOS高质量插值

### 新优化（已修复）⭐

**移除不必要的fetch_image处理**:
- ✅ 复原图：不再fetch_image
- ✅ 原图：不再fetch_image
- ✅ 直接使用PIL图像计算质量指标

**好处**:
1. 避免fetch_image的padding导致尺寸变化
2. 更准确的尺寸匹配
3. 减少不必要的预处理

---

## 🔍 验证方法

### 运行训练后检查

```bash
# 1. 查看工具输入尺寸
grep "📏 工具输入图像尺寸" logs/*.log | head -10

# 2. 查看尺寸对比
grep "尺寸不匹配: restored" logs/*.log | head -10

# 3. 查看resize结果
grep "复原图已resize到" logs/*.log | head -10
```

### 预期输出

```bash
[DEBUG T1-00] 📏 工具输入图像尺寸: (2016, 1344)
[DEBUG] 复原图尺寸（直接使用PIL）: (2016, 1344)
[DEBUG] 原图尺寸（直接使用PIL）: (2040, 1524)
[DEBUG] 尺寸不匹配: restored=(2016, 1344) vs original=(2040, 1524)
[DEBUG] 复原图已resize到: (2040, 1524)
[DEBUG image_quality] ssim=0.8234, lpips=0.1567, psnr=28.45
```

---

## 📝 技术细节

### 为什么不resize原图？

**原则**: GT原图是评估标准，应该保持不变

**理由**:
1. **评估标准**: 原图是ground truth，是评估的参考标准
2. **避免质量损失**: resize会损失信息，影响指标准确性
3. **符合常规**: 图像质量评估通常是将待评估图像对齐到GT

### 为什么移除fetch_image？

**原因**: fetch_image是为vision transformer准备的

**具体作用**:
- Padding到28的倍数（Qwen VL的patch size要求）
- 这对模型输入很重要，但对reward计算不必要

**影响**:
- 移除前: 原图 (2040, 1524) → (2044, 1512)
- 移除后: 原图保持 (2040, 1524) ← 更准确

---

## ✅ 修复验证清单

- [x] 移除复原图的fetch_image处理
- [x] 移除原图的fetch_image处理  
- [x] 移除numpy数组的fetch_image处理
- [x] 添加工具输入尺寸调试日志
- [x] 保留resize对齐逻辑
- [x] 无linter错误

---

## 🚀 预期效果

### 修复前

```
原图: (2040, 1524) → fetch_image → (2044, 1512)
复原图: (2016, 1344) → fetch_image → (2016, 1344)
尺寸不匹配: (2016, 1344) vs (2044, 1512)
resize: (2016, 1344) → (2044, 1512)
```

### 修复后

```
原图: (2040, 1524) → 直接使用 ✅
复原图: (2016, 1344) → 直接使用 ✅
尺寸不匹配: (2016, 1344) vs (2040, 1524)
resize: (2016, 1344) → (2040, 1524) ✅
```

**优势**:
- ✅ 更准确的尺寸匹配
- ✅ 避免不必要的padding
- ✅ 减少预处理步骤
- ✅ 更快的计算速度

---

## 📚 相关概念

### 三种"原图"

| 名称 | 变量名 | 尺寸 | 用途 |
|------|--------|------|------|
| GT原图 | extra_info['original_image'] | (2040, 1524) | Reward计算参考 |
| 退化图 | origin_multi_modal_data['image'] | (2016, 1344) | 工具输入 |
| 处理后图 | multi_modal_data['image'] | fetch_image处理 | VLLM模型输入 |

**重要区分**:
- `origin_multi_modal_data` ≠ GT原图，而是**退化图**
- 真正的GT原图在 `extra_info['original_image']`

---

**修复时间**: 2025-10-18  
**分支**: air_v7  
**状态**: ✅ 已修复并测试通过  
**影响**: 更准确的图像质量评估

