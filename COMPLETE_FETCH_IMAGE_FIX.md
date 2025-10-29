# fetch_image污染问题 - 完整修复

## 🎯 核心问题

**用户发现**: `image_history` 保存的是经过 `fetch_image` 处理后的图像，导致与GT原图尺寸不匹配！

---

## 🔍 问题根源

### Bug #1: _preprocess_multi_modal_inputs 修改原始数据

```python
# parallel_env.py 第1111行
prompt_str_vllm, obs_token_ids_model, mm_inputs = _preprocess_multi_modal_inputs(
    prompt_str, processor, **final_tool_result  # ← 传入multi_modal_data
)

# _preprocess_multi_modal_inputs 内部（第264, 281行）
input_mm_data = kwargs.get("multi_modal_data", ...)  # ← 获取引用
input_mm_data["image"] = [process_image(img) for ...]  # ← 修改原始数据！

# process_image 调用 fetch_image
def process_image(image):
    return fetch_image(image)  # ← padding到28的倍数
```

**后果**: `final_tool_result["multi_modal_data"]` 被修改，保存的是fetch后的图像！

### Bug #2: Reward计算中使用fetch_image

**文件**: `image_restoration.py`

```python
# 原图
original_img → fetch_image → (2044, 1512)  # padding

# 复原图  
restored_img → fetch_image → (2016, 1344)

# 尺寸不匹配！
```

### Bug #3: tracking_image_utils中使用fetch_image

**文件**: `tracking_image_utils.py` 第1784-1801行

```python
original_img = fetch_image(original_dict)  # ← 也在用fetch_image
```

---

## ✅ 完整修复方案

### 修复1: 保存原始PIL图像（parallel_env.py）

**位置**: 第1104-1123行

```python
# 🔥 关键修复：在_preprocess之前保存原始数据
original_multi_modal_data_for_reward = deepcopy(
    final_tool_result.get("multi_modal_data", {})
)
print(f'💾 保存原始multi_modal_data用于reward计算')

# 调用_preprocess（会修改final_tool_result）
prompt_str_vllm, obs_token_ids_model, mm_inputs = _preprocess_multi_modal_inputs(
    prompt_str, processor, **final_tool_result
)

# 返回时包含两份数据
tool_result_info = {
    "multi_modal_data": ...,  # fetch后（给VLLM）
    "multi_modal_data_for_reward": original_multi_modal_data_for_reward  # 原始（给Reward）
}
```

### 修复2: 优先保存原始PIL到历史

**位置**: 第1286-1295行, 第1322-1331行

```python
# 🔥 优先使用原始PIL图像
if 'multi_modal_data_for_reward' in obs:
    # 使用原始PIL（工具输出，未经fetch_image）
    self.multi_modal_data_history_list[valid_idx].append(
        deepcopy(obs['multi_modal_data_for_reward'])
    )
    print(f'💾 保存原始PIL图像到历史')
elif 'multi_modal_data' in obs:
    # Fallback: 兼容旧逻辑
    self.multi_modal_data_history_list[valid_idx].append(
        deepcopy(obs['multi_modal_data'])
    )
    print(f'⚠️  使用fetch后的图像（fallback）')
```

### 修复3: Reward计算移除fetch_image（image_restoration.py）

**位置**: 第889-892行, 第943-950行

```python
# 修改前:
restored_image = fetch_image(restored_dict)

# 修改后:
restored_image = restored_image_pil  # 直接使用PIL
print(f"[DEBUG] 复原图尺寸（直接使用PIL）: {restored_image.size}")

# 原图同样移除fetch_image
original_image = original_image  # 直接使用PIL
print(f"[DEBUG] 原图尺寸（直接使用PIL）: {original_image.size}")
```

### 修复4: tracking_image_utils移除fetch_image

**位置**: 第1784-1797行

```python
# 修改前:
original_img = fetch_image(original_dict)
print(f"Sample {idx}: original_img size after fetch_image: ...")

# 修改后:
# 直接使用PIL图像
if isinstance(original_img_raw, Image.Image):
    original_img = original_img_raw
elif isinstance(original_img_raw, bytes):
    original_img = Image.open(io.BytesIO(original_img_raw))
else:
    original_img = original_img_raw

print(f"Sample {idx}: original_img size (直接使用PIL): {original_img.size}")
```

---

## 📊 修复前后对比

### 修复前（Bug）❌

```
工具输出: PIL (2016, 1344)
  ↓
被_preprocess修改
  ↓
fetch_image: (2016, 1344) → 可能padding
  ↓
保存到history: fetch后
  ↓
Reward计算:
  原图: PIL (2040, 1524) → fetch → (2044, 1512)
  复原图: fetch后
  ❌ 尺寸对齐不准确
```

### 修复后（Correct）✅

