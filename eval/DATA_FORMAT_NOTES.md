# Parquet 数据格式详解

## 实际数据格式

经过测试 `/app/xiaominl/air_full_v1/shard-test-000000.parquet`，实际格式如下：

### 字段列表

```python
{
    "data_source": str,           # 数据来源
    "prompt": np.ndarray,         # 对话提示数组
    "images": np.ndarray,         # 图像数组
    "ability": str,               # 能力类型（如"IR"）
    "env_name": str,              # 退化类型（逗号分隔）
    "reward_model": np.ndarray,   # 奖励模型配置
    "extra_info": dict            # 额外信息
}
```

### 详细结构

#### 1. `prompt` 字段

```python
prompt = [
    {
        "role": "system",
        "content": "You are a helpful assistant specialized in image restoration..."
    },
    {
        "role": "user", 
        "content": "<image>\nDetected degradations: rain, noise\n\nRestore this image..."
    }
]
```

- **长度**: 通常是 2（system + user）
- **类型**: numpy数组，元素是字典
- **system消息**: 包含完整的系统提示词（约10K字符）
- **user消息**: 包含 `<image>` 占位符和具体任务描述

#### 2. `images` 字段

```python
images = [
    {
        "bytes": b'\x89PNG\r\n...'  # PNG图像的原始字节
    }
]
```

- **长度**: 通常是 1（仅退化图像）
- **类型**: numpy数组，元素是字典
- **格式**: `{'bytes': <PNG/JPEG bytes>}`
- **退化图像**: `images[0]['bytes']`

**⚠️ 注意**: 不是base64字符串，而是包含bytes的字典！

#### 3. `extra_info` 字段

```python
extra_info = {
    "index": int,                      # 样本索引
    "split": str,                      # 数据集划分（train/test）
    "original_image": bytes,           # GT图像（PNG/JPEG bytes）
    "use_original": bool,              # 是否使用GT（通常为True）
    "degradation_combo": str           # 退化组合描述
}
```

- **GT图像位置**: `extra_info['original_image']`
- **类型**: 直接是 bytes，不是字典
- **尺寸**: 可能与退化图像不同（如4倍超分场景）

#### 4. `env_name` 字段

```python
env_name = "defocus blur, low resolution, motion blur"
```

- **格式**: 逗号分隔的字符串
- **解析**: `env_name.split(', ')`

#### 5. `reward_model` 字段

```python
reward_model = [
    {
        "degradation_type": "motion blur",
        "degradation_level": "high",
        "has_original": True
    },
    {
        "degradation_type": "low resolution",
        "degradation_level": "high", 
        "has_original": True
    }
]
```

- **长度**: 与退化数量相同
- **用途**: 配置每种退化的奖励计算方式

## 图像尺寸处理

### 常见场景

1. **普通复原**：退化图像和GT图像尺寸相同
   - 例：`degraded: 512x512, GT: 512x512`

2. **超分辨率**：GT图像是退化图像的整数倍
   - 例：`degraded: 510x336, GT: 2040x1344`（4倍）

### 自动处理

评估脚本使用 `ImageQualityMetrics._handle_size_mismatch()` 自动处理：
- 检测整数倍关系
- 下采样较大图像到相同尺寸
- 确保指标计算在相同分辨率下进行

## 评估脚本的数据处理流程

```python
# 1. 提取退化图像
images = sample['images']
if isinstance(images[0], dict) and 'bytes' in images[0]:
    degraded_image = Image.open(io.BytesIO(images[0]['bytes']))

# 2. 提取GT图像
extra_info = sample['extra_info']
if extra_info.get('use_original') and 'original_image' in extra_info:
    gt_image = Image.open(io.BytesIO(extra_info['original_image']))

# 3. 提取系统提示词
prompt = sample['prompt']
system_prompt = prompt[0]['content']  # 如果 prompt[0]['role'] == 'system'

# 4. 提取用户消息
user_text = prompt[1]['content'].replace('<image>', '').strip()

# 5. 提取退化类型
degradations = sample['env_name'].split(', ')
```

## 已修复的问题

### ❌ 原问题

```python
# 错误：直接将字典传给base64解码
degraded_image_base64 = images[0]  # 这是 {'bytes': b'...'}
degraded_image = self._decode_base64_to_image(degraded_image_base64)
# TypeError: argument should be a bytes-like object or ASCII string, not 'dict'
```

### ✅ 修复方案

添加了 `_extract_image_from_data()` 方法，支持多种格式：
- 字典格式：`{'bytes': b'...'}`
- bytes格式：直接bytes
- base64字符串格式
- 文件路径格式

## 验证测试

运行测试脚本验证数据加载：

```bash
python eval/test_data_loading.py
```

预期输出：
```
✅ 成功加载 324 个样本
✅ 成功提取退化图像: (510, 336), RGB
✅ 成功提取GT图像: (2040, 1344), RGB
✅ 所有测试通过！
```

## 兼容性说明

评估脚本现在支持：
1. ✅ 字典格式的图像数据（当前air_full_v1数据集）
2. ✅ 直接bytes格式
3. ✅ Base64字符串格式
4. ✅ 文件路径格式

确保与各种数据集格式兼容。

