#!/usr/bin/env python3
"""
Agent 逐步评估脚本 - 可视化每一步的图像处理结果
"""

import os
import sys
import json
import torch
import pandas as pd
from PIL import Image
from pathlib import Path
from typing import Dict, List, Any
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from datetime import datetime

# 添加项目路径
sys.path.append('/app/xiaominl/DeepEyes')

from verl.utils import hf_tokenizer, hf_processor
from verl.workers.agent.parallel_env_v2 import agent_rollout_loop, ParallelEnv
from verl import DataProto
from verl.utils.dataset.vision_utils import process_image
import hydra
from omegaconf import DictConfig, OmegaConf

def load_test_data(data_file: str, num_samples: int = 5):
    """加载测试数据"""
    print(f"📁 加载测试数据: {data_file}")
    
    if not os.path.exists(data_file):
        raise FileNotFoundError(f"数据文件不存在: {data_file}")
    
    # 读取parquet文件
    df = pd.read_parquet(data_file)
    print(f"📊 数据文件包含 {len(df)} 个样本")
    
    # 取前num_samples个样本
    df = df.head(num_samples)
    print(f"🎯 选择前 {len(df)} 个样本进行评估")
    
    return df

def prepare_eval_data(df: pd.DataFrame, tokenizer, processor):
    """准备评估数据，转换为模型输入格式"""
    print(f"🔧 准备评估数据...")
    
    prompts_list = []
    vllm_inputs_list = []
    
    for idx, row in df.iterrows():
        # 提取数据
        conversations = row.get('conversations', [])
        images = row.get('images', [])
        env_name = row.get('env_name', '')
        
        print(f"样本 {idx}: env_name={env_name}, 图像数量={len(images)}")
        
        # 处理对话数据
        if conversations and len(conversations) > 0:
            # 通常第一个是用户输入
            user_message = conversations[0].get('value', '') if conversations[0].get('from') == 'user' else ''
            
            # 处理图像
            pil_images = []
            if images:
                for img_data in images:
                    if isinstance(img_data, str):
                        # 如果是base64编码
                        import base64
                        import io
                        img_bytes = base64.b64decode(img_data)
                        pil_image = Image.open(io.BytesIO(img_bytes)).convert('RGB')
                    else:
                        # 如果已经是PIL图像
                        pil_image = img_data
                    pil_images.append(pil_image)
            
            # 创建提示
            if pil_images:
                prompt_text = user_message.replace('<image>', '<image>' * len(pil_images))
            else:
                prompt_text = user_message
            
            # Tokenize
            if processor and pil_images:
                # 多模态输入
                inputs = processor(text=[prompt_text], images=pil_images, return_tensors="pt")
                input_ids = inputs['input_ids'][0]
                attention_mask = inputs['attention_mask'][0]
                
                # VLLM输入
                vllm_input = {
                    'prompt_token_ids': input_ids.cpu().numpy().tolist(),
                    'multi_modal_data': {'image': pil_images}
                }
            else:
                # 纯文本输入
                inputs = tokenizer(prompt_text, return_tensors="pt")
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
                    'origin_multi_modal_data': [{'image': pil_images}] if pil_images else [{}]
                }
            )
            
            prompts_list.append(prompt_data)
            vllm_inputs_list.append(vllm_input)
    
    return prompts_list, vllm_inputs_list

def save_step_images(step_images: List[List[Image.Image]], output_dir: str, sample_idx: int):
    """保存每一步的图像"""
    sample_dir = Path(output_dir) / f"sample_{sample_idx:02d}"
    sample_dir.mkdir(parents=True, exist_ok=True)
    
    for step, images in enumerate(step_images):
        step_dir = sample_dir / f"step_{step:02d}"
        step_dir.mkdir(exist_ok=True)
        
        for img_idx, img in enumerate(images):
            img_path = step_dir / f"image_{img_idx:02d}.png"
            img.save(img_path)
            print(f"💾 保存图像: {img_path}")

def create_visualization_grid(step_images: List[List[Image.Image]], output_dir: str, sample_idx: int):
    """创建可视化网格"""
    if not step_images:
        return
    
    max_steps = len(step_images)
    max_images = max(len(images) for images in step_images)
    
    fig, axes = plt.subplots(max_steps, max_images, figsize=(max_images * 4, max_steps * 4))
    if max_steps == 1:
        axes = [axes]
    if max_images == 1:
        axes = [[ax] for ax in axes]
    
    for step, images in enumerate(step_images):
        for img_idx, img in enumerate(images):
            ax = axes[step][img_idx]
            ax.imshow(img)
            ax.set_title(f"Step {step + 1}, Image {img_idx + 1}")
            ax.axis('off')
        
        # 隐藏多余的子图
        for img_idx in range(len(images), max_images):
            axes[step][img_idx].axis('off')
    
    plt.tight_layout()
    grid_path = Path(output_dir) / f"sample_{sample_idx:02d}" / "visualization_grid.png"
    plt.savefig(grid_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"📊 保存可视化网格: {grid_path}")

