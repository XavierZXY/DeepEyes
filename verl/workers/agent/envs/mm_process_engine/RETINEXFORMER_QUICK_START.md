# Retinexformer Low-light Enhancement Toolbox - 快速开始指南

## 📋 目录

1. [简介](#简介)
2. [架构概览](#架构概览)
3. [快速开始](#快速开始)
4. [工具列表](#工具列表)
5. [使用示例](#使用示例)
6. [API参考](#api参考)
7. [常见问题](#常见问题)
8. [性能优化](#性能优化)

---

## 简介

**RetinexformerToolbox** 是一个基于 Retinexformer 模型的低光图像增强工具集，支持多种预训练模型用于不同场景的低光增强任务。

### 主要特性

- ✅ **多模型支持**: 8个预训练模型，覆盖不同的低光场景
- ✅ **自动注册**: 工具自动注册到 ToolBase 框架
- ✅ **统一接口**: 与 SwinIR、SCUNet 等工具保持一致的使用方式
- ✅ **灵活选择**: 可以使用通用工具或特定模型工具
- ✅ **GPU加速**: 支持多GPU并发处理
- ✅ **错误处理**: 完善的错误处理和超时机制

### 支持的模型

| 模型名称 | 训练数据集 | 适用场景 | 推荐度 |
|---------|-----------|---------|-------|
| LOL_v1 | LOL-v1 | 通用低光增强 | ⭐⭐⭐ |
| LOL_v2_real | LOL-v2 真实场景 | 真实拍摄的低光照片 | ⭐⭐⭐⭐⭐ |
| LOL_v2_synthetic | LOL-v2 合成数据 | 合成降质图片 | ⭐⭐⭐ |
| SDSD_indoor | SDSD 室内 | 室内弱光环境 | ⭐⭐⭐⭐ |
| SDSD_outdoor | SDSD 室外 | 夜间户外场景 | ⭐⭐⭐⭐ |
| SID | See in the Dark | 极低光场景 | ⭐⭐⭐⭐ |
| SMID | 静态多场景 | 多样化场景 | ⭐⭐⭐⭐ |
| FiveK | MIT Adobe FiveK | 专业级调色 | ⭐⭐⭐⭐ |

---

## 架构概览

```
RetinexformerToolbox 架构
│
├── RetinexformerPrompt.py          # 提示词定义
│   └── PROMPT 类
│       ├── USER_PROMPT_V1          # 基础提示词
│       ├── USER_PROMPT_V2          # 详细提示词
│       └── TOOL_DESCRIPTION        # 工具描述
│
├── RetinexformerToolbox.py         # 主工具实现
│   ├── BaseRetinexformerToolbox    # 基类（公共逻辑）
│   │   ├── _call_retinexformer_api()  # API调用
│   │   ├── execute()                  # 工具执行
│   │   ├── reset()                    # 状态重置
│   │   └── build_params()             # 参数构建（抽象）
│   │
│   ├── RetinexformerToolbox        # 通用工具（推荐）⭐
│   │   └── 支持所有8个模型
│   │
│   └── 8个特定模型工具
│       ├── RetinexformerLOLv1Toolbox
│       ├── RetinexformerLOLv2RealToolbox
│       ├── RetinexformerLOLv2SyntheticToolbox
│       ├── RetinexformerSDSDIndoorToolbox
│       ├── RetinexformerSDSDOutdoorToolbox
│       ├── RetinexformerSIDToolbox
│       ├── RetinexformerSMIDToolbox
│       └── RetinexformerFiveKToolbox
│
└── Retinexformer Server (端口: 5009)
    ├── 多GPU并发支持
    ├── 智能排队机制
    └── 自动显存管理
```

---

## 快速开始

### 1. 环境准备

```bash
# 确保已安装必要的依赖
pip install torch torchvision
pip install numpy pillow requests

# 设置服务器IP地址（可选）
export TOOL_SERVICE_IP=10.21.9.34  # 默认值

# 确保 Retinexformer 服务正在运行
# 服务应该监听在 http://<TOOL_SERVICE_IP>:5009
```

### 2. 启动 Retinexformer 服务

```bash
# 在服务器上启动 Retinexformer 服务
cd /path/to/retinexformer
python retinexformer_server_v1.py

# 服务将在端口 5009 上监听
# 输出应包含: "🚀 Starting Retinexformer Low-light Enhancement Server v1..."
```

### 3. 验证工具注册

```python
from verl.workers.agent.envs.tool_envs import ToolBase

# 检查所有已注册的工具
print(list(ToolBase.registry.keys()))

# 应该看到以下工具:
# - retinexformer_enhance          (通用工具，推荐)
# - retinexformer_lol_v1
# - retinexformer_lol_v2_real
# - retinexformer_lol_v2_synthetic
# - retinexformer_sdsd_indoor
# - retinexformer_sdsd_outdoor
# - retinexformer_sid
# - retinexformer_smid
# - retinexformer_fivek
```

### 4. 基础使用示例

```python
from PIL import Image
from verl.workers.agent.envs.tool_envs import ToolBase

# 加载一张低光图片
low_light_image = Image.open("dark_photo.jpg")

# 准备初始数据
initial_prompt = [{"role": "user", "content": "Please enhance this low-light image."}]
initial_data = {"image": [low_light_image]}

# 创建工具实例（使用通用工具）
tool = ToolBase.create("retinexformer_enhance")

# 重置工具状态
tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)

# 构造工具调用字符串（模拟LLM输出）
tool_call = """<tool_call>
{
    "name": "retinexformer_enhance",
    "arguments": {
        "task": "LOL_v2_real"
    }
}
</tool_call>"""

# 执行工具
obs, reward, done, info = tool.execute(tool_call)

# 检查结果
if info.get("status") == "success":
    enhanced_image = obs['multi_modal_data']['image'][0]
    enhanced_image.save("enhanced_photo.jpg")
    print("✓ 图像增强成功!")
else:
    print(f"✗ 增强失败: {info.get('error')}")
```

---

## 工具列表

### 🌟 通用工具（推荐使用）

#### `retinexformer_enhance`
- **名称**: `retinexformer_enhance`
- **用途**: 通用低光图像增强，支持选择不同的预训练模型
- **参数**:
  - `task` (可选): 模型名称，默认 `LOL_v2_real`
    - 可选值: `LOL_v1`, `LOL_v2_real`, `LOL_v2_synthetic`, `SDSD_indoor`, `SDSD_outdoor`, `SID`, `SMID`, `FiveK`
- **优点**: 
  - 灵活性高，可以轻松切换模型
  - 适合需要测试多个模型的场景
  - 代码简洁，推荐使用

**使用示例**:
```python
tool_call = """<tool_call>
{
    "name": "retinexformer_enhance",
    "arguments": {
        "task": "LOL_v2_real"
    }
}
</tool_call>"""
```

---

### 📦 特定模型工具

如果你总是使用某个特定模型，可以使用对应的专用工具：

#### 1. `retinexformer_lol_v1`
- **模型**: LOL-v1
- **场景**: 通用低光增强（经典模型）
- **特点**: 较为保守，不会过度增强
- **参数**: 无需参数

```python
tool_call = """<tool_call>
{
    "name": "retinexformer_lol_v1",
    "arguments": {}
}
</tool_call>"""
```

#### 2. `retinexformer_lol_v2_real` ⭐ 推荐
- **模型**: LOL-v2 真实场景
- **场景**: 真实拍摄的低光照片
- **特点**: 对真实噪声和光照变化处理好
- **参数**: 无需参数

```python
tool_call = """<tool_call>
{
    "name": "retinexformer_lol_v2_real",
    "arguments": {}
}
</tool_call>"""
```

#### 3. `retinexformer_lol_v2_synthetic`
- **模型**: LOL-v2 合成数据
- **场景**: 合成降质的图片
- **特点**: 对人工降低亮度的图片效果好
- **参数**: 无需参数

#### 4. `retinexformer_sdsd_indoor`
- **模型**: SDSD 室内
- **场景**: 室内弱光环境
- **特点**: 针对室内光源特性优化
- **参数**: 无需参数

#### 5. `retinexformer_sdsd_outdoor`
- **模型**: SDSD 室外
- **场景**: 夜间户外场景
- **特点**: 处理户外夜景效果好
- **参数**: 无需参数

#### 6. `retinexformer_sid`
- **模型**: SID (See in the Dark)
- **场景**: 极低光场景
- **特点**: 处理极端低光情况
- **参数**: 无需参数

#### 7. `retinexformer_smid`
- **模型**: SMID 静态多场景
- **场景**: 多样化场景
- **特点**: 泛化能力强
- **参数**: 无需参数

#### 8. `retinexformer_fivek`
- **模型**: MIT Adobe FiveK
- **场景**: 需要专业级调色的照片
- **特点**: 专业数据集训练
- **参数**: 无需参数

---

## 使用示例

### 示例 1: 增强夜间街景照片

```python
from PIL import Image
from verl.workers.agent.envs.tool_envs import ToolBase

# 加载夜间街景照片
night_street = Image.open("night_street.jpg")

# 准备数据
data = {"image": [night_street]}
prompt = [{"role": "user", "content": "Enhance this night street photo."}]

# 使用 SDSD_outdoor 模型（适合户外夜景）
tool = ToolBase.create("retinexformer_enhance")
tool.reset(raw_prompt=prompt, multi_modal_data=data)

tool_call = """<tool_call>
{
    "name": "retinexformer_enhance",
    "arguments": {
        "task": "SDSD_outdoor"
    }
}
</tool_call>"""

obs, reward, done, info = tool.execute(tool_call)

if info.get("status") == "success":
    enhanced = obs['multi_modal_data']['image'][0]
    enhanced.save("night_street_enhanced.jpg")
    print("✓ 夜景增强完成!")
```

### 示例 2: 增强室内弱光照片

```python
# 使用 SDSD_indoor 模型（适合室内）
tool = ToolBase.create("retinexformer_sdsd_indoor")

indoor_photo = Image.open("indoor_lowlight.jpg")
data = {"image": [indoor_photo]}
prompt = [{"role": "user", "content": "Enhance this indoor photo."}]

tool.reset(raw_prompt=prompt, multi_modal_data=data)

# 使用特定工具类，无需指定task参数
tool_call = """<tool_call>
{
    "name": "retinexformer_sdsd_indoor",
    "arguments": {}
}
</tool_call>"""

obs, reward, done, info = tool.execute(tool_call)

if info.get("status") == "success":
    enhanced = obs['multi_modal_data']['image'][0]
    enhanced.save("indoor_enhanced.jpg")
```

### 示例 3: 批量测试不同模型

```python
from PIL import Image
from verl.workers.agent.envs.tool_envs import ToolBase
import os

# 加载测试图片
test_image = Image.open("test_lowlight.jpg")
data = {"image": [test_image]}
prompt = [{"role": "user", "content": "Enhance this image."}]

# 创建输出目录
os.makedirs("output", exist_ok=True)

# 测试不同模型
models = ["LOL_v1", "LOL_v2_real", "SDSD_indoor", "SDSD_outdoor", "SID"]

tool = ToolBase.create("retinexformer_enhance")

for model_name in models:
    print(f"Testing {model_name}...")
    
    # 每次测试前重置工具状态
    tool.reset(raw_prompt=prompt, multi_modal_data=data)
    
    tool_call = f"""<tool_call>
{{
    "name": "retinexformer_enhance",
    "arguments": {{
        "task": "{model_name}"
    }}
}}
</tool_call>"""
    
    obs, reward, done, info = tool.execute(tool_call)
    
    if info.get("status") == "success":
        enhanced = obs['multi_modal_data']['image'][0]
        enhanced.save(f"output/enhanced_{model_name}.jpg")
        print(f"  ✓ Saved to output/enhanced_{model_name}.jpg")
    else:
        print(f"  ✗ Failed: {info.get('error')}")
```

### 示例 4: 在 Agent 环境中使用

```python
# 在 parallel_env.py 或类似的环境中使用

class MyEnv:
    def __init__(self):
        # 注册所有工具
        self.tools = {
            "retinexformer_enhance": ToolBase.create("retinexformer_enhance"),
            "retinexformer_lol_v2_real": ToolBase.create("retinexformer_lol_v2_real"),
            # ... 其他工具
        }
    
    def step(self, action_string):
        # 从 action_string 中提取工具名称
        tool_name = self._parse_tool_name(action_string)
        
        if tool_name in self.tools:
            tool = self.tools[tool_name]
            obs, reward, done, info = tool.execute(action_string)
            return obs, reward, done, info
        else:
            return self._handle_unknown_tool(tool_name)
    
    def reset(self, image_path):
        image = Image.open(image_path)
        data = {"image": [image]}
        prompt = [{"role": "user", "content": "Analyze this image."}]
        
        # 重置所有工具
        for tool in self.tools.values():
            tool.reset(raw_prompt=prompt, multi_modal_data=data)
```

---

## API 参考

### BaseRetinexformerToolbox

#### 方法

##### `__init__(self, _name, _desc, _params, **kwargs)`
- 初始化工具实例
- 设置API地址（从环境变量 `TOOL_SERVICE_IP` 读取）

##### `reset(self, raw_prompt, multi_modal_data, origin_multi_modal_data=None, **kwargs)`
- 重置工具状态
- **参数**:
  - `raw_prompt`: 对话历史
  - `multi_modal_data`: 当前多模态数据（包含图像）
  - `origin_multi_modal_data`: 原始多模态数据（可选）

##### `execute(self, action_string, **kwargs) -> tuple`
- 执行工具调用
- **参数**:
  - `action_string`: 包含 `<tool_call>` 或 `<answer>` 的字符串
- **返回**: `(observation, reward, done, info)`
  - `observation`: 观察结果（包含增强后的图像）
  - `reward`: 奖励值
  - `done`: 是否结束
  - `info`: 执行信息字典

##### `build_params(self, args: Dict[str, Any]) -> Dict[str, Any]`
- 构建API请求参数（由子类实现）
- **参数**:
  - `args`: 工具调用参数
- **返回**: API请求参数字典

---

### RetinexformerToolbox（通用工具）

#### 额外属性

- `AVAILABLE_TASKS`: 可用的任务列表
  ```python
  ["LOL_v1", "LOL_v2_real", "LOL_v2_synthetic",
   "SDSD_indoor", "SDSD_outdoor", "SID", "SMID", "FiveK"]
  ```

#### 参数说明

- `task` (字符串，可选): 指定使用的模型
  - 默认值: `"LOL_v2_real"`
  - 如果提供了无效的任务名称，将使用默认值

---

## 常见问题

### Q1: 如何选择合适的模型？

**A**: 根据你的图片类型选择：

| 场景 | 推荐模型 | 备选模型 |
|-----|---------|---------|
| 手机/相机拍摄的低光照片 | `LOL_v2_real` | `LOL_v1`, `SMID` |
| 室内环境 | `SDSD_indoor` | `LOL_v2_real` |
| 夜间户外 | `SDSD_outdoor` | `SID` |
| 极暗环境 | `SID` | `SDSD_outdoor` |
| 专业摄影后期 | `FiveK` | `LOL_v2_real` |
| 测试/实验 | `LOL_v2_synthetic` | `LOL_v1` |
| 不确定 | `LOL_v2_real` | `SMID` |

### Q2: 工具执行失败怎么办？

**A**: 检查以下几点：

1. **服务是否运行**:
   ```bash
   curl http://<TOOL_SERVICE_IP>:5009/health
   ```

2. **网络连接**:
   ```python
   import os
   print(f"API URL: http://{os.environ.get('TOOL_SERVICE_IP', '10.21.9.34')}:5009/enhance")
   ```

3. **查看错误信息**:
   ```python
   obs, reward, done, info = tool.execute(tool_call)
   if info.get("status") != "success":
       print(f"Error: {info.get('error')}")
   ```

4. **常见错误**:
   - `503 SERVICE UNAVAILABLE`: GPU显存不足或服务过载
   - `408 Timeout`: 服务器队列满，等待超时
   - `Connection Error`: 无法连接到服务器

### Q3: 如何修改服务器地址？

**A**: 设置环境变量 `TOOL_SERVICE_IP`:

```bash
# 临时设置（当前终端）
export TOOL_SERVICE_IP=192.168.1.100

# 或在 Python 代码中设置
import os
os.environ['TOOL_SERVICE_IP'] = '192.168.1.100'

# 然后再导入工具
from verl.workers.agent.envs.mm_process_engine.RetinexformerToolbox import *
```

### Q4: 可以同时使用多个工具吗？

**A**: 可以，但需要注意：

```python
# 正确做法：每个工具独立的实例
tool1 = ToolBase.create("retinexformer_enhance")
tool2 = ToolBase.create("retinexformer_lol_v2_real")

# 分别重置
tool1.reset(raw_prompt=prompt1, multi_modal_data=data1)
tool2.reset(raw_prompt=prompt2, multi_modal_data=data2)

# 分别执行
obs1, _, _, info1 = tool1.execute(call1)
obs2, _, _, info2 = tool2.execute(call2)
```

### Q5: 工具对图像尺寸有限制吗？

**A**: 
- 理论上无限制，但建议不超过 4K (3840×2160)
- 较大图像会消耗更多GPU显存和处理时间
- 服务器会自动进行必要的padding（window_size=4的倍数）

### Q6: 如何获取处理进度或日志？

**A**: 工具会打印调试日志到标准输出：

```python
# 执行工具时会看到类似输出：
# [RETINEXFORMER API] 🚀 开始调用API: http://...
# [RETINEXFORMER API] 任务参数: {'task': 'LOL_v2_real', ...}
# [RETINEXFORMER DEBUG] 开始处理图像，尺寸: (1024, 768)
# [RETINEXFORMER DEBUG] 输入图像统计: mean=45.32, std=23.15
# [RETINEXFORMER API] ✅ API调用成功
# [TOOL EXECUTE] ✅ retinexformer_enhance 执行成功 (耗时: 2.35s)

# 可以从 info 字典获取执行时间
if info.get("status") == "success":
    print(f"Processing time: {info['execution_time']:.2f}s")
```

### Q7: 通用工具和特定工具有什么区别？

**A**: 

| 特性 | 通用工具 (`retinexformer_enhance`) | 特定工具 (如 `retinexformer_lol_v2_real`) |
|-----|-----------------------------------|------------------------------------------|
| 灵活性 | ✅ 可以切换模型 | ❌ 固定模型 |
| 代码复杂度 | 稍高（需要指定task参数） | 低（无需参数） |
| 推荐场景 | 需要测试多个模型 | 明确使用某个模型 |
| 性能 | 相同 | 相同 |

**推荐**: 优先使用通用工具 `retinexformer_enhance`，它更灵活。

---

## 性能优化

### 服务器端优化

1. **多GPU配置**:
   ```bash
   # 指定使用的GPU
   export RETINEXFORMER_GPUS=0,1,2,3
   python retinexformer_server_v1.py
   ```

2. **并发控制**:
   ```python
   # 在 retinexformer_server_v1.py 中调整
   MAX_CONCURRENT_PER_GPU = 3  # 每GPU并发数
   MAX_QUEUE_SIZE = 100        # 最大队列大小
   ```

3. **显存管理**:
   ```python
   # 启用激进显存清理
   AGGRESSIVE_MEMORY_CLEANUP = True
   ```

### 客户端优化

1. **批量处理时重用工具实例**:
   ```python
   # 好的做法
   tool = ToolBase.create("retinexformer_enhance")
   for image_path in image_list:
       image = Image.open(image_path)
       tool.reset(raw_prompt=prompt, multi_modal_data={"image": [image]})
       obs, _, _, info = tool.execute(tool_call)
   
   # 避免每次都创建新实例
   ```

2. **预先调整图像尺寸**:
   ```python
   from PIL import Image
   
   # 如果图像很大，先缩小
   image = Image.open("huge_image.jpg")
   if max(image.size) > 2048:
       image.thumbnail((2048, 2048), Image.LANCZOS)
   ```

3. **异步处理**（适用于多张图片）:
   ```python
   import concurrent.futures
   
   def process_image(image_path, model):
       tool = ToolBase.create("retinexformer_enhance")
       image = Image.open(image_path)
       tool.reset(raw_prompt=prompt, multi_modal_data={"image": [image]})
       # ... 执行处理
       return enhanced_image
   
   with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
       futures = [executor.submit(process_image, path, model) 
                  for path in image_paths]
       results = [f.result() for f in futures]
   ```

### 服务监控

检查服务状态：
```bash
# 健康检查
curl http://<IP>:5009/health

# GPU状态
curl http://<IP>:5009/gpus

# 模型池状态
curl http://<IP>:5009/models

# 手动清理显存
curl -X POST http://<IP>:5009/cleanup \
  -H "Content-Type: application/json" \
  -d '{"gpu_id": 0}'
```

---

## 相关文件

- `RetinexformerToolbox.py` - 主工具实现
- `RetinexformerPrompt.py` - 提示词定义
- `example_retinexformer_usage.py` - 详细使用示例
- `retinexformer_server_v1.py` - 服务器端实现

---

## 技术支持

如有问题或建议，请：
1. 查看本文档的"常见问题"部分
2. 运行 `example_retinexformer_usage.py` 查看完整示例
3. 检查服务器日志以获取详细错误信息
4. 联系开发团队

---

## 更新日志

### v1.0.0 (2025-10-15)
- ✅ 初始版本发布
- ✅ 支持8个预训练模型
- ✅ 实现通用工具和特定模型工具
- ✅ 完整的错误处理和日志系统
- ✅ 多GPU支持和智能排队机制
- ✅ 与 SwinIR、SCUNet 工具保持一致的接口

---

**祝使用愉快！** 🎉

