# 工具API测试结果 - 重大发现

## 🎯 测试结果

### 工具API完全不改变尺寸！

```
测试工具: restormer_deraining, scunet_real_denoising_gan

测试尺寸1: (924, 956)  ← 不能被8整除(956%8=4)
  输入: (924, 956)
  输出: (924, 956)  ✅ 完全相同！

测试尺寸2: (800, 804)  ← 不能被8整除(804%8=4)
  输入: (800, 804)
  输出: (800, 804)  ✅ 完全相同！

测试尺寸3: (1024, 1020)  ← 不能被8整除(1020%8=4)
  输入: (1024, 1020)
  输出: (1024, 1020)  ✅ 完全相同！
```

**结论**: **工具API不做任何crop或padding！**

---

## 🔍 那么956→952的变化从哪来？

### 可能的来源

#### 来源1: 数据加载时的fetch_image

```python
# rl_dataset.py 第170-173行
images = [process_image(image)]  # ← 调用fetch_image
multi_modal_data["image"] = images
```

**process_image内部**:
```python
def process_image(image):
    return fetch_image(image)  # ← 可能padding/crop
```

#### 来源2: 初始化时保存的是fetch后的

```python
# parallel_env.py 第1507行
image_history = [deepcopy(multi_modal_data)]  # ← multi_modal_data经过fetch_image

# 如果multi_modal_data是(924, 952) fetch后的
# 那么image_history[0]就是(924, 952)
```

#### 来源3: GT原图是未处理的bytes

```python
# extra_info['original_image'] = 原始bytes
# 转为PIL: (924, 956)  ← 原始尺寸，未fetch
```

---

## 📊 推测的完整数据流

```
数据集中:
  退化图bytes → PIL → (924, 956)
  GT原图bytes → PIL → (924, 956)

数据加载(rl_dataset.py):
  退化图 → process_image → fetch_image → (924, 952)?  ← 可能被处理
  存为multi_modal_data

训练时初始化(parallel_env.py):
  image_history[0] = multi_modal_data = (924, 952)?

工具执行:
  输入: (924, 952)
  工具API: 保持不变
  输出: (924, 952)
  保存到history: (924, 952)

Reward计算:
  复原图: image_history[-1] = (924, 952)
  GT: extra_info['original_image'] bytes → PIL → (924, 956)
  
  差异: 4像素 ← 来自fetch_image！
```

---

## 🔧 下次batch会显示

```bash
[DEBUG GT SIZE] Sample 0: image_history长度 = 2  ← 关键！
[DEBUG GT SIZE] Sample 0: 退化图尺寸(初始) = (924, 952)  ← 如果是952，说明fetch_image影响了
[DEBUG GT SIZE] Sample 0: 复原图尺寸(最后) = (924, 952)
[DEBUG GT SIZE] Sample 0: GT原图尺寸 = (924, 956)  ← 原始bytes
```

**如果初始退化图就是(924, 952)**:
→ 说明multi_modal_data在数据加载时被fetch_image处理了
→ 这不是工具的问题，是数据加载的问题

---

## ✅ 重要结论

1. **✅ 工具API完全正常** - 不改变任何尺寸
2. **⚠️ 956→952可能来自数据加载时的fetch_image**
3. **✅ GT索引修复已生效** - GT和复原图来自同一样本
4. **⏳ 等待新batch的详细日志** - 确认exact原因

---

**等待新batch显示image_history长度和初始退化图尺寸！** 🔍