class StepByStepEvaluator:
    """逐步评估器"""
    
    def __init__(self, model_path: str, output_dir: str = "eval_results"):
        self.model_path = model_path
        self.output_dir = output_dir
        self.tokenizer = hf_tokenizer(model_path)
        self.processor = hf_processor(model_path)
        
        # 创建输出目录
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        print(f"🚀 初始化评估器")
        print(f"📁 输出目录: {output_dir}")
    
    def evaluate_sample(self, prompt_data: DataProto, vllm_input: Dict, sample_idx: int):
        """评估单个样本，记录每一步的图像"""
        print(f"\n{'='*60}")
        print(f"🎯 评估样本 {sample_idx}")
        print(f"{'='*60}")
        
        # 模拟配置
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
        
        config = MockConfig()
        sampling_params = MockSamplingParams()
        
        # 记录每一步的图像
        step_images = []
        step_actions = []
        step_rewards = []
        
        # 自定义的agent环境，记录每一步
        env = ParallelEnv(config.agent, self.tokenizer, self.processor)
        
        # 重写step方法来捕获图像
        original_step = env.step
        def capture_step(active_indices, actions, current_turn=1):
            print(f"\n📸 捕获第 {current_turn} 轮的动作和图像")
            
            # 记录动作
            for idx, action in enumerate(actions):
                action_text = action.outputs[0].text
                step_actions.append({
                    'turn': current_turn,
                    'action_idx': idx,
                    'text': action_text
                })
                print(f"🎭 动作 {idx}: {action_text[:100]}...")
            
            # 调用原始step方法
            result = original_step(active_indices, actions, current_turn)
            observations, rewards, dones, info = result
            
            # 记录奖励
            step_rewards.extend(rewards)
            
            # 提取图像
            current_step_images = []
            for obs in observations:
                if isinstance(obs, dict) and 'multi_modal_data' in obs:
                    mm_data = obs['multi_modal_data']
                    if 'image' in mm_data:
                        current_step_images.extend(mm_data['image'])
            
            if current_step_images:
                step_images.append(current_step_images)
                print(f"📷 第 {current_turn} 轮捕获了 {len(current_step_images)} 张图像")
            
            return result
        
        env.step = capture_step
        
        # 模拟VLLM引擎（这里简化处理）
        class MockVLLMEngine:
            def __init__(self, tokenizer, processor):
                self.tokenizer = tokenizer
                self.processor = processor
            
            def generate(self, prompts, sampling_params, use_tqdm=False):
                # 这里应该调用实际的VLLM生成
                # 为了演示，我们返回模拟的结果
                class MockOutput:
                    def __init__(self, text="<think>{\"diagnosis\":{\"labels\":[\"haze\"]},\"pass\":false}</think><tool_call>[{\"name\":\"dehazeformer_dehaze\",\"arguments\":{\"strength\":0.7}}]</tool_call>"):
                        self.text = text
                        self.token_ids = tokenizer.encode(text)
                        self.finish_reason = 'stop'
                
                class MockAction:
                    def __init__(self, text):
                        self.outputs = [MockOutput(text)]
                
                # 返回模拟动作
                return [MockAction("<think>{\"diagnosis\":{\"labels\":[\"clean\"]},\"pass\":true}</think><answer>success</answer>")]
        
        # 注意：这里使用模拟引擎，实际使用时需要真实的VLLM引擎
        mock_engine = MockVLLMEngine(self.tokenizer, self.processor)
        
        try:
            # 执行agent rollout（简化版本）
            prompts = DataProto.from_list([prompt_data])
            
            # 初始图像
            if 'multi_modal_data' in vllm_input and 'image' in vllm_input['multi_modal_data']:
                initial_images = vllm_input['multi_modal_data']['image']
                step_images.append(initial_images)
                print(f"📷 初始图像: {len(initial_images)} 张")
            
            # 这里应该调用真实的agent_rollout_loop
            # result = agent_rollout_loop(config, mock_engine, [vllm_input], prompts, None, sampling_params)
            
        except Exception as e:
            print(f"❌ 评估过程中出错: {e}")
            import traceback
            traceback.print_exc()
        
        # 保存结果
        sample_output_dir = Path(self.output_dir) / f"sample_{sample_idx:02d}"
        sample_output_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存每一步的图像
        save_step_images(step_images, self.output_dir, sample_idx)
        
        # 创建可视化网格
        if step_images:
            create_visualization_grid(step_images, self.output_dir, sample_idx)
        
        # 保存动作历史
        actions_file = sample_output_dir / "actions.json"
        with open(actions_file, 'w', encoding='utf-8') as f:
            json.dump(step_actions, f, indent=2, ensure_ascii=False)
        print(f"💾 保存动作历史: {actions_file}")
        
        # 保存奖励历史
        rewards_file = sample_output_dir / "rewards.json"
        with open(rewards_file, 'w') as f:
            json.dump(step_rewards, f, indent=2)
        print(f"💾 保存奖励历史: {rewards_file}")
        
        return {
            'step_images': step_images,
            'step_actions': step_actions,
            'step_rewards': step_rewards
        }

