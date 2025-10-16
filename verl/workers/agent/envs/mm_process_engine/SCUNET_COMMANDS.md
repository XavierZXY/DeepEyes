# SCUNet 工具快速命令参考

## 📂 创建的文件

```
verl/workers/agent/envs/mm_process_engine/
├── SCUNetPrompt.py              # Prompt 模板
├── SCUNetToolbox.py             # 主要工具实现 (4个工具类)
├── test_scunet_toolbox.py       # 测试脚本
├── example_scunet_usage.py      # 使用示例脚本
├── README_SCUNet.md             # 详细文档
├── SCUNET_QUICK_START.md        # 快速开始指南
└── SCUNET_COMMANDS.md           # 本文件（快速命令参考）

SCUNET_IMPLEMENTATION_SUMMARY.md # 项目根目录下的实现总结
```

## 🧪 测试命令

### 运行完整测试套件
```bash
cd /app/xiaominl/DeepEyes_v2
python3 verl/workers/agent/envs/mm_process_engine/test_scunet_toolbox.py
```

### 快速验证工具注册
```bash
cd /app/xiaominl/DeepEyes_v2
python3 -c "
import sys
sys.path.insert(0, '/app/xiaominl/DeepEyes_v2')
from verl.workers.agent.tool_envs import ToolBase
from verl.workers.agent.envs.mm_process_engine.SCUNetToolbox import *

tools = ['scunet_real_denoising_psnr', 'scunet_real_denoising_gan', 
         'scunet_color_denoising', 'scunet_gray_denoising']
print('已注册的 SCUNet 工具:')
for tool in tools:
    status = '✓' if tool in ToolBase.registry else '✗'
    print(f'  {status} {tool}')
"
```

## 💡 使用示例命令

### 运行所有示例（不包括从文件读取）
```bash
cd /app/xiaominl/DeepEyes_v2
python3 verl/workers/agent/envs/mm_process_engine/example_scunet_usage.py --all
```

### 运行单个示例
```bash
# 示例 1: 真实图像去噪（PSNR）
python3 verl/workers/agent/envs/mm_process_engine/example_scunet_usage.py --example 1

# 示例 2: 真实图像去噪（GAN）
python3 verl/workers/agent/envs/mm_process_engine/example_scunet_usage.py --example 2

# 示例 3: 彩色图像去噪（不同噪声等级）
python3 verl/workers/agent/envs/mm_process_engine/example_scunet_usage.py --example 3

# 示例 4: 灰度图像去噪
python3 verl/workers/agent/envs/mm_process_engine/example_scunet_usage.py --example 4

# 示例 5: 错误处理演示
python3 verl/workers/agent/envs/mm_process_engine/example_scunet_usage.py --example 5

# 示例 6: 从文件读取图像
python3 verl/workers/agent/envs/mm_process_engine/example_scunet_usage.py --example 6 --image /path/to/image.png
```

## 🔧 在 Python 代码中使用

### 导入工具
```python
import sys
sys.path.insert(0, '/app/xiaominl/DeepEyes_v2')

from verl.workers.agent.tool_envs import ToolBase
from PIL import Image
```

### 使用真实图像去噪（PSNR）
```python
# 创建工具
tool = ToolBase.create("scunet_real_denoising_psnr")

# 准备数据
image = Image.open("noisy.png")
tool.reset(
    raw_prompt=[{"role": "user", "content": "Denoise this image"}],
    multi_modal_data={"image": [image]}
)

# 执行
action = '<tool_call>{"name": "scunet_real_denoising_psnr", "arguments": {}}</tool_call>'
obs, reward, done, info = tool.execute(action)

# 获取结果
if info.get("status") == "success":
    result = obs['multi_modal_data']['image'][0]
    result.save("denoised.png")
```

### 使用真实图像去噪（GAN）
```python
tool = ToolBase.create("scunet_real_denoising_gan")
tool.reset(raw_prompt=prompt, multi_modal_data=data)
action = '<tool_call>{"name": "scunet_real_denoising_gan", "arguments": {}}</tool_call>'
obs, reward, done, info = tool.execute(action)
```

