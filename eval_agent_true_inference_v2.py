#!/usr/bin/env python3
"""
真实Agent推理评估 V2 - 兼容新的v2输出格式
完全基于训练脚本的逻辑，使用真实的VLLM推理
"""

import os
import sys
import json
import torch
import pandas as pd
import numpy as np
from PIL import Image
from pathlib import Path
from datetime import datetime
import io
from copy import deepcopy

# 添加项目路径
sys.path.append('/app/xiaominl/DeepEyes')

from verl.utils import hf_tokenizer, hf_processor
from verl.workers.agent.parallel_env_v2 import agent_rollout_loop
from verl import DataProto
from verl.utils.dataset.vision_utils import process_image
from omegaconf import DictConfig, OmegaConf

def load_sample_data(data_file: str, sample_idx: int):
    """加载样本数据"""
    df = pd.read_parquet(data_file)
    if sample_idx >= len(df):
        raise IndexError(f"样本索引超出范围")
    
    row = df.iloc[sample_idx]
    
    # 解析图像 - 使用与训练相同的处理方式
    from verl.utils.dataset.vision_utils import process_image
    images = []
    if isinstance(row['images'], np.ndarray):
        # 按照训练时的方式处理图像
        for img_data in row['images']:
            processed_img = process_image(img_data)
            # 确保是PIL图像格式
            if isinstance(processed_img, dict) and 'image' in processed_img:
                images.append(processed_img['image'])
            elif hasattr(processed_img, 'size'):  # PIL图像
                images.append(processed_img)
            else:
                print(f"[WARNING] 未知图像格式: {type(processed_img)}")
                images.append(processed_img)
        print(f"[DEBUG] 使用process_image处理了 {len(images)} 张图像")
    
    # 解析对话
    conversations = []
    if isinstance(row['prompt'], np.ndarray):
        conversations = row['prompt'].tolist()
    
    return {
        'env_name': row['env_name'],
        'images': images,
        'conversations': conversations,
        'data_source': row['data_source']
    }

