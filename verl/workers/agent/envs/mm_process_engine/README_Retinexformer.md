# Retinexformer Low-light Enhancement Toolbox

## 概述

**RetinexformerToolbox** 是一个基于 Retinexformer 深度学习模型的低光图像增强工具集，集成到 DeepEyes 框架中。它支持多种预训练模型，适用于不同场景的低光图像增强任务。

## 目录结构

```
mm_process_engine/
├── RetinexformerToolbox.py          # 主工具实现
├── RetinexformerPrompt.py           # 提示词定义
├── example_retinexformer_usage.py   # 使用示例
├── test_retinexformer_toolbox.py    # 测试套件
├── RETINEXFORMER_QUICK_START.md     # 快速开始指南
└── README_Retinexformer.md          # 本文件
```

## 主要特性

### 1. 多模型支持
支持 8 个预训练模型，覆盖不同的低光场景：

| 模型 | 数据集 | 适用场景 |
|------|--------|---------|
| LOL_v1 | LOL-v1 | 通用低光增强 |
| LOL_v2_real | LOL-v2 真实 | 真实拍摄照片 ⭐ 推荐 |
| LOL_v2_synthetic | LOL-v2 合成 | 合成降质图片 |
| SDSD_indoor | SDSD 室内 | 室内弱光环境 |
| SDSD_outdoor | SDSD 室外 | 夜间户外场景 |
| SID | See in the Dark | 极低光场景 |
| SMID | 静态多场景 | 多样化场景 |
| FiveK | MIT Adobe FiveK | 专业级调色 |

### 2. 灵活的工具架构

提供两种使用方式：

#### 方式 1: 通用工具（推荐）
```python
tool = ToolBase.create("retinexformer_enhance")
# 可以通过参数选择不同的模型
tool_call = {
    "name": "retinexformer_enhance",
    "arguments": {"task": "LOL_v2_real"}
}
```

#### 方式 2: 特定模型工具
```python
tool = ToolBase.create("retinexformer_lol_v2_real")
# 固定使用 LOL_v2_real 模型
tool_call = {
    "name": "retinexformer_lol_v2_real",
    "arguments": {}
}
```

### 3. 自动注册机制

所有工具在导入时自动注册到 `ToolBase.registry`：

```python
from verl.workers.agent.envs.tool_envs import ToolBase

# 自动注册的工具列表
registered_tools = [
    "retinexformer_enhance",           # 通用工具
    "retinexformer_lol_v1",
    "retinexformer_lol_v2_real",
    "retinexformer_lol_v2_synthetic",
    "retinexformer_sdsd_indoor",
    "retinexformer_sdsd_outdoor",
    "retinexformer_sid",
    "retinexformer_smid",
    "retinexformer_fivek",
]
```

### 4. 统一的接口设计

与 SwinIR、SCUNet 等工具保持一致的接口：

```python
# 创建工具
tool = ToolBase.create("retinexformer_enhance")

# 重置状态
tool.reset(raw_prompt=prompt, multi_modal_data=data)

# 执行工具
obs, reward, done, info = tool.execute(tool_call_string)
```

## 架构设计

### 类层次结构

```
ToolBase (框架基类)
    ↓
BaseRetinexformerToolbox (公共逻辑)
    ├── RetinexformerToolbox (通用工具) ⭐
    ├── RetinexformerLOLv1Toolbox
    ├── RetinexformerLOLv2RealToolbox
    ├── RetinexformerLOLv2SyntheticToolbox
    ├── RetinexformerSDSDIndoorToolbox
    ├── RetinexformerSDSDOutdoorToolbox
    ├── RetinexformerSIDToolbox
    ├── RetinexformerSMIDToolbox
    └── RetinexformerFiveKToolbox
```

### 核心组件

#### 1. BaseRetinexformerToolbox
基类，包含所有公共逻辑：

- **API 调用**: `_call_retinexformer_api()` - 与后端服务通信
- **工具执行**: `execute()` - 解析和执行工具调用
- **状态管理**: `reset()` - 重置工具状态
- **提取方法**: `extract_action()`, `extract_answer()` - 解析LLM输出
- **参数构建**: `build_params()` - 抽象方法，由子类实现

#### 2. RetinexformerToolbox
通用工具类，支持所有模型：

```python
class RetinexformerToolbox(BaseRetinexformerToolbox):
    name = "retinexformer_enhance"
    task_name = "LOL_v2_real"  # 默认模型
    
    AVAILABLE_TASKS = [
        "LOL_v1", "LOL_v2_real", "LOL_v2_synthetic",
        "SDSD_indoor", "SDSD_outdoor", "SID", "SMID", "FiveK"
    ]
    
    def build_params(self, args):
        task = args.get("task", self.task_name)
        # 验证任务名称
        if task not in self.AVAILABLE_TASKS:
            task = self.task_name
        return {"task": task, "format": "base64"}
```

#### 3. 特定模型工具类
每个模型一个类，简化使用：

```python
class RetinexformerLOLv2RealToolbox(BaseRetinexformerToolbox):
    name = "retinexformer_lol_v2_real"
    task_name = "LOL_v2_real"
    
    def build_params(self, args):
        return {"task": self.task_name, "format": "base64"}
```

