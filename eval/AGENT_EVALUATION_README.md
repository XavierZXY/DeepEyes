# Agent图像复原评估脚本使用说明

## 概述

`eval_agent_restoration.py` 是一个完整的 Agent 图像复原评估脚本，支持调用通过 vLLM 部署的模型（OpenAI 兼容接口），并计算多种图像质量指标。

## 功能特性

### 🎯 支持两种对话模式

1. **multi_tool_planning（多工具规划模式）**
   - 模型一次输出多个工具 `[tool1, tool2, tool3]`
   - 系统链式执行：原图 → tool1 → tool2 → tool3 → 结果
   - 工具间自动传递图像
   - 适合策略规划型任务
   - 推荐设置：`max_turns=1`

2. **single_tool_iterative（单工具迭代模式）**
   - 模型每次只输出一个工具
   - 每轮基于上轮结果决策
   - 逐步处理图像
   - 适合逐步反应型任务
   - 推荐设置：`max_turns=5-8`

### 📊 支持的评估指标

**有参考指标**（需要 ground truth）：
- **PSNR** (Peak Signal-to-Noise Ratio)
- **SSIM** (Structural Similarity Index)
- **LPIPS** (Learned Perceptual Image Patch Similarity)

**无参考指标**（仅需复原图）：
- **MANIQA** (Multi-dimension Attention Network for No-reference Image Quality Assessment)
- **MUSIQ** (Multi-Scale Image Quality Transformer)
- **CLIP-IQA** (CLIP-based Image Quality Assessment)

## 环境要求

### 必需依赖

```bash
# 基础依赖
pip install openai pyarrow pandas pillow numpy tqdm

# 图像质量评估
pip install pyiqa lpips scikit-image

# PyTorch (根据您的CUDA版本选择)
pip install torch torchvision
```

### 工具服务

确保图像处理工具服务已启动（参考项目中的工具服务配置）。

## 使用方法

### 1. 启动 vLLM 服务

首先需要启动 vLLM 服务部署您的模型：

```bash
vllm serve /path/to/your/model \
    --port 8000 \
    --gpu-memory-utilization 0.8 \
    --max-model-len 32768 \
    --tensor-parallel-size 4 \
    --trust-remote-code \
    --disable-log-requests
```

### 2. 运行评估

#### 基本用法（使用parquet中的系统提示词）

```bash
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results/default \
    --api_url http://localhost:8000/v1 \
    --conversation_mode multi_tool_planning \
    --max_turns 1 \
    --tool_service_ip 10.21.9.6 \
    --num_samples 100
```

**说明**：默认情况下会使用parquet文件中的系统提示词（`prompt[0]['content']`）。

#### 使用自定义系统提示词

```bash
python eval/eval_agent_restoration.py \
    --data_path /path/to/test_data.parquet \
    --output_dir ./eval_results/custom_prompt \
    --api_url http://localhost:8000/v1 \
    --no_parquet_system_prompt \
    --custom_system_prompt /path/to/custom_system_prompt.txt \
    --conversation_mode multi_tool_planning \
    --max_turns 1
```

**说明**：
- `--no_parquet_system_prompt`: 禁用parquet中的系统提示词
- `--custom_system_prompt`: 可以是文件路径或直接的提示词文本

#### 单工具迭代模式

```bash
python eval/eval_agent_restoration.py \
    --data_path /path/to/test_data.parquet \
    --output_dir ./eval_results/single_tool \
    --api_url http://localhost:8000/v1 \
    --conversation_mode single_tool_iterative \
    --max_turns 5 \
    --tool_service_ip 10.21.9.6
```

### 3. 完整参数说明

```bash
python eval/eval_agent_restoration.py --help
```

**主要参数：**

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--api_url` | vLLM API地址 | `http://localhost:8000/v1` |
| `--api_key` | API密钥 | `EMPTY` |
| `--model_name` | 模型名称（自动检测） | `None` |
| `--data_path` | 测试数据路径（parquet） | **必需** |
| `--output_dir` | 输出目录 | `./eval_results` |
| `--conversation_mode` | 对话模式 | `multi_tool_planning` |
| `--max_turns` | 最大对话轮次 | `1` |
| `--temperature` | 采样温度 | `0.7` |
| `--top_p` | Top-p采样 | `0.9` |
| `--no_parquet_system_prompt` | 不使用parquet中的系统提示词 | `False` |
| `--custom_system_prompt` | 自定义系统提示词（文件路径或文本） | `None` |
| `--tool_service_ip` | 工具服务IP | `10.21.9.6` |
| `--num_samples` | 评估样本数 | `None`（全部） |
| `--no_reference_metrics` | 禁用有参考指标 | `False` |
| `--no_no_reference_metrics` | 禁用无参考指标 | `False` |

## 数据格式

评估脚本期望 parquet 文件包含以下字段：

```python
{
    "prompt": [
        {"role": "system", "content": "系统提示词..."},
        {"role": "user", "content": "<image>\n用户消息..."}
    ],  # 对话prompt（numpy数组，包含系统和用户消息）
    "images": [
        "degraded_image_base64...",  # 退化图像（base64编码）
        "gt_image_base64..."  # Ground truth图像（base64编码）
    ],  # 图像数组
    "env_name": "rain, noise, blur",  # 退化类型（逗号分隔）
    "ability": "IR",  # 任务类型
    "reward_model": [...],  # 奖励模型配置
}
```

### System Prompt 处理逻辑

