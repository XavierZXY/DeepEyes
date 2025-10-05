# FBCNN工具箱

基于FBCNN (Flexible Blind Convolutional Neural Network)的JPEG压缩伪影去除工具箱，专为DeepEyes多模态代理系统设计。

## 概述

FBCNN工具箱提供了两个主要工具：
1. **FBCNN JPEG伪影去除工具** (`fbcnn_jpeg_artifact_removal`) - 去除图像中的JPEG压缩伪影
2. **FBCNN盲质量评估工具** (`fbcnn_blind_quality_assessment`) - 评估图像的JPEG压缩质量

## 特性

- 🔧 **自动工具注册** - 工具会自动注册到ToolBase.registry中
- 🎯 **智能参数处理** - 支持盲预测和指定质量因子两种模式
- 🚀 **多GPU支持** - 支持指定GPU和负载均衡
- 📊 **队列管理** - 支持请求队列以处理高并发
- ⚡ **错误处理** - 完善的错误处理和参数验证
- 🔄 **API集成** - 与FBCNN服务端无缝集成

## 工具详情

### 1. FBCNN JPEG伪影去除工具

**工具名称**: `fbcnn_jpeg_artifact_removal`

**功能**: 使用FBCNN模型去除图像中的JPEG压缩伪影，提升图像质量。

**支持参数**:
- `qf` (可选): 质量因子
  - `"blind"` - 盲预测模式，自动检测质量因子（默认）
  - `1-100` - 指定原始JPEG的质量因子
- `gpu` (可选): 指定GPU ID
- `queue` (可选): 是否启用队列，默认`true`
- `format` (可选): 返回格式，默认`"base64"`

**使用示例**:
```json
{
  "name": "fbcnn_jpeg_artifact_removal",
  "arguments": {
    "qf": "blind",
    "queue": true
  }
}
```

### 2. FBCNN盲质量评估工具

**工具名称**: `fbcnn_blind_quality_assessment`

**功能**: 评估图像的JPEG压缩质量，预测原始质量因子。

**支持参数**:
- `gpu` (可选): 指定GPU ID

**使用示例**:
```json
{
  "name": "fbcnn_blind_quality_assessment",
  "arguments": {}
}
```

## 使用方法

### 1. 基本使用

```python
from verl.workers.agent.tool_envs import ToolBase
from verl.workers.agent.envs.mm_process_engine.FBCNNToolbox import (
    FBCNNJpegArtifactRemovalToolbox,
    FBCNNBlindQualityAssessmentToolbox
)

# 创建工具实例
fbcnn_tool = ToolBase.create("fbcnn_jpeg_artifact_removal")

# 准备环境数据
initial_prompt = [{"role": "user", "content": "请去除图像的JPEG伪影"}]
initial_data = {"image": [your_image]}

# 重置工具状态
fbcnn_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)

# 构建工具调用
tool_call = json.dumps([{
    "name": "fbcnn_jpeg_artifact_removal",
    "arguments": {"qf": "blind"}
}])
action_string = f"<tool_call>{tool_call}</tool_call>"

# 执行工具
obs, reward, done, info = fbcnn_tool.execute(action_string)
```

### 2. 不同模式示例

#### 盲预测模式
```python
# 让FBCNN自动检测和处理
arguments = {"qf": "blind", "queue": True}
```

#### 指定质量因子模式
```python
# 如果知道原始JPEG的质量因子
arguments = {"qf": "30", "queue": True}
```

#### 指定GPU模式
```python
# 指定使用特定GPU
arguments = {"qf": "blind", "gpu": "0", "queue": False}
```

### 3. 质量评估
```python
quality_tool = ToolBase.create("fbcnn_blind_quality_assessment")
quality_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)

tool_call = json.dumps([{
    "name": "fbcnn_blind_quality_assessment",
    "arguments": {}
}])
action_string = f"<tool_call>{tool_call}</tool_call>"

obs, reward, done, info = quality_tool.execute(action_string)
```

## API集成

工具箱与FBCNN服务端API集成，默认端点为：`http://172.18.148.193:5005/process`

### 服务端要求
- FBCNN服务必须运行在指定端点
- 支持多GPU并发处理
- 提供健康检查端点：`/health`

### 错误处理
- **连接错误**: 自动检测服务不可用状态
- **超时错误**: 处理高负载情况下的超时
- **参数错误**: 自动验证和修正无效参数
- **GPU错误**: 处理GPU资源不足等情况

## 配置说明

### 环境变量
可以通过修改工具类中的配置来调整：

```python
class BaseFBCNNToolbox(ToolBase):
    api_url = "http://172.18.148.193:5005/process"  # FBCNN API端点
    user_prompt = PROMPT.USER_PROMPT_V1  # 用户提示模板
```

### 参数验证
- QF参数自动验证，无效值会回退到`"blind"`模式
- GPU ID会进行类型转换和验证
- 队列参数支持布尔值和字符串格式

## 测试

### 运行基础测试
```bash
cd /app/xiaominl/DeepEyes
python test_fbcnn_toolbox.py
```

### 运行使用示例
```bash
cd /app/xiaominl/DeepEyes
python examples/fbcnn_usage_example.py
```

### 测试覆盖
- ✅ 工具注册验证
- ✅ 参数构建和验证
- ✅ 错误处理机制
- ✅ API连接性测试
- ✅ 多种使用模式演示

## 故障排除

### 常见问题

1. **工具未注册**
   ```python
   # 确保导入工具类以触发注册
   from verl.workers.agent.envs.mm_process_engine.FBCNNToolbox import (
       FBCNNJpegArtifactRemovalToolbox,
       FBCNNBlindQualityAssessmentToolbox
   )
   ```

2. **API连接失败**
   - 检查FBCNN服务是否运行在正确端口
   - 验证网络连接
   - 检查服务健康状态：`curl http://172.18.148.193:5005/health`

3. **GPU相关错误**
   - 检查GPU可用性
   - 确认FBCNN服务的GPU配置
   - 尝试不指定GPU让系统自动选择

4. **参数错误**
   - QF必须是"blind"或1-100的整数
   - GPU ID必须是有效的整数
   - 队列参数接受布尔值或字符串"true"/"false"

### 调试模式
工具提供详细的调试输出：
- API调用状态
- 参数构建过程
- 错误详情
- 执行时间统计

## 更新日志

### v1.0.0
- ✅ 实现FBCNN JPEG伪影去除工具
- ✅ 实现FBCNN盲质量评估工具
- ✅ 支持多种参数模式
- ✅ 完善错误处理机制
- ✅ 添加完整测试套件
- ✅ 提供使用示例和文档

## 许可证

本工具箱遵循项目的整体许可证。
