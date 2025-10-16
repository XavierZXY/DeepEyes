# SCUNet 工具快速开始指南

## 📦 已创建的文件

1. **SCUNetPrompt.py** - Prompt 模板文件
2. **SCUNetToolbox.py** - 主要工具实现文件
3. **README_SCUNet.md** - 详细文档
4. **test_scunet_toolbox.py** - 测试脚本
5. **SCUNET_QUICK_START.md** - 本文件（快速开始指南）

## ✅ 已实现的工具

### 1. scunet_real_denoising_psnr
- **用途**: 真实图像去噪（PSNR优化）
- **工具类**: `SCUNetRealDenoisingPSNRToolbox`
- **任务**: `real_denoising_psnr`

### 2. scunet_real_denoising_gan
- **用途**: 真实图像去噪（GAN版本，视觉效果更好）
- **工具类**: `SCUNetRealDenoisingGANToolbox`
- **任务**: `real_denoising_gan`

### 3. scunet_color_denoising
- **用途**: 彩色图像去噪（支持噪声等级 15/25/50）
- **工具类**: `SCUNetColorDenoisingToolbox`
- **默认任务**: `color_denoising_25`

### 4. scunet_gray_denoising
- **用途**: 灰度图像去噪（支持噪声等级 15/25/50）
- **工具类**: `SCUNetGrayDenoisingToolbox`
- **默认任务**: `gray_denoising_25`

## 🚀 快速测试

```bash
# 运行测试脚本
cd /app/xiaominl/DeepEyes_v2
python3 verl/workers/agent/envs/mm_process_engine/test_scunet_toolbox.py
```

## 💻 基本使用

```python
import sys
sys.path.insert(0, '/app/xiaominl/DeepEyes_v2')

from verl.workers.agent.tool_envs import ToolBase
from PIL import Image

# 1. 创建工具
tool = ToolBase.create("scunet_real_denoising_psnr")

# 2. 准备数据
image = Image.open("your_image.png")
multi_modal_data = {"image": [image]}
prompt = [{"role": "user", "content": "Denoise this image"}]

# 3. 重置工具
tool.reset(raw_prompt=prompt, multi_modal_data=multi_modal_data)

# 4. 执行工具
action_string = '''
<tool_call>
{"name": "scunet_real_denoising_psnr", "arguments": {}}
</tool_call>
'''

obs, reward, done, info = tool.execute(action_string)

# 5. 获取结果
if info.get("status") == "success":
    result_image = obs['multi_modal_data']['image'][0]
    result_image.save("denoised.png")
```

## 🎯 工具选择建议

| 场景 | 推荐工具 | 说明 |
|------|---------|------|
| 真实拍摄的噪声照片（追求指标） | `scunet_real_denoising_psnr` | PSNR优化版本 |
| 真实拍摄的噪声照片（追求效果） | `scunet_real_denoising_gan` | 视觉效果更好 |
| 已知噪声等级的彩色图像 | `scunet_color_denoising` | 指定 `noise_level` |
| 已知噪声等级的灰度图像 | `scunet_gray_denoising` | 指定 `noise_level` |

## 🔧 配置说明

### 环境变量
- `TOOL_SERVICE_IP`: SCUNet 服务的 IP 地址，默认为 `10.21.9.34`

### API 配置
- **端口**: 5008
- **地址**: `http://{TOOL_SERVICE_IP}:5008/process`
- **超时**: 300秒

## 📝 参数说明

### 彩色/灰度去噪工具参数

```python
# 使用默认噪声等级（25）
action_string = '''
<tool_call>
{"name": "scunet_color_denoising", "arguments": {}}
</tool_call>
'''

# 指定噪声等级
action_string = '''
<tool_call>
{"name": "scunet_color_denoising", "arguments": {"noise_level": 50}}
</tool_call>
'''
```

支持的噪声等级：`15`, `25`, `50`

## 📊 测试结果

运行 `test_scunet_toolbox.py` 的结果：

```
✅ 所有测试通过！

测试项目：
  ✓ 工具注册
  ✓ 工具创建
  ✓ 参数构建
  ✓ Reset功能
  ✓ Action解析
```

## 🔍 与 SwinIR 的对比

| 特性 | SwinIR | SCUNet |
|------|--------|--------|
| 主要用途 | 超分辨率、去噪、JPEG压缩伪影 | 图像去噪 |
| 端口 | 5001 | 5008 |
| 真实噪声 | ❌ | ✅ (PSNR/GAN 两个版本) |
| 合成噪声 | ✅ | ✅ (15/25/50 三个等级) |
| 灰度支持 | ❌ | ✅ |

## 🐛 故障排查

### 工具未注册
```python
# 确认导入
from verl.workers.agent.envs.mm_process_engine.SCUNetToolbox import *

# 检查注册
from verl.workers.agent.tool_envs import ToolBase
print("scunet_real_denoising_psnr" in ToolBase.registry)
```

### API 连接失败
1. 检查服务是否运行
2. 检查 `TOOL_SERVICE_IP` 环境变量
3. 检查网络连接和端口 5008

### 参数错误
- 彩色/灰度去噪的 `noise_level` 必须是 15、25 或 50
- 真实图像去噪工具不需要参数

## 📚 更多信息

- 详细文档: [README_SCUNet.md](README_SCUNet.md)
- 测试脚本: [test_scunet_toolbox.py](test_scunet_toolbox.py)
- 服务端代码: `scunet_server_v1.py`

## 🎉 完成状态

- ✅ 基类实现 (`BaseSCUNetToolbox`)
- ✅ 4 个工具类实现
- ✅ Prompt 模板
- ✅ 自动注册机制
- ✅ 参数构建逻辑
- ✅ 错误处理
- ✅ 完整测试套件
- ✅ 文档

**所有功能已实现并测试通过！** 🚀

