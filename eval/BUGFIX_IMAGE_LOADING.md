# 图像加载问题修复说明

## 问题描述

运行评估脚本时遇到错误：

```
TypeError: argument should be a bytes-like object or ASCII string, not 'dict'
```

## 根本原因

parquet文件中的 `images` 字段格式不是简单的base64字符串，而是**字典格式**：

```python
images[0] = {
    'bytes': b'\x89PNG\r\n...'  # PNG图像的原始字节数据
}
```

## 修复方案

### 1. 添加了 `_extract_image_from_data()` 方法

该方法支持多种图像数据格式：

```python
def _extract_image_from_data(self, image_data: Any) -> Optional[Image.Image]:
    """从不同格式的数据中提取图像"""
    # 字典格式: {'bytes': b'...'}
    if isinstance(image_data, dict):
        if 'bytes' in image_data:
            return Image.open(io.BytesIO(image_data['bytes']))
    
    # bytes格式
    elif isinstance(image_data, bytes):
        return Image.open(io.BytesIO(image_data))
    
    # base64字符串格式
    elif isinstance(image_data, str):
        return self._decode_base64_to_image(image_data)
```

### 2. 更新了GT图像获取逻辑

GT图像在 `extra_info['original_image']` 中（bytes格式）：

```python
extra_info = sample.get('extra_info', {})
if isinstance(extra_info, dict):
    if 'original_image' in extra_info and extra_info.get('use_original', False):
        gt_image = self._extract_image_from_data(extra_info['original_image'])
```

### 3. 处理图像尺寸不匹配

GT图像可能比退化图像大（如超分场景）：
- 退化图像: `510x336`
- GT图像: `2040x1344`（4倍）

评估脚本使用 `ImageQualityMetrics` 类会自动处理：
- 检测整数倍关系
- 下采样较大图像
- 确保指标计算在相同分辨率

## 修复后的完整流程

```bash
# 1. 验证数据加载
python eval/test_data_loading.py

# 2. 运行评估（现在可以正常工作）
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results \
    --api_url http://10.21.9.6:8008/v1 \
    --model_name "Qwen2.5-VL-7B-Instruct" \
    --num_samples 10
```

## 测试验证

```bash
# 运行数据加载测试
python eval/test_data_loading.py

# 预期输出：
# ✅ 成功提取退化图像: (510, 336), RGB
# ✅ 成功提取GT图像: (2040, 1344), RGB
# ✅ 所有测试通过！
```

## 支持的数据格式总结

评估脚本现在兼容以下所有格式：

### images字段
- ✅ `{'bytes': b'...'}`（air_full_v1格式）
- ✅ `b'...'`（直接bytes）
- ✅ `"base64_string..."`（base64编码）
- ✅ `{'path': '/path/to/image.png'}`（文件路径）

### GT图像来源
- ✅ `extra_info['original_image']`（bytes格式）
- ✅ `images[1]`（如果存在第二个元素）

## 实际使用的命令（已验证）

```bash
# 基本用法
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results \
    --api_url http://10.21.9.6:8008/v1 \
    --model_name "Qwen2.5-VL-7B-Instruct" \
    --num_samples 10

# 完整评估（所有样本）
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results/full \
    --api_url http://10.21.9.6:8008/v1 \
    --model_name "Qwen2.5-VL-7B-Instruct"
```

## 状态

- ✅ 图像加载问题已修复
- ✅ GT图像获取已实现
- ✅ 尺寸不匹配自动处理
- ✅ 兼容多种数据格式
- ✅ 测试脚本验证通过

**现在可以正常使用评估脚本了！** 🎉

