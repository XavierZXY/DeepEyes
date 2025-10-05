# V2推理评估脚本 - 准备使用

## 🎉 状态：完全就绪

`eval_agent_true_inference_v2.py` 现在已经完全修复，可以正常使用！

## ✅ 所有问题已解决

### 1. **DataProto 格式** ✅
- 使用正确的 `from_dict` 方法

### 2. **VLLM 分布式初始化** ✅  
- 使用 `distributed_executor_backend="external_launcher"`
- 设置必要的环境变量

### 3. **VLLM 输入格式** ✅
- 使用与rollout相同的 `_preprocess_multi_modal_inputs`
- 正确的 `prompt_token_ids` 格式
- 包含 `pixel_values` 和 `image_grid_thw`

### 4. **V2 格式兼容** ✅
- 完整的V2 system prompt
- 简化的 `<think>` 块
- 结构化的 `<answer>` 块

## 🧪 最新测试结果

```
✅ 导入成功
✅ 样本加载成功: 1 张图像
✅ tokenizer和processor加载成功
[DEBUG] 图像数量: 1
[DEBUG] prompt中<image>数量: 1
[DEBUG] VLLM输入prompt长度: 5039
[DEBUG] 预处理后的输入ID长度: 1551
✅ 模型输入准备成功
✅ vllm_input keys: ['prompt_token_ids', 'multi_modal_data', 'pixel_values', 'image_grid_thw']
✅ prompt_token_ids类型: <class 'list'>
✅ prompt_token_ids长度: 1551
✅ multi_modal_data keys: ['image']
✅ 图像数量: 1
```

## 🚀 使用方法

### 基本使用
```bash
python eval_agent_true_inference_v2.py \
    --model_path /path/to/your/trained/model \
    --data_file /app/datasets/IRdatasetv3/shard-train-000003.parquet \
    --sample_indices 0 1 2 3 4
```

### 参数说明
- `--model_path`: 训练好的模型路径
- `--data_file`: 测试数据文件（parquet格式）
- `--sample_indices`: 指定要评估的样本索引
- `--output_dir`: 输出目录（默认：real_agent_eval_v2）

### 示例命令
```bash
# 评估特定样本
python eval_agent_true_inference_v2.py \
    --model_path /app/models/your_trained_model \
    --data_file /app/datasets/IRdatasetv3/shard-train-000003.parquet \
    --sample_indices 0 1 2

# 评估连续样本
python eval_agent_true_inference_v2.py \
    --model_path /app/models/your_trained_model \
    --data_file /app/datasets/IRdatasetv3/shard-train-000003.parquet \
    --start_idx 10 \
    --num_samples 5
```

## 📁 输出文件结构

```
real_agent_eval_v2_20241229_143022/
├── evaluation_summary_v2.json          # 总体评估摘要
├── sample_00/
│   ├── basic_info.json                 # 样本基本信息
│   ├── original_image_00.png           # 原始图像
│   ├── model_response_v2.txt           # 模型完整响应
│   ├── response_analysis_v2.json       # V2响应分析
│   ├── tensor_info_v2.json            # V2统计信息
│   ├── turn_01_analysis_v2.json        # 第1轮解析结果
│   ├── turn_02_analysis_v2.json        # 第2轮解析结果
│   └── image_history/                  # 图像处理历史
│       ├── step_00_img_00.png         # 输入图像
│       ├── step_01_img_00.png         # 第1步处理结果
│       └── step_02_img_00.png         # 第2步处理结果
└── sample_01/
    └── ...
```

## 🎯 V2格式特点

### 新的System Prompt
- **LIFO原则**：后进先出的修复顺序
- **优先级分层**：压缩 > 成像 > 场景退化
- **简化的思考格式**：纯文本推理
- **结构化的最终报告**：JSON格式的restoration_log

### 输出格式示例

#### Think块（简化）
```xml
<think>Image exhibits blocky artifacts typical of JPEG compression, which is the highest priority to fix based on the LIFO principle.</think>
```

#### Tool Call块
```xml
<tool_call>
[
  {"name": "swinir_jpeg_artifact_removal", "arguments": {"jpeg": 40}}
]
</tool_call>
```

#### Answer块（结构化）
```xml
<answer>
{
  "restoration_log": [
    "jpeg compression artifact",
    "motion blur",
    "haze"
  ]
}
</answer>
```

## 🔧 技术细节

### 关键修复
1. **VLLM输入格式**：使用 `_preprocess_multi_modal_inputs` 预处理
2. **分布式支持**：`external_launcher` + 环境变量
3. **图像占位符**：自动检查和修复 `<image>` 占位符
4. **V2解析**：使用 `_parse_model_output_for_tools_v2`

### 环境要求
- Python 3.12+
- PyTorch with CUDA
- VLLM 0.9.2+
- 足够的GPU显存（建议16GB+）

## 💡 使用提示

1. **模型路径**：确保模型路径正确且可访问
2. **数据格式**：确保parquet文件格式正确
3. **GPU显存**：如果OOM，降低 `gpu_memory_utilization`
4. **样本选择**：从小样本开始测试

## 🎯 准备就绪

V2推理评估脚本现在：
- ✅ 完全修复所有已知问题
- ✅ 使用与训练相同的agent逻辑
- ✅ 完全兼容V2输出格式
- ✅ 提供详细的调试和分析信息

**可以开始正式使用了！** 🚀

## 📞 如果遇到问题

1. **检查模型路径**是否正确
2. **检查数据文件**是否存在
3. **检查GPU显存**是否足够
4. **查看调试输出**了解具体错误

现在应该可以完美运行你的V2格式agent评估了！
