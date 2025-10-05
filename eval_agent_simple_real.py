#!/usr/bin/env python3
"""
简化的Agent评估脚本 - 基于退化类型直接测试工具调用效果
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
from verl.workers.agent.parallel_env_v2 import ParallelEnv, _create_tools_from_parsed_output
from verl import DataProto

class SimpleAgentEvaluator:
    """简化Agent评估器 - 直接基于退化类型测试工具效果"""
    
    def __init__(self, model_path: str, output_dir: str = "simple_agent_eval"):
        self.model_path = model_path
        self.tokenizer = hf_tokenizer(model_path)
        self.processor = hf_processor(model_path)
        
        # 创建输出目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = Path(output_dir) / f"eval_{timestamp}"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"🎯 简化Agent评估器初始化")
        print(f"📁 输出目录: {self.output_dir}")
        
        # 导入工具模块
        self._import_all_tools()
        
        # 定义退化类型到工具的映射
        self.degradation_to_tools = {
            "low resolution": [{"name": "swinir_super_resolution", "arguments": {"scale": 4}}],
            "noise": [{"name": "swinir_denoising", "arguments": {"strength": 0.5}}],
            "haze": [{"name": "dehazeformer_dehaze", "arguments": {"strength": 0.7}}],
            "defocus blur": [{"name": "drbnet_defocus_deblurring", "arguments": {"radius": 3}}],
            "motion blur": [{"name": "xrestormer_motion_deblurring", "arguments": {"strength": 0.8}}],
            "dark": [{"name": "histogram_equalization", "arguments": {"mode": "clahe"}}],
            "jpeg compression artifact": [{"name": "swinir_jpeg_artifact_removal", "arguments": {"strength": 0.7}}],
            "rain": [{"name": "xrestormer_motion_deblurring", "arguments": {"strength": 0.8}}],
            # 组合退化类型
            "noise, motion blur": [
                {"name": "swinir_denoising", "arguments": {"strength": 0.5}},
                {"name": "xrestormer_motion_deblurring", "arguments": {"strength": 0.8}}
            ],
            "low resolution, dark": [
                {"name": "swinir_super_resolution", "arguments": {"scale": 4}},
                {"name": "histogram_equalization", "arguments": {"mode": "clahe"}}
            ]
        }
    
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
    
    def get_tools_for_degradation(self, env_name: str):
        """根据退化类型获取对应的工具调用"""
        
        # 直接查找匹配的退化类型
        if env_name in self.degradation_to_tools:
            return self.degradation_to_tools[env_name]
        
        # 如果没有直接匹配，尝试部分匹配
        for degradation, tools in self.degradation_to_tools.items():
            if degradation in env_name or any(d.strip() in env_name for d in degradation.split(',')):
                return tools
        
        # 如果都没匹配，返回空（表示clean）
        print(f"⚠️  未找到匹配的退化类型: {env_name}")
        return []
    
    def evaluate_sample(self, sample_data: dict, sample_idx: int):
        """评估单个样本"""
        
        print(f"\n{'='*60}")
        print(f"🎯 评估样本 {sample_idx}: {sample_data['env_name']}")
        print(f"{'='*60}")
        
        # 创建样本目录
        sample_dir = self.output_dir / f"sample_{sample_idx:02d}"
        sample_dir.mkdir(exist_ok=True)
        
        # 保存原始数据
        self._save_original_data(sample_data, sample_dir)
        
        # 获取需要使用的工具
        tool_calls = self.get_tools_for_degradation(sample_data['env_name'])
        
        if not tool_calls:
            print(f"🎯 图像被认为是clean，无需处理")
            self._save_clean_result(sample_dir)
            return {'status': 'clean', 'steps': 0}
        
        print(f"🔧 计划执行 {len(tool_calls)} 个工具: {[tc['name'] for tc in tool_calls]}")
        
        # 初始化环境
        class MockAgentConfig:
            def __init__(self):
                self.tool_name_key = 'env_name'
                self.concurrent_workers = 1
                self.show_tqdm = False
        
        agent_config = MockAgentConfig()
        env = ParallelEnv(agent_config, self.tokenizer, self.processor)
        
        # 准备初始数据
        images = sample_data['images']
        conversations = sample_data['conversations']
        
        # 模拟prompt数据
        mock_prompt_data = DataProto.from_dict(
            tensors={
                'input_ids': torch.zeros(1, 100, dtype=torch.long),
                'attention_mask': torch.ones(1, 100, dtype=torch.long)
            },
            non_tensors={
                'env_name': [sample_data['env_name']],
                'raw_prompt': [conversations],
                'origin_multi_modal_data': [{'image': images}] if images else [{}]
            }
        )
        
        vllm_inputs = [{
            'prompt_token_ids': list(range(100)),
            'multi_modal_data': {'image': images} if images else {}
        }]
        
        # 重置环境
        env.reset([mock_prompt_data], vllm_inputs, n=1)
        
        # 逐步执行工具
        step_results = []
        current_images = deepcopy(images)
        
        for step, tool_call in enumerate(tool_calls):
            print(f"\n🔄 第 {step + 1} 步: {tool_call['name']}")
            
            # 保存处理前的图像
            self._save_step_images(current_images, sample_dir, step, "before")
            
            # 创建模拟的parsed_output
            parsed_output = {
                'think': {
                    'diagnosis': {'labels': [sample_data['env_name'].split(',')[0].strip()]},
                    'pass': False
                },
                'tool_calls': [tool_call],
                'answer': None,
                'is_done': False
            }
            
            # 创建工具
            tools = _create_tools_from_parsed_output(
                parsed_output,
                multi_modal_data={'image': current_images},
                origin_multi_modal_data={'image': images},
                raw_prompt=conversations,
                turn_info=f"eval-step{step+1}"
            )
            
            # 执行工具
            tool_executed = False
            for tool in tools:
                if tool is not None:
                    try:
                        compatible_action_string = f"<tool_call>{json.dumps(tool_call)}</tool_call>"
                        
                        print(f"⚙️  执行工具: {tool.name}")
                        print(f"🖼️  输入图像尺寸: {[img.size for img in current_images]}")
                        
                        tool_result, reward, done, info = tool.execute(compatible_action_string)
                        
                        step_result = {
                            'step': step + 1,
                            'tool_name': tool.name,
                            'tool_call': tool_call,
                            'reward': reward,
                            'status': info.get('status', 'unknown'),
                            'execution_time': info.get('execution_time', 0)
                        }
                        
                        # 检查是否有新图像
                        if isinstance(tool_result, dict) and 'multi_modal_data' in tool_result:
                            if 'image' in tool_result['multi_modal_data']:
                                new_images = tool_result['multi_modal_data']['image']
                                print(f"🖼️  输出图像尺寸: {[img.size for img in new_images]}")
                                
                                # 更新当前图像为最新处理的图像
                                current_images = new_images  # ← 关键：使用最新图像！
                                step_result['output_image_sizes'] = [img.size for img in new_images]
                                tool_executed = True
                        
                        step_results.append(step_result)
                        
                        if info.get('status') == 'success':
                            print(f"✅ 工具 {tool.name} 执行成功 (耗时: {info.get('execution_time', 0):.2f}s)")
                        else:
                            print(f"❌ 工具 {tool.name} 执行失败")
                        
                    except Exception as e:
                        print(f"❌ 工具执行错误: {e}")
                        step_results.append({
                            'step': step + 1,
                            'tool_name': tool.name if tool else 'unknown',
                            'error': str(e),
                            'status': 'failed'
                        })
            
            # 保存处理后的图像
            if tool_executed:
                self._save_step_images(current_images, sample_dir, step, "after")
            
            # 保存步骤信息
            step_file = sample_dir / f"step_{step + 1:02d}_info.json"
            with open(step_file, 'w', encoding='utf-8') as f:
                json.dump(step_results[-1] if step_results else {}, f, indent=2, ensure_ascii=False)
        
        # 保存完整结果
        final_result = {
            'env_name': sample_data['env_name'],
            'original_image_sizes': [img.size for img in images],
            'final_image_sizes': [img.size for img in current_images],
            'steps_executed': len(step_results),
            'tools_used': [sr['tool_name'] for sr in step_results if 'tool_name' in sr],
            'total_execution_time': sum(sr.get('execution_time', 0) for sr in step_results),
            'all_successful': all(sr.get('status') == 'success' for sr in step_results),
            'step_details': step_results
        }
        
        with open(sample_dir / "evaluation_result.json", 'w', encoding='utf-8') as f:
            json.dump(final_result, f, indent=2, ensure_ascii=False)
        
        # 创建简单的HTML报告
        self._create_simple_html_report(sample_data, final_result, sample_dir)
        
        print(f"📊 样本 {sample_idx} 评估完成")
        print(f"🔧 执行了 {len(step_results)} 个工具")
        print(f"⏱️  总耗时: {final_result['total_execution_time']:.2f}s")
        
        return final_result
    
    def _save_original_data(self, sample_data: dict, sample_dir: Path):
        """保存原始数据"""
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
            img_path = sample_dir / f"step_00_original_{img_idx:02d}.png"
            img.save(img_path)
            print(f"💾 原始图像: {img_path}")
    
    def _save_step_images(self, images: list, sample_dir: Path, step: int, stage: str):
        """保存步骤图像"""
        if not images:
            return
        
        for img_idx, img in enumerate(images):
            if isinstance(img, Image.Image):
                img_path = sample_dir / f"step_{step + 1:02d}_{stage}_{img_idx:02d}.png"
                img.save(img_path)
                print(f"💾 {stage}图像: step_{step + 1:02d}_{stage}_{img_idx:02d}.png")
    
    def _save_clean_result(self, sample_dir: Path):
        """保存clean结果"""
        clean_result = {
            'status': 'clean',
            'message': 'Image is already clean, no processing needed',
            'steps': 0
        }
        
        with open(sample_dir / "evaluation_result.json", 'w') as f:
            json.dump(clean_result, f, indent=2)
        
        print(f"✅ 图像标记为clean，无需处理")
    
    def _create_simple_html_report(self, sample_data: dict, result: dict, sample_dir: Path):
        """创建简单的HTML报告"""
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Agent评估 - {sample_data['env_name']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #f0f8ff; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .step {{ border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }}
        .images {{ display: flex; flex-wrap: wrap; gap: 15px; margin: 10px 0; }}
        .image-container {{ text-align: center; border: 1px solid #eee; padding: 10px; border-radius: 5px; }}
        img {{ max-width: 250px; max-height: 250px; }}
        .success {{ background: #f0fff0; }}
        .failed {{ background: #ffe7e7; }}
        .stats {{ background: #f5f5f5; padding: 10px; border-radius: 3px; margin: 10px 0; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 Agent评估结果</h1>
        <p><strong>退化类型:</strong> {sample_data['env_name']}</p>
        <p><strong>执行工具:</strong> {', '.join(result.get('tools_used', []))}</p>
        <p><strong>总耗时:</strong> {result.get('total_execution_time', 0):.2f}秒</p>
        <p><strong>成功率:</strong> {'✅ 全部成功' if result.get('all_successful') else '❌ 有失败'}</p>
    </div>
    
    <div class="step">
        <h2>📷 图像处理过程</h2>
        <div class="images">
            <div class="image-container">
                <img src="step_00_original_00.png" alt="原始图像">
                <p><strong>原始图像</strong><br>{result.get('original_image_sizes', ['unknown'])[0]}</p>
            </div>
"""
        
        # 添加每一步的处理结果
        for step_detail in result.get('step_details', []):
            step_num = step_detail['step']
            tool_name = step_detail.get('tool_name', 'unknown')
            status = step_detail.get('status', 'unknown')
            
            css_class = 'success' if status == 'success' else 'failed'
            
            html_content += f'''
            <div class="image-container {css_class}">
                <img src="step_{step_num:02d}_after_00.png" alt="第{step_num}步处理后">
                <p><strong>第{step_num}步: {tool_name}</strong><br>
                状态: {status}<br>
                尺寸: {step_detail.get('output_image_sizes', ['unknown'])[0] if step_detail.get('output_image_sizes') else 'unknown'}</p>
            </div>
'''
        
        html_content += """
        </div>
    </div>
    
    <div class="stats">
        <h3>📊 详细统计</h3>
        <ul>
"""
        
        for step_detail in result.get('step_details', []):
            execution_time = step_detail.get('execution_time', 0)
            html_content += f"<li>第{step_detail['step']}步 - {step_detail.get('tool_name', 'unknown')}: {execution_time:.2f}秒</li>"
        
        html_content += """
        </ul>
    </div>
</body>
</html>
"""
        
        summary_file = sample_dir / "report.html"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"📋 HTML报告: {summary_file}")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="简化Agent评估")
    parser.add_argument("--model_path", default="/app/models/Qwen2.5-VL-7B-Instruct", help="模型路径（用于tokenizer）")
    parser.add_argument("--data_file", default="/app/datasets/IRdataset/shard-000003.parquet", help="测试数据文件")
    parser.add_argument("--output_dir", default="simple_agent_eval", help="输出目录")
    parser.add_argument("--num_samples", type=int, default=5, help="评估样本数量")
    parser.add_argument("--start_idx", type=int, default=0, help="起始样本索引")
    
    args = parser.parse_args()
    
    print(f"🎯 简化Agent评估")
    print(f"📁 数据: {args.data_file}")
    print(f"📊 样本: {args.num_samples} (从索引 {args.start_idx} 开始)")
    print(f"📁 输出: {args.output_dir}")
    
    try:
        # 创建评估器
        evaluator = SimpleAgentEvaluator(args.model_path, args.output_dir)
        
        # 评估样本
        all_results = []
        successful_count = 0
        
        for i in range(args.start_idx, args.start_idx + args.num_samples):
            try:
                # 加载样本
                sample_data = evaluator.load_sample_data(args.data_file, i)
                
                # 评估
                result = evaluator.evaluate_sample(sample_data, i)
                
                all_results.append(result)
                
                if result.get('status') == 'clean' or result.get('all_successful', False):
                    successful_count += 1
                
            except Exception as e:
                print(f"❌ 样本 {i} 失败: {e}")
                all_results.append({'sample_idx': i, 'error': str(e)})
        
        # 保存总体统计
        summary = {
            'evaluation_time': datetime.now().isoformat(),
            'data_file': args.data_file,
            'num_samples': len(all_results),
            'successful_samples': successful_count,
            'success_rate': successful_count / len(all_results) if all_results else 0,
            'results': all_results
        }
        
        summary_file = evaluator.output_dir / "evaluation_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"\n🎉 评估完成！")
        print(f"📁 结果目录: {evaluator.output_dir}")
        print(f"📈 成功率: {successful_count}/{len(all_results)} ({summary['success_rate']:.2%})")
        print(f"📊 详细摘要: {summary_file}")
        print(f"🖼️  查看各样本的 report.html 了解详细过程")
        
    except Exception as e:
        print(f"❌ 评估失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
