#!/usr/bin/env python3
"""
真实Agent评估脚本 - 使用VLLM进行真实推理
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
from verl.workers.agent.parallel_env_v2 import agent_rollout_loop, ParallelEnv
from verl import DataProto

class RealAgentEvaluator:
    """真实Agent评估器 - 使用实际的VLLM推理"""
    
    def __init__(self, model_path: str, vllm_port: int = 18899, output_dir: str = "real_agent_eval"):
        self.model_path = model_path
        self.vllm_port = vllm_port
        self.tokenizer = hf_tokenizer(model_path)
        self.processor = hf_processor(model_path)
        
        # 创建输出目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = Path(output_dir) / f"eval_{timestamp}"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"🎯 真实Agent评估器初始化")
        print(f"🤖 模型: {model_path}")
        print(f"🌐 VLLM端口: {vllm_port}")
        print(f"📁 输出: {self.output_dir}")
        
        # 导入工具模块
        self._import_all_tools()
        
        # 初始化VLLM引擎
        self.vllm_engine = self._init_vllm_engine()
    
    def _import_all_tools(self):
        """导入所有工具模块"""
        try:
            import verl.workers.agent.envs.mm_process_engine.DehazeFormerToolbox
            import verl.workers.agent.envs.mm_process_engine.BrighteningToolbox
            import verl.workers.agent.envs.mm_process_engine.SwinIRToolbox
            import verl.workers.agent.envs.mm_process_engine.DeblurToolbox
            import verl.workers.agent.envs.mm_process_engine.XRestormerToolbox
            print(f"✅ 工具模块导入成功")
        except Exception as e:
            print(f"⚠️  部分工具模块导入失败: {e}")
    
    def _init_vllm_engine(self):
        """初始化VLLM引擎"""
        try:
            from vllm import LLM, SamplingParams
            
            print(f"🚀 初始化VLLM引擎...")
            vllm_engine = LLM(
                model=self.model_path,
                tensor_parallel_size=1,
                gpu_memory_utilization=0.4,
                max_model_len=32768,
                trust_remote_code=True,
                disable_log_requests=True
            )
            
            print(f"✅ VLLM引擎初始化成功")
            return vllm_engine
            
        except Exception as e:
            print(f"❌ VLLM引擎初始化失败: {e}")
            print(f"💡 请确保模型路径正确，或使用 --use_openai_api 选项")
            return None
    
    def load_sample_data(self, data_file: str, sample_idx: int):
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
    
    def prepare_input_data(self, sample_data: dict):
        """准备模型输入数据"""
        conversations = sample_data['conversations']
        images = sample_data['images']
        env_name = sample_data['env_name']
        
        # 构建输入文本
        if conversations and len(conversations) >= 2:
            # 使用数据中的对话模板
            input_text = self.tokenizer.apply_chat_template(
                conversations, 
                add_generation_prompt=True, 
                tokenize=False
            )
        else:
            # 默认提示
            input_text = "<|im_start|>system\nYou are a helpful assistant.\n\n## Goal\nGiven an image (and optional question), decide restoration tools **and minimal parameters** (if any). When choosing a tool, you must select from the list below based on the diagnosed degradation type(s). On every step you must output one <think> block, then either a <tool_call> (to execute next) or an <answer> (final success only).\n\n## Degradation Types\nYou must classify the image degradation using **only** the following labels. The `diagnosis.labels` array must be a subset of this list.\n- `\"rain\"`\n- `\"haze\"`\n- `\"dark\"`\n- `\"motion blur\"`\n- `\"defocus blur\"`\n- `\"noise\"`\n- `\"low resolution\"`\n- `\"jpeg compression artifact\"`\n- `\"clean\"` (Use this if the image has no detectable degradations)\n\n## Allowed tools (names & minimal arguments)\n- `dehazeformer_dehaze`: `{\"strength\": 0..1}` (Applies to: `\"haze\"`)\n- `drbnet_defocus_deblurring`: `{\"radius\": >0, \"strength\": 0..1 (optional)}` (Applies to: `\"defocus blur\"`)\n- `histogram_equalization`: `{\"mode\": \"global\"|\"clahe\"}` (Applies to: `\"dark\"`)\n- `gamma_correction`: `{\"gamma\": >0}` (Applies to: `\"dark\"`)\n- `constant_shift`: `{\"shift\": integer}` (Applies to: `\"dark\"`)\n- `xrestormer_motion_deblurring`: `{\"strength\": 0..1}` (Applies to: `\"motion blur\"`, `\"rain\"`)\n- `swinir_jpeg_artifact_removal`: `{\"strength\": 0..1}` (Applies to: `\"jpeg compression artifact\"`)\n- `swinir_super_resolution`: `{\"scale\": 2|3|4}` (Applies to: `\"low resolution\"`)\n- `swinir_denoising`: `{\"strength\": 0..1}` (Applies to: `\"noise\"`)\n\n## Step protocol (STRICT)\n1) Output exactly one <think> block (brief JSON: diagnosis & pass flag).\n2) If pass=false, output one <tool_call> block with an **ordered array** of tool objects including **name** and **arguments** (omit keys you don't override; use `{}` to accept defaults).\n3) If pass=true and external quality gate has PASSED, output one <answer> block. No other text.\n\n### <think> (brief JSON only)\n<think>{\n  \"diagnosis\": {\"labels\": [/* a list of strings from the \"Degradation Types\" list above */], \"levels\": {\"haze\": \"weak|medium|strong\"}},\n   \"pass\": true|false\n}</think>\n\n### <tool_call> (must include parameters if any)\n<tool_call>[\n  {\"name\": \"tool_name_1\", \"arguments\": { /* e.g., {\"strength\": 0.7} or {} */ }},\n  {\"name\": \"tool_name_2\", \"arguments\": {} }\n]</tool_call>\n- Execute in array order.\n- Keep the sequence short and minimal.\n\n### <answer> (final success only)\n<answer>success</answer>\n\n## Formatting rules\n- **Always** include <think> each step.\n- Use tool names **exactly** as listed.\n- Include only the keys you intend to set; otherwise use empty `{}`.\n- No explanations or extra text outside the three blocks.<|im_end|>\n<|im_start|>user\n<image>\nPlease assess the quality of this image. If there are any degradation issues that need fixing, please provide the first step of the solution.<|im_end|>\n<|im_start|>assistant\n"
        
        # 处理图像占位符
        if images:
            image_count = len(images)
            if '<image>' in input_text:
                # 确保占位符数量匹配
                input_text = input_text.replace('<image>', '<image>' * image_count, 1)
        
        # Tokenize
        if self.processor and images:
            model_inputs = self.processor(text=[input_text], images=images, return_tensors="pt")
            input_ids = model_inputs['input_ids'][0]
            attention_mask = model_inputs['attention_mask'][0]
            
            # 移除额外的键
            model_inputs.pop('input_ids')
            model_inputs.pop('attention_mask')
            if 'second_per_grid_ts' in model_inputs:
                model_inputs.pop('second_per_grid_ts')
            
            # VLLM输入
            vllm_input = {
                'prompt_token_ids': input_ids.cpu().numpy().tolist(),
                'multi_modal_data': {'image': images}
            }
            
            # 添加多模态输入
            if model_inputs:
                vllm_input.update(model_inputs)
        else:
            inputs = self.tokenizer(input_text, return_tensors="pt")
            input_ids = inputs['input_ids'][0]
            attention_mask = inputs['attention_mask'][0]
            
            vllm_input = {
                'prompt_token_ids': input_ids.cpu().numpy().tolist()
            }
        
        # 创建DataProto
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
    
    def evaluate_sample_with_real_model(self, sample_data: dict, sample_idx: int):
        """使用真实模型评估样本"""
        
        print(f"\n{'='*60}")
        print(f"🎯 评估样本 {sample_idx}: {sample_data['env_name']}")
        print(f"{'='*60}")
        
        if not self.vllm_engine:
            print(f"❌ VLLM引擎未初始化，跳过推理")
            return None
        
        # 创建样本目录
        sample_dir = self.output_dir / f"sample_{sample_idx:02d}"
        sample_dir.mkdir(exist_ok=True)
        
        # 保存原始数据
        self._save_original_data(sample_data, sample_dir)
        
        # 准备输入
        prompt_data, vllm_input = self.prepare_input_data(sample_data)
        
        # 配置参数（参考训练脚本）
        class EvalConfig:
            def __init__(self):
                self.prompt_length = 8192
                self.response_length = 20480
                self.agent = EvalAgentConfig()
        
        class EvalAgentConfig:
            def __init__(self):
                self.max_turns = 6
                self.single_response_max_tokens = 10240
                self.tool_name_key = 'env_name'
                self.concurrent_workers = 1
                self.show_tqdm = True
                self.custom_stop = []
        
        class EvalSamplingParams:
            def __init__(self):
                self.n = 1
                self.stop = None
                self.max_tokens = 10240
                self.temperature = 0.7
                self.top_p = 0.9
                self.detokenize = True
                self.skip_special_tokens = False
                self.spaces_between_special_tokens = False
                self.include_stop_str_in_output = True
        
        config = EvalConfig()
        sampling_params = EvalSamplingParams()
        
        try:
            print(f"🚀 开始真实Agent推理...")
            
            # 准备数据
            prompts = DataProto.from_list([prompt_data])
            
            # 多模态输入
            multi_modal_inputs = None
            if 'multi_modal_data' in vllm_input:
                # 创建占位符tensor
                multi_modal_inputs = torch.zeros(1, 1)
            
            # 执行真实的agent rollout
            result = agent_rollout_loop(
                config=config,
                vllm_engine=self.vllm_engine,
                vllm_inputs=[vllm_input],
                prompts=prompts,
                multi_modal_inputs=multi_modal_inputs,
                sampling_params=sampling_params
            )
            
            print(f"✅ Agent推理完成")
            
            # 保存详细结果
            self._save_real_evaluation_results(result, sample_dir, sample_idx)
            
            return result
            
        except Exception as e:
            print(f"❌ Agent推理失败: {e}")
            import traceback
            traceback.print_exc()
            
            # 保存错误信息
            error_info = {
                'error': str(e),
                'traceback': traceback.format_exc(),
                'sample_idx': sample_idx,
                'env_name': sample_data['env_name']
            }
            
            with open(sample_dir / "error.json", 'w') as f:
                json.dump(error_info, f, indent=2)
            
            return None
    
    def _save_original_data(self, sample_data: dict, sample_dir: Path):
        """保存原始数据"""
        
        # 保存基本信息
        basic_info = {
            'env_name': sample_data['env_name'],
            'data_source': sample_data['data_source'],
            'num_images': len(sample_data['images']),
            'image_sizes': [img.size for img in sample_data['images']],
            'conversations': len(sample_data['conversations'])
        }
        
        with open(sample_dir / "basic_info.json", 'w', encoding='utf-8') as f:
            json.dump(basic_info, f, indent=2, ensure_ascii=False)
        
        # 保存原始图像
        for img_idx, img in enumerate(sample_data['images']):
            img_path = sample_dir / f"original_image_{img_idx:02d}.png"
            img.save(img_path)
            print(f"💾 保存原始图像: {img_path}")
        
        # 保存对话
        if sample_data['conversations']:
            with open(sample_dir / "conversations.json", 'w', encoding='utf-8') as f:
                json.dump(sample_data['conversations'], f, indent=2, ensure_ascii=False)
    
    def _save_real_evaluation_results(self, result, sample_dir: Path, sample_idx: int):
        """保存真实推理结果"""
        
        if result is None:
            return
        
        # 保存tensor结果
        if hasattr(result, 'tensors'):
            tensor_info = {}
            for key, tensor in result.tensors.items():
                if torch.is_tensor(tensor):
                    tensor_info[key] = {
                        'shape': list(tensor.shape),
                        'dtype': str(tensor.dtype),
                        'device': str(tensor.device)
                    }
                    
                    # 保存一些关键数据
                    if key in ['tool_cnt', 'final_answer', 'repeated_degradation_cnt']:
                        tensor_info[key]['data'] = tensor.cpu().numpy().tolist()
                    elif key.startswith('degradation_'):
                        tensor_info[key]['data'] = tensor.cpu().numpy().tolist()
            
            with open(sample_dir / "tensor_results.json", 'w') as f:
                json.dump(tensor_info, f, indent=2)
        
        # 解码并保存响应文本
        if hasattr(result, 'tensors') and 'response' in result.tensors:
            response_ids = result.tensors['response'][0]  # 第一个样本
            
            # 移除padding tokens
            if hasattr(self.tokenizer, 'pad_token_id') and self.tokenizer.pad_token_id is not None:
                response_ids = response_ids[response_ids != self.tokenizer.pad_token_id]
            
            response_text = self.tokenizer.decode(response_ids, skip_special_tokens=True)
            
            with open(sample_dir / "full_response.txt", 'w', encoding='utf-8') as f:
                f.write(response_text)
            
            print(f"📝 保存完整响应: {sample_dir / 'full_response.txt'}")
            print(f"📝 响应长度: {len(response_text)} 字符")
            print(f"📝 响应预览: {response_text[:300]}...")
            
            # 分析响应中的工具调用
            self._analyze_response(response_text, sample_dir)
        
        # 保存多模态输入（如果有）
        if hasattr(result, 'non_tensors') and result.non_tensors:
            mm_inputs = result.non_tensors.get('multi_modal_inputs', [])
            if mm_inputs:
                # 保存最终的图像结果
                final_images_dir = sample_dir / "final_images"
                final_images_dir.mkdir(exist_ok=True)
                
                print(f"📷 保存最终图像状态...")
        
        print(f"✅ 样本 {sample_idx} 真实推理结果已保存")
    
    def _analyze_response(self, response_text: str, sample_dir: Path):
        """分析响应文本中的工具调用"""
        
        from verl.workers.agent.parallel_env_v2 import _parse_model_output_for_tools
        
        # 按轮次分割响应（简化处理）
        turns = response_text.split('<|im_start|>assistant\n')
        
        turn_analyses = []
        for turn_idx, turn_text in enumerate(turns[1:], 1):  # 跳过第一个空的分割
            if not turn_text.strip():
                continue
                
            print(f"🔍 分析第 {turn_idx} 轮响应...")
            
            # 解析这一轮的输出
            parsed_output = _parse_model_output_for_tools(turn_text, f"analysis-turn{turn_idx}")
            
            turn_analysis = {
                'turn': turn_idx,
                'raw_text': turn_text[:500] + '...' if len(turn_text) > 500 else turn_text,
                'has_think': parsed_output.get('think') is not None,
                'has_tool_calls': len(parsed_output.get('tool_calls', [])) > 0,
                'has_answer': parsed_output.get('is_done', False),
                'tool_calls': parsed_output.get('tool_calls', []),
                'think_data': parsed_output.get('think')
            }
            
            turn_analyses.append(turn_analysis)
            
            # 保存单独的轮次分析
            turn_file = sample_dir / f"turn_{turn_idx:02d}_analysis.json"
            with open(turn_file, 'w', encoding='utf-8') as f:
                json.dump(turn_analysis, f, indent=2, ensure_ascii=False)
        
        # 保存完整分析
        with open(sample_dir / "response_analysis.json", 'w', encoding='utf-8') as f:
            json.dump(turn_analyses, f, indent=2, ensure_ascii=False)
        
        print(f"📊 响应分析完成: {len(turn_analyses)} 轮")

def create_evaluation_script():
    """创建便捷的评估脚本"""
    
    script_content = '''#!/bin/bash
# Agent真实推理评估脚本

set -e

# 设置参数
MODEL_PATH="/app/models/verl_checkpoints/agent_vlagent/your_experiment_name/actor"  # 修改为你的模型路径
DATA_FILE="/app/datasets/IRdataset/shard-000003.parquet"
OUTPUT_DIR="real_agent_eval"
NUM_SAMPLES=5

echo "🎯 Agent真实推理评估"
echo "🤖 模型: $MODEL_PATH"
echo "📁 数据: $DATA_FILE"
echo "📊 样本: $NUM_SAMPLES"

# 设置环境
export PYTHONPATH=/app/xiaominl/DeepEyes:$PYTHONPATH
export CUDA_VISIBLE_DEVICES=0

# 运行评估
python3 eval_agent_real.py \\
    --model_path "$MODEL_PATH" \\
    --data_file "$DATA_FILE" \\
    --output_dir "$OUTPUT_DIR" \\
    --num_samples $NUM_SAMPLES

echo "✅ 评估完成！"
echo "📁 查看结果: $OUTPUT_DIR"
'''
    
    script_path = Path("eval_real_agent.sh")
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    os.chmod(script_path, 0o755)
    print(f"📝 创建评估脚本: {script_path}")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent真实推理评估")
    parser.add_argument("--model_path", required=True, help="训练好的模型路径")
    parser.add_argument("--data_file", default="/app/datasets/IRdataset/shard-000003.parquet", help="测试数据文件")
    parser.add_argument("--output_dir", default="real_agent_eval", help="输出目录")
    parser.add_argument("--num_samples", type=int, default=3, help="评估样本数量")
    parser.add_argument("--vllm_port", type=int, default=18899, help="VLLM服务端口")
    
    args = parser.parse_args()
    
    print(f"🎯 Agent真实推理评估")
    print(f"🤖 模型: {args.model_path}")
    print(f"📁 数据: {args.data_file}")
    print(f"📊 样本: {args.num_samples}")
    
    try:
        # 创建评估器
        evaluator = RealAgentEvaluator(
            model_path=args.model_path,
            vllm_port=args.vllm_port,
            output_dir=args.output_dir
        )
        
        # 评估每个样本
        all_results = []
        successful_count = 0
        
        for i in range(args.num_samples):
            try:
                # 加载样本
                sample_data = evaluator.load_sample_data(args.data_file, i)
                
                # 真实推理
                result = evaluator.evaluate_sample_with_real_model(sample_data, i)
                
                if result:
                    successful_count += 1
                    all_results.append({
                        'sample_idx': i,
                        'env_name': sample_data['env_name'],
                        'status': 'success'
                    })
                    print(f"✅ 样本 {i} 推理成功")
                else:
                    all_results.append({
                        'sample_idx': i,
                        'env_name': sample_data['env_name'],
                        'status': 'failed'
                    })
                    print(f"❌ 样本 {i} 推理失败")
                    
            except Exception as e:
                print(f"❌ 样本 {i} 处理失败: {e}")
                all_results.append({
                    'sample_idx': i,
                    'error': str(e),
                    'status': 'error'
                })
        
        # 保存总体结果
        overall_results = {
            'evaluation_time': datetime.now().isoformat(),
            'model_path': args.model_path,
            'data_file': args.data_file,
            'num_samples': args.num_samples,
            'successful_samples': successful_count,
            'success_rate': successful_count / args.num_samples,
            'results': all_results
        }
        
        results_file = evaluator.output_dir / "evaluation_summary.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(overall_results, f, indent=2, ensure_ascii=False)
        
        print(f"\n🎉 评估完成！")
        print(f"📁 结果目录: {evaluator.output_dir}")
        print(f"📊 成功率: {successful_count}/{args.num_samples} ({overall_results['success_rate']:.2%})")
        print(f"📋 详细结果: {results_file}")
        
        # 创建便捷脚本
        create_evaluation_script()
        
    except Exception as e:
        print(f"❌ 评估过程出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
