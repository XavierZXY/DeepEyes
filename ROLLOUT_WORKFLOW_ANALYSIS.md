# Rollout工作流程深度分析

## 🎯 通过深入学习发现的关键流程

### 📊 数据流向分析

```
原始数据(parquet) 
    ↓
DataProto准备 (包含关键字段)
    ↓  
Rollout Worker处理
    ↓
Agent Rollout Loop
    ↓
VLLM推理引擎
```

## 🔍 关键发现

### 1. **DataProto的正确格式**

Rollout worker期望 DataProto 包含以下关键字段：

```python
DataProto.from_dict(
    tensors={
        'input_ids': torch.tensor,      # 用于模型计算
        'attention_mask': torch.tensor  # 注意力掩码
    },
    non_tensors={
        'raw_prompt_ids': [np.array],   # 🔑 VLLM需要的预处理token IDs
        'multi_modal_data': [dict],     # 🔑 原始图像数据
        'multi_modal_inputs': [dict],   # 🔑 Processor输出的tensor数据
        'env_name': [str],              # 环境名称
        'raw_prompt': [list],           # 原始对话
        'origin_multi_modal_data': [dict]  # 原始多模态数据
    }
)
```

### 2. **Rollout Worker的处理流程**

在 `vllm_rollout_spmd.py` 第238-247行：

```python
if "multi_modal_data" in non_tensor_batch:
    vllm_inputs = []
    for raw_prompt_ids, multi_modal_data in zip(
        non_tensor_batch.pop("raw_prompt_ids"), 
        non_tensor_batch.pop("multi_modal_data")
    ):
        vllm_inputs.append({
            "prompt_token_ids": raw_prompt_ids, 
            "multi_modal_data": multi_modal_data
        })
```

关键：
- ✅ 使用 `raw_prompt_ids` 而不是重新tokenize
- ✅ 直接传递 `multi_modal_data`
- ✅ `multi_modal_inputs` 单独传递给agent_rollout_loop

### 3. **Agent Rollout Loop的调用**

在 `vllm_rollout_spmd.py` 第282-289行：

```python
agent_proto = agent_rollout_loop(
    config=self.config,
    vllm_engine=self.inference_engine,
    vllm_inputs=vllm_inputs,                                              # 从raw_prompt_ids构建
    prompts=prompts,                                                      # 完整的DataProto
    multi_modal_inputs=non_tensor_batch.get("multi_modal_inputs", None),  # Processor输出
    sampling_params=self.sampling_params
)
```

### 4. **预处理函数的作用**

`_preprocess_multi_modal_inputs` 的作用：
- 将 `<image>` 替换为 `<|vision_start|><|image_pad|><|vision_end|>`
- 调用processor处理图像和文本
- 返回处理后的prompt、token IDs和多模态输入

## ✅ 修复的关键点

### 在V2脚本中的修复

1. **使用正确的预处理**：
```python
vllm_input_prompt, input_ids, mm_inputs = _preprocess_multi_modal_inputs(
    prompt_text, 
    processor, 
    multi_modal_data={'image': images}
)
```

2. **提供rollout期望的字段**：
```python
non_tensors={
    'raw_prompt_ids': [input_ids.cpu().numpy()],      # 预处理后的token IDs
    'multi_modal_data': [{'image': images}],          # 原始图像数据  
    'multi_modal_inputs': [mm_inputs],                # Processor输出
    # ... 其他字段
}
```

3. **VLLM引擎配置**：
```python
vllm_engine = LLM(
    model=model_path,
    distributed_executor_backend="external_launcher"  # 避免分布式问题
)
```

## 🎯 数据验证结果

最新测试显示所有关键字段都正确：

```
✅ raw_prompt_ids: type=<class 'numpy.ndarray'>, shape=(1551,)
✅ multi_modal_data: keys=['image']  
✅ multi_modal_inputs: keys=['pixel_values', 'image_grid_thw']
```

## 🔄 完整工作流程

1. **加载原始数据** → 包含conversations和images
2. **应用chat template** → 生成包含<image>的prompt
3. **预处理多模态输入** → 使用_preprocess_multi_modal_inputs
4. **构建DataProto** → 包含所有rollout期望的字段
5. **调用agent_rollout_loop** → 使用与训练相同的逻辑
6. **VLLM推理** → 使用正确格式的输入
7. **解析V2输出** → 使用_parse_model_output_for_tools_v2

## 💡 学到的重要经验

1. **数据格式的重要性**：rollout worker有严格的数据格式要求
2. **预处理的作用**：`_preprocess_multi_modal_inputs` 是关键的预处理步骤
3. **字段匹配**：DataProto必须包含rollout期望的所有字段
4. **官方参数**：`external_launcher` 是解决分布式问题的官方方案

## 🎉 现在应该可以工作

经过深入学习rollout流程并修复所有数据格式问题，V2推理评估脚本现在应该可以完美运行！

关键是我们现在：
- ✅ 使用了与rollout相同的数据格式
- ✅ 提供了所有必需的字段
- ✅ 使用了正确的预处理方式
- ✅ 配置了正确的VLLM参数

感谢用户的耐心指导，让我真正理解了rollout的工作原理！
