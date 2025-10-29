# GT原图索引不匹配问题说明

## 🔴 问题示例

### 当前情况（如果有Bug）

```python
actual_size = 32
sampling_params.n = 8
batch_size估计 = 32 // 8 = 4

saved_extra_info_list = [
    extra_info_0,  # 样本0，包含GT (1016, 880)
    extra_info_1,  # 样本1，包含GT (800, 900)
    extra_info_2,  # 样本2，包含GT (796, 888)
    extra_info_3,  # 样本3
    ...
    extra_info_31  # 样本31
]
```

### 构建original_images时（第803-842行）

**旧代码**（Bug）:
```python
for i in range(32):
    extra_info = saved_extra_info_list[i]  # 直接用i
    original_images[i] = extra_info['original_image']

结果:
  original_images[0] = GT_0 (1016, 880)
  original_images[1] = GT_1 (800, 900)
  original_images[2] = GT_2 (796, 888)
  ...
```

### 添加extra_info时（第869-877行）

**有interleave**:
```python
for i in range(32):
    orig_idx = i // 8  # interleave逻辑
    extra_info[i] = saved_extra_info_list[orig_idx]

结果:
  i=0: orig_idx=0 → extra_info_0
  i=1: orig_idx=0 → extra_info_0
  i=2: orig_idx=0 → extra_info_0  ← 还是extra_info_0！
  ...
  i=7: orig_idx=0 → extra_info_0
  i=8: orig_idx=1 → extra_info_1
  ...
```

### Reward计算时

```python
样本索引2:
  image_history[2] = 样本2的复原图 (512, 438)  ✓
  
  # 从extra_info[2]获取GT
  extra_info[2] → 是样本0的extra_info（因为2//8=0）
  → 但会读取original_images[2]？
  
  如果从extra_info获取:
    GT = 样本0的GT (1016, 880)  ✗ 错误！
  
  如果从original_images获取:
    GT = original_images[2] = 样本2的GT (796, 888)  ？
```

---

## 🔍 实际情况需要验证

### 关键问题

**Reward计算时，GT从哪里来？**

查看 `image_restoration.py`:
```python
# 第808-812行
original_image_data = extra_info.get('original_image', None)
```

**GT是从extra_info中获取的！**

所以如果extra_info索引错误，GT就会错位！

---

## ✅ 我的修复

### 修复代码（第803-842行）

```python
# 检测是否需要interleave
needs_interleave = (
    len(saved_extra_info_list) * sampling_params.n == expected_size 
    if sampling_params.n > 1 
    else False
)

for i in range(expected_size):
    # 统一使用orig_idx逻辑
    if needs_interleave:
        orig_idx = i // sampling_params.n
    else:
        orig_idx = i
    
    # 从extra_info中获取original_image
    extra_info = saved_extra_info_list[orig_idx]
    original_img = extra_info['original_image']
```

**这样original_images和extra_info使用相同的索引逻辑！** ✅

---

## 🎯 验证方法

### 查看新的调试日志

```bash
# 运行训练
# 查看日志
grep "needs_interleave" logs/*.log

# 应该看到
[DEBUG GT] needs_interleave=False  # 或True
[DEBUG GT] i=0, orig_idx=0
```

### 检查尺寸匹配是否改善

**如果修复成功**:
```
之前: (512, 438) vs (796, 888)  ← GT来自其他样本
现在: (512, 438) vs (1016, 880)  ← GT来自正确样本
      如果SR×2: (256, 219) × 2 = (512, 438)
      GT应该是: (256, 219) × 4 = (1024, 876) ≈ (1016, 880) ✓
```

---

## 📝 总结

### 是的，很可能是索引不匹配！

**Bug**:
- `original_images`提取时：没有interleave逻辑
- `extra_info`添加时：有interleave逻辑
- 结果：GT原图对应错误

**修复**:
- 统一两者的索引逻辑
- 根据长度自动检测是否需要interleave
- 确保复原图和GT来自同一个样本

---

**重新运行训练，查看是否修复！** 🔍

