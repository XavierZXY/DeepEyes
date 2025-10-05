
#!/usr/bin/env python3
"""
基于parallel_env的Agent评估脚本 - 重用训练时的工具调用逻辑
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
from verl.workers.agent.parallel_env_v2 import ParallelEnv, _parse_model_output_for_tools, _create_tools_from_parsed_output
from verl import DataProto

class AgentStepByStepEvaluator:
    """基于parallel_env的逐步评估器"""
    
    def __init__(self, model_path: str, output_dir: str = "agent_step_eval"):
        self.model_path = model_path
        self.tokenizer = hf_tokenizer(model_path)
        self.processor = hf_processor(model_path)
        
        # 创建输出目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = Path(output_dir) / f"eval_{timestamp}"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"🎯 Agent逐步评估器初始化")
        print(f"📁 输出目录: {self.output_dir}")
        
        # 导入所有工具模块以注册工具
        self._import_all_tools()
    
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
    
    def simulate_model_response(self, step: int, env_name: str, images: list):
        """模拟模型响应（实际使用时替换为真实的VLLM调用）"""
        
        # 根据环境名称模拟不同的响应
        if step == 0:
            # 第一轮：识别问题
            if "low resolution" in env_name:
                return '<think>{"reasoning":"The image appears to have low resolution with pixelated details.","diagnosis":{"label":"low resolution"},"pass":false}</think><tool_call>[{"name":"swinir_super_resolution","arguments":{"scale":4}}]</tool_call>'
            elif "haze" in env_name:
                return '<think>{"reasoning":"The image shows hazy appearance with reduced contrast.","diagnosis":{"label":"haze"},"pass":false}</think><tool_call>[{"name":"dehazeformer_dehaze","arguments":{"strength":0.7}}]</tool_call>'
            elif "defocus blur" in env_name:
                return '<think>{"reasoning":"The image exhibits defocus blur with soft edges.","diagnosis":{"label":"defocus blur"},"pass":false}</think><tool_call>[{"name":"drbnet_defocus_deblurring","arguments":{"radius":3}}]</tool_call>'
            elif "noise" in env_name:
                return '<think>{"reasoning":"The image contains visible noise artifacts.","diagnosis":{"label":"noise"},"pass":false}</think><tool_call>[{"name":"swinir_denoising","arguments":{"noise":25}}]</tool_call>'
            else:
                return '<think>{"reasoning":"The image appears clean without significant degradations.","diagnosis":{"label":"clean"},"pass":true}</think><answer>{"status":"success","restoration_log":[]}</answer>'
        else:
            # 后续轮次：通常结束
            return '<think>{"reasoning":"After processing, the image quality has been improved and no further degradations are detected.","diagnosis":{"label":"clean"},"pass":true}</think><answer>{"status":"success","restoration_log":["' + env_name.split(',')[0].strip() + '"]}</answer>'
    
    def evaluate_sample_step_by_step(self, sample_data: dict, sample_idx: int, max_turns: int = 6):
        """逐步评估样本"""
        
        print(f"\n{'='*60}")
        print(f"🎯 评估样本 {sample_idx}: {sample_data['env_name']}")
        print(f"{'='*60}")
        
        # 创建样本目录
        sample_dir = self.output_dir / f"sample_{sample_idx:02d}"
        sample_dir.mkdir(exist_ok=True)
        
        # 保存原始数据
        self._save_original_data(sample_data, sample_dir)
        
        # 初始化环境
        class MockAgentConfig:
            def __init__(self):
                self.tool_name_key = 'env_name'
                self.concurrent_workers = 1
                self.show_tqdm = True
        
        agent_config = MockAgentConfig()
        env = ParallelEnv(agent_config, self.tokenizer, self.processor)
        
        # 准备初始数据
        images = sample_data['images']
        conversations = sample_data['conversations']
        env_name = sample_data['env_name']
        
        # 模拟prompts数据
        mock_prompt_data = DataProto.from_dict(
            tensors={
                'input_ids': torch.zeros(1, 100, dtype=torch.long),
                'attention_mask': torch.ones(1, 100, dtype=torch.long)
            },
            non_tensors={
                'env_name': [env_name],
                'raw_prompt': [conversations],
                'origin_multi_modal_data': [{'image': images}] if images else [{}]
            }
        )
        
        # 模拟vllm_inputs
        vllm_inputs = [{
            'prompt_token_ids': list(range(100)),
            'multi_modal_data': {'image': images} if images else {}
        }]
        
        # 重置环境
        env.reset([mock_prompt_data], vllm_inputs, n=1)
        
        # 逐步执行
        step_results = []
        current_images = deepcopy(images)
        
        for step in range(max_turns):
            print(f"\n🔄 第 {step + 1} 轮")
            
            # 保存当前轮次前的图像
            self._save_step_images(current_images, sample_dir, step, "before")
            
            # 模拟模型响应
            model_response = self.simulate_model_response(step, env_name, current_images)
            print(f"🤖 模型响应: {model_response[:100]}...")
            
            # 保存模型响应
            response_file = sample_dir / f"step_{step + 1:02d}_response.txt"
            with open(response_file, 'w', encoding='utf-8') as f:
                f.write(model_response)
            
            # 解析模型输出
            parsed_output = _parse_model_output_for_tools(model_response, f"eval-step{step+1}")
            
            # 保存解析结果
            parse_file = sample_dir / f"step_{step + 1:02d}_parsed.json"
            with open(parse_file, 'w', encoding='utf-8') as f:
                json.dump(parsed_output, f, indent=2, ensure_ascii=False)
            
            # 检查是否结束
            if parsed_output.get('is_done', False):
                print(f"🏁 任务完成: {parsed_output.get('answer', 'success')}")
                step_results.append({
                    'step': step + 1,
                    'type': 'answer',
                    'content': parsed_output.get('answer'),
                    'done': True
                })
                break
            
            # 创建工具
            if parsed_output['tool_calls']:
                print(f"🔧 创建 {len(parsed_output['tool_calls'])} 个工具")
                
                tools = _create_tools_from_parsed_output(
                    parsed_output,
                    multi_modal_data={'image': current_images},
                    origin_multi_modal_data={'image': images},
                    raw_prompt=conversations,
                    turn_info=f"eval-step{step+1}"
                )
                
                # 执行工具
                tool_results = []
                for i, tool in enumerate(tools):
                    if tool is not None:
                        try:
                            tool_call = parsed_output['tool_calls'][i]
                            compatible_action_string = f"<tool_call>{json.dumps(tool_call)}</tool_call>"
                            
                            print(f"⚙️  执行工具: {tool.name}")
                            tool_result, reward, done, info = tool.execute(compatible_action_string)
                            
                            tool_results.append({
                                'tool_name': tool.name,
                                'reward': reward,
                                'done': done,
                                'status': info.get('status', 'unknown')
                            })
                            
                            # 如果工具返回了新图像，更新当前图像
                            if isinstance(tool_result, dict) and 'multi_modal_data' in tool_result:
                                if 'image' in tool_result['multi_modal_data']:
                                    new_images = tool_result['multi_modal_data']['image']
                                    current_images.extend(new_images)
                                    print(f"📷 工具返回 {len(new_images)} 张新图像")
                            
                        except Exception as e:
                            print(f"❌ 工具执行失败: {e}")
                            tool_results.append({
                                'tool_name': tool.name if tool else 'unknown',
                                'error': str(e),
                                'status': 'failed'
                            })
                
                step_results.append({
                    'step': step + 1,
                    'type': 'tool_call',
                    'tools': tool_results,
                    'parsed_output': parsed_output
                })
            
            # 保存当前轮次后的图像
            self._save_step_images(current_images, sample_dir, step, "after")
            
            print(f"✅ 第 {step + 1} 轮完成")
        
        # 保存完整的步骤结果
        results_file = sample_dir / "step_results.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(step_results, f, indent=2, ensure_ascii=False)
        
        print(f"📊 保存步骤结果: {results_file}")
        
        # 创建可视化摘要
        self._create_sample_summary(sample_data, step_results, sample_dir)
        
        return step_results
    
    def _save_original_data(self, sample_data: dict, sample_dir: Path):
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
            print(f"💾 保存原始图像: {img_path}")
        
        # 保存对话
        if sample_data['conversations']:
            with open(sample_dir / "conversations.json", 'w', encoding='utf-8') as f:
                json.dump(sample_data['conversations'], f, indent=2, ensure_ascii=False)
    
    def _save_step_images(self, images: list, sample_dir: Path, step: int, stage: str):
        """保存步骤图像"""
        if not images:
            return
        
        step_dir = sample_dir / f"step_{step + 1:02d}_{stage}"
        step_dir.mkdir(exist_ok=True)
        
        for img_idx, img in enumerate(images):
            if isinstance(img, Image.Image):
                img_path = step_dir / f"image_{img_idx:02d}.png"
                img.save(img_path)
                # print(f"💾 保存图像: step_{step + 1:02d}_{stage}/image_{img_idx:02d}.png")
    
    def _create_sample_summary(self, sample_data: dict, step_results: list, sample_dir: Path):
        """创建样本摘要"""
        
        summary_html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Agent评估 - 样本 {sample_dir.name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #f0f8ff; padding: 15px; border-radius: 5px; }}
        .step {{ border: 1px solid #ddd; margin: 15px 0; padding: 15px; border-radius: 5px; }}
        .images {{ display: flex; flex-wrap: wrap; gap: 10px; }}
        .image-container {{ text-align: center; }}
        img {{ max-width: 200px; max-height: 200px; border: 1px solid #ccc; }}
        .action {{ background: #e7f3ff; padding: 10px; margin: 5px 0; border-radius: 3px; }}
        .tool-result {{ background: #f0fff0; padding: 10px; margin: 5px 0; border-radius: 3px; }}
        .error {{ background: #ffe7e7; padding: 10px; margin: 5px 0; border-radius: 3px; }}
        pre {{ white-space: pre-wrap; word-wrap: break-word; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 Agent评估结果</h1>
        <p><strong>环境名称:</strong> {sample_data['env_name']}</p>
        <p><strong>数据源:</strong> {sample_data['data_source']}</p>
        <p><strong>原始图像数量:</strong> {len(sample_data['images'])}</p>
        <p><strong>评估时间:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <div class="step">
        <h2>📷 原始图像</h2>
        <div class="images">
"""
        
        # 添加原始图像
        for img_idx in range(len(sample_data['images'])):
            summary_html += f'''
            <div class="image-container">
                <img src="original_image_{img_idx:02d}.png" alt="原始图像 {img_idx}">
                <p>原始图像 {img_idx + 1}</p>
            </div>
'''
        
        summary_html += """
        </div>
    </div>
"""
        
        # 添加每一步的结果
        for step_result in step_results:
            step_num = step_result['step']
            summary_html += f'''
    <div class="step">
        <h2>🔄 第 {step_num} 轮</h2>
'''
            
            if step_result['type'] == 'tool_call':
                # 工具调用步骤
                summary_html += f'''
        <div class="action">
            <h3>🤖 模型响应</h3>
            <p>检测到工具调用: {len(step_result.get("tools", []))} 个工具</p>
        </div>
'''
                
                # 显示工具执行结果
                for tool_result in step_result.get('tools', []):
                    if tool_result.get('status') == 'success':
                        css_class = 'tool-result'
                        icon = '✅'
                    else:
                        css_class = 'error'
                        icon = '❌'
                    
                    summary_html += f'''
        <div class="{css_class}">
            <h4>{icon} 工具: {tool_result.get("tool_name", "unknown")}</h4>
            <p>状态: {tool_result.get("status", "unknown")}</p>
            <p>奖励: {tool_result.get("reward", 0)}</p>
        </div>
'''
                
                # 显示处理后的图像
                step_after_dir = f"step_{step_num:02d}_after"
                if (sample_dir / step_after_dir).exists():
                    summary_html += f'''
        <h3>📷 处理后图像</h3>
        <div class="images">
'''
                    for img_file in sorted((sample_dir / step_after_dir).glob("*.png")):
                        img_name = img_file.name
                        summary_html += f'''
            <div class="image-container">
                <img src="{step_after_dir}/{img_name}" alt="{img_name}">
                <p>{img_name}</p>
            </div>
'''
                    summary_html += '</div>'
            
            elif step_result['type'] == 'answer':
                # 最终答案
                summary_html += f'''
        <div class="tool-result">
            <h3>🏁 最终答案</h3>
            <p>任务完成: {step_result.get("content", "success")}</p>
        </div>
'''
            
            summary_html += '</div>'
        
        summary_html += """
</body>
</html>
"""
        
        # 保存HTML摘要
        summary_file = sample_dir / "summary.html"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(summary_html)
        
        print(f"📋 创建HTML摘要: {summary_file}")
        print(f"💡 用浏览器打开查看: file://{summary_file.absolute()}")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent逐步评估")
    parser.add_argument("--model_path", default="/app/models/Qwen2.5-VL-7B-Instruct", help="模型路径")
    parser.add_argument("--data_file", default="/app/datasets/IRdataset/shard-000003.parquet", help="数据文件")
    parser.add_argument("--output_dir", default="agent_step_eval", help="输出目录")
    parser.add_argument("--num_samples", type=int, default=3, help="评估样本数量")
    parser.add_argument("--max_turns", type=int, default=6, help="最大轮次")
    
    args = parser.parse_args()
    
    print(f"🎯 Agent逐步评估")
    print(f"🤖 模型: {args.model_path}")
    print(f"📁 数据: {args.data_file}")
    print(f"📊 样本: {args.num_samples}")
    print(f"🔄 最大轮次: {args.max_turns}")
    
    try:
        # 创建评估器
        evaluator = AgentStepByStepEvaluator(args.model_path, args.output_dir)
        
        # 评估每个样本
        all_results = []
        for i in range(args.num_samples):
            try:
                # 加载样本
                sample_data = evaluator.load_sample_data(args.data_file, i)
                
                # 逐步评估
                step_results = evaluator.evaluate_sample_step_by_step(
                    sample_data, i, args.max_turns
                )
                
                all_results.append({
                    'sample_idx': i,
                    'env_name': sample_data['env_name'],
                    'num_steps': len(step_results),
                    'completed': any(r.get('done', False) for r in step_results)
                })
                
                print(f"✅ 样本 {i} 评估完成")
                
            except Exception as e:
                print(f"❌ 样本 {i} 评估失败: {e}")
                all_results.append({
                    'sample_idx': i,
                    'error': str(e)
                })
        
        # 保存总体结果
        overall_results = {
            'evaluation_time': datetime.now().isoformat(),
            'model_path': args.model_path,
            'data_file': args.data_file,
            'num_samples': args.num_samples,
            'results': all_results
        }
        
        results_file = evaluator.output_dir / "overall_results.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(overall_results, f, indent=2, ensure_ascii=False)
        
        print(f"\n🎉 所有样本评估完成！")
        print(f"📁 结果目录: {evaluator.output_dir}")
        print(f"📊 总体结果: {results_file}")
        print(f"🖼️  查看各个样本目录中的 summary.html")
        
        # 统计结果
        successful_samples = sum(1 for r in all_results if r.get('completed', False))
        print(f"📈 成功完成: {successful_samples}/{len(all_results)} 个样本")
        
    except Exception as e:
        print(f"❌ 评估过程出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()