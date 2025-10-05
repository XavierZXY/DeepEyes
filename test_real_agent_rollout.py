#!/usr/bin/env python3
"""
真实Agent Rollout测试
直接调用agent_rollout_loop进行真实的推理和工具调用
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


class RealAgentTester:
    """真实Agent测试器"""
    
    def __init__(self, model_path: str, output_dir: str = "real_agent_test"):
        self.model_path = model_path
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
    
    def load_test_image(self, image_path: str):
        """加载测试图片"""
        if not os.path.exists(image_path):
            # 如果没有提供图片，创建一个测试图片
            return self.create_test_image()
        
        img = Image.open(image_path).convert('RGB')
        print(f"📸 加载图片: {image_path}, 尺寸: {img.size}")
        return img
    
    def create_test_image(self):
        """创建测试图片（有多种退化问题）"""
        # 创建一个带有多种问题的测试图片
        img = Image.new('RGB', (512, 512), color='lightgray')
        img_array = np.array(img)
        
        # 添加一些图案
        for i in range(0, 512, 64):
            for j in range(0, 512, 64):
                if (i//64 + j//64) % 2 == 0:
                    img_array[i:i+64, j:j+64] = [120, 160, 200]
        
        # 添加JPEG压缩风格的块状伪影
        for i in range(0, 512, 8):
            for j in range(0, 512, 8):
                if (i//8 + j//8) % 3 == 0:
                    img_array[i:i+8, j:j+8] = img_array[i:i+8, j:j+8] * 0.8
        
        # 添加噪声（模拟多种问题）
        noise = np.random.normal(0, 15, img_array.shape)
        img_array = np.clip(img_array + noise, 0, 255).astype(np.uint8)
        
        # 模拟轻微模糊
        from scipy import ndimage
        img_array = ndimage.gaussian_filter(img_array, sigma=0.8)
        img_array = np.clip(img_array, 0, 255).astype(np.uint8)
        
        test_img = Image.fromarray(img_array)
        
        # 保存测试图片
        test_img_path = self.output_dir / "test_input.png"
        test_img.save(test_img_path)
        print(f"✅ 创建测试图片: {test_img_path}, 尺寸: {test_img.size}")
        
        return test_img
    
    def prepare_inputs(self, image: Image.Image):
        """准备输入数据"""
        
        # V2格式的system prompt
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
        
        # 构建prompt
        prompt_text = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n<image>\nPlease assess the quality of this image. If there are any degradation issues that need fixing, please provide the first step of the solution.<|im_end|>\n<|im_start|>assistant\n"
        
        # 处理图像
        processed_image = process_image({'image': image})
        if isinstance(processed_image, dict) and 'image' in processed_image:
            processed_image = processed_image['image']
        
        print(f"📝 Prompt长度: {len(prompt_text)} 字符")
        print(f"🖼️ 处理后图像类型: {type(processed_image)}")
        
        # 准备raw prompt ids（纯文本）
        raw_prompt_ids = self.tokenizer.encode(prompt_text, add_special_tokens=False)
        
        # 准备完整的模型输入（包含视觉tokens）
        model_inputs = self.processor(text=[prompt_text], images=[processed_image], return_tensors="pt")
        
        # 创建DataProto格式的prompts
        prompts = DataProto.from_dict(
            tensors={
                'input_ids': model_inputs['input_ids'],
                'attention_mask': model_inputs['attention_mask']
            },
            non_tensors={
                'raw_prompt': [prompt_text],
                'raw_prompt_ids': [raw_prompt_ids],
                'env_name': ['test_env'],
                'origin_multi_modal_data': [{'image': [image]}]
            }
        )
        
        # 准备VLLM输入
        vllm_input = {
            'prompt_token_ids': raw_prompt_ids,
            'multi_modal_data': {'image': [processed_image]}
        }
        
        # 多模态输入占位符
        multi_modal_inputs = torch.zeros(1, 1)
        
        return prompts, vllm_input, multi_modal_inputs
    
    def init_models(self):
        """初始化模型"""
        print(f"🚀 初始化模型: {self.model_path}")
        
        # 初始化tokenizer和processor
        self.tokenizer = hf_tokenizer(self.model_path)
        self.processor = hf_processor(self.model_path)
        
        # 初始化VLLM引擎
        self.vllm_engine = LLM(
            model=self.model_path,
            tensor_parallel_size=1,
            trust_remote_code=True,
            max_model_len=8192,
            dtype=torch.bfloat16
        )
        
        print("✅ 模型初始化完成")
    
    def run_test(self, image_path: str = None):
        """运行测试"""
        print("🎯 开始真实Agent Rollout测试")
        print("=" * 60)
        
        try:
            # 初始化模型
            self.init_models()
            
            # 加载测试图片
            test_image = self.load_test_image(image_path) if image_path else self.create_test_image()
            
            # 准备输入
            prompts, vllm_input, multi_modal_inputs = self.prepare_inputs(test_image)
            
            # 设置采样参数
            sampling_params = SamplingParams(
                temperature=0.0,
                top_p=1.0,
                max_tokens=2048,
                n=1
            )
            
            print(f"🔄 开始Agent Rollout...")
            print(f"  Max turns: {self.config.agent.max_turns}")
            print(f"  Max tokens per turn: {self.config.agent.single_response_max_tokens}")
            
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
            self.save_and_analyze_results(result, test_image)
            
            return True
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def save_and_analyze_results(self, result, original_image: Image.Image):
        """保存和分析结果"""
        print(f"\n📊 分析结果...")
        
        # 保存原始图片
        original_image.save(self.output_dir / "original_image.png")
        
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
            print(f"  预览: {response_text[:300]}...")
            
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
        
        for turn_idx, turn_text in enumerate(assistant_turns[1:], 1):
            if not turn_text.strip():
                continue
            
            # 清理文本
            turn_text = turn_text.split('<|im_end|>')[0].strip()
            
            print(f"\n🔄 分析第 {turn_idx} 轮:")
            print(f"  原始文本长度: {len(turn_text)} 字符")
            
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
            
            print(f"  思考内容: {turn_analysis['think_content']}")
            print(f"  工具调用: {len(turn_analysis['tool_calls'])} 个")
            if turn_analysis['tool_calls']:
                for tool_call in turn_analysis['tool_calls']:
                    if isinstance(tool_call, dict):
                        print(f"    - {tool_call.get('name', 'unknown')}: {tool_call.get('arguments', {})}")
            
            if turn_analysis['is_done']:
                print(f"  ✅ 完成！修复日志: {turn_analysis['restoration_log']}")
            
            conversation_analysis.append(turn_analysis)
            
            # 保存单轮分析
            turn_file = self.output_dir / f"turn_{turn_idx:02d}_analysis.json"
            with open(turn_file, 'w', encoding='utf-8') as f:
                json.dump(turn_analysis, f, indent=2, ensure_ascii=False)
        
        # 保存完整对话分析
        with open(self.output_dir / "conversation_analysis.json", 'w', encoding='utf-8') as f:
            json.dump(conversation_analysis, f, indent=2, ensure_ascii=False)
        
        print(f"\n📋 对话分析: 共 {len(conversation_analysis)} 轮")
    
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
    model_path = "/app/models/Qwen2.5-VL-7B-Instruct"  # 修改为你的模型路径
    
    # 检查模型是否存在
    if not os.path.exists(model_path):
        print(f"❌ 模型路径不存在: {model_path}")
        print("请修改model_path变量为你的实际模型路径")
        return
    
    # 创建测试器
    tester = RealAgentTester(model_path)
    
    # 运行测试
    print("🎯 真实Agent Rollout测试")
    print("=" * 60)
    
    success = tester.run_test()
    
    if success:
        print(f"\n🎉 测试完成！")
        print(f"📁 查看结果: {tester.output_dir}")
        print(f"📋 主要文件:")
        print(f"  - full_response.txt: 完整模型响应")
        print(f"  - conversation_analysis.json: 对话分析")
        print(f"  - tensor_analysis.json: 张量统计")
        print(f"  - image_progression.png: 图像变化过程")
    else:
        print(f"\n❌ 测试失败，请检查日志")


if __name__ == "__main__":
    main()