def prepare_model_inputs_v2(sample_data: dict, tokenizer, processor):
    """准备模型输入 V2 - 使用新的system prompt格式"""
    
    conversations = sample_data['conversations']
    images = sample_data['images']
    env_name = sample_data['env_name']
    
    # 构建V2格式的system prompt
    system_prompt = """You are a helpful assistant.

## Goal
Your mission is twofold:
1.  Act as an expert in an **iterative image restoration process**. In each step, you must identify the single highest-priority degradation, explain your reasoning, and suggest the correct tool.
2.  Act as a **final reporter**. Once the image is fully restored, you must provide a summary report listing all the restoration steps taken in the order they were performed.

## Restoration Principle (Execution Order)
You must restore the image by **reversing the degradation process (LIFO)**. The execution priority is the inverse of the degradation order. Always fix a Stage 1 issue before a Stage 2 issue, and a Stage 2 issue before a Stage 3 issue.

-   **Priority 1: Compression Degradation (`Dcompression`)**
    -   *Caused by digital storage/transmission. **Fix these first.***
    -   Types: "jpeg compression artifact"

-   **Priority 2: Imaging Degradation (`Dimaging`)**
    -   *Caused by camera hardware/process. **Fix these after compression is clear.***
    -   Types: "motion blur", "defocus blur", "noise", "low resolution"

-   **Priority 3: Scene Degradation (`Dscene`)**
    -   *Caused by environmental factors. **Fix these last.***
    -   Types: "haze", "rain", "dark"

If no degradations are found, the diagnosis label must be "clean".

## Allowed tools (names & minimal arguments)
-   `dehazeformer_dehaze`: `{ "strength": 0..1 }` (Applies to: "haze")
-   `drbnet_defocus_deblurring`: `{ "radius": >0 }` (Applies to: "defocus blur")
-   `histogram_equalization`: `{ "mode": "global"|"clahe" }` (Applies to: "dark")
-   `gamma_correction`: `{ "gamma": >0 }` (Applies to: "dark")
-   `xrestormer_motion_deblurring`: `{ "strength": 0..1 }` (Applies to: "motion blur", "rain")
-   `mprnet_motion_deblurring`: `{ "strength": 0..1 }` (Applies to: "motion blur")
-   `mprnet_deraining`: `{ "strength": 0..1 }` (Applies to: "rain")
-   `swinir_jpeg_artifact_removal`: `{ "jpeg": 1..100 }` (Applies to: "jpeg compression artifact")
-   `fbcnn_jpeg_artifact_removal`: `{ "jpeg": 1..100 }` (Applies to: "jpeg compression artifact")
-   `swinir_super_resolution`: `{ "scale": 2|3|4 }` (Applies to: "low resolution")
-   `swinir_denoising`: `{ "noise": 1..50 }` (Applies to: "noise")
-   `mprnet_denoising`: `{ "strength": 0..1 }` (Applies to: "noise")

## Step protocol (STRICT)
1)  For each step, output exactly one `<think>` block that contains **only** a brief reasoning string explaining your diagnosis.
2)  If you find a degradation, output a `<tool_call>` block.
3)  If the image is clean, you must output the final `<answer>` block, which is a JSON report. The `restoration_log` in the report lists the degradations in the order they were fixed (the "addition order").

### <think> (brief reasoning only)
Example 1:
<think>Image exhibits blocky artifacts typical of JPEG compression, which is the highest priority to fix based on the LIFO principle.</think>

Example 2:
<think>No significant artifacts remain.</think>

### <tool_call> (must include parameters if any)
<tool_call>
[
  {"name": "tool_name", "arguments": {}}
]
</tool_call>

### <answer> (Final JSON Report Only)
The `restoration_log` array **must** list the degradations in the order they were fixed.
<answer>
{
  "restoration_log": [
    "jpeg compression artifact",
    "motion blur",
    "haze"
  ]
}
</answer>

## Formatting rules
-   **Always** include a `<think>` block with non-empty reasoning.
-   The final `<answer>` must be the specified JSON object (no `status` field).

## Examples
*Scenario: An input image has both JPEG artifacts (Priority 1) and motion blur (Priority 2).*

# Example A (First Pass)
<think>The image shows noticeable 8x8 blockiness and ringing artifacts, especially in flat areas. According to the restoration principle, compression artifacts are Priority 1 and must be fixed first.</think>
<tool_call>
[
  {"name":"swinir_jpeg_artifact_removal","arguments":{"jpeg":40}}
]
</tool_call>

# Example B (Second Pass)
*The user provides the de-compressed image and a restoration log.*
<think>The compression artifacts are gone, but a clear directional blur is now visible, indicating camera shake. This is an imaging degradation (Priority 2) and is now the most critical issue. I will choose xrestormer as it's a strong general-purpose deblurrer.</think>
<tool_call>
[
  {"name":"xrestormer_motion_deblurring","arguments":{}}
]
</tool_call>

# Example C (Final Pass)
*The user provides the de-blurred image and the final restoration log.*
<think>After analyzing the image, I can no longer detect any significant compression, imaging, or scene-level degradations. The image is now considered clean.</think>
<answer>
{
  "restoration_log": [
    "jpeg compression artifact",
    "motion blur"
  ]
}
</answer>"""
    
    # 构建prompt文本 - 保持原始<image>格式供agent rollout loop处理
    if conversations and len(conversations) >= 2:
        # 直接使用原始conversations，保持<image>占位符
        prompt_text = tokenizer.apply_chat_template(
            conversations, 
            add_generation_prompt=True, 
            tokenize=False
        )
        print(f"[DEBUG] 使用原始conversations，保持<image>占位符供rollout处理")
    else:
        # 如果没有对话，使用默认V2模板
        prompt_text = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n<image>\nPlease assess the quality of this image. If there are any degradation issues that need fixing, please provide the first step of the solution.<|im_end|>\n<|im_start|>assistant\n"
    
    # 处理多模态输入 - 使用与rollout相同的格式
    if processor and images:
        # 使用与训练相同的图像处理（images已经是process_image处理后的结果）
        processed_images = images
        
        # 确保占位符数量匹配图像数量
        image_count = len(processed_images)
        print(f"[DEBUG] 图像数量: {image_count}")
        print(f"[DEBUG] prompt中<image>数量: {prompt_text.count('<image>')}")
        
        if '<image>' not in prompt_text:
            # 如果prompt中没有<image>占位符，添加一个
            print(f"[DEBUG] 添加<image>占位符")
            prompt_text = prompt_text.replace('<|im_start|>user\n', f'<|im_start|>user\n<image>\n')
        
        # 确保<image>数量与图像数量匹配
        current_image_count = prompt_text.count('<image>')
        if current_image_count != image_count:
            print(f"[WARNING] <image>占位符数量不匹配: 需要{image_count}个，实际{current_image_count}个")
            # 如果不匹配，尝试修复
            if current_image_count == 0:
                prompt_text = prompt_text.replace('<|im_start|>user\n', f'<|im_start|>user\n<image>\n')
            elif current_image_count < image_count:
                # 需要添加更多占位符
                additional_images = '<image>' * (image_count - current_image_count)
                prompt_text = prompt_text.replace('<image>', f'<image>{additional_images}', 1)
        
        # 关键修复：按照训练时的方式处理
        # 1. raw_prompt_ids: 纯文本tokenize（不包含vision token）
        raw_prompt_ids = tokenizer.encode(prompt_text, add_special_tokens=False)
        print(f"[DEBUG] raw_prompt_ids长度: {len(raw_prompt_ids)}")
        
        # 2. 用processor处理完整的输入（包含图像和文本）
        model_inputs = processor(text=[prompt_text], images=processed_images, return_tensors="pt")
        dataproto_input_ids = model_inputs['input_ids'][0]
        dataproto_attention_mask = model_inputs['attention_mask'][0]
        
        print(f"[DEBUG] processor处理后input_ids长度: {len(dataproto_input_ids)}")
        print(f"[DEBUG] 长度差异: {len(dataproto_input_ids) - len(raw_prompt_ids)} (应该是vision token数量)")
        
        # 3. 移除不需要的键，保留多模态输入
        model_inputs.pop('input_ids')
        model_inputs.pop('attention_mask')
        if 'second_per_grid_ts' in model_inputs:
            model_inputs.pop('second_per_grid_ts')
        
        mm_inputs = dict(model_inputs)
        
        # 4. 创建VLLM输入 - 关键修复：让_preprocess_multi_modal_inputs来处理
        vllm_input = {
            'prompt_token_ids': raw_prompt_ids,  # 包含<image>的原始token序列
            'multi_modal_data': {'image': processed_images}
        }
    else:
        # 纯文本输入
        inputs = tokenizer(prompt_text, return_tensors="pt")
        dataproto_input_ids = inputs['input_ids'][0]
        dataproto_attention_mask = inputs['attention_mask'][0]
        
        vllm_input = {
            'prompt_token_ids': dataproto_input_ids.cpu().numpy().tolist()
        }
    
    # 创建DataProto格式的prompt - 关键：添加raw_prompt_ids
    prompt_data = DataProto.from_dict(
        tensors={
            'input_ids': dataproto_input_ids.unsqueeze(0),
            'attention_mask': dataproto_attention_mask.unsqueeze(0)
        },
        non_tensors={
            'env_name': [env_name],
            'raw_prompt': [updated_conversations if 'updated_conversations' in locals() else conversations],
            'origin_multi_modal_data': [{'image': images}] if images else [{}],
            'raw_prompt_ids': [np.array(raw_prompt_ids)],  # 关键！使用纯文本的token IDs
            'multi_modal_data': [{'image': processed_images}] if processed_images else [{}],  # 使用processed_images
            'multi_modal_inputs': [mm_inputs] if mm_inputs else [{}]  # rollout需要的多模态输入
        }
    )
    
    return prompt_data, vllm_input

