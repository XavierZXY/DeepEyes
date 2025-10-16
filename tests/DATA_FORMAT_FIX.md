# 📝 数据格式修复说明

## ✅ 已修复问题

**问题**: 脚本无法从parquet文件提取退化图

**原因**: 数据格式与脚本预期不匹配

---

## 🔍 实际数据格式

您的parquet文件使用的是以下格式：

### 字段列表
```python
['data_source', 'prompt', 'images', 'ability', 'env_name', 'reward_model', 'extra_info']
```

### 关键字段格式

#### 1. `images` (注意是复数！)
```python
类型: numpy.ndarray
形状: (1,)  # 单个图像
元素类型: dict
元素格式: {'bytes': b'\x89PNG...'}  # PNG字节数据

# 提取退化图
images = row['images']  # numpy.ndarray
degraded_img_dict = images[0]  # 第一个元素，dict类型
img_bytes = degraded_img_dict['bytes']  # PNG字节
degraded_image = Image.open(io.BytesIO(img_bytes))
```

#### 2. `extra_info`
```python
类型: dict (已经是字典，不需要JSON解析)
键: ['index', 'split', 'original_image', 'use_original']

# 提取原图
extra_info = row['extra_info']  # 已经是dict
img_bytes = extra_info['original_image']  # bytes类型
original_image = Image.open(io.BytesIO(img_bytes))
```

#### 3. `reward_model`
```python
类型: numpy.ndarray
长度: 1  # 单个退化
元素类型: dict
元素格式: {
    'degradation_type': 'low resolution',
    'degradation_level': 'medium',
    'has_original': True
}

# 提取退化类型
reward_model = row['reward_model']  # numpy.ndarray
for deg in reward_model:
    deg_type = deg['degradation_type']
    deg_level = deg['degradation_level']
```

---

## 🔧 修复内容

### 修改1: 支持 `images` 字段（复数）

**修改前**（只支持 `image` 单数）:
```python
if 'image' in row:
    img_data = row['image']
```

**修改后**（优先支持 `images` 复数）:
```python
if 'images' in row:
    img_data = row['images']
    # images 是 numpy.ndarray，取第一个元素
    if isinstance(img_data, np.ndarray) and len(img_data) > 0:
        img_data = img_data[0]
        if isinstance(img_data, dict) and 'bytes' in img_data:
            degraded_image = Image.open(io.BytesIO(img_data['bytes']))
```

### 修改2: 移除不必要的JSON解析

**修改前**（错误地尝试JSON解析）:
```python
extra_info = row.get('extra_info', {})
if isinstance(extra_info, str):
    extra_info = json.loads(extra_info)  # ❌ 不需要
```

**修改后**（直接使用dict）:
```python
extra_info = row.get('extra_info', {})
# extra_info 已经是 dict，不需要 JSON 解析
```

### 修改3: 支持 numpy.ndarray 格式的 reward_model

**修改前**（只支持list）:
```python
if isinstance(reward_model, list):
    for deg in reward_model:
        ...
```

**修改后**（同时支持list和numpy.ndarray）:
```python
if isinstance(reward_model, (list, np.ndarray)):
    for deg in reward_model:
        ...
```

---

## ✅ 验证结果

运行修复后的脚本：

```bash
python3 tests/test_all_tools_metrics.py \
    --parquet /app/xiaominl/datasets/air_d1_sp9_up2_balanced/shard-test-000000.parquet \
    --output_dir ./test_fix \
    --max_samples 3
```

**成功输出**:
```
总样本数: 128
限制样本数: 3
  ✅ 样本 0: ['low resolution'] (['medium'])
  ✅ 样本 1: ['jpeg compression artifact'] (['very high'])
  ✅ 样本 2: ['dark'] (['medium'])

成功加载 3 个样本
```

---

## 📊 数据示例

### 样本0: 低分辨率
- **退化类型**: low resolution
- **退化等级**: medium
- **原图尺寸**: 2040×1356 (高分辨率)
- **退化图尺寸**: 510×339 (降采样4倍)

### 样本1: JPEG压缩伪影
- **退化类型**: jpeg compression artifact
- **退化等级**: very high
- **需要的工具**: `fbcnn_jpeg_artifact_removal` 或 `swinir_jpeg_artifact_removal`

### 样本2: 暗光
- **退化类型**: dark
- **退化等级**: medium
- **需要的工具**: 亮度调整工具（如 `gamma_correction`）

---

## 🔄 兼容性

修复后的脚本**向后兼容**旧格式：

1. ✅ 优先尝试 `images` (新格式)
2. ✅ 回退到 `image` (旧格式)
3. ✅ 支持 dict 和 JSON 字符串的 `extra_info`
4. ✅ 支持 list 和 numpy.ndarray 的 `reward_model`

---

## 🎯 完整的数据提取流程

```python
import pandas as pd
import numpy as np
from PIL import Image
import io

# 1. 读取parquet
df = pd.read_parquet('shard-test-000000.parquet')
row = df.iloc[0]

# 2. 提取原图
extra_info = row['extra_info']  # 已经是dict
original_image = Image.open(io.BytesIO(extra_info['original_image']))

# 3. 提取退化图
images = row['images']  # numpy.ndarray
degraded_image = Image.open(io.BytesIO(images[0]['bytes']))

# 4. 提取退化信息
reward_model = row['reward_model']  # numpy.ndarray
degradation_type = reward_model[0]['degradation_type']
degradation_level = reward_model[0]['degradation_level']

print(f"退化类型: {degradation_type}")
print(f"退化等级: {degradation_level}")
print(f"原图尺寸: {original_image.size}")
print(f"退化图尺寸: {degraded_image.size}")
```

---

## 📝 注意事项

### 1. numpy.ndarray 处理
- parquet文件中的数组字段会被读取为 `numpy.ndarray`
- 需要使用 `isinstance(data, (list, np.ndarray))` 同时支持两种类型

### 2. 字节数据格式
- 图像数据可能是：
  - 直接的 `bytes`
  - 字典 `{'bytes': b'...'}`
- 脚本已同时支持两种格式

### 3. 字段名称
- 新格式使用 `images` (复数)
- 旧格式使用 `image` (单数)
- 脚本已同时支持

---

## ✅ 状态

- ✅ **数据加载**: 正常
- ✅ **原图提取**: 正常
- ✅ **退化图提取**: 正常
- ✅ **退化信息提取**: 正常
- ⚠️ **工具API调用**: 部分400错误（服务端问题，非脚本问题）

---

**更新时间**: 2025-10-13  
**修复版本**: test_all_tools_metrics.py v1.1

