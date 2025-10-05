#!/usr/bin/env python3
"""
Agent 可视化评估脚本 - 基于现有训练基础设施
"""

import os
import sys
import json
import torch
import pandas as pd
from PIL import Image
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt

# 添加项目路径
sys.path.append('/app/xiaominl/DeepEyes')

def load_and_visualize_data(data_file: str, num_samples: int = 3, output_dir: str = "eval_visual"):
    """加载数据并可视化"""
    
    print(f"🎯 Agent 可视化评估")
    print(f"📁 数据文件: {data_file}")
    print(f"📊 样本数量: {num_samples}")
    
    # 创建输出目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    full_output_dir = f"{output_dir}/eval_{timestamp}"
    Path(full_output_dir).mkdir(parents=True, exist_ok=True)
    
    # 检查文件是否存在
    if not os.path.exists(data_file):
        print(f"❌ 数据文件不存在: {data_file}")
        return
    
    try:
        # 读取parquet文件
        df = pd.read_parquet(data_file)
        print(f"📊 数据文件包含 {len(df)} 个样本")
        
        # 取前num_samples个样本
        df = df.head(num_samples)
        
        # 处理每个样本
        for idx, row in df.iterrows():
            print(f"\n{'='*50}")
            print(f"🔍 处理样本 {idx}")
            
            # 提取基本信息
            conversations = row.get('conversations', [])
            images = row.get('images', [])
            env_name = row.get('env_name', '')
            
            print(f"📋 env_name: {env_name}")
            print(f"🖼️  图像数量: {len(images)}")
            print(f"💬 对话数量: {len(conversations)}")
            
            # 创建样本目录
            sample_dir = Path(full_output_dir) / f"sample_{idx:02d}"
            sample_dir.mkdir(exist_ok=True)
            
            # 保存原始图像
            if images:
                for img_idx, img_data in enumerate(images):
                    try:
                        if isinstance(img_data, dict) and 'bytes' in img_data:
                            # 字典格式 {'bytes': PNG字节数据}
                            import io
                            img_bytes = img_data['bytes']
                            pil_image = Image.open(io.BytesIO(img_bytes)).convert('RGB')
                            print(f"📷 图像 {img_idx}: {pil_image.size} (从字典bytes解析)")
                        elif isinstance(img_data, str):
                            # Base64编码的图像
                            import base64
                            import io
                            img_bytes = base64.b64decode(img_data)
                            pil_image = Image.open(io.BytesIO(img_bytes)).convert('RGB')
                            print(f"📷 图像 {img_idx}: {pil_image.size} (从base64解析)")
                        elif isinstance(img_data, bytes):
                            # 直接的字节数据
                            import io
                            pil_image = Image.open(io.BytesIO(img_data)).convert('RGB')
                            print(f"📷 图像 {img_idx}: {pil_image.size} (从bytes解析)")
                        else:
                            # 已经是PIL图像
                            pil_image = img_data
                            print(f"📷 图像 {img_idx}: {pil_image.size} (PIL图像)")
                        
                        # 保存原始图像
                        img_path = sample_dir / f"original_image_{img_idx:02d}.png"
                        pil_image.save(img_path)
                        print(f"💾 保存原始图像: {img_path}")
                        
                    except Exception as e:
                        print(f"❌ 处理图像 {img_idx} 时出错: {e}")
                        print(f"   图像数据类型: {type(img_data)}")
                        if isinstance(img_data, dict):
                            print(f"   字典键: {list(img_data.keys())}")
            
            # 保存对话信息
            if conversations:
                conversations_file = sample_dir / "conversations.json"
                with open(conversations_file, 'w', encoding='utf-8') as f:
                    json.dump(conversations, f, indent=2, ensure_ascii=False)
                print(f"💾 保存对话: {conversations_file}")
                
                # 提取并显示用户输入
                user_messages = [conv for conv in conversations if conv.get('from') == 'user']
                if user_messages:
                    user_input = user_messages[0].get('value', '')
                    print(f"👤 用户输入: {user_input[:200]}...")
            
            # 保存样本信息摘要
            sample_info = {
                'sample_idx': idx,
                'env_name': env_name,
                'num_images': len(images),
                'num_conversations': len(conversations),
                'image_sizes': [img.size if hasattr(img, 'size') else 'unknown' for img in images] if images else [],
                'user_input': user_messages[0].get('value', '') if conversations and user_messages else ''
            }
            
            info_file = sample_dir / "sample_info.json"
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(sample_info, f, indent=2, ensure_ascii=False)
            print(f"📋 保存样本信息: {info_file}")
        
        # 创建总体摘要
        summary = {
            'total_samples': len(df),
            'timestamp': timestamp,
            'data_file': data_file,
            'output_dir': full_output_dir,
            'env_names': df['env_name'].value_counts().to_dict() if 'env_name' in df.columns else {},
            'avg_images_per_sample': df['images'].apply(len).mean() if 'images' in df.columns else 0
        }
        
        summary_file = Path(full_output_dir) / "summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ 可视化评估完成！")
        print(f"📁 结果保存在: {full_output_dir}")
        print(f"📊 总结信息: {summary_file}")
        
        return full_output_dir
        
    except Exception as e:
        print(f"❌ 加载数据时出错: {e}")
        import traceback
        traceback.print_exc()

