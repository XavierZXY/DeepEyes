#!/usr/bin/env python3
"""
实时 Agent 评估脚本 - 集成到训练流程中
可以在训练过程中保存每一步的图像处理结果
"""

import os
import sys
import json
import torch
from PIL import Image
from pathlib import Path
from datetime import datetime
import shutil

# 添加项目路径
sys.path.append('/app/xiaominl/DeepEyes')

class AgentVisualizationHook:
    """Agent 可视化钩子，集成到训练流程中"""
    
    def __init__(self, output_dir: str = "agent_visualization", max_samples: int = 5):
        self.output_dir = output_dir
        self.max_samples = max_samples
        self.sample_count = 0
        
        # 创建输出目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.full_output_dir = Path(output_dir) / f"eval_{timestamp}"
        self.full_output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"🎯 Agent 可视化钩子初始化")
        print(f"📁 输出目录: {self.full_output_dir}")
        print(f"📊 最大样本数: {max_samples}")
    
    def capture_agent_step(self, step: int, sample_idx: int, action_text: str, images: list, rewards: list):
        """捕获agent的每一步"""
        
        if self.sample_count >= self.max_samples:
            return  # 超过最大样本数，不再保存
        
        # 创建样本目录
        sample_dir = self.full_output_dir / f"sample_{sample_idx:02d}"
        sample_dir.mkdir(exist_ok=True)
        
        # 创建步骤目录
        step_dir = sample_dir / f"step_{step:02d}"
        step_dir.mkdir(exist_ok=True)
        
        # 保存动作文本
        action_file = step_dir / "action.txt"
        with open(action_file, 'w', encoding='utf-8') as f:
            f.write(action_text)
        
        # 保存图像
        if images:
            for img_idx, img in enumerate(images):
                if isinstance(img, Image.Image):
                    img_path = step_dir / f"image_{img_idx:02d}.png"
                    img.save(img_path)
                    print(f"💾 保存图像: step_{step:02d}/image_{img_idx:02d}.png")
        
        # 保存奖励信息
        if rewards:
            reward_file = step_dir / "rewards.json"
            with open(reward_file, 'w') as f:
                json.dump(rewards, f, indent=2)
        
        # 解析并保存think信息
        self._parse_and_save_think(action_text, step_dir)
        
        print(f"📸 捕获样本 {sample_idx} 步骤 {step}")
    
    def _parse_and_save_think(self, action_text: str, step_dir: Path):
        """解析并保存think信息"""
        import re
        
        # 提取think块
        think_pattern = r'<think>(.*?)</think>'
        think_match = re.search(think_pattern, action_text, re.DOTALL)
        
        if think_match:
            think_content = think_match.group(1).strip()
            think_file = step_dir / "think.json"
            
            try:
                think_data = json.loads(think_content)
                with open(think_file, 'w', encoding='utf-8') as f:
                    json.dump(think_data, f, indent=2, ensure_ascii=False)
                
                # 提取退化信息
                if isinstance(think_data, dict) and 'diagnosis' in think_data:
                    diagnosis = think_data['diagnosis']
                    if isinstance(diagnosis, dict) and 'labels' in diagnosis:
                        labels = diagnosis['labels']
                        print(f"🔍 检测到退化类型: {labels}")
                        
            except json.JSONDecodeError as e:
                # 保存原始文本
                with open(think_file, 'w', encoding='utf-8') as f:
                    f.write(think_content)
                print(f"⚠️  think块JSON解析失败，保存原始文本")
    
    def create_summary(self):
        """创建评估摘要"""
        summary_file = self.full_output_dir / "summary.html"
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Agent 评估结果</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .sample {{ border: 1px solid #ddd; margin: 20px 0; padding: 15px; }}
        .step {{ margin: 10px 0; padding: 10px; background: #f9f9f9; }}
        img {{ max-width: 300px; margin: 5px; }}
        .action {{ background: #e7f3ff; padding: 10px; margin: 5px 0; }}
        .think {{ background: #fff3cd; padding: 10px; margin: 5px 0; }}
    </style>
</head>
<body>
    <h1>🎯 Agent 评估结果</h1>
    <p>评估时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p>结果目录: {self.full_output_dir}</p>
    
    <h2>📊 样本列表</h2>
"""
        
        # 遍历样本目录
        for sample_dir in sorted(self.full_output_dir.glob("sample_*")):
            sample_name = sample_dir.name
            html_content += f'<div class="sample"><h3>{sample_name}</h3>'
            
            # 遍历步骤
            for step_dir in sorted(sample_dir.glob("step_*")):
                step_name = step_dir.name
                html_content += f'<div class="step"><h4>{step_name}</h4>'
                
                # 显示图像
                for img_file in sorted(step_dir.glob("*.png")):
                    rel_path = img_file.relative_to(self.full_output_dir)
                    html_content += f'<img src="{rel_path}" alt="{img_file.name}">'
                
                # 显示动作
                action_file = step_dir / "action.txt"
                if action_file.exists():
                    with open(action_file, 'r', encoding='utf-8') as f:
                        action_text = f.read()
                    html_content += f'<div class="action"><strong>动作:</strong><br><pre>{action_text[:500]}...</pre></div>'
                
                # 显示think
                think_file = step_dir / "think.json"
                if think_file.exists():
                    with open(think_file, 'r', encoding='utf-8') as f:
                        think_content = f.read()
                    html_content += f'<div class="think"><strong>思考:</strong><br><pre>{think_content}</pre></div>'
                
                html_content += '</div>'
            
            html_content += '</div>'
        
        html_content += """
</body>
</html>
"""
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"📋 创建HTML摘要: {summary_file}")
        print(f"💡 用浏览器打开查看: file://{summary_file.absolute()}")

def monkey_patch_parallel_env():
    """给ParallelEnv添加可视化功能"""
    from verl.workers.agent.parallel_env_v2 import ParallelEnv
    
    # 创建全局可视化钩子
    global_viz_hook = AgentVisualizationHook()
    
    # 保存原始的step方法
    original_step = ParallelEnv.step
    
    def step_with_visualization(self, active_indices, actions, current_turn=1):
        """带可视化的step方法"""
        
        # 在执行前捕获信息
        for idx, action in enumerate(actions):
            action_text = action.outputs[0].text
            sample_idx = active_indices[idx] if idx < len(active_indices) else idx
            
            # 获取当前图像（如果有）
            current_images = []
            if hasattr(self, 'multi_modal_data_list') and sample_idx < len(self.multi_modal_data_list):
                mm_data = self.multi_modal_data_list[sample_idx]
                if mm_data and 'image' in mm_data:
                    current_images = mm_data['image']
            
            # 捕获这一步
            global_viz_hook.capture_agent_step(
                step=current_turn,
                sample_idx=sample_idx,
                action_text=action_text,
                images=current_images,
                rewards=[]  # 奖励在step执行后才有
            )
        
        # 调用原始step方法
        return original_step(self, active_indices, actions, current_turn)
    
    # 替换step方法
    ParallelEnv.step = step_with_visualization
    
    print(f"🔧 已安装Agent可视化钩子")
    return global_viz_hook

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent 可视化评估")
    parser.add_argument("--model_path", default="/app/models/Qwen2.5-VL-7B-Instruct", help="模型路径")
    parser.add_argument("--data_file", default="/app/xiaominl/shard-000003.parquet", help="数据文件路径")
    parser.add_argument("--output_dir", default="eval_results", help="输出目录")
    parser.add_argument("--num_samples", type=int, default=3, help="评估样本数量")
    parser.add_argument("--mode", choices=["data_only", "full_eval"], default="data_only", help="评估模式")
    
    args = parser.parse_args()
    
    if args.mode == "data_only":
        # 只可视化数据，不运行模型
        print(f"📊 数据可视化模式")
        result_dir = load_and_visualize_data(
            data_file=args.data_file,
            num_samples=args.num_samples,
            output_dir=args.output_dir
        )
    else:
        # 完整评估模式（需要集成到训练脚本中）
        print(f"🚀 完整评估模式")
        print(f"💡 请在训练脚本开始时调用 monkey_patch_parallel_env()")
        viz_hook = monkey_patch_parallel_env()
        print(f"✅ 可视化钩子已安装，训练时会自动保存图像")