def create_eval_config_v2():
    """创建V2评估配置 - 基于训练配置，添加rollout配置"""
    
    config = {
        'prompt_length': 8192,
        'response_length': 20480,
        'agent': {
            'max_turns': 5,  # 恢复正常的多轮设置
            'single_response_max_tokens': 10240,
            'tool_name_key': 'env_name',
            'concurrent_workers': 1,
            'show_tqdm': True,
            'custom_stop': [],
            'vl_model_path': '/app/models/Qwen2.5-VL-7B-Instruct',  # 这里需要改为你的训练模型路径
            'activate_agent': True
        },
        'rollout': {
            'name': 'vllm',
            'tensor_model_parallel_size': 1,
            'gpu_memory_utilization': 0.4,
            'max_model_len': 32768,
            'trust_remote_code': True,
            'distributed_executor_backend': 'external_launcher'
        }
    }
    
    return OmegaConf.create(config)

def evaluate_with_real_vllm_v2(model_path: str, data_file: str, sample_indices: list, output_dir: str):
    """使用真实VLLM进行V2评估"""
    
    print(f"🎯 真实VLLM Agent评估 V2")
    print(f"🤖 模型: {model_path}")
    print(f"📁 数据: {data_file}")
    print(f"📊 样本: {sample_indices}")
    
    # 创建输出目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    full_output_dir = Path(output_dir) / f"real_eval_v2_{timestamp}"
    full_output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # 设置external_launcher需要的环境变量
        os.environ.setdefault("RANK", "0")
        os.environ.setdefault("LOCAL_RANK", "0") 
        os.environ.setdefault("WORLD_SIZE", "1")
        os.environ.setdefault("MASTER_ADDR", "127.0.0.1")
        os.environ.setdefault("MASTER_PORT", "29500")
        
        # 初始化VLLM引擎（使用external_launcher避免分布式问题）
        from vllm import LLM, SamplingParams
        
        print(f"🚀 初始化VLLM引擎...")
        vllm_engine = LLM(
            model=model_path,
            tensor_parallel_size=1,
            gpu_memory_utilization=0.4,
            max_model_len=32768,
            trust_remote_code=True,
            distributed_executor_backend="external_launcher"  # 关键参数！
        )
        print(f"✅ VLLM引擎初始化成功")
        
        # 初始化tokenizer和processor
        tokenizer = hf_tokenizer(model_path)
        processor = hf_processor(model_path)
        
        # 导入工具模块
        import verl.workers.agent.envs.mm_process_engine.DehazeFormerToolbox
        import verl.workers.agent.envs.mm_process_engine.BrighteningToolbox
        import verl.workers.agent.envs.mm_process_engine.SwinIRToolbox
        import verl.workers.agent.envs.mm_process_engine.DeblurToolbox
        import verl.workers.agent.envs.mm_process_engine.XRestormerToolbox
        import verl.workers.agent.envs.mm_process_engine.MPRNetToolbox
        import verl.workers.agent.envs.mm_process_engine.FBCNNToolbox
        
        # 创建配置
        config = create_eval_config_v2()
        config.agent.vl_model_path = model_path  # 使用实际模型路径
        
        # 创建采样参数
        sampling_params = SamplingParams(
            n=1,
            max_tokens=10240,
            temperature=0.1,
            top_p=0.9,
            stop=None,
            skip_special_tokens=False,
            spaces_between_special_tokens=False,
            include_stop_str_in_output=True
        )
        
        # 评估每个样本
        all_results = []
        
        for sample_idx in sample_indices:
            try:
                print(f"\n{'='*60}")
                print(f"🔍 评估样本 {sample_idx} (V2格式)")
                
                # 加载样本
                sample_data = load_sample_data(data_file, sample_idx)
                
                # 创建样本目录
                sample_dir = full_output_dir / f"sample_{sample_idx:02d}"
                sample_dir.mkdir(exist_ok=True)
                
                # 保存原始数据
                save_original_data(sample_data, sample_dir)
                
                # 准备模型输入 (V2)
                prompt_data, vllm_input = prepare_model_inputs_v2(sample_data, tokenizer, processor)
                
                # 准备数据 - 直接使用prompt_data
                prompts = prompt_data
                
                # 多模态输入 - 修复格式问题
                multi_modal_inputs = None
                if 'multi_modal_data' in vllm_input:
                    # 从DataProto中获取正确的multi_modal_inputs
                    if 'multi_modal_inputs' in prompts.non_tensor_batch:
                        mm_inputs_from_dataproto = prompts.non_tensor_batch['multi_modal_inputs']
                        multi_modal_inputs = mm_inputs_from_dataproto  # 直接使用DataProto中的格式
                        print(f"[DEBUG] 使用DataProto中的multi_modal_inputs: {type(mm_inputs_from_dataproto)}")
                    else:
                        # 如果没有，创建占位符
                        multi_modal_inputs = [{}]  # 列表格式，每个元素是字典
                        print(f"[DEBUG] 创建占位符multi_modal_inputs")
                
                print(f"🚀 开始真实Agent推理 (V2) - 使用rollout worker...")
                
                # 直接调用agent_rollout_loop，但先检查数据格式
                print(f"[DEBUG] 调用前检查:")
                print(f"  prompts.non_tensor_batch keys: {list(prompts.non_tensor_batch.keys())}")
                if 'raw_prompt_ids' in prompts.non_tensor_batch:
                    raw_ids = prompts.non_tensor_batch['raw_prompt_ids'][0]
                    print(f"  raw_prompt_ids长度: {len(raw_ids)}")
                
                # 执行agent rollout loop
                result = agent_rollout_loop(
                    config=config,
                    vllm_engine=vllm_engine,
                    vllm_inputs=[vllm_input],
                    prompts=prompts,
                    multi_modal_inputs=multi_modal_inputs,
                    sampling_params=sampling_params
                )
                
                print(f"✅ Agent推理完成 (V2)")
                
                # 保存推理结果 (V2)
                save_inference_results_v2(result, sample_data, sample_dir, sample_idx, tokenizer)
                
                all_results.append({
                    'sample_idx': sample_idx,
                    'env_name': sample_data['env_name'],
                    'status': 'success'
                })
                
            except Exception as e:
                print(f"❌ 样本 {sample_idx} 推理失败: {e}")
                import traceback
                traceback.print_exc()
                
                all_results.append({
                    'sample_idx': sample_idx,
                    'env_name': sample_data.get('env_name', 'unknown'),
                    'status': 'failed',
                    'error': str(e)
                })
        
        # 保存总体结果
        save_overall_results(all_results, full_output_dir, model_path, data_file)
        
        print(f"\n🎉 真实推理评估V2完成！")
        print(f"📁 结果目录: {full_output_dir}")
        
        return full_output_dir
        
    except Exception as e:
        print(f"❌ VLLM引擎初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def save_original_data(sample_data: dict, sample_dir: Path):
    """保存原始数据"""
    
    # 保存基本信息
    basic_info = {
        'env_name': sample_data['env_name'],
        'data_source': sample_data['data_source'],
        'num_images': len(sample_data['images']),
        'image_sizes': [img.size for img in sample_data['images']]
    }
    
    with open(sample_dir / "basic_info.json", 'w', encoding='utf-8') as f:
        json.dump(basic_info, f, indent=2, ensure_ascii=False)
    
    # 保存原始图像
    for img_idx, img in enumerate(sample_data['images']):
        img_path = sample_dir / f"original_image_{img_idx:02d}.png"
        img.save(img_path)
        print(f"💾 保存原始图像: {img_path} ({img.size})")
    
    # 保存对话
    if sample_data['conversations']:
        with open(sample_dir / "conversations.json", 'w', encoding='utf-8') as f:
            json.dump(sample_data['conversations'], f, indent=2, ensure_ascii=False)

def save_inference_results_v2(result, sample_data: dict, sample_dir: Path, sample_idx: int, tokenizer):
    """保存V2推理结果"""
    
    if result is None:
        return
    
    # 保存tensor信息
    if hasattr(result, 'tensors'):
        tensor_info = {}
        for key, tensor in result.tensors.items():
            if torch.is_tensor(tensor):
                tensor_info[key] = {
                    'shape': list(tensor.shape),
                    'dtype': str(tensor.dtype)
                }
                
                # 保存重要的统计数据
                if key in ['tool_cnt', 'final_answer', 'repeated_degradation_cnt', 'restoration_log_length']:
                    tensor_info[key]['data'] = tensor.cpu().numpy().tolist()
                elif key.startswith('degradation_'):
                    tensor_info[key]['data'] = tensor.cpu().numpy().tolist()
                elif key.startswith('tool_usage_'):
                    tensor_info[key]['data'] = tensor.cpu().numpy().tolist()
        
        with open(sample_dir / "tensor_info_v2.json", 'w') as f:
            json.dump(tensor_info, f, indent=2)
    
    # 解码并保存响应文本
    if hasattr(result, 'tensors') and 'response' in result.tensors:
        response_ids = result.tensors['response'][0]  # 第一个样本
        
        # 移除padding tokens
        if hasattr(tokenizer, 'pad_token_id') and tokenizer.pad_token_id is not None:
            response_ids = response_ids[response_ids != tokenizer.pad_token_id]
        
        response_text = tokenizer.decode(response_ids, skip_special_tokens=True)
        
        # 保存完整响应
        with open(sample_dir / "model_response_v2.txt", 'w', encoding='utf-8') as f:
            f.write(response_text)
        
        print(f"📝 模型响应长度: {len(response_text)} 字符")
        print(f"📝 响应预览: {response_text[:200]}...")
        
        # 分析V2响应中的工具调用和图像变化
        analyze_response_v2_and_save_images(response_text, sample_dir, result)
    
    # 保存图像历史（如果有）
    if hasattr(result, 'non_tensors') and result.non_tensors:
        image_history_list = result.non_tensors.get('image_history_list', None)
        if image_history_list is not None and len(image_history_list) > 0:
            save_image_history_v2(image_history_list[0], sample_dir)  # 第一个样本的图像历史
    
    print(f"✅ 样本 {sample_idx} V2推理结果已保存")

def analyze_response_v2_and_save_images(response_text: str, sample_dir: Path, result):
    """分析V2响应并提取图像变化"""
    
    from verl.workers.agent.parallel_env_v2 import _parse_model_output_for_tools_v2
    
    # 分割多轮对话
    assistant_turns = response_text.split('<|im_start|>assistant\n')
    
    turn_analyses = []
    for turn_idx, turn_text in enumerate(assistant_turns[1:], 1):  # 跳过第一个空分割
        if not turn_text.strip():
            continue
        
        # 移除可能的结束标记
        turn_text = turn_text.split('<|im_end|>')[0].strip()
        
        print(f"🔍 分析第 {turn_idx} 轮 (V2格式)...")
        
        # 使用V2解析器解析这一轮
        parsed = _parse_model_output_for_tools_v2(turn_text, f"analysis-turn{turn_idx}")
        
        turn_analysis = {
            'turn': turn_idx,
            'raw_text': turn_text,
            'has_think': parsed.get('think') is not None,
            'think_content': parsed.get('think'),  # V2: 直接是文本内容
            'has_tool_calls': len(parsed.get('tool_calls', [])) > 0,
            'tool_calls': parsed.get('tool_calls', []),
            'has_answer': parsed.get('is_done', False),
            'answer': parsed.get('answer'),
            'restoration_log': parsed.get('restoration_log', []),  # V2: 从answer中提取的restoration_log
            'format_version': 'v2'
        }
        
        turn_analyses.append(turn_analysis)
        
        # 保存单轮分析
        turn_file = sample_dir / f"turn_{turn_idx:02d}_analysis_v2.json"
        with open(turn_file, 'w', encoding='utf-8') as f:
            json.dump(turn_analysis, f, indent=2, ensure_ascii=False)
        
        print(f"  📋 第{turn_idx}轮(V2): think={turn_analysis['has_think']}, tools={len(turn_analysis['tool_calls'])}, answer={turn_analysis['has_answer']}")
        if turn_analysis['restoration_log']:
            print(f"      🔧 修复日志: {turn_analysis['restoration_log']}")
    
    # 保存完整分析
    with open(sample_dir / "response_analysis_v2.json", 'w', encoding='utf-8') as f:
        json.dump(turn_analyses, f, indent=2, ensure_ascii=False)
    
    print(f"📊 V2响应分析完成: {len(turn_analyses)} 轮")

def save_image_history_v2(image_history, sample_dir: Path):
    """保存V2图像历史"""
    
    if not image_history or len(image_history) == 0:
        print(f"⚠️  没有图像历史可保存")
        return
    
    history_dir = sample_dir / "image_history"
    history_dir.mkdir(exist_ok=True)
    
    print(f"💾 保存图像历史: {len(image_history)} 步")
    
    for step_idx, step_data in enumerate(image_history):
        if isinstance(step_data, dict) and 'image' in step_data:
            images = step_data['image']
            if images and len(images) > 0:
                for img_idx, img in enumerate(images):
                    if hasattr(img, 'save'):  # PIL Image
                        img_path = history_dir / f"step_{step_idx:02d}_img_{img_idx:02d}.png"
                        img.save(img_path)
                        print(f"  💾 步骤{step_idx} 图像{img_idx}: {img_path} ({img.size})")

def save_overall_results(all_results: list, output_dir: Path, model_path: str, data_file: str):
    """保存总体结果"""
    
    successful_count = sum(1 for r in all_results if r.get('status') == 'success')
    
    summary = {
        'evaluation_time': datetime.now().isoformat(),
        'model_path': model_path,
        'data_file': data_file,
        'total_samples': len(all_results),
        'successful_samples': successful_count,
        'success_rate': successful_count / len(all_results) if all_results else 0,
        'failed_samples': [r for r in all_results if r.get('status') != 'success'],
        'sample_results': all_results,
        'format_version': 'v2'
    }
    
    summary_file = output_dir / "evaluation_summary_v2.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"📊 总体摘要: {summary_file}")
    print(f"📈 成功率: {successful_count}/{len(all_results)} ({summary['success_rate']:.2%})")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="真实Agent推理评估 V2")
    parser.add_argument("--model_path", required=True, help="训练好的模型路径")
    parser.add_argument("--data_file", default="/app/datasets/IRdatasetv3/shard-train-000003.parquet", help="测试数据文件")
    parser.add_argument("--output_dir", default="real_agent_eval_v2", help="输出目录")
    parser.add_argument("--sample_indices", nargs='+', type=int, help="指定样本索引，如: 0 1 2 3")
    parser.add_argument("--num_samples", type=int, default=3, help="评估样本数量（从索引0开始）")
    parser.add_argument("--start_idx", type=int, default=0, help="起始样本索引")
    
    args = parser.parse_args()
    
    # 确定要评估的样本索引
    if args.sample_indices:
        sample_indices = args.sample_indices
    else:
        sample_indices = list(range(args.start_idx, args.start_idx + args.num_samples))
    
    print(f"🎯 真实Agent推理评估 V2")
    print(f"🤖 模型: {args.model_path}")
    print(f"📁 数据: {args.data_file}")
    print(f"📊 评估样本索引: {sample_indices}")
    
    # 设置环境变量
    os.environ['CUDA_VISIBLE_DEVICES'] = '4'  # 使用第一个GPU
    
    try:
        result_dir = evaluate_with_real_vllm_v2(
            model_path=args.model_path,
            data_file=args.data_file,
            sample_indices=sample_indices,
            output_dir=args.output_dir
        )
        
        if result_dir:
            print(f"\n🎉 V2评估完成！")
            print(f"📁 查看结果: {result_dir}")
            print(f"💡 V2格式提示:")
            print(f"   - model_response_v2.txt: 模型的完整输出")
            print(f"   - turn_XX_analysis_v2.json: 每轮的V2解析结果") 
            print(f"   - tensor_info_v2.json: V2统计信息")
            print(f"   - response_analysis_v2.json: 完整V2响应分析")
            print(f"   - image_history/: 图像处理历史")
        
    except Exception as e:
        print(f"❌ V2评估失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