def create_real_evaluator(model_path: str, data_file: str, output_dir: str = "eval_results"):
    """创建真实的评估器（使用实际的VLLM）"""
    print(f"🚀 创建真实评估器")
    
    # 加载数据
    df = load_test_data(data_file, num_samples=3)
    
    # 初始化
    tokenizer = hf_tokenizer(model_path)
    processor = hf_processor(model_path)
    
    # 准备数据
    prompts_list, vllm_inputs_list = prepare_eval_data(df, tokenizer, processor)
    
    print(f"✅ 准备完成，共 {len(prompts_list)} 个样本")
    print(f"📁 结果将保存到: {output_dir}")
    
    # 创建输出目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    full_output_dir = f"{output_dir}/eval_{timestamp}"
    Path(full_output_dir).mkdir(parents=True, exist_ok=True)
    
    # 保存配置信息
    config_info = {
        'model_path': model_path,
        'data_file': data_file,
        'num_samples': len(prompts_list),
        'timestamp': timestamp
    }
    
    config_file = Path(full_output_dir) / "config.json"
    with open(config_file, 'w') as f:
        json.dump(config_info, f, indent=2)
    
    print(f"📋 配置信息保存到: {config_file}")
    
    return full_output_dir, prompts_list, vllm_inputs_list

@hydra.main(version_base=None, config_path="examples/agent", config_name="config")
def main(config: DictConfig):
    """主函数"""
    print(f"🎯 Agent 逐步评估开始")
    print(f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 从配置中获取参数
    model_path = config.actor_rollout_ref.model.path
    val_files = config.data.val_files
    
    if not val_files:
        print("❌ 配置中没有找到验证文件")
        return
    
    data_file = val_files[0]  # 使用第一个验证文件
    
    try:
        # 创建评估器
        output_dir, prompts_list, vllm_inputs_list = create_real_evaluator(
            model_path=model_path,
            data_file=data_file,
            output_dir="eval_results"
        )
        
        # 评估每个样本
        evaluator = StepByStepEvaluator(model_path, output_dir)
        
        for idx, (prompt_data, vllm_input) in enumerate(zip(prompts_list, vllm_inputs_list)):
            print(f"\n🔍 开始评估样本 {idx}")
            result = evaluator.evaluate_sample(prompt_data, vllm_input, idx)
            print(f"✅ 样本 {idx} 评估完成")
        
        print(f"\n🎉 所有样本评估完成！")
        print(f"📁 结果保存在: {output_dir}")
        print(f"🖼️  可以查看每一步的图像变化")
        
    except Exception as e:
        print(f"❌ 评估过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 简化版本，直接指定参数
    model_path = "/app/models/Qwen2.5-VL-7B-Instruct"
    data_file = "/app/xiaominl/shard-000003.parquet"  # 验证数据文件
    
    print(f"🎯 简化评估模式")
    print(f"📁 模型路径: {model_path}")
    print(f"📁 数据文件: {data_file}")
    
    try:
        output_dir, prompts_list, vllm_inputs_list = create_real_evaluator(
            model_path=model_path,
            data_file=data_file,
            output_dir="eval_results"
        )
        
        print(f"✅ 评估器创建完成")
        print(f"📊 准备评估 {len(prompts_list)} 个样本")
        print(f"💡 提示：要使用真实的VLLM引擎，请修改 MockVLLMEngine 部分")
        
    except Exception as e:
        print(f"❌ 创建评估器时出错: {e}")
        import traceback
        traceback.print_exc()
