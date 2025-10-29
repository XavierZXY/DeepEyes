# 图像尺寸不匹配诊断

## 📊 问题现象

```
原图 (GT, 来自数据集):       (2040, 1524)  ← extra_info['original_image']
复原图 (工具处理后):         (2016, 1344)  ← image_history[-1]
```

尺寸不匹配！

---

## 🔍 数据流分析

### 第一层：数据集中的图像

数据集parquet文件中包含：
1. **images** 列：退化后的输入图像
2. **extra_info.original_image**：未退化的GT原图

**尺寸**:
- GT原图：可能是原始高分辨率 (2040, 1524)
- 退化图：可能在退化过程中被resize (2016, 1344)

---

### 第二层：数据加载时的处理 (rl_dataset.py)

```python
# 第170-173行
origin_images = [process_raw_image(image)]      # 只转RGB，不改尺寸
images = [process_image(image)]                 # fetch_image，可能改尺寸

multi_modal_data["image"] = images              # 给模型看的
origin_multi_modal_data["image"] = origin_images  # 给工具用的
```

**功能对比**:

| 函数 | 作用 | 尺寸变化 |
|------|------|---------|
| `process_raw_image` | 只做RGB转换 | ❌ 不变 |
| `process_image` | 调用fetch_image | ⚠️ 可能变 |

**用途**:
- `origin_multi_modal_data`: 工具处理的输入
- `multi_modal_data`: VLLM模型的输入（经过processor处理）

---

### 第三层：工具处理

```python
# execute_tool_call 第948行
current_image_data = origin_multi_modal_data  # 从这里开始

# 工具链执行
for tool in tools:
    tool.reset(multi_modal_data=current_image_data, ...)
    tool_result = tool.execute(...)
    current_image_data = tool_result['multi_modal_data']  # 工具输出
```

**工具行为**:
- 大多数工具（去噪、去雨、去模糊等）：**保持输入尺寸**
- `swinir_super_resolution`：**增大尺寸** (×2, ×3, ×4)

---

### 第四层：Reward计算

```python
# image_restoration.py 第840行
restored_image_data = image_history[-1]  # 工具链最终输出

# 第808-812行
original_image_data = extra_info.get('original_image', None)  # GT原图

# 第993-997行
if restored_image.size != original_image.size:
    # 将复原图resize到原图的尺寸（GT是参考标准）
    restored_image = restored_image.resize(original_image.size, Image.Resampling.LANCZOS)
    print(f"[DEBUG] 复原图已resize到: {restored_image.size}")
```

---

## 🔍 尺寸来源追踪

### 原图 (2040, 1524)

```
数据集 parquet
  ↓
extra_info['original_image'] (bytes)
  ↓
PIL.Image (2040, 1524)  ← GT原图
  ↓
fetch_image() → (2044, 1512)  ← Qwen VL处理后（padding到28的倍数）
```

### 退化图/复原图 (2016, 1344)

```
数据集 parquet
  ↓
images列 (退化图 bytes)
  ↓
process_raw_image() → PIL.Image (2016, 1344?)  ← 退化图
  ↓
origin_multi_modal_data["image"] → (2016, 1344)
  ↓
工具处理 (保持尺寸)
  ↓
工具输出 (2016, 1344)
  ↓
image_history[-1] (2016, 1344)  ← 复原图
```

---

## 🎯 根本问题

### 问题1: 退化图本身尺寸可能不同

**可能原因**:
1. 数据集制作时，退化过程包含了resize
2. 数据集中存储的退化图和GT原图来自不同的source
3. 数据预处理时做了尺寸调整

**验证方法**:
```bash
# 运行训练，查看工具输入尺寸
grep "📏 工具输入图像尺寸" logs/*.log | head -10
```

### 问题2: fetch_image导致原图尺寸变化

```
原图: (2040, 1524) → fetch_image → (2044, 1512)
```

**原因**: Qwen VL的fetch_image会padding到28的倍数（用于vision transformer）

---

## ✅ 当前的处理逻辑（已有）

**代码位置**: `image_restoration.py` 第993-997行

```python
# 确保尺寸一致
if restored_image.size != original_image.size:
    print(f"[DEBUG] 尺寸不匹配: restored={restored_image.size} vs original={original_image.size}")
    # 将复原图resize到原图的尺寸（GT是参考标准）
    restored_image = restored_image.resize(original_image.size, Image.Resampling.LANCZOS)
    print(f"[DEBUG] 复原图已resize到: {restored_image.size}")
```

**这个逻辑是正确的！** ✅

---

## 🔧 优化建议

### 方案1: 移除fetch_image处理（推荐）⭐

**原因**: reward计算不需要vision transformer的padding

```python
# 修改 image_restoration.py 第889-897, 948-984行
# 移除对原图和复原图的fetch_image处理
# 直接使用PIL图像计算质量指标
```

<function_calls>
<invoke name="search_replace">
<parameter name="file_path">/app/xiaominl/DeepEyes_v2/verl/utils/reward_score/image_restoration.py
