# 尺寸不匹配问题完整解释

## 🎯 核心发现

**工具执行时**:
```
✅ 所有工具都保持尺寸或按整数倍缩放（SR工具）
```

**Reward计算时**:
```
⚠️  复原图 vs GT原图：尺寸不匹配
例如: (512, 480) vs (804, 1020)
```

**结论**: 工具没有问题，不匹配发生在**复原图与GT对比时**！

---

## 📊 两个阶段的区别

### 阶段1: 工具链执行（工具内部）

```python
# 检测点：工具输入 vs 工具输出
工具输入: (256, 240)
  ↓ swinir_super_resolution(scale=2)
工具输出: (512, 480)

检查: (512, 480) vs (256, 240)
比例: 2.0x, 2.0x
✅ 整数倍！工具正常！
```

**我的检测报告**: ✅ 所有工具都保持尺寸或按整数倍缩放

### 阶段2: Reward计算（复原图 vs GT）

```python
# 检测点：最终复原图 vs GT原图
复原图: (512, 480)  ← SR×2后的结果
GT原图: (804, 1020)  ← 数据集中的真实原图

检查: (512, 480) vs (804, 1020)
比例: 1.570x, 2.125x
❌ 不是整数倍！宽高比例不一致！
```

**日志显示**: 尺寸不匹配，需要resize对齐

---

## 🔍 为什么会不匹配？

### 根本原因：数据集的尺寸关系不完美

```
理想情况（完美4倍）:
  GT原图: (804, 1020)
  退化图(0.25倍): (201, 255)  ← 精确1/4
  SR×2后: (402, 510)  ← 精确1/2
  SR×2再次: (804, 1020)  ← 完美匹配GT！

实际情况（数据集）:
  GT原图: (804, 1020)
  退化图(约0.32倍): (256, 240)  ← 不是精确1/4！
  SR×2后: (512, 480)  ← 不匹配GT！
  
  比例: 
    width: 804/512 = 1.570x  ← 不是2倍
    height: 1020/480 = 2.125x  ← 接近2倍但不精确
```

### 为什么数据集会这样？

**可能原因**:

1. **数据集制作时的随机crop/resize**
   ```python
   # 数据增强
   original = load_image(path)  # (804, 1020)
   degraded = random_resize(original, scale_range=[0.2, 0.35])
   # 结果: (256, 240) ← 随机，不是精确0.25
   ```

2. **不同的退化流程**
   ```python
   # low resolution退化可能这样实现
   target_size = random.randint(200, 300)  # 随机目标尺寸
   degraded = resize_with_aspect_ratio(original, target_size)
   # 结果: 尺寸不是原图的精确倍数
   ```

3. **数据集混合来源**
   ```python
   # GT原图来自一个source
   # 退化图来自另一个处理流程
   # 尺寸关系不完美
   ```

---

## 📈 具体案例分析

### 案例: (512, 480) vs (804, 1020)

```
数据集中:
  GT原图: (804, 1020)
  退化图(实际): (256, 240)  ← 不是精确的(201, 255)

训练时:
  退化图: (256, 240)
  ↓ SR×2
  复原图: (512, 480)
  
Reward计算:
  复原图: (512, 480)
  GT: (804, 1020)
  
  比例: 1.570x, 2.125x  ← 不匹配！
  
  原因: 
    804/512 = 1.570 (不是2.0)
    1020/480 = 2.125 (接近2.0)
  
  说明: 宽度方向的缩放不是2倍
       可能退化图的宽度不是GT的1/4
```

---

## ✅ 当前的处理（正确）

**代码**: `image_restoration.py` 第963-967行

```python
if restored_image.size != original_image.size:
    # 将复原图resize到GT尺寸
    restored_image = restored_image.resize(
        original_image.size, 
        Image.Resampling.LANCZOS
    )
```

**这个逻辑会处理**:
- ✅ SR×2后不完美匹配 → resize对齐
- ✅ SR×4后不完美匹配 → resize对齐
- ✅ 任何尺寸差异 → resize对齐

---

## 🎯 验证数据集

让我检查一下数据集中退化图和GT的实际尺寸关系：

<function_calls>
<invoke name="run_terminal_cmd">
<parameter name="command">cd /app/xiaominl/DeepEyes_v2 && python3 << 'EOF'
import pandas as pd
from PIL import Image
import io

df = pd.read_parquet('/app/datasets/air_v13/shards/shard-train-000000.parquet')

print("="*80)
print("检查数据集中low resolution样本的尺寸精确性")
print("="*80)

perfect_4x = 0
imperfect = []

for idx in range(len(df)):
    row = df.iloc[idx]
    
    if 'low resolution' not in row['env_name'].lower():
        continue
    
    try:
        degraded_img_data = row['images'][0]
        if isinstance(degraded_img_data, dict) and 'bytes' in degraded_img_data:
            degraded_img = Image.open(io.BytesIO(degraded_img_data['bytes']))
        else:
            continue
        
        extra = row['extra_info']
        if not extra or 'original_image' not in extra or not extra['original_image']:
            continue
            
        orig_data = extra['original_image']
        if isinstance(orig_data, bytes):
            orig_img = Image.open(io.BytesIO(orig_data))
        else:
            continue
        
        # 检查是否是精确的4倍
        expected_degraded = (orig_img.size[0] // 4, orig_img.size[1] // 4)
        
        if degraded_img.size == expected_degraded:
            perfect_4x += 1
        else:
            # SR×2后的尺寸
            sr2_size = (degraded_img.size[0] * 2, degraded_img.size[1] * 2)
            
            imperfect.append({
                'idx': idx,
                'degraded': degraded_img.size,
                'expected': expected_degraded,
                'gt': orig_img.size,
                'sr2': sr2_size,
                'diff_from_gt': (sr2_size[0] - orig_img.size[0], sr2_size[1] - orig_img.size[1])
            })
    except:
        continue

print(f"\n统计结果:")
print(f"  ✅ 精确4倍关系: {perfect_4x} 个")
print(f"  ⚠️  不精确: {len(imperfect)} 个")

if imperfect:
    print(f"\n不精确案例（前10个）:")
    print("-"*80)
    for i, case in enumerate(imperfect[:10], 1):
        print(f"\n样本 {case['idx']}:")
        print(f"  GT原图: {case['gt']}")
        print(f"  预期退化图(0.25x): {case['expected']}")
        print(f"  实际退化图: {case['degraded']}")
        print(f"  差异: ({case['degraded'][0]-case['expected'][0]}, {case['degraded'][1]-case['expected'][1]})")
        print(f"  SR×2后: {case['sr2']}")
        print(f"  与GT差异: {case['diff_from_gt']}")

EOF

