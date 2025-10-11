# MPRNet工具箱使用说明

## 概述

MPRNet工具箱是基于MPRNet模型的图像修复工具集合，支持三种主要的图像修复任务：

- **去噪** (`mprnet_denoising`) - 去除图像中的噪声
- **去雨** (`mprnet_deraining`) - 去除图像中的雨线
- **运动去模糊** (`mprnet_motion_deblurring`) - 修复运动模糊的图像

## 架构设计

### 基类设计
- `BaseMPRNetToolbox`: 所有MPRNet工具的基类，实现通用的API调用逻辑
- 继承自 `ToolBase`，支持自动工具注册机制

### 具体工具类
- `MPRNetDenoisingToolbox`: 去噪工具
- `MPRNetDeraininingToolbox`: 去雨工具  
- `MPRNetMotionDeblurringToolbox`: 运动去模糊工具

## API接口

### 服务端配置
- **API端点**: `http://172.18.148.193:5004/process`
- **请求方法**: POST
- **支持任务**: `denoising`, `deraining`, `motion_deblurring`
- **排队机制**: 支持智能排队，避免GPU资源争抢

### 请求参数
```python
{
    "task": "denoising",  # 任务类型
    "queue": "true"       # 启用排队机制
}
```

### 响应格式
```python
{
    "status": "🚀 Success",
    "success": True,
    "image": "base64_encoded_image",
    "task": "denoising",
    "processing_time": "2.34s",
    "thread_id": 12345,
    "message": "✨ Denoising completed successfully!"
}
```

## 使用方法

### 1. 基本使用
```python
from verl.workers.agent.tool_envs import ToolBase

# 创建工具实例
denoise_tool = ToolBase.create("mprnet_denoising")

# 准备数据
initial_prompt = [{"role": "user", "content": "Please enhance this image."}]
initial_data = {"image": [your_pil_image]}

# 重置工具状态
denoise_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)

# 执行工具调用
action_string = '''<tool_call>
{"name": "mprnet_denoising", "arguments": {}}
</tool_call>'''

obs, reward, done, info = denoise_tool.execute(action_string)
```

### 2. 在Agent环境中使用
工具会自动注册到ToolBase注册表中，可以在parallel_env.py等环境中直接使用。

### 3. 演示脚本
```bash
# 测试工具注册
python examples/mprnet_demo.py --test-mode

# 完整功能测试（需要API服务运行）
python examples/mprnet_demo.py
```

## 错误处理

### 常见错误类型
1. **服务不可用** (503): GPU内存不足或队列已满
2. **请求超时** (408): 队列处理超时
3. **连接错误**: API服务未运行或网络问题

### 错误处理机制
- 自动重试机制（在ConnectionError时）
- 详细的错误信息和建议
- 支持排队和非阻塞两种模式

## 性能特性

### 排队机制
- **最大并发**: 2个请求（GPU显存限制）
- **最大队列**: 30个请求
- **队列超时**: 300秒
- **智能调度**: 避免GPU资源争抢

### 优化特性
- 模型缓存机制
- GPU内存自动清理
- 多线程安全
- 详细的性能监控

## 配置选项

### API端点配置
可以通过修改类属性来更改API端点：
```python
BaseMPRNetToolbox.api_url = "http://your-server:port/process"
```

### 提示词配置
使用IRprompt.py中的提示词模板：
```python
user_prompt = PROMPT.USER_PROMPT_V1
```

## 监控和调试

### 日志输出
工具提供详细的日志输出，包括：
- API调用状态
- 处理时间
- 错误信息
- 性能指标

### 调试信息
```python
print(f"[MPRNET DEBUG] 开始处理图像，尺寸: {image.size}")
print(f"[MPRNET DEBUG] API参数: {params}")
print(f"[MPRNET DEBUG] API调用完成")
```

## 扩展开发

### 添加新任务
1. 在服务端添加新的任务配置
2. 创建新的工具类继承`BaseMPRNetToolbox`
3. 实现`build_params`方法
4. 设置正确的`name`和`task_name`

### 自定义参数
可以在`build_params`方法中添加自定义参数：
```python
def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "task": self.task_name,
        "queue": "true",
        "custom_param": args.get("custom_param", "default_value")
    }
```

## 故障排除

### 常见问题
1. **工具未注册**: 检查导入路径和类定义
2. **API连接失败**: 检查服务端是否运行，端口是否正确
3. **内存不足**: 等待队列处理或重启服务
4. **图像格式错误**: 确保输入为PIL Image对象

### 调试步骤
1. 运行`examples/mprnet_demo.py --test-mode`检查注册
2. 检查API服务状态：`curl http://172.18.148.193:5004/health`
3. 查看详细日志输出
4. 检查图像数据格式

## 版本信息
- 基于SwinIRToolbox架构设计
- 兼容ToolBase自动注册机制
- 支持MPRNet服务端v1.0 API