1. **默认行为**（`use_parquet_system_prompt=True`）：
   - 从 `prompt[0]['content']` 读取系统提示词
   - 如果格式不正确，回退到内置系统提示词

2. **自定义模式**（`--no_parquet_system_prompt --custom_system_prompt FILE`）：
   - 使用指定文件或文本作为系统提示词
   - 忽略parquet中的系统提示词

3. **内置模式**（`--no_parquet_system_prompt`，无自定义）：
   - 使用脚本内置的系统提示词

## 输出结果

评估完成后，输出目录包含：

```
eval_results/
├── config.json                      # 评估配置
├── evaluation_results.csv           # 主要结果（CSV格式）
├── summary.txt                      # 统计汇总
├── details/                         # 详细结果（JSON）
│   ├── sample_0000.json
│   ├── sample_0001.json
│   └── ...
└── images/                          # 复原图像
    ├── restored_0000.png
    ├── restored_0001.png
    └── ...
```

### evaluation_results.csv 字段说明

| 字段 | 说明 |
|------|------|
| `sample_id` | 样本ID |
| `psnr` | PSNR值（dB） |
| `ssim` | SSIM值 [0,1] |
| `lpips` | LPIPS值 [0,1]，越小越好 |
| `maniqa` | MANIQA分数 |
| `musiq` | MUSIQ分数 |
| `clipiqa` | CLIP-IQA分数 |
| `num_tools_used` | 使用的工具数量 |
| `tools_used` | 使用的工具名称 |
| `gt_degradations` | Ground truth退化类型 |
| `num_turns` | 对话轮次 |

### details/sample_XXXX.json 内容

```json
{
  "sample_id": 0,
  "conversation_history": [
    {
      "turn": 1,
      "model_output": "<think>...</think><tool_call>...</tool_call>"
    }
  ],
  "tool_results": [
    {
      "tool_name": "nafnet_deblur",
      "arguments": {...},
      "success": true,
      "reward": 0.85,
      "info": {...}
    }
  ],
  "metrics": {
    "psnr": 28.5,
    "ssim": 0.85,
    "lpips": 0.12,
    "maniqa": 0.75,
    ...
  }
}
```

## 示例脚本

参考 `eval_agent_restoration_example.sh` 查看完整的评估流程示例。

## 性能优化建议

### GPU内存优化

1. **调整batch size**：根据GPU显存调整
2. **使用量化模型**：如果显存不足，考虑使用量化版本
3. **分批评估**：使用 `--num_samples` 参数分批评估大数据集

### 加速评估

1. **减少指标计算**：
   - 如果不需要有参考指标：`--no_reference_metrics`
   - 如果不需要无参考指标：`--no_no_reference_metrics`

2. **调整温度**：
   - 更低的温度（如0.3）可以获得更稳定的输出
   - 更高的温度可以增加多样性

## 常见问题

### Q1: vLLM连接失败

**A:** 检查vLLM服务是否正常运行：
```bash
curl http://localhost:8000/v1/models
```

### Q2: 工具执行失败

**A:** 确保：
1. 工具服务正在运行
2. `TOOL_SERVICE_IP` 设置正确
3. 网络连接正常

### Q3: 指标计算失败

**A:** 检查pyiqa是否正确安装：
```bash
python -c "import pyiqa; print(pyiqa.list_models())"
```

### Q4: 内存不足

**A:** 尝试：
1. 减少 `--num_samples`
2. 降低 vLLM 的 `--max-model-len`
3. 使用 `--no_no_reference_metrics` 禁用部分指标

## 指标说明

### PSNR (Peak Signal-to-Noise Ratio)
- 范围：通常 10-50 dB
- 越高越好
- 衡量像素级误差

### SSIM (Structural Similarity Index)
- 范围：[-1, 1]，实际通常 [0, 1]
- 越高越好（1表示完全相同）
- 衡量结构相似性

### LPIPS (Learned Perceptual Image Patch Similarity)
- 范围：[0, 1]
- **越低越好**（0表示感知上相同）
- 基于深度学习特征，更接近人类感知

### MANIQA
- 无参考指标
- 越高越好
- 多维度注意力网络评估

### MUSIQ
- 无参考指标
- 越高越好
- 基于Transformer的多尺度评估

### CLIP-IQA
- 无参考指标
- 越高越好
- 基于CLIP的语义质量评估

## 与训练过程的对比

该评估脚本实现了与训练过程相同的：
1. 工具调用逻辑
2. 对话流程
3. 指标计算方法

可以直接用于验证训练后的模型性能。

## 进阶用法

### 自定义评估指标

可以在 `ImageQualityEvaluator` 类中添加新的指标：

```python
# 添加新的pyiqa指标
self.no_ref_metrics['your_metric'] = pyiqa.create_metric('your_metric', device=device)
```

### 自定义工具

工具会自动从 `ToolBase.registry` 注册，只需确保工具类已导入。

### 批量评估多个检查点

```bash
for ckpt in /path/to/checkpoints/*/; do
    # 启动vLLM
    vllm serve $ckpt --port 8000 &
    sleep 60
    
    # 评估
    python eval/eval_agent_restoration.py \
        --data_path data/test.parquet \
        --output_dir results/$(basename $ckpt)
    
    # 停止vLLM
    pkill -f "vllm serve"
done
```

## 贡献与反馈

如有问题或建议，请提交 Issue 或 Pull Request。

## 许可证

遵循项目主许可证（Apache 2.0）。