## 后端服务

### 服务架构

Retinexformer 服务 (`retinexformer_server_v1.py`) 提供以下功能：

#### 1. 多GPU支持
- 自动检测和管理多个GPU
- 智能负载均衡
- 并发请求处理

#### 2. 模型预加载
- 启动时预加载所有模型到所有GPU
- 减少首次请求延迟
- 提高响应速度

#### 3. 智能排队机制
- 请求队列管理
- 超时处理
- GPU槽位分配

#### 4. 显存管理
- 自动显存清理
- 显存监控
- 激进清理模式

### API 端点

#### `/enhance` - 图像增强
```bash
curl -X POST http://<IP>:5009/enhance \
  -F "image=@lowlight.jpg" \
  -F "task=LOL_v2_real" \
  -F "format=base64"
```

**参数**:
- `image`: 图像文件 (必需)
- `task`: 模型名称 (可选，默认 LOL_v2_real)
- `format`: 返回格式 (base64 或 file)
- `gpu`: 指定GPU (可选)
- `queue`: 启用排队 (可选，默认 true)

**响应**:
```json
{
    "success": true,
    "image": "base64_encoded_string",
    "task": "LOL_v2_real",
    "processing_time": "2.35s",
    "gpu_id": 0,
    "description": "LOL-v2 real captured dataset trained model"
}
```

#### `/health` - 健康检查
```bash
curl http://<IP>:5009/health
```

#### `/gpus` - GPU状态
```bash
curl http://<IP>:5009/gpus
```

#### `/models` - 模型池状态
```bash
curl http://<IP>:5009/models
```

#### `/cleanup` - 手动清理显存
```bash
curl -X POST http://<IP>:5009/cleanup \
  -H "Content-Type: application/json" \
  -d '{"gpu_id": 0}'
```

## 使用指南

### 基础使用

```python
from PIL import Image
from verl.workers.agent.envs.tool_envs import ToolBase

# 1. 加载图像
image = Image.open("lowlight_photo.jpg")
data = {"image": [image]}
prompt = [{"role": "user", "content": "Enhance this image."}]

# 2. 创建工具
tool = ToolBase.create("retinexformer_enhance")

# 3. 重置状态
tool.reset(raw_prompt=prompt, multi_modal_data=data)

# 4. 构造工具调用
tool_call = """<tool_call>
{
    "name": "retinexformer_enhance",
    "arguments": {
        "task": "LOL_v2_real"
    }
}
</tool_call>"""

# 5. 执行工具
obs, reward, done, info = tool.execute(tool_call)

# 6. 获取结果
if info.get("status") == "success":
    enhanced_image = obs['multi_modal_data']['image'][0]
    enhanced_image.save("enhanced_photo.jpg")
```

### 场景选择指南

| 你的场景 | 推荐模型 | 备选 |
|---------|---------|------|
| 手机/相机拍摄 | LOL_v2_real | SMID |
| 室内照片 | SDSD_indoor | LOL_v2_real |
| 夜景照片 | SDSD_outdoor | SID |
| 极暗环境 | SID | SDSD_outdoor |
| 专业后期 | FiveK | LOL_v2_real |
| 不确定 | LOL_v2_real | SMID |

### 批量处理示例

```python
import os
from pathlib import Path

# 批量处理目录下的所有图片
input_dir = Path("lowlight_images")
output_dir = Path("enhanced_images")
output_dir.mkdir(exist_ok=True)

tool = ToolBase.create("retinexformer_enhance")

for img_path in input_dir.glob("*.jpg"):
    print(f"Processing {img_path.name}...")
    
    # 加载图像
    image = Image.open(img_path)
    tool.reset(
        raw_prompt=[{"role": "user", "content": "Enhance."}],
        multi_modal_data={"image": [image]}
    )
    
    # 执行增强
    tool_call = """<tool_call>
    {
        "name": "retinexformer_enhance",
        "arguments": {"task": "LOL_v2_real"}
    }
    </tool_call>"""
    
    obs, _, _, info = tool.execute(tool_call)
    
    if info.get("status") == "success":
        enhanced = obs['multi_modal_data']['image'][0]
        enhanced.save(output_dir / img_path.name)
        print(f"  ✓ Saved to {output_dir / img_path.name}")
    else:
        print(f"  ✗ Failed: {info.get('error')}")
```

## 配置

### 环境变量

```bash
# 服务器IP地址（默认: 10.21.9.34）
export TOOL_SERVICE_IP=192.168.1.100

# 指定使用的GPU（服务器端）
export RETINEXFORMER_GPUS=0,1,2,3

# 启用集成测试
export RUN_INTEGRATION_TESTS=1
```

### 服务器配置

在 `retinexformer_server_v1.py` 中可以调整：

```python
# 并发控制
MAX_CONCURRENT_PER_GPU = 3  # 每GPU并发数
MAX_QUEUE_SIZE = 100        # 最大队列大小
QUEUE_TIMEOUT = 300         # 队列超时（秒）

# 显存管理
AGGRESSIVE_MEMORY_CLEANUP = True  # 激进清理模式
```