```
工具输出: PIL (2016, 1344)
  ↓ (分两路)
  
路径1 (VLLM):
  deepcopy → _preprocess → fetch_image
  ↓
  obs["multi_modal_data"]
  
路径2 (Reward):
  deepcopy → 直接保存
  ↓
  obs["multi_modal_data_for_reward"]
  ↓
  image_history: 原始PIL (2016, 1344)
  ↓
Reward计算:
  原图: PIL (2040, 1524) → 直接使用 ✅
  复原图: PIL (2016, 1344) → 直接使用 ✅
  ✅ 尺寸对齐准确
```

---

## 🎉 修复效果

### 预期日志输出

```bash
# 工具执行
[DEBUG T1-00] 💾 保存原始multi_modal_data用于reward计算
[DEBUG T1-00] 🔄 预处理multi_modal输入...
[DEBUG T1-00] ✅ 预处理完成，已保存原始图像用于reward

# 历史保存
[DEBUG step 1-00] 💾 保存原始PIL图像到历史  ← 应该看到这个

# Reward计算（image_restoration.py）
[DEBUG] 复原图尺寸（直接使用PIL）: (2016, 1344)
[DEBUG] 原图尺寸（直接使用PIL）: (2040, 1524)
[DEBUG] 尺寸不匹配: restored=(2016, 1344) vs original=(2040, 1524)
[DEBUG] 复原图已resize到: (2040, 1524)

# Tracking（tracking_image_utils.py）
[DEBUG REF METRICS] Sample 0: original_img size (直接使用PIL): (2040, 1524)
[DEBUG REF METRICS] Sample 0: restored_img size: (2016, 1344)
```

**不应该再看到**:
- ❌ `after fetch_image`
- ❌ `(2044, 1512)` 这种padding后的尺寸

---

## 🔍 验证方法

```bash
# 1. 检查是否保存了原始PIL
grep "💾 保存原始PIL图像到历史" logs/*.log | wc -l

# 2. 不应该有fallback
grep "⚠️  使用fetch后的图像" logs/*.log | wc -l

# 3. 不应该有fetch_image
grep "after fetch_image" logs/*.log | wc -l

# 4. 检查尺寸对齐
grep "复原图已resize到" logs/*.log | head -10
```

**健康指标**:
- `保存原始PIL` 次数 > 0  ✅
- `使用fetch后的` 次数 = 0  ✅
- `after fetch_image` 次数 = 0  ✅

---

## 📋 修复清单

### 修复文件列表

| 文件 | 修复内容 | 行数 |
|------|---------|------|
| `parallel_env.py` | 保存原始PIL副本 | 1107 |
| `parallel_env.py` | 添加multi_modal_data_for_reward | 1122 |
| `parallel_env.py` | 优先保存原始PIL（单线程） | 1288-1295 |
| `parallel_env.py` | 优先保存原始PIL（多线程） | 1324-1331 |
| `image_restoration.py` | 移除复原图fetch_image | 889-892 |
| `image_restoration.py` | 移除原图fetch_image | 943-950 |
| `tracking_image_utils.py` | 移除原图fetch_image | 1784-1797 |

### 核心改进

1. ✅ **数据隔离**: VLLM用fetch后的，Reward用原始的
2. ✅ **避免污染**: deepcopy在_preprocess之前
3. ✅ **统一处理**: 三个地方都移除了fetch_image
4. ✅ **向后兼容**: 有fallback机制

---

## 🚀 预期改进

### 尺寸匹配

修复前:
```
尺寸不匹配: (2016, 1344) vs (2044, 1512)  ← padding导致
```

修复后:
```
尺寸不匹配: (2016, 1344) vs (2040, 1524)  ← 真实尺寸差异
```

### 质量评估

- ✅ 更准确的SSIM（避免padding像素干扰）
- ✅ 更准确的LPIPS（特征对齐更好）
- ✅ 更准确的PSNR（像素对齐更准确）

---

## 💡 为什么会有尺寸差异？

### 情况1: 数据集本身

```
GT原图: (2040, 1524)  ← 高分辨率原图
退化图: (2016, 1344)  ← 退化时可能resize了
```

**可能原因**:
- 某些退化包含resize（例如：低分辨率退化）
- 数据增强时的crop/resize
- 数据集来源不同

### 情况2: 工具改变尺寸

```
输入: (2016, 1344)
  ↓
swinir_super_resolution (scale=2)
  ↓
输出: (4032, 2688)  ← 尺寸放大
```

**处理**: resize对齐逻辑会自动处理

---

## ✅ 验证清单

- [x] parallel_env.py: 保存原始PIL副本
- [x] parallel_env.py: 优先保存原始PIL到历史
- [x] image_restoration.py: 移除fetch_image（2处）
- [x] tracking_image_utils.py: 移除fetch_image
- [x] 无linter错误
- [x] 添加详细调试日志

---

**修复完成！所有fetch_image污染已清除！** 🎉

**关键改进**:
1. ✅ VLLM和Reward使用不同的图像数据（隔离）
2. ✅ 保存工具的真实输出（原始PIL）
3. ✅ 移除所有reward相关的fetch_image
4. ✅ 更准确的质量评估

现在训练后应该能看到正确的尺寸对齐！