### 使用彩色图像去噪（指定噪声等级）
```python
tool = ToolBase.create("scunet_color_denoising")
tool.reset(raw_prompt=prompt, multi_modal_data=data)

# 噪声等级可以是 15, 25, 或 50
action = '<tool_call>{"name": "scunet_color_denoising", "arguments": {"noise_level": 25}}</tool_call>'
obs, reward, done, info = tool.execute(action)
```

### 使用灰度图像去噪
```python
tool = ToolBase.create("scunet_gray_denoising")
tool.reset(raw_prompt=prompt, multi_modal_data=data)
action = '<tool_call>{"name": "scunet_gray_denoising", "arguments": {"noise_level": 50}}</tool_call>'
obs, reward, done, info = tool.execute(action)
```

## 🔍 调试命令

### 检查工具属性
```python
import sys
sys.path.insert(0, '/app/xiaominl/DeepEyes_v2')
from verl.workers.agent.tool_envs import ToolBase

tool = ToolBase.create("scunet_real_denoising_psnr")
print(f"工具名: {tool.name}")
print(f"任务名: {tool.task_name}")
print(f"API URL: {tool.api_url}")
```

### 测试参数构建
```python
tool = ToolBase.create("scunet_color_denoising")
params = tool.build_params({"noise_level": 25})
print(f"API 参数: {params}")
```

### 查看所有已注册工具
```python
from verl.workers.agent.tool_envs import ToolBase
print(f"共注册 {len(ToolBase.registry)} 个工具")
scunet_tools = [name for name in ToolBase.registry.keys() if 'scunet' in name]
print(f"SCUNet 工具: {scunet_tools}")
```

## 🌐 API 配置

### 设置自定义 IP 地址
```bash
export TOOL_SERVICE_IP=192.168.1.100
python3 your_script.py
```

### 检查 API 配置
```python
from verl.workers.agent.envs.mm_process_engine.SCUNetToolbox import BaseSCUNetToolbox
print(f"API URL: {BaseSCUNetToolbox.api_url}")
```

## 📊 工具对比

| 工具名称 | 适用场景 | 参数 |
|---------|---------|------|
| `scunet_real_denoising_psnr` | 真实噪声（高PSNR） | 无 |
| `scunet_real_denoising_gan` | 真实噪声（好视觉效果） | 无 |
| `scunet_color_denoising` | 合成噪声（彩色） | `noise_level`: 15/25/50 |
| `scunet_gray_denoising` | 合成噪声（灰度） | `noise_level`: 15/25/50 |

## 🚨 常见错误和解决方案

### 错误: "ModuleNotFoundError: No module named 'verl'"
```bash
# 确保正确设置 Python 路径
import sys
sys.path.insert(0, '/app/xiaominl/DeepEyes_v2')
```

### 错误: "ConnectionError: Failed to connect to SCUNet API"
```bash
# 检查服务是否运行
# 检查 IP 地址和端口配置
# 默认: http://10.21.9.34:5008
```

### 错误: "ValueError: Unknown tool name"
```python
# 确保工具名称正确
# 正确: "scunet_real_denoising_psnr"
# 错误: "SCUNet_real_denoising_psnr"
```

### 警告: "Unsupported noise level X, defaulting to 25"
```python
# 噪声等级必须是 15, 25, 或 50
# 自动回退到默认值 25
```

## 📖 文档索引

- **快速开始**: [SCUNET_QUICK_START.md](SCUNET_QUICK_START.md)
- **详细文档**: [README_SCUNet.md](README_SCUNet.md)
- **实现总结**: [SCUNET_IMPLEMENTATION_SUMMARY.md](../../../../../../SCUNET_IMPLEMENTATION_SUMMARY.md)
- **测试脚本**: [test_scunet_toolbox.py](test_scunet_toolbox.py)
- **使用示例**: [example_scunet_usage.py](example_scunet_usage.py)

## ✨ 快速参考卡片

```
工具名称                      端口    参数
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
scunet_real_denoising_psnr   5008    无
scunet_real_denoising_gan    5008    无
scunet_color_denoising       5008    noise_level (15/25/50)
scunet_gray_denoising        5008    noise_level (15/25/50)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

**提示**: 将本文件加入书签，方便快速查找命令！

