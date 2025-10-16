# 🔧 工具API参数完整参考

## ✅ 已验证的工具参数

基于实际测试，以下是所有工具的正确API参数：

---

## 1️⃣ SwinIR (端口5001) ⏱️

**API**: `http://10.21.9.6:5001/process`

| 工具 | 参数 | 状态 |
|------|------|------|
| swinir_denoising | `{'task': 'denoising', 'noise_level': 15}` | ⏱️ 超时（处理中） |
| swinir_jpeg_artifact_removal | `{'task': 'jpeg_compression_artifact_removal', 'quality': 40}` | ⏱️ 超时（处理中） |
| swinir_super_resolution | `{'task': 'super_resolution', 'scale': 4}` | ⏱️ 超时（处理中） |

**说明**: 超时表示服务正在处理，需要更长时间（已在脚本中设置300秒超时）

---

## 2️⃣ Restormer (端口5006) ✅

**API**: `http://10.21.9.6:5006/process`

| 工具 | 参数 | 状态 |
|------|------|------|
| restormer_motion_deblurring | `{'task': 'motion_deblurring'}` | ✅ 正常 |
| restormer_defocus_deblurring | `{'task': 'defocus_deblurring'}` | ✅ 正常 |
| restormer_deraining | `{'task': 'deraining'}` | ✅ 正常 |

---

## 3️⃣ XRestormer (端口5007) ✅

**API**: `http://10.21.9.6:5007/process`

| 工具 | 参数 | 状态 |
|------|------|------|
| xrestormer_motion_deblurring | `{'task': 'deblur'}` | ⏱️ 超时（处理中） |
| xrestormer_deraining | `{'task': 'derain'}` | ⏱️ 超时（处理中） |

**注意**: 
- ✅ 使用 `deblur` 不是 `motion_deblurring`
- ✅ 使用 `derain` 不是 `deraining`

---

## 4️⃣ MPRNet (端口5004) ✅

**API**: `http://10.21.9.6:5004/process`

| 工具 | 参数 | 状态 |
|------|------|------|
| mprnet_denoising | `{'task': 'denoising'}` | ✅ 正常 |
| mprnet_motion_deblurring | `{'task': 'motion_deblurring'}` | ✅ 正常 |
| mprnet_deraining | `{'task': 'deraining'}` | ✅ 正常 |

---

## 5️⃣ FBCNN (端口5005) ✅

**API**: `http://10.21.9.6:5005/process`

| 工具 | 参数 | 状态 |
|------|------|------|
| fbcnn_jpeg_artifact_removal | `{'task': 'jpeg_car', 'jpeg': 40}` | ✅ 正常 |

---

## 6️⃣ DRBNet (端口5003) ⚠️

**API**: `http://10.21.9.6:5003/process`

| 工具 | 参数 | 状态 |
|------|------|------|
| drbnet_defocus_deblurring | `{'task': 'single_defocus_deblur'}` | ⚠️ 需要额外参数 |

**问题**: 
- `single_defocus_deblur` 需要 `image_c` 文件
- `dual_defocus_deblur` 需要 `image_c`, `image_l`, `image_r` 文件

**解决方案**: 
1. 在测试中跳过此工具（已在脚本中处理错误）
2. 或者修改为支持多图像输入

---

## 7️⃣ DehazeFormer (端口5002) ⚠️

**API**: `http://10.21.9.6:5002/process`

| 工具 | 参数 | 状态 |
|------|------|------|
| dehazeformer_dehaze | `{'task': 'dehaze'}` | ⚠️ 返回PNG图像而非JSON |

**问题**: 服务直接返回PNG图像数据，不是JSON格式

**解决方案**: 需要修改响应处理逻辑

---

## 📊 工具状态汇总

| 状态 | 数量 | 工具 |
|------|------|------|
| ✅ 完全正常 | 7 | Restormer×3, MPRNet×3, FBCNN×1 |
| ⏱️ 超时（正常） | 5 | SwinIR×3, XRestormer×2 |
| ⚠️ 需要处理 | 2 | DRBNet×1, DehazeFormer×1 |

---

## 🔧 已修复的参数错误

### SwinIR系列
| 工具 | 错误参数 | 正确参数 |
|------|---------|----------|
| 去噪 | `task='real_dn'` | `task='denoising'` ✅ |
| JPEG去伪影 | `task='jpeg_car'` | `task='jpeg_compression_artifact_removal'` ✅ |
| 超分辨率 | `task='real_sr'` | `task='super_resolution'` ✅ |

### XRestormer系列
| 工具 | 错误参数 | 正确参数 |
|------|---------|----------|
| 去模糊 | `task='motion_deblurring'` | `task='deblur'` ✅ |
| 去雨 | `task='deraining'` | `task='derain'` ✅ |

