#!/usr/bin/env python3
"""
评估训练好的Agent模型 - 测试工具调用能力和逐步图像处理
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
import hydra
from omegaconf import DictConfig

# 添加项目路径
sys.path.append('/app/xiaominl/DeepEyes')

from verl.utils import hf_tokenizer, hf_processor
from verl.workers.agent.parallel_env_v2 import agent_rollout_loop, ParallelEnv
from verl.workers.rollout.vllm_rollout.vllm_rollout_spmd import VLLMRollout
from verl import DataProto
from verl.utils.dataset.vision_utils import process_image

class AgentEvaluator:
    """Agent评估器"""
    
    def __init__(self, model_path: str, output_dir: str = "agent_eval_results"):
        self.model_path = model_path
        self.output_dir = output_dir
        self.tokenizer = hf_tokenizer(model_path)
        self.processor = hf_processor(model_path)
        
        # 创建输出目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.full_output_dir = Path(output_dir) / f"eval_{timestamp}"
        self.full_output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"🎯 Agent评估器初始化")
        print(f"🤖 模型路径: {model_path}")
        print(f"📁 输出目录: {self.full_output_dir}")
    
    def load_sample_from_dataset(self, data_file: str, sample_idx: int):
        """从数据集加载样本"""
        print(f"📁 加载样本 {sample_idx} 从 {data_file}")
        
        df = pd.read_parquet(data_file)
        if sample_idx >= len(df):
            raise IndexError(f"样本索引 {sample_idx} 超出范围 (最大: {len(df)-1})")
        
        row = df.iloc[sample_idx]
        
        # 解析图像
        images = []
        if isinstance(row['images'], np.ndarray):
            for img_data in row['images']:
                if isinstance(img_data, dict) and 'bytes' in img_data:
                    img_bytes = img_data['bytes']
                    pil_image = Image.open(io.BytesIO(img_bytes)).convert('RGB')
                    images.append(pil_image)
        
        # 解析prompt
        conversations = []
        if isinstance(row['prompt'], np.ndarray):
            conversations = row['prompt'].tolist()
        
        sample_data = {
            'env_name': row['env_name'],
            'images': images,
            'conversations': conversations,
            'data_source': row['data_source'],
            'ability': row['ability']
        }
        
        print(f"📋 环境名称: {sample_data['env_name']}")
        print(f"📷 图像数量: {len(images)}")
        print(f"💬 对话数量: {len(conversations)}")
        
        return sample_data
    
    def prepare_vllm_input(self, sample_data: dict):
        """准备VLLM输入"""
        conversations = sample_data['conversations']
        images = sample_data['images']
        
        # 构建输入文本
        if conversations and len(conversations) > 0:
            # 使用聊天模板
            input_text = self.tokenizer.apply_chat_template(
                conversations, 
                add_generation_prompt=True, 
                tokenize=False
            )
        else:
            # 默认提示
            input_text = "<|im_start|>user\n<image>\nPlease assess the quality of this image. If there are any degradation issues that need fixing, please provide the first step of the solution.<|im_end|>\n<|im_start|>assistant\n"
        
        # 处理多模态输入
        if self.processor and images:
            # 替换图像占位符
            image_count = len(images)
            input_text = input_text.replace('<image>', '<image>' * image_count)
            
            # 处理图像
            processed_images = []
            for img in images:
                # 转换为处理格式
                buf = io.BytesIO()
                img.save(buf, format='PNG')
                png_bytes = buf.getvalue()
                buf.close()
                img_info = {"bytes": png_bytes}
                processed_images.append(process_image(img_info))
            
            # 创建VLLM输入
            vllm_input = {
                'prompt': input_text,
                'multi_modal_data': {'image': images}  # 原始PIL图像
            }
        else:
            vllm_input = {
                'prompt': input_text
            }
        
        # 创建DataProto格式的prompt
        if self.processor and images:
            model_inputs = self.processor(text=[input_text], images=images, return_tensors="pt")
            input_ids = model_inputs['input_ids'][0]
            attention_mask = model_inputs['attention_mask'][0]
        else:
            inputs = self.tokenizer(input_text, return_tensors="pt")
            input_ids = inputs['input_ids'][0]
            attention_mask = inputs['attention_mask'][0]
        
        prompt_data = DataProto.from_dict(
            tensors={
                'input_ids': input_ids.unsqueeze(0),
                'attention_mask': attention_mask.unsqueeze(0)
            },
            non_tensors={
                'env_name': [sample_data['env_name']],
                'raw_prompt': [conversations],
                'origin_multi_modal_data': [{'image': images}] if images else [{}]
            }
        )
        
        return prompt_data, vllm_input
    
    def evaluate_sample_with_vllm(self, sample_data: dict, sample_idx: int, vllm_engine):
        """使用VLLM引擎评估样本"""
        print(f"\n{'='*60}")
        print(f"🎯 评估样本 {sample_idx}: {sample_data['env_name']}")
        print(f"{'='*60}")
        
        # 创建样本输出目录
        sample_dir = self.full_output_dir / f"sample_{sample_idx:02d}"
        sample_dir.mkdir(exist_ok=True)
        
        # 保存原始数据
        self._save_original_data(sample_data, sample_dir)
        
        # 准备输入
        prompt_data, vllm_input = self.prepare_vllm_input(sample_data)
        
        # 模拟配置（参考训练脚本）
        class MockConfig:
            def __init__(self):
                self.prompt_length = 8192
                self.response_length = 20480
                self.agent = MockAgentConfig()
        
        class MockAgentConfig:
            def __init__(self):
                self.max_turns = 6
                self.single_response_max_tokens = 10240
                self.tool_name_key = 'env_name'
                self.concurrent_workers = 1
                self.show_tqdm = True
                self.custom_stop = []
        
        class MockSamplingParams:
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
        
        config = MockConfig()
        sampling_params = MockSamplingParams()
        
        # 执行agent rollout
        try:
            print(f"🚀 开始Agent推理...")
            
            # 准备输入数据
            prompts = DataProto.from_list([prompt_data])
            multi_modal_inputs = None
            if 'multi_modal_data' in vllm_input:
                # 转换为tensor格式
                mm_data = vllm_input['multi_modal_data']
                multi_modal_inputs = torch.zeros(1, 1)  # 占位符
            
            # 执行agent rollout loop
            result = agent_rollout_loop(
                config=config,
                vllm_engine=vllm_engine,
                vllm_inputs=[vllm_input],
                prompts=prompts,
                multi_modal_inputs=multi_modal_inputs,
                sampling_params=sampling_params
            )
            
            print(f"✅ Agent推理完成")
            
            # 保存结果
            self._save_evaluation_results(result, sample_dir, sample_idx)
            
            return result
            
        except Exception as e:
            print(f"❌ Agent推理失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _save_original_data(self, sample_data: dict, sample_dir: Path):
        """保存原始数据"""
        
        # 保存基本信息
        basic_info = {
            'env_name': sample_data['env_name'],
            'data_source': sample_data['data_source'],
            'ability': sample_data['ability'],
            'num_images': len(sample_data['images']),
            'num_conversations': len(sample_data['conversations'])
        }
        
        with open(sample_dir / "basic_info.json", 'w', encoding='utf-8') as f:
            json.dump(basic_info, f, indent=2, ensure_ascii=False)
        
        # 保存对话
        with open(sample_dir / "conversations.json", 'w', encoding='utf-8') as f:
            json.dump(sample_data['conversations'], f, indent=2, ensure_ascii=False)
        
        # 保存原始图像
        for img_idx, img in enumerate(sample_data['images']):
            img_path = sample_dir / f"original_image_{img_idx:02d}.png"
            img.save(img_path)
            print(f"💾 保存原始图像: {img_path}")
    
    def _save_evaluation_results(self, result, sample_dir: Path, sample_idx: int):
        """保存评估结果"""
        
        # 保存推理结果
        if result and hasattr(result, 'tensors'):
            result_info = {
                'tensor_keys': list(result.tensors.keys()),
                'response_shape': result.tensors['response'].shape if 'response' in result.tensors else None,
                'tool_cnt': result.tensors['tool_cnt'].cpu().numpy().tolist() if 'tool_cnt' in result.tensors else None,
                'final_answer': result.tensors['final_answer'].cpu().numpy().tolist() if 'final_answer' in result.tensors else None
            }
            
            with open(sample_dir / "inference_result.json", 'w') as f:
                json.dump(result_info, f, indent=2)
            
            print(f"📊 保存推理结果: {sample_dir / 'inference_result.json'}")
        
        # 解码响应文本
        if result and 'response' in result.tensors:
            response_ids = result.tensors['response'][0]  # 第一个样本
            response_text = self.tokenizer.decode(response_ids, skip_special_tokens=True)
            
            with open(sample_dir / "response_text.txt", 'w', encoding='utf-8') as f:
                f.write(response_text)
            
            print(f"📝 保存响应文本: {sample_dir / 'response_text.txt'}")
            print(f"📝 响应预览: {response_text[:200]}...")
        
        print(f"✅ 样本 {sample_idx} 评估结果已保存")

def create_evaluation_script():
    """创建评估脚本"""
    
    script_content = '''#!/bin/bash
# Agent模型评估脚本

set -e

# 设置环境变量
export PYTHONPATH=/app/xiaominl/DeepEyes:$PYTHONPATH
export CUDA_VISIBLE_DEVICES=0  # 使用第一个GPU

# 参数设置
MODEL_PATH="/app/models/verl_checkpoints/agent_vlagent/your_experiment_name/actor"  # 修改为你的模型路径
DATA_FILE="/app/datasets/IRdataset/shard-000003.parquet"
OUTPUT_DIR="agent_eval_results"
NUM_SAMPLES=5
VLLM_PORT=18888

echo "🎯 Agent模型评估"
echo "🤖 模型路径: $MODEL_PATH"
echo "📁 数据文件: $DATA_FILE"
echo "📊 评估样本: $NUM_SAMPLES"
echo "📁 输出目录: $OUTPUT_DIR"

# 1. 启动VLLM服务
echo "🚀 启动VLLM服务..."
python3 -m vllm.entrypoints.openai.api_server \\
    --model "$MODEL_PATH" \\
    --port $VLLM_PORT \\
    --gpu-memory-utilization 0.8 \\
    --max-model-len 32768 \\
    --tensor-parallel-size 1 \\
    --trust-remote-code \\
    --disable-log-requests &

VLLM_PID=$!
echo "VLLM服务PID: $VLLM_PID"

# 等待服务启动
echo "⏳ 等待VLLM服务启动..."
sleep 30

# 2. 运行评估
echo "🔍 开始评估..."
python3 eval_trained_agent.py \\
    --model_path "$MODEL_PATH" \\
    --data_file "$DATA_FILE" \\
    --output_dir "$OUTPUT_DIR" \\
    --num_samples $NUM_SAMPLES \\
    --vllm_port $VLLM_PORT

# 3. 清理
echo "🧹 清理VLLM服务..."
kill $VLLM_PID 2>/dev/null || true

echo "✅ 评估完成！"
echo "📁 查看结果: $OUTPUT_DIR"
'''
    
    script_path = Path("eval_agent.sh")
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    os.chmod(script_path, 0o755)
    print(f"📝 创建评估脚本: {script_path}")

def monkey_patch_parallel_env_for_eval(output_dir: Path):
    """为评估修改ParallelEnv，保存每一步的图像"""
    
    from verl.workers.agent.parallel_env_v2 import ParallelEnv
    
    # 保存原始方法
    original_step = ParallelEnv.step
    
    def step_with_image_capture(self, active_indices, actions, current_turn=1):
        """带图像捕获的step方法"""
        
        print(f"\n📸 捕获第 {current_turn} 轮")
        
        # 在执行前保存当前状态的图像
        for local_idx, global_idx in enumerate(active_indices):
            if hasattr(self, 'multi_modal_data_list') and global_idx < len(self.multi_modal_data_list):
                mm_data = self.multi_modal_data_list[global_idx]
                if mm_data and 'image' in mm_data:
                    images = mm_data['image']
                    
                    # 保存当前轮的图像
                    sample_dir = output_dir / f"sample_{global_idx:02d}"
                    step_dir = sample_dir / f"step_{current_turn:02d}_before"
                    step_dir.mkdir(parents=True, exist_ok=True)
                    
                    for img_idx, img in enumerate(images):
                        if isinstance(img, Image.Image):
                            img_path = step_dir / f"image_{img_idx:02d}.png"
                            img.save(img_path)
                            print(f"💾 保存轮次前图像: step_{current_turn:02d}_before/image_{img_idx:02d}.png")
        
        # 记录动作
        for local_idx, action in enumerate(actions):
            global_idx = active_indices[local_idx] if local_idx < len(active_indices) else local_idx
            action_text = action.outputs[0].text
            
            sample_dir = output_dir / f"sample_{global_idx:02d}"
            action_file = sample_dir / f"step_{current_turn:02d}_action.txt"
            
            with open(action_file, 'w', encoding='utf-8') as f:
                f.write(action_text)
            print(f"📝 保存动作: step_{current_turn:02d}_action.txt")
        
        # 调用原始step方法
        result = original_step(self, active_indices, actions, current_turn)
        observations, rewards, dones, info = result
        
        # 执行后保存观察结果中的图像
        for local_idx, obs in enumerate(observations):
            global_idx = active_indices[local_idx] if local_idx < len(active_indices) else local_idx
            
            if isinstance(obs, dict) and 'multi_modal_data' in obs:
                mm_data = obs['multi_modal_data']
                if 'image' in mm_data:
                    images = mm_data['image']
                    
                    sample_dir = output_dir / f"sample_{global_idx:02d}"
                    step_dir = sample_dir / f"step_{current_turn:02d}_after"
                    step_dir.mkdir(parents=True, exist_ok=True)
                    
                    for img_idx, img in enumerate(images):
                        if isinstance(img, Image.Image):
                            img_path = step_dir / f"image_{img_idx:02d}.png"
                            img.save(img_path)
                            print(f"💾 保存轮次后图像: step_{current_turn:02d}_after/image_{img_idx:02d}.png")
            
            # 保存奖励和状态信息
            step_info = {
                'turn': current_turn,
                'reward': rewards[local_idx] if local_idx < len(rewards) else 0.0,
                'done': dones[local_idx] if local_idx < len(dones) else False,
                'observation_keys': list(obs.keys()) if isinstance(obs, dict) else []
            }
            
            sample_dir = output_dir / f"sample_{global_idx:02d}"
            info_file = sample_dir / f"step_{current_turn:02d}_info.json"
            with open(info_file, 'w') as f:
                json.dump(step_info, f, indent=2)
        
        return result
    
    # 替换方法
    ParallelEnv.step = step_with_image_capture
    print(f"🔧 已安装图像捕获钩子")

@hydra.main(version_base=None, config_path="verl/trainer/config", config_name="ppo_trainer")
def main(config: DictConfig):
    """主评估函数"""
    
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", required=True, help="训练好的模型路径")
    parser.add_argument("--data_file", required=True, help="测试数据文件")
    parser.add_argument("--output_dir", default="agent_eval_results", help="输出目录")
    parser.add_argument("--num_samples", type=int, default=3, help="评估样本数量")
    parser.add_argument("--vllm_port", type=int, default=18888, help="VLLM服务端口")
    
    args = parser.parse_args()
    
    print(f"🎯 Agent模型评估")
    print(f"🤖 模型: {args.model_path}")
    print(f"📁 数据: {args.data_file}")
    print(f"📊 样本: {args.num_samples}")
    
    # 创建评估器
    evaluator = AgentEvaluator(args.model_path, args.output_dir)
    
    # 安装图像捕获钩子
    monkey_patch_parallel_env_for_eval(evaluator.full_output_dir)
    
    # 初始化VLLM引擎（这里需要根据实际情况调整）
    try:
        from vllm import LLM, SamplingParams
        
        # 创建VLLM引擎
        vllm_engine = LLM(
            model=args.model_path,
            tensor_parallel_size=1,
            gpu_memory_utilization=0.8,
            max_model_len=32768,
            trust_remote_code=True
        )
        
        print(f"✅ VLLM引擎初始化成功")
        
        # 评估样本
        for i in range(args.num_samples):
            try:
                sample_data = evaluator.load_sample_from_dataset(args.data_file, i)
                result = evaluator.evaluate_sample_with_vllm(sample_data, i, vllm_engine)
                
                if result:
                    print(f"✅ 样本 {i} 评估成功")
                else:
                    print(f"❌ 样本 {i} 评估失败")
                    
            except Exception as e:
                print(f"❌ 样本 {i} 处理失败: {e}")
        
        print(f"\n🎉 评估完成！")
        print(f"📁 结果目录: {evaluator.full_output_dir}")
        print(f"🖼️  查看每一步的图像变化")
        
    except Exception as e:
        print(f"❌ VLLM引擎初始化失败: {e}")
        print(f"💡 请确保模型路径正确，或使用外部VLLM服务")

if __name__ == "__main__":
    # 创建评估脚本
    create_evaluation_script()
    
    print(f"📝 评估脚本已创建")
    print(f"💡 使用方法:")
    print(f"   1. 修改 eval_agent.sh 中的 MODEL_PATH 为你的模型路径")
    print(f"   2. 运行: bash eval_agent.sh")
    print(f"   3. 或者直接运行: python3 eval_trained_agent.py --model_path YOUR_MODEL_PATH --data_file /app/datasets/IRdataset/shard-000003.parquet")
    
    # 如果直接运行，使用简单模式
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", help="训练好的模型路径")
    parser.add_argument("--data_file", default="/app/datasets/IRdataset/shard-000003.parquet", help="测试数据文件")
    parser.add_argument("--output_dir", default="agent_eval_results", help="输出目录")
    parser.add_argument("--num_samples", type=int, default=3, help="评估样本数量")
    
    args = parser.parse_args()
    
    if args.model_path:
        print(f"🚀 开始简单评估模式")
        evaluator = AgentEvaluator(args.model_path, args.output_dir)
        
        # 只加载和保存数据，不运行模型推理
        for i in range(args.num_samples):
            try:
                sample_data = evaluator.load_sample_from_dataset(args.data_file, i)
                sample_dir = evaluator.full_output_dir / f"sample_{i:02d}"
                sample_dir.mkdir(exist_ok=True)
                evaluator._save_original_data(sample_data, sample_dir)
                print(f"✅ 样本 {i} 数据已准备")
            except Exception as e:
                print(f"❌ 样本 {i} 处理失败: {e}")
        
        print(f"📁 数据已准备完成: {evaluator.full_output_dir}")
        print(f"💡 要运行完整评估，请使用 bash eval_agent.sh")
