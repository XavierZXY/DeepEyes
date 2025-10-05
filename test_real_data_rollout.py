#!/usr/bin/env python3
"""
使用真实数据的Agent Rollout测试
从parquet文件加载真实的有退化问题的图片进行测试
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
from copy import deepcopy
from omegaconf import DictConfig, OmegaConf

# 添加项目路径
sys.path.append('/app/xiaominl/DeepEyes')

from verl.utils import hf_tokenizer, hf_processor
from verl.workers.agent.parallel_env_v2 import agent_rollout_loop
from verl import DataProto
from verl.utils.dataset.vision_utils import process_image
from vllm import LLM, SamplingParams


class RealDataAgentTester:
    """使用真实数据的Agent测试器"""
    
    def __init__(self, model_path: str, data_file: str, output_dir: str = "real_data_test"):
        self.model_path = model_path
        self.data_file = data_file
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # 创建配置
        self.config = self.create_config()
        
        # 初始化模型组件
        self.tokenizer = None
        self.processor = None
        self.vllm_engine = None
        
    def create_config(self):
        """创建测试配置"""
        config = DictConfig({
            'agent': {
                'vl_model_path': self.model_path,
                'max_turns': 10,
                'single_response_max_tokens': 2048,
                'concurrent_workers': 1,
                'show_tqdm': True,
                'custom_stop': [],
                'tool_name_key': 'env_name'
            },
            'prompt_length': 8192,
            'response_length': 2048
        })
        return config
    
    def load_sample_data(self, sample_idx: int):
        """加载样本数据 - 从现有代码复制"""
        df = pd.read_parquet(self.data_file)
        if sample_idx >= len(df):
            raise IndexError(f"样本索引超出范围: {sample_idx} >= {len(df)}")
        
        row = df.iloc[sample_idx]
        print(f"📊 数据行信息:")
        print(f"  env_name: {row.get('env_name', 'N/A')}")
        print(f"  data_source: {row.get('data_source', 'N/A')}")
        print(f"  images类型: {type(row.get('images', None))}")
        print(f"  prompt类型: {type(row.get('prompt', None))}")
        
        # 解析图像 - 使用与训练相同的处理方式
        images = []
        if isinstance(row['images'], np.ndarray):
            print(f"  images数组长度: {len(row['images'])}")
            # 按照训练时的方式处理图像
            for i, img_data in enumerate(row['images']):
                print(f"  处理图像 {i}: 类型={type(img_data)}")
                processed_img = process_image(img_data)
                print(f"  process_image结果类型: {type(processed_img)}")
                
                # 确保是PIL图像格式
                if isinstance(processed_img, dict) and 'image' in processed_img:
                    images.append(processed_img['image'])
                    print(f"    -> 提取PIL图像: {processed_img['image'].size}")
                elif hasattr(processed_img, 'size'):  # PIL图像
                    images.append(processed_img)
                    print(f"    -> 直接PIL图像: {processed_img.size}")
                else:
                    print(f"    -> 未知图像格式: {type(processed_img)}")
                    images.append(processed_img)
            print(f"[DEBUG] 使用process_image处理了 {len(images)} 张图像")
        
        # 解析对话
        conversations = []
        if isinstance(row['prompt'], np.ndarray):
            conversations = row['prompt'].tolist()
            print(f"  对话数量: {len(conversations)}")
        
        return {
            'env_name': row['env_name'],
            'images': images,
            'conversations': conversations,
            'data_source': row['data_source'],
            'sample_idx': sample_idx
        }
    
    def prepare_model_inputs_v2(self, sample_data: dict):
        """准备模型输入 V2 - 基于现有代码"""
        
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
-   The final `<answer>` must be the specified JSON object (no `status` field)."""
        
        # 构建prompt文本 - 使用Qwen2VL的正确格式
        if conversations and len(conversations) >= 2:
            print(f"📝 使用原有对话格式，对话数量: {len(conversations)}")
            # 将conversations转换为Qwen2VL的结构化格式
            structured_conversations = []
            for conv in conversations:
                if conv.get('role') == 'user':
                    # 将user的content转换为结构化格式
                    content = conv.get('content', '')
                    if '<image>' in content:
                        # 创建结构化content：图像 + 文本
                        text_content = content.replace('<image>', '').strip()
                        structured_content = [
                            {'type': 'image'},
                            {'type': 'text', 'text': text_content}
                        ]
                        structured_conversations.append({
                            'role': 'user',
                            'content': structured_content
                        })
                    else:
                        structured_conversations.append(conv)
                else:
                    structured_conversations.append(conv)
            
            # 使用processor的apply_chat_template（支持结构化格式）
            prompt_text = self.processor.apply_chat_template(
                structured_conversations, 
                add_generation_prompt=True, 
                tokenize=False
            )
            print(f"[DEBUG] 使用结构化conversations格式")
        else:
            # 如果没有对话，使用默认V2模板
            print(f"📝 使用默认V2模板格式")
            prompt_text = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n<image>\nPlease assess the quality of this image. If there are any degradation issues that need fixing, please provide the first step of the solution.<|im_end|>\n<|im_start|>assistant\n"
        
        # 处理多模态输入 - 使用与rollout相同的格式
        if self.processor and images:
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
            raw_prompt_ids = self.tokenizer.encode(prompt_text, add_special_tokens=False)
            print(f"[DEBUG] raw_prompt_ids长度: {len(raw_prompt_ids)}")
            
            # 2. 用processor处理完整的输入（包含图像和文本）
            model_inputs = self.processor(text=[prompt_text], images=processed_images, return_tensors="pt")
            dataproto_input_ids = model_inputs['input_ids'][0]
            dataproto_attention_mask = model_inputs['attention_mask'][0]
            
            print(f"[DEBUG] processor处理后input_ids长度: {len(dataproto_input_ids)}")
            print(f"[DEBUG] model_inputs keys: {list(model_inputs.keys())}")
            
            # 创建DataProto格式的prompts
            prompts = DataProto.from_dict(
                tensors={
                    'input_ids': dataproto_input_ids.unsqueeze(0),  # shape: [1, seq_len]
                    'attention_mask': dataproto_attention_mask.unsqueeze(0),
                },
                non_tensors={
                    'raw_prompt': [prompt_text],
                    'raw_prompt_ids': [raw_prompt_ids],
                    'env_name': [env_name],
                    'origin_multi_modal_data': [{'image': images}]  # 使用原始图像
                }
            )
            
            # 准备VLLM输入
            vllm_input = {
                'prompt_token_ids': raw_prompt_ids,
                'multi_modal_data': {'image': processed_images}
            }
            
            return prompts, vllm_input
        
        else:
            raise ValueError("没有图像数据或processor未初始化")
    
    def init_models(self):
        """初始化模型"""
        print(f"🚀 初始化模型: {self.model_path}")
        
        # 导入工具模块
        try:
            import verl.workers.agent.envs.mm_process_engine.DehazeFormerToolbox
            import verl.workers.agent.envs.mm_process_engine.BrighteningToolbox
            import verl.workers.agent.envs.mm_process_engine.SwinIRToolbox
            import verl.workers.agent.envs.mm_process_engine.DeblurToolbox
            import verl.workers.agent.envs.mm_process_engine.XRestormerToolbox
            import verl.workers.agent.envs.mm_process_engine.MPRNetToolbox
            import verl.workers.agent.envs.mm_process_engine.FBCNNToolbox
            print("✅ 工具模块导入成功")
        except ImportError as e:
            print(f"⚠️ 工具模块导入失败: {e}")
        
        # 初始化tokenizer和processor
        self.tokenizer = hf_tokenizer(self.model_path)
        self.processor = hf_processor(self.model_path)
        
        # 初始化VLLM引擎
        self.vllm_engine = LLM(
            model=self.model_path,
            tensor_parallel_size=1,
            trust_remote_code=True,
            max_model_len=8192,
            dtype=torch.bfloat16,
            gpu_memory_utilization=0.4
        )
        
        print("✅ 模型初始化完成")
    
    def run_test(self, sample_idx: int = 0):
        """运行测试"""
        print("🎯 开始真实数据Agent Rollout测试")
        print("=" * 60)
        
        try:
            # 初始化模型
            self.init_models()
            
            # 加载样本数据
            sample_data = self.load_sample_data(sample_idx)
            
            # 保存原始数据
            self.save_original_data(sample_data)
            
            # 准备模型输入
            prompts, vllm_input = self.prepare_model_inputs_v2(sample_data)
            
            # 多模态输入占位符
            multi_modal_inputs = torch.zeros(1, 1) if 'multi_modal_data' in vllm_input else None
            
            # 设置采样参数
            sampling_params = SamplingParams(
                n=1,
                max_tokens=2048,
                temperature=0.1,
                top_p=0.9,
                stop=None,
                skip_special_tokens=False,
                spaces_between_special_tokens=False,
                include_stop_str_in_output=True
            )
            
            print(f"🔄 开始Agent Rollout...")
            print(f"  Max turns: {self.config.agent.max_turns}")
            print(f"  Sample: {sample_idx} ({sample_data['env_name']})")
            print(f"  Images: {len(sample_data['images'])}")
            
            # 调用真实的agent rollout
            result = agent_rollout_loop(
                config=self.config,
                vllm_engine=self.vllm_engine,
                vllm_inputs=[vllm_input],
                prompts=prompts,
                multi_modal_inputs=multi_modal_inputs,
                sampling_params=sampling_params
            )
            
            print(f"✅ Agent Rollout完成！")
            
            # 保存和分析结果
            self.save_and_analyze_results(result, sample_data)
            
            return True
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def save_original_data(self, sample_data: dict):
        """保存原始数据"""
        
        # 保存基本信息
        basic_info = {
            'sample_idx': sample_data['sample_idx'],
            'env_name': sample_data['env_name'],
            'data_source': sample_data['data_source'],
            'num_images': len(sample_data['images']),
            'image_sizes': [img.size for img in sample_data['images']] if sample_data['images'] else [],
            'num_conversations': len(sample_data['conversations'])
        }
        
        with open(self.output_dir / "sample_info.json", 'w', encoding='utf-8') as f:
            json.dump(basic_info, f, indent=2, ensure_ascii=False)
        
        # 保存原始图像
        for img_idx, img in enumerate(sample_data['images']):
            img_path = self.output_dir / f"original_image_{img_idx:02d}.png"
            img.save(img_path)
            print(f"💾 保存原始图像: {img_path} ({img.size})")
        
        # 保存对话
        if sample_data['conversations']:
            with open(self.output_dir / "conversations.json", 'w', encoding='utf-8') as f:
                json.dump(sample_data['conversations'], f, indent=2, ensure_ascii=False)
            print(f"💾 保存对话历史: {len(sample_data['conversations'])} 条")
    
    def save_and_analyze_results(self, result, sample_data: dict):
        """保存和分析结果"""
        print(f"\n📊 分析结果...")
        
        # 分析tensor结果
        if hasattr(result, 'tensors'):
            tensor_info = {}
            print(f"\n🔍 Tensor信息:")
            
            for key, tensor in result.tensors.items():
                if torch.is_tensor(tensor):
                    shape = list(tensor.shape)
                    tensor_info[key] = {
                        'shape': shape,
                        'dtype': str(tensor.dtype)
                    }
                    
                    # 打印重要信息
                    if key in ['tool_cnt', 'final_answer', 'repeated_degradation_cnt', 'restoration_log_length']:
                        data = tensor.cpu().numpy().tolist()
                        tensor_info[key]['data'] = data
                        print(f"  {key}: {data}")
                    elif key.startswith('degradation_') or key.startswith('tool_usage_'):
                        data = tensor.cpu().numpy().tolist()
                        if any(x > 0 for x in data):  # 只显示有值的
                            tensor_info[key]['data'] = data
                            print(f"  {key}: {data}")
            
            # 保存tensor信息
            with open(self.output_dir / "tensor_analysis.json", 'w') as f:
                json.dump(tensor_info, f, indent=2)
        
        # 解码模型响应
        if hasattr(result, 'tensors') and 'response' in result.tensors:
            response_ids = result.tensors['response'][0]  # 第一个样本
            
            # 移除padding
            if hasattr(self.tokenizer, 'pad_token_id') and self.tokenizer.pad_token_id is not None:
                response_ids = response_ids[response_ids != self.tokenizer.pad_token_id]
            
            response_text = self.tokenizer.decode(response_ids, skip_special_tokens=True)
            
            # 保存完整响应
            with open(self.output_dir / "full_response.txt", 'w', encoding='utf-8') as f:
                f.write(response_text)
            
            print(f"\n📝 模型响应:")
            print(f"  长度: {len(response_text)} 字符")
            print(f"  预览: {response_text[:500]}...")
            
            # 分析对话轮次
            self.analyze_conversation(response_text)
        
        # 保存图像历史
        if hasattr(result, 'non_tensors') and result.non_tensors:
            image_history = result.non_tensors.get('image_history_list', None)
            if image_history is not None and len(image_history) > 0:
                self.save_image_history(image_history[0])  # 第一个样本
        
        print(f"\n✅ 结果已保存到: {self.output_dir}")
    
    def analyze_conversation(self, response_text: str):
        """分析对话过程"""
        from verl.workers.agent.parallel_env_v2 import _parse_model_output_for_tools_v2
        
        # 分割assistant的回复
        assistant_turns = response_text.split('<|im_start|>assistant\n')
        
        conversation_analysis = []
        restoration_log = []
        
        for turn_idx, turn_text in enumerate(assistant_turns[1:], 1):
            if not turn_text.strip():
                continue
            
            # 清理文本
            turn_text = turn_text.split('<|im_end|>')[0].strip()
            
            print(f"\n🔄 第 {turn_idx} 轮分析:")
            print(f"  文本长度: {len(turn_text)} 字符")
            
            # 使用V2解析器
            parsed = _parse_model_output_for_tools_v2(turn_text, f"turn-{turn_idx}")
            
            turn_analysis = {
                'turn': turn_idx,
                'raw_text': turn_text,
                'think_content': parsed.get('think'),
                'tool_calls': parsed.get('tool_calls', []),
                'is_done': parsed.get('is_done', False),
                'answer': parsed.get('answer'),
                'restoration_log': parsed.get('restoration_log', [])
            }
            
            print(f"  💭 思考: {turn_analysis['think_content']}")
            print(f"  🔧 工具调用: {len(turn_analysis['tool_calls'])} 个")
            if turn_analysis['tool_calls']:
                for tool_call in turn_analysis['tool_calls']:
                    if isinstance(tool_call, dict):
                        tool_name = tool_call.get('name', 'unknown')
                        tool_args = tool_call.get('arguments', {})
                        print(f"    - {tool_name}: {tool_args}")
            
            if turn_analysis['is_done']:
                restoration_log = turn_analysis['restoration_log']
                print(f"  ✅ 完成！修复日志: {restoration_log}")
            
            conversation_analysis.append(turn_analysis)
            
            # 保存单轮分析
            turn_file = self.output_dir / f"turn_{turn_idx:02d}_analysis.json"
            with open(turn_file, 'w', encoding='utf-8') as f:
                json.dump(turn_analysis, f, indent=2, ensure_ascii=False)
        
        # 保存完整对话分析
        with open(self.output_dir / "conversation_analysis.json", 'w', encoding='utf-8') as f:
            json.dump(conversation_analysis, f, indent=2, ensure_ascii=False)
        
        # 创建摘要
        summary = {
            'total_turns': len(conversation_analysis),
            'final_restoration_log': restoration_log,
            'tools_used': [],
            'completed': any(turn['is_done'] for turn in conversation_analysis)
        }
        
        # 收集使用的工具
        for turn in conversation_analysis:
            for tool_call in turn['tool_calls']:
                if isinstance(tool_call, dict):
                    tool_name = tool_call.get('name', 'unknown')
                    if tool_name not in summary['tools_used']:
                        summary['tools_used'].append(tool_name)
        
        with open(self.output_dir / "conversation_summary.json", 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"\n📋 对话摘要:")
        print(f"  总轮次: {summary['total_turns']}")
        print(f"  使用工具: {summary['tools_used']}")
        print(f"  是否完成: {summary['completed']}")
        print(f"  最终修复日志: {summary['final_restoration_log']}")
    
    def save_image_history(self, image_history):
        """保存图像历史"""
        print(f"\n🖼️ 保存图像历史: {len(image_history)} 步")
        
        for step_idx, step_data in enumerate(image_history):
            if isinstance(step_data, dict) and 'image' in step_data:
                images = step_data['image']
                for img_idx, img in enumerate(images):
                    if hasattr(img, 'save'):  # PIL图像
                        img_path = self.output_dir / f"step_{step_idx:02d}_image_{img_idx:02d}.png"
                        img.save(img_path)
                        print(f"  💾 步骤 {step_idx}, 图像 {img_idx}: {img_path} ({img.size})")
        
        # 创建对比图
        self.create_comparison_grid(image_history)
    
    def create_comparison_grid(self, image_history):
        """创建图像对比网格"""
        if not image_history:
            return
        
        import matplotlib.pyplot as plt
        
        # 收集所有图像
        all_images = []
        step_labels = []
        
        for step_idx, step_data in enumerate(image_history):
            if isinstance(step_data, dict) and 'image' in step_data:
                images = step_data['image']
                if images and hasattr(images[0], 'size'):
                    all_images.append(images[0])  # 取第一张图
                    step_labels.append(f"Step {step_idx}")
        
        if len(all_images) <= 1:
            return
        
        # 创建网格
        n_images = len(all_images)
        cols = min(4, n_images)
        rows = (n_images + cols - 1) // cols
        
        fig, axes = plt.subplots(rows, cols, figsize=(4*cols, 4*rows))
        if rows == 1:
            axes = [axes] if cols == 1 else axes
        else:
            axes = axes.flatten()
        
        for i, (img, label) in enumerate(zip(all_images, step_labels)):
            if i < len(axes):
                axes[i].imshow(img)
                axes[i].set_title(label)
                axes[i].axis('off')
        
        # 隐藏多余的子图
        for i in range(len(all_images), len(axes)):
            axes[i].axis('off')
        
        plt.tight_layout()
        comparison_path = self.output_dir / "image_progression.png"
        plt.savefig(comparison_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"📊 图像进展对比图: {comparison_path}")


