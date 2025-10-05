#!/usr/bin/env python3
"""
真实Agent推理评估 - 完全基于训练脚本的逻辑，使用真实的VLLM推理
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
    
    # 解析图像
    images = []
    if isinstance(row['images'], np.ndarray):
        for img_data in row['images']:
            if isinstance(img_data, dict) and 'bytes' in img_data:
                img_bytes = img_data['bytes']
                pil_image = Image.open(io.BytesIO(img_bytes)).convert('RGB')
                images.append(pil_image)
    
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

def prepare_model_inputs(sample_data: dict, tokenizer, processor):
    """准备模型输入 - 完全按照训练时的格式"""
    
    conversations = sample_data['conversations']
    images = sample_data['images']
    env_name = sample_data['env_name']
    
    # 构建prompt文本
    if conversations and len(conversations) >= 2:
        # 使用实际的对话模板
        prompt_text = tokenizer.apply_chat_template(
            conversations, 
            add_generation_prompt=True, 
            tokenize=False
        )
    else:
        # 如果没有对话，使用默认模板
        prompt_text = "<|im_start|>system\nYou are a helpful assistant.\n\n## Goal\nGiven an image (and optional question), decide restoration tools **and minimal parameters** (if any). When choosing a tool, you must select from the list below based on the diagnosed degradation type(s). On every step you must output one <think> block, then either a <tool_call> (to execute next) or an <answer> (final success only).\n\n## Degradation Types\nYou must classify the image degradation using **only** the following labels. The `diagnosis.labels` array must be a subset of this list.\n- `\"rain\"`\n- `\"haze\"`\n- `\"dark\"`\n- `\"motion blur\"`\n- `\"defocus blur\"`\n- `\"noise\"`\n- `\"low resolution\"`\n- `\"jpeg compression artifact\"`\n- `\"clean\"` (Use this if the image has no detectable degradations)\n\n## Allowed tools (names & minimal arguments)\n- `dehazeformer_dehaze`: `{\"strength\": 0..1}` (Applies to: `\"haze\"`)\n- `drbnet_defocus_deblurring`: `{\"radius\": >0, \"strength\": 0..1 (optional)}` (Applies to: `\"defocus blur\"`)\n- `histogram_equalization`: `{\"mode\": \"global\"|\"clahe\"}` (Applies to: `\"dark\"`)\n- `gamma_correction`: `{\"gamma\": >0}` (Applies to: `\"dark\"`)\n- `constant_shift`: `{\"shift\": integer}` (Applies to: `\"dark\"`)\n- `xrestormer_motion_deblurring`: `{\"strength\": 0..1}` (Applies to: `\"motion blur\"`, `\"rain\"`)\n- `swinir_jpeg_artifact_removal`: `{\"strength\": 0..1}` (Applies to: `\"jpeg compression artifact\"`)\n- `swinir_super_resolution`: `{\"scale\": 2|3|4}` (Applies to: `\"low resolution\"`)\n- `swinir_denoising`: `{\"strength\": 0..1}` (Applies to: `\"noise\"`)\n\n## Step protocol (STRICT)\n1) Output exactly one <think> block (brief JSON: diagnosis & pass flag).\n2) If pass=false, output one <tool_call> block with an **ordered array** of tool objects including **name** and **arguments** (omit keys you don't override; use `{}` to accept defaults).\n3) If pass=true and external quality gate has PASSED, output one <answer> block. No other text.\n\n### <think> (brief JSON only)\n<think>{\n  \"diagnosis\": {\"labels\": [/* a list of strings from the \"Degradation Types\" list above */], \"levels\": {\"haze\": \"weak|medium|strong\"}},\n   \"pass\": true|false\n}</think>\n\n### <tool_call> (must include parameters if any)\n<tool_call>[\n  {\"name\": \"tool_name_1\", \"arguments\": { /* e.g., {\"strength\": 0.7} or {} */ }},\n  {\"name\": \"tool_name_2\", \"arguments\": {} }\n]</tool_call>\n- Execute in array order.\n- Keep the sequence short and minimal.\n\n### <answer> (final success only)\n<answer>success</answer>\n\n## Formatting rules\n- **Always** include <think> each step.\n- Use tool names **exactly** as listed.\n- Include only the keys you intend to set; otherwise use empty `{}`.\n- No explanations or extra text outside the three blocks.<|im_end|>\n<|im_start|>user\n<image>\nPlease assess the quality of this image. If there are any degradation issues that need fixing, please provide the first step of the solution.<|im_end|>\n<|im_start|>assistant\n"
    
    # 处理多模态输入
    if processor and images:
        # 确保占位符数量匹配图像数量
        image_count = len(images)
        prompt_text = prompt_text.replace('<image>', '<image>' * image_count, 1)
        
        # 处理图像
        model_inputs = processor(text=[prompt_text], images=images, return_tensors="pt")
        input_ids = model_inputs['input_ids'][0]
        attention_mask = model_inputs['attention_mask'][0]
        
        # 移除不需要的键
        model_inputs.pop('input_ids')
        model_inputs.pop('attention_mask')
        if 'second_per_grid_ts' in model_inputs:
            model_inputs.pop('second_per_grid_ts')
        
        # 创建VLLM输入
        vllm_input = {
            'prompt_token_ids': input_ids.cpu().numpy().tolist(),
            'multi_modal_data': {'image': images}
        }
        
        # 添加其他多模态数据
        if model_inputs:
            for key, value in model_inputs.items():
                if torch.is_tensor(value):
                    vllm_input[key] = value
    else:
        # 纯文本输入
        inputs = tokenizer(prompt_text, return_tensors="pt")
        input_ids = inputs['input_ids'][0]
        attention_mask = inputs['attention_mask'][0]
        
        vllm_input = {
            'prompt_token_ids': input_ids.cpu().numpy().tolist()
        }
    
    # 创建DataProto格式的prompt
    prompt_data = DataProto.from_dict(
        tensors={
            'input_ids': input_ids.unsqueeze(0),
            'attention_mask': attention_mask.unsqueeze(0)
        },
        non_tensors={
            'env_name': [env_name],
            'raw_prompt': [conversations],
            'origin_multi_modal_data': [{'image': images}] if images else [{}]
        }
    )
    
    return prompt_data, vllm_input

def create_eval_config():
    """创建评估配置 - 基于训练配置"""
    
    config = {
        'prompt_length': 8192,
        'response_length': 20480,
        'agent': {
            'max_turns': 5,
            'single_response_max_tokens': 10240,
            'tool_name_key': 'env_name',
            'concurrent_workers': 1,
            'show_tqdm': True,
            'custom_stop': [],
            'vl_model_path': '/app/models/Qwen2.5-VL-7B-Instruct'  # 这里需要改为你的训练模型路径
        }
    }
    
    return OmegaConf.create(config)

def evaluate_with_real_vllm(model_path: str, data_file: str, sample_indices: list, output_dir: str):
    """使用真实VLLM进行评估"""
    
    print(f"🎯 真实VLLM Agent评估")
    print(f"🤖 模型: {model_path}")
    print(f"📁 数据: {data_file}")
    print(f"📊 样本: {sample_indices}")
    
    # 创建输出目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    full_output_dir = Path(output_dir) / f"real_eval_{timestamp}"
    full_output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # 初始化VLLM引擎
        from vllm import LLM, SamplingParams
        
        print(f"🚀 初始化VLLM引擎...")
        vllm_engine = LLM(
            model=model_path,
            tensor_parallel_size=1,
            gpu_memory_utilization=0.4,
            max_model_len=32768,
            trust_remote_code=True
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
        
        # 创建配置
        config = create_eval_config()
        config.agent.vl_model_path = model_path  # 使用实际模型路径
        
        # 创建采样参数
        sampling_params = SamplingParams(
            n=1,
            max_tokens=10240,
            temperature=0.7,
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
                print(f"🔍 评估样本 {sample_idx}")
                
                # 加载样本
                sample_data = load_sample_data(data_file, sample_idx)
                
                # 创建样本目录
                sample_dir = full_output_dir / f"sample_{sample_idx:02d}"
                sample_dir.mkdir(exist_ok=True)
                
                # 保存原始数据
                save_original_data(sample_data, sample_dir)
                
                # 准备模型输入
                prompt_data, vllm_input = prepare_model_inputs(sample_data, tokenizer, processor)
                
                # 准备数据
                prompts = DataProto.from_list([prompt_data])
                
                # 多模态输入
                multi_modal_inputs = None
                if 'multi_modal_data' in vllm_input:
                    # 创建占位符tensor
                    multi_modal_inputs = torch.zeros(1, 1)
                
                print(f"🚀 开始真实Agent推理...")
                
                # 执行真实的agent rollout loop - 这里调用的是训练时相同的逻辑！
                result = agent_rollout_loop(
                    config=config,
                    vllm_engine=vllm_engine,
                    vllm_inputs=[vllm_input],
                    prompts=prompts,
                    multi_modal_inputs=multi_modal_inputs,
                    sampling_params=sampling_params
                )
                
                print(f"✅ Agent推理完成")
                
                # 保存推理结果
                save_inference_results(result, sample_data, sample_dir, sample_idx, tokenizer)
                
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
        
        print(f"\n🎉 真实推理评估完成！")
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

def save_inference_results(result, sample_data: dict, sample_dir: Path, sample_idx: int, tokenizer):
    """保存推理结果"""
    
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
                if key in ['tool_cnt', 'final_answer', 'repeated_degradation_cnt']:
                    tensor_info[key]['data'] = tensor.cpu().numpy().tolist()
                elif key.startswith('degradation_'):
                    tensor_info[key]['data'] = tensor.cpu().numpy().tolist()
        
        with open(sample_dir / "tensor_info.json", 'w') as f:
            json.dump(tensor_info, f, indent=2)
    
    # 解码并保存响应文本
    if hasattr(result, 'tensors') and 'response' in result.tensors:
        response_ids = result.tensors['response'][0]  # 第一个样本
        
        # 移除padding tokens
        if hasattr(tokenizer, 'pad_token_id') and tokenizer.pad_token_id is not None:
            response_ids = response_ids[response_ids != tokenizer.pad_token_id]
        
        response_text = tokenizer.decode(response_ids, skip_special_tokens=True)
        
        # 保存完整响应
        with open(sample_dir / "model_response.txt", 'w', encoding='utf-8') as f:
            f.write(response_text)
        
        print(f"📝 模型响应长度: {len(response_text)} 字符")
        print(f"📝 响应预览: {response_text[:200]}...")
        
        # 分析响应中的工具调用和图像变化
        analyze_response_and_save_images(response_text, sample_dir, result)
    
    print(f"✅ 样本 {sample_idx} 推理结果已保存")

def analyze_response_and_save_images(response_text: str, sample_dir: Path, result):
    """分析响应并提取图像变化"""
    
    from verl.workers.agent.parallel_env_v2 import _parse_model_output_for_tools
    
    # 分割多轮对话
    # 简化处理：按assistant回合分割
    assistant_turns = response_text.split('<|im_start|>assistant\n')
    
    turn_analyses = []
    for turn_idx, turn_text in enumerate(assistant_turns[1:], 1):  # 跳过第一个空分割
        if not turn_text.strip():
            continue
        
        # 移除可能的结束标记
        turn_text = turn_text.split('<|im_end|>')[0].strip()
        
        print(f"🔍 分析第 {turn_idx} 轮...")
        
        # 解析这一轮
        parsed = _parse_model_output_for_tools(turn_text, f"analysis-turn{turn_idx}")
        
        turn_analysis = {
            'turn': turn_idx,
            'raw_text': turn_text,
            'has_think': parsed.get('think') is not None,
            'think_data': parsed.get('think'),
            'has_tool_calls': len(parsed.get('tool_calls', [])) > 0,
            'tool_calls': parsed.get('tool_calls', []),
            'has_answer': parsed.get('is_done', False),
            'answer': parsed.get('answer')
        }
        
        turn_analyses.append(turn_analysis)
        
        # 保存单轮分析
        turn_file = sample_dir / f"turn_{turn_idx:02d}_analysis.json"
        with open(turn_file, 'w', encoding='utf-8') as f:
            json.dump(turn_analysis, f, indent=2, ensure_ascii=False)
        
        print(f"  📋 第{turn_idx}轮: think={turn_analysis['has_think']}, tools={len(turn_analysis['tool_calls'])}, answer={turn_analysis['has_answer']}")
    
    # 保存完整分析
    with open(sample_dir / "response_analysis.json", 'w', encoding='utf-8') as f:
        json.dump(turn_analyses, f, indent=2, ensure_ascii=False)
    
    print(f"📊 响应分析完成: {len(turn_analyses)} 轮")
    
    # 提取图像（如果有）
    if hasattr(result, 'non_tensors') and result.non_tensors:
        mm_inputs = result.non_tensors.get('multi_modal_inputs', [])
        if mm_inputs and len(mm_inputs) > 0:
            sample_mm_input = mm_inputs[0]  # 第一个样本的多模态输入
            
            # 这里可以提取最终的图像状态
            # 但由于结构复杂，我们主要依赖工具调用时保存的图像
            print(f"📷 多模态输入键: {list(sample_mm_input.keys()) if isinstance(sample_mm_input, dict) else 'Not a dict'}")

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
        'sample_results': all_results
    }
    
    summary_file = output_dir / "evaluation_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"📊 总体摘要: {summary_file}")
    print(f"📈 成功率: {successful_count}/{len(all_results)} ({summary['success_rate']:.2%})")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="真实Agent推理评估")
    parser.add_argument("--model_path", required=True, help="训练好的模型路径")
    parser.add_argument("--data_file", default="/app/datasets/IRdataset/shard-000003.parquet", help="测试数据文件")
    parser.add_argument("--output_dir", default="real_agent_eval", help="输出目录")
    parser.add_argument("--sample_indices", nargs='+', type=int, help="指定样本索引，如: 0 1 2 3")
    parser.add_argument("--num_samples", type=int, default=3, help="评估样本数量（从索引0开始）")
    parser.add_argument("--start_idx", type=int, default=0, help="起始样本索引")
    
    args = parser.parse_args()
    
    # 确定要评估的样本索引
    if args.sample_indices:
        sample_indices = args.sample_indices
    else:
        sample_indices = list(range(args.start_idx, args.start_idx + args.num_samples))
    
    print(f"🎯 真实Agent推理评估")
    print(f"🤖 模型: {args.model_path}")
    print(f"📁 数据: {args.data_file}")
    print(f"📊 评估样本索引: {sample_indices}")
    
    # 设置环境变量
    os.environ['CUDA_VISIBLE_DEVICES'] = '4'  # 使用第一个GPU
    
    try:
        result_dir = evaluate_with_real_vllm(
            model_path=args.model_path,
            data_file=args.data_file,
            sample_indices=sample_indices,
            output_dir=args.output_dir
        )
        
        if result_dir:
            print(f"\n🎉 评估完成！")
            print(f"📁 查看结果: {result_dir}")
            print(f"💡 提示:")
            print(f"   - model_response.txt: 模型的完整输出")
            print(f"   - turn_XX_analysis.json: 每轮的解析结果") 
            print(f"   - tensor_info.json: 统计信息")
            print(f"   - response_analysis.json: 完整响应分析")
        
    except Exception as e:
        print(f"❌ 评估失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
