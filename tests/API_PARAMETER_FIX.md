# 🔧 工具API参数修复

## ❌ 原始问题

运行测试时出现400错误：
```
requests.exceptions.HTTPError: 400 Client Error: BAD REQUEST
```

## 🔍 问题分析

### 错误原因
服务端返回的错误信息：
```json
{
  "error": "Invalid task. Must be one of ['super_resolution', 'denoising', 'jpeg_compression_artifact_removal']"
}
```

### 参数不匹配

**脚本使用的参数（错误）**：
```python
# SwinIR去噪
{'task': 'real_dn', 'noise': 15}  # ❌ 

# SwinIR JPEG伪影去除
{'task': 'jpeg_car', 'jpeg': 40}  # ❌

# SwinIR超分辨率
{'task': 'real_sr', 'scale': 4}  # ❌
```

**服务端期待的参数（正确）**：
```python
# SwinIR去噪
{'task': 'denoising', 'noise_level': 15}  # ✅

# SwinIR JPEG伪影去除
{'task': 'jpeg_compression_artifact_removal', 'quality': 40}  # ✅

# SwinIR超分辨率
{'task': 'super_resolution', 'scale': 4}  # ✅
```

---

## ✅ 已修复

### SwinIR系列工具参数

| 工具 | 修改前 | 修改后 |
|------|--------|--------|
| swinir_denoising | `task='real_dn'` | `task='denoising'` ✅ |
| swinir_jpeg_artifact_removal | `task='jpeg_car'` | `task='jpeg_compression_artifact_removal'` ✅ |
| swinir_super_resolution | `task='real_sr'` | `task='super_resolution'` ✅ |

### 参数名称修改

| 工具 | 参数 | 修改前 | 修改后 |
|------|------|--------|--------|
| swinir_denoising | 噪声等级 | `noise=15` | `noise_level=15` ✅ |
| swinir_jpeg_artifact_removal | 质量 | `jpeg=40` | `quality=40` ✅ |

---

## 📝 其他工具参数

### Restormer系列 (端口5006)
```python
'restormer_motion_deblurring': {'task': 'motion_deblurring'}
'restormer_defocus_deblurring': {'task': 'defocus_deblurring'}
'restormer_deraining': {'task': 'deraining'}
```

### XRestormer系列 (端口5007)
```python
'xrestormer_motion_deblurring': {'task': 'motion_deblurring'}
'xrestormer_deraining': {'task': 'deraining'}
```

### MPRNet系列 (端口5004)
```python
'mprnet_denoising': {'task': 'denoising'}
'mprnet_motion_deblurring': {'task': 'motion_deblurring'}
'mprnet_deraining': {'task': 'deraining'}
```

### 其他工具
```python
'fbcnn_jpeg_artifact_removal': {'task': 'jpeg_car', 'jpeg': 40}
'drbnet_defocus_deblurring': {'task': 'defocus_deblurring'}
'dehazeformer_dehaze': {'task': 'dehaze'}
```

---

## ⚠️ 注意事项

### 1. 超时问题
某些工具处理可能需要较长时间（特别是超分辨率），脚本已设置300秒超时。

### 2. 服务端差异
不同端口的工具服务可能使用不同的参数格式：
- SwinIR (5001): 使用标准名称
- 其他工具: 可能使用简化名称

### 3. 参数验证
运行测试前，可以先用curl测试工具服务：
```bash
# 测试SwinIR服务
curl -X POST http://10.21.9.6:5001/process \
  -F "image=@test.png" \
  -F "task=denoising" \
  -F "noise_level=15"
```

---

## 🔍 如何发现正确参数

### 方法1: 查看服务端错误信息
```python
response = requests.post(api_url, ...)
if response.status_code == 400:
    print(response.json())  # 会显示期待的参数
```

### 方法2: 查看服务端代码
检查工具服务的API定义文件

### 方法3: 查看训练代码
参考 `verl/workers/agent/envs/mm_process_engine/` 中的工具实现

---

## ✅ 验证方法

运行小批量测试验证修复：
```bash
python3 tests/test_all_tools_metrics.py \
    --parquet /path/to/data.parquet \
    --output_dir ./api_test \
    --max_samples 1 \
    --tools swinir_denoising
```

预期输出：
```
✅ 样本 0: ['noise'] (['high'])
🔧 工具: swinir_denoising
   [API] ✅ 调用成功
```

---

## 📋 完整的工具参数列表

```python
tools = {
    # SwinIR (5001)
    'swinir_denoising': {
        'task': 'denoising',
        'noise_level': 15
    },
    'swinir_jpeg_artifact_removal': {
        'task': 'jpeg_compression_artifact_removal',
        'quality': 40
    },
    'swinir_super_resolution': {
        'task': 'super_resolution',
        'scale': 4
    },
    
    # Restormer (5006)
    'restormer_motion_deblurring': {
        'task': 'motion_deblurring'
    },
    'restormer_defocus_deblurring': {
        'task': 'defocus_deblurring'
    },
    'restormer_deraining': {
        'task': 'deraining'
    },
    
    # XRestormer (5007)
    'xrestormer_motion_deblurring': {
        'task': 'motion_deblurring'
    },
    'xrestormer_deraining': {
        'task': 'deraining'
    },
    
    # MPRNet (5004)
    'mprnet_denoising': {
        'task': 'denoising'
    },
    'mprnet_motion_deblurring': {
        'task': 'motion_deblurring'
    },
    'mprnet_deraining': {
        'task': 'deraining'
    },
    
    # FBCNN (5005)
    'fbcnn_jpeg_artifact_removal': {
        'task': 'jpeg_car',
        'jpeg': 40
    },
    
    # DRBNet (5003)
    'drbnet_defocus_deblurring': {
        'task': 'defocus_deblurring'
    },
    
    # DehazeFormer (5002)
    'dehazeformer_dehaze': {
        'task': 'dehaze'
    }
}
```

---

**更新时间**: 2025-10-13  
**修复版本**: test_all_tools_metrics.py v1.2  
**状态**: ✅ SwinIR参数已修复

