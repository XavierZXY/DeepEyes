# SCUNet Denoising Toolbox

## 概述

SCUNet (Self-Calibrated Blind Denoising Network) 是一个强大的图像去噪工具集，支持真实世界噪声和合成噪声的处理。

## 服务端配置

- **服务端口**: 5008
- **API 地址**: `http://{TOOL_SERVICE_IP}:5008/process`
- **支持的任务**:
  - `real_denoising_psnr`: 真实图像去噪（PSNR优化）
  - `real_denoising_gan`: 真实图像去噪（GAN版本，视觉效果更好）
  - `color_denoising_15/25/50`: 彩色图像去噪（噪声等级 15/25/50）
  - `gray_denoising_15/25/50`: 灰度图像去噪（噪声等级 15/25/50）

## 已注册的工具类

### 1. SCUNetRealDenoisingPSNRToolbox
- **工具名称**: `scunet_real_denoising_psnr`
- **用途**: 真实世界图像去噪（PSNR优化版本）
- **适用场景**: 真实拍摄的噪声图像，追求更高的 PSNR 指标
- **参数**: 无需额外参数

### 2. SCUNetRealDenoisingGANToolbox
- **工具名称**: `scunet_real_denoising_gan`
- **用途**: 真实世界图像去噪（GAN版本）
- **适用场景**: 真实拍摄的噪声图像，追求更好的视觉效果
- **参数**: 无需额外参数

### 3. SCUNetColorDenoisingToolbox
- **工具名称**: `scunet_color_denoising`
- **用途**: 彩色图像去噪
- **适用场景**: 已知噪声等级的彩色图像
- **参数**:
  - `noise_level` (可选): 15, 25, 或 50，默认为 25

### 4. SCUNetGrayDenoisingToolbox
- **工具名称**: `scunet_gray_denoising`
- **用途**: 灰度图像去噪
- **适用场景**: 已知噪声等级的灰度图像
- **参数**:
  - `noise_level` (可选): 15, 25, 或 50，默认为 25

## 工具使用示例

### 基本使用流程

```python
from verl.workers.agent.envs.tool_envs import ToolBase

# 1. 创建工具实例
tool = ToolBase.create("scunet_real_denoising_psnr")

# 2. 准备图像数据
from PIL import Image
image = Image.open("noisy_image.png")
initial_data = {"image": [image]}
initial_prompt = [{"role": "user", "content": "Please denoise this image."}]

# 3. 重置工具状态
tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)

# 4. 执行工具调用
action_string = """
<tool_call>
{"name": "scunet_real_denoising_psnr", "arguments": {}}
</tool_call>
"""

obs, reward, done, info = tool.execute(action_string)

# 5. 获取处理后的图像
if info.get("status") == "success":
    processed_image = obs['multi_modal_data']['image'][0]
    processed_image.save("denoised_result.png")
```

### 使用不同的去噪工具

#### 真实图像去噪（GAN版本）
```python
tool = ToolBase.create("scunet_real_denoising_gan")
tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)

action_string = """
<tool_call>
{"name": "scunet_real_denoising_gan", "arguments": {}}
</tool_call>
"""
obs, reward, done, info = tool.execute(action_string)
```

#### 彩色图像去噪（指定噪声等级）
```python
tool = ToolBase.create("scunet_color_denoising")
tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)

action_string = """
<tool_call>
{"name": "scunet_color_denoising", "arguments": {"noise_level": 50}}
</tool_call>
"""
obs, reward, done, info = tool.execute(action_string)
```

#### 灰度图像去噪
```python
tool = ToolBase.create("scunet_gray_denoising")
tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)

action_string = """
<tool_call>
{"name": "scunet_gray_denoising", "arguments": {"noise_level": 25}}
</tool_call>
"""
obs, reward, done, info = tool.execute(action_string)
```

## 测试

运行测试脚本：

```bash
cd /app/xiaominl/DeepEyes_v2
python -m verl.workers.agent.envs.mm_process_engine.SCUNetToolbox
```

## 工具选择建议

1. **真实世界噪声图像**:
   - 如果追求更高的 PSNR 指标 → `scunet_real_denoising_psnr`
   - 如果追求更好的视觉效果 → `scunet_real_denoising_gan`

2. **合成噪声图像**:
   - 彩色图像 → `scunet_color_denoising`（根据噪声等级选择 15/25/50）
   - 灰度图像 → `scunet_gray_denoising`（根据噪声等级选择 15/25/50）

## 技术细节

- **输入**: RGB 或灰度图像（PIL Image 格式）
- **输出**: 去噪后的图像（PIL Image 格式）
- **超时**: 300秒
- **多GPU支持**: 服务端自动进行负载均衡
- **队列机制**: 支持请求排队，避免过载

## 错误处理

工具会处理以下错误情况：

1. **服务不可用 (503)**: GPU 显存不足，建议稍后重试
2. **超时 (408)**: GPU 队列已满，建议稍后重试
3. **连接错误**: 检查服务端是否正常运行
4. **无效参数**: 检查噪声等级是否为 15/25/50

## 环境变量

- `TOOL_SERVICE_IP`: SCUNet 服务的 IP 地址，默认为 `10.21.9.34`

## 参考

- 服务端实现: `scunet_server_v1.py`
- 基类: `BaseSCUNetToolbox`
- Prompt 模板: `SCUNetPrompt.py`