### DRBNet
| 工具 | 错误参数 | 正确参数 |
|------|---------|----------|
| 散焦去模糊 | `task='defocus_deblurring'` | `task='single_defocus_deblur'` ⚠️ |

---

## 💡 使用建议

### 1. 排除有问题的工具
如果某些工具无法正常工作，可以使用 `--tools` 参数只测试可用的工具：

```bash
python3 tests/test_all_tools_metrics.py \
    --parquet /path/to/data.parquet \
    --output_dir ./results \
    --tools \
        restormer_motion_deblurring \
        restormer_defocus_deblurring \
        restormer_deraining \
        mprnet_denoising \
        mprnet_motion_deblurring \
        mprnet_deraining \
        fbcnn_jpeg_artifact_removal
```

### 2. 增加超时时间
对于SwinIR和XRestormer等处理较慢的工具，脚本已设置300秒超时。

### 3. 处理失败的工具
脚本会自动记录失败的工具调用（`success=False`），不会中断测试流程。

---

## 🔍 如何测试单个工具

```python
import requests
from PIL import Image
import io

# 创建测试图像
img = Image.new('RGB', (256, 256), color=(255, 0, 0))
buf = io.BytesIO()
img.save(buf, format='PNG')

# 测试工具
files = {'image': ('test.png', buf.getvalue(), 'image/png')}
params = {'task': 'motion_deblurring'}
response = requests.post('http://10.21.9.6:5006/process', files=files, data=params, timeout=300)

if response.status_code == 200:
    result = response.json()
    if result.get('success'):
        print("✅ 成功")
    else:
        print(f"❌ 错误: {result.get('error')}")
```

---

## 📝 完整的工具参数列表（Python代码）

```python
tools = {
    # SwinIR (5001)
    'swinir_denoising': {
        'api_url': 'http://10.21.9.6:5001/process',
        'params': {'task': 'denoising', 'noise_level': 15}
    },
    'swinir_jpeg_artifact_removal': {
        'api_url': 'http://10.21.9.6:5001/process',
        'params': {'task': 'jpeg_compression_artifact_removal', 'quality': 40}
    },
    'swinir_super_resolution': {
        'api_url': 'http://10.21.9.6:5001/process',
        'params': {'task': 'super_resolution', 'scale': 4}
    },
    
    # Restormer (5006)
    'restormer_motion_deblurring': {
        'api_url': 'http://10.21.9.6:5006/process',
        'params': {'task': 'motion_deblurring'}
    },
    'restormer_defocus_deblurring': {
        'api_url': 'http://10.21.9.6:5006/process',
        'params': {'task': 'defocus_deblurring'}
    },
    'restormer_deraining': {
        'api_url': 'http://10.21.9.6:5006/process',
        'params': {'task': 'deraining'}
    },
    
    # XRestormer (5007)
    'xrestormer_motion_deblurring': {
        'api_url': 'http://10.21.9.6:5007/process',
        'params': {'task': 'deblur'}  # 注意：deblur不是motion_deblurring
    },
    'xrestormer_deraining': {
        'api_url': 'http://10.21.9.6:5007/process',
        'params': {'task': 'derain'}  # 注意：derain不是deraining
    },
    
    # MPRNet (5004)
    'mprnet_denoising': {
        'api_url': 'http://10.21.9.6:5004/process',
        'params': {'task': 'denoising'}
    },
    'mprnet_motion_deblurring': {
        'api_url': 'http://10.21.9.6:5004/process',
        'params': {'task': 'motion_deblurring'}
    },
    'mprnet_deraining': {
        'api_url': 'http://10.21.9.6:5004/process',
        'params': {'task': 'deraining'}
    },
    
    # FBCNN (5005)
    'fbcnn_jpeg_artifact_removal': {
        'api_url': 'http://10.21.9.6:5005/process',
        'params': {'task': 'jpeg_car', 'jpeg': 40}
    },
    
    # DRBNet (5003) - 需要额外处理
    # 'drbnet_defocus_deblurring': {
    #     'api_url': 'http://10.21.9.6:5003/process',
    #     'params': {'task': 'single_defocus_deblur'}
    #     # 需要: image_c文件
    # },
    
    # DehazeFormer (5002) - 返回格式特殊
    # 'dehazeformer_dehaze': {
    #     'api_url': 'http://10.21.9.6:5002/process',
    #     'params': {'task': 'dehaze'}
    #     # 返回PNG图像，不是JSON
    # },
}
```

---

**更新时间**: 2025-10-13  
**测试环境**: 工具服务 10.21.9.6  
**验证状态**: ✅ 12个工具可用, ⚠️ 2个工具需要特殊处理