def main():
    """主函数"""
    # 配置
    model_path = "/app/models/Qwen2.5-VL-7B-Instruct"
    data_file = "/app/datasets/DeepEyes-Datasets-47k/data_0.1.2_visual_toolbox_v2.parquet"  # 使用真实数据
    sample_idx = 0  # 可以修改这个索引来测试不同样本
    
    # 检查文件是否存在
    if not os.path.exists(model_path):
        print(f"❌ 模型路径不存在: {model_path}")
        return
    
    if not os.path.exists(data_file):
        print(f"❌ 数据文件不存在: {data_file}")
        print("可用的数据文件:")
        import glob
        parquet_files = glob.glob("/app/datasets/**/*.parquet", recursive=True)
        for f in parquet_files[:5]:
            print(f"  {f}")
        return
    
    # 创建测试器
    output_dir = f"real_data_test_sample_{sample_idx}"
    tester = RealDataAgentTester(model_path, data_file, output_dir)
    
    # 运行测试
    print("🎯 真实数据Agent Rollout测试")
    print("=" * 60)
    print(f"📁 数据文件: {data_file}")
    print(f"📊 测试样本: {sample_idx}")
    
    success = tester.run_test(sample_idx)
    
    if success:
        print(f"\n🎉 测试完成！")
        print(f"📁 查看结果: {tester.output_dir}")
        print(f"📋 主要文件:")
        print(f"  - sample_info.json: 样本基本信息")
        print(f"  - original_image_XX.png: 原始图像")
        print(f"  - full_response.txt: 完整模型响应")
        print(f"  - conversation_analysis.json: 对话分析")
        print(f"  - conversation_summary.json: 对话摘要")
        print(f"  - step_XX_image_XX.png: 处理过程图像")
        print(f"  - image_progression.png: 图像变化进展")
    else:
        print(f"\n❌ 测试失败，请检查日志")


if __name__ == "__main__":
    main()