## 测试

### 运行测试套件

```bash
# 基础测试（不需要服务）
python test_retinexformer_toolbox.py

# 包含集成测试（需要服务运行）
export RUN_INTEGRATION_TESTS=1
python test_retinexformer_toolbox.py
```

### 测试覆盖

- ✅ 工具注册测试
- ✅ 工具创建测试
- ✅ 参数构建测试
- ✅ 状态重置测试
- ✅ 错误处理测试
- ✅ 边界情况测试
- ✅ 提示词测试
- ✅ 集成测试（需要服务）

## 性能优化

### 服务器端

1. **使用多GPU**: 
   ```bash
   export RETINEXFORMER_GPUS=0,1,2,3
   ```

2. **调整并发数**: 根据GPU显存调整 `MAX_CONCURRENT_PER_GPU`

3. **预加载模型**: 启动时预加载所有模型（已默认启用）

### 客户端

1. **重用工具实例**: 批量处理时重用同一个工具实例

2. **图像预处理**: 
   ```python
   # 大图片先缩小
   if max(image.size) > 2048:
       image.thumbnail((2048, 2048), Image.LANCZOS)
   ```

3. **异步处理**: 使用 `ThreadPoolExecutor` 并行处理多张图片

## 与其他工具的比较

| 特性 | Retinexformer | SwinIR | SCUNet |
|-----|--------------|--------|--------|
| 主要功能 | 低光增强 | 超分/去噪/去压缩伪影 | 盲图像去噪 |
| 模型数量 | 8 | 3 | 1 |
| 参数化 | 模型选择 | 强度/缩放 | 噪声等级 |
| 适用场景 | 低光照片 | 图像修复 | 噪声图像 |
| API端口 | 5009 | 5001 | 5002 |

## 故障排除

### 常见问题

#### 1. 服务连接失败
```
ConnectionError: Failed to connect to Retinexformer API
```

**解决方案**:
- 检查服务是否运行: `curl http://<IP>:5009/health`
- 检查防火墙设置
- 验证 `TOOL_SERVICE_IP` 环境变量

#### 2. GPU显存不足
```
503 SERVICE UNAVAILABLE: GPU memory shortage
```

**解决方案**:
- 减少 `MAX_CONCURRENT_PER_GPU`
- 启用 `AGGRESSIVE_MEMORY_CLEANUP`
- 使用更多GPU
- 手动清理显存: `curl -X POST http://<IP>:5009/cleanup`

#### 3. 请求超时
```
408 Timeout: No GPU available within timeout
```

**解决方案**:
- 增加 `QUEUE_TIMEOUT`
- 增加GPU数量
- 减少并发请求

#### 4. 工具未注册
```
ValueError: Tool 'retinexformer_enhance' not found in registry
```

**解决方案**:
- 确保正确导入: `from verl.workers.agent.envs.mm_process_engine.RetinexformerToolbox import *`
- 检查 `sys.path` 是否包含项目路径

## 文档索引

- **快速开始**: `RETINEXFORMER_QUICK_START.md` - 详细的快速开始指南
- **使用示例**: `example_retinexformer_usage.py` - 6个详细示例
- **测试文件**: `test_retinexformer_toolbox.py` - 完整测试套件
- **工具实现**: `RetinexformerToolbox.py` - 源代码
- **提示词**: `RetinexformerPrompt.py` - 提示词定义

## 技术细节

### 工具调用流程

```
1. LLM生成输出 (包含 <tool_call> 标签)
    ↓
2. execute() 解析输出
    ↓
3. extract_action() 提取JSON
    ↓
4. 验证工具名称和参数
    ↓
5. build_params() 构建API参数
    ↓
6. _call_retinexformer_api() 调用后端
    ↓
7. 接收增强后的图像
    ↓
8. 更新 multi_modal_data
    ↓
9. 返回 observation
```

### 数据流

```
Input Image (PIL.Image)
    ↓
转换为 PNG bytes
    ↓
HTTP POST → Retinexformer Server
    ↓
GPU处理 (Retinexformer模型)
    ↓
返回 base64编码图像
    ↓
解码为 PIL.Image
    ↓
更新到 multi_modal_data
    ↓
返回给 Agent
```

## 参考资料

- **Retinexformer论文**: [Retinexformer: One-stage Retinex-based Transformer for Low-light Image Enhancement](https://arxiv.org/abs/2303.06705)
- **数据集**:
  - LOL: https://daooshee.github.io/BMVC2018website/
  - SDSD: https://github.com/dvlab-research/SDSD
  - SID: https://github.com/cchen156/Learning-to-See-in-the-Dark
  - FiveK: https://data.csail.mit.edu/graphics/fivek/

## 许可证

本工具遵循与 DeepEyes 项目相同的许可证。

## 贡献者

- 基于 SwinIRToolbox 架构设计
- 参考 SCUNet 工具实现
- Retinexformer 模型来自原作者

---

**版本**: v1.0.0  
**最后更新**: 2025-10-15  
**维护者**: DeepEyes Team