def create_evaluation_script():
    """创建评估脚本模板"""
    
    script_content = '''#!/bin/bash
# Agent 评估脚本

export PYTHONPATH=/app/xiaominl/DeepEyes:$PYTHONPATH

# 设置参数
MODEL_PATH="/app/models/Qwen2.5-VL-7B-Instruct"
DATA_FILE="/app/xiaominl/shard-000003.parquet"
OUTPUT_DIR="eval_results"
NUM_SAMPLES=5

echo "🎯 开始 Agent 可视化评估"
echo "📁 模型路径: $MODEL_PATH"
echo "📁 数据文件: $DATA_FILE"
echo "📊 样本数量: $NUM_SAMPLES"

# 运行评估
python3 eval_agent_visual.py \\
    --model_path "$MODEL_PATH" \\
    --data_file "$DATA_FILE" \\
    --output_dir "$OUTPUT_DIR" \\
    --num_samples $NUM_SAMPLES

echo "✅ 评估完成！"
echo "📁 查看结果: $OUTPUT_DIR"
'''
    
    script_path = Path("eval_agent.sh")
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    # 设置执行权限
    os.chmod(script_path, 0o755)
    print(f"📝 创建评估脚本: {script_path}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent 可视化评估")
    parser.add_argument("--model_path", default="/app/models/Qwen2.5-VL-7B-Instruct", help="模型路径")
    parser.add_argument("--data_file", default="/app/xiaominl/shard-000003.parquet", help="数据文件路径")
    parser.add_argument("--output_dir", default="eval_results", help="输出目录")
    parser.add_argument("--num_samples", type=int, default=3, help="评估样本数量")
    
    args = parser.parse_args()
    
    print(f"🎯 Agent 可视化评估")
    print(f"📁 模型: {args.model_path}")
    print(f"📁 数据: {args.data_file}")
    print(f"📊 样本: {args.num_samples}")
    print(f"📁 输出: {args.output_dir}")
    
    # 运行可视化评估
    result_dir = load_and_visualize_data(
        data_file=args.data_file,
        num_samples=args.num_samples,
        output_dir=args.output_dir
    )
    
    if result_dir:
        print(f"\n🎉 评估完成！")
        print(f"📁 结果目录: {result_dir}")
        print(f"💡 提示：")
        print(f"   - 查看 sample_XX/original_image_XX.png 看原始图像")
        print(f"   - 查看 sample_XX/conversations.json 看对话内容")
        print(f"   - 查看 sample_XX/sample_info.json 看样本信息")
        
        # 创建评估脚本
        create_evaluation_script()
    else:
        print(f"❌ 评估失败")
