#!/usr/bin/env python3
"""
简化的 Agent 评估脚本 - 查看训练数据格式和保存图像
"""

import os
import sys
import json
import pandas as pd
from PIL import Image
from pathlib import Path
from datetime import datetime
import base64
import io

# 添加项目路径
sys.path.append('/app/xiaominl/DeepEyes')

def analyze_training_data(data_file: str, num_samples: int = 3, output_dir: str = "eval_analysis"):
    """分析训练数据格式并保存图像"""
    
    print(f"🎯 分析训练数据格式")
    print(f"📁 数据文件: {data_file}")
    
    # 检查文件是否存在
    if not os.path.exists(data_file):
        print(f"❌ 数据文件不存在: {data_file}")
        return
    
    try:
        # 读取parquet文件
        df = pd.read_parquet(data_file)
        print(f"📊 数据文件包含 {len(df)} 个样本")
        print(f"📋 列名: {list(df.columns)}")
        
        # 分析数据结构
        print(f"\n📋 数据结构分析:")
        for col in df.columns:
            print(f"  {col}: {df[col].dtype}")
            if col in ['env_name']:
                print(f"    唯一值: {df[col].unique()[:10]}")
        
        # 创建输出目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        full_output_dir = Path(output_dir) / f"analysis_{timestamp}"
        full_output_dir.mkdir(parents=True, exist_ok=True)
        
        # 处理前几个样本
        for idx in range(min(num_samples, len(df))):
            row = df.iloc[idx]
            print(f"\n{'='*50}")
            print(f"🔍 分析样本 {idx}")
            
            # 创建样本目录
            sample_dir = full_output_dir / f"sample_{idx:02d}"
            sample_dir.mkdir(exist_ok=True)
            
            # 分析各个字段
            sample_info = {}
            
            for col, value in row.items():
                print(f"📋 {col}: {type(value)}")
                
                if col == 'conversations':
                    if isinstance(value, list):
                        print(f"  对话数量: {len(value)}")
                        for i, conv in enumerate(value[:3]):  # 只显示前3个
                            print(f"    对话 {i}: from={conv.get('from', 'unknown')}")
                            content = conv.get('value', '')
                            print(f"             content={content[:100]}...")
                        
                        # 保存对话
                        conv_file = sample_dir / "conversations.json"
                        with open(conv_file, 'w', encoding='utf-8') as f:
                            json.dump(value, f, indent=2, ensure_ascii=False)
                        
                        sample_info['conversations'] = len(value)
                
                elif col == 'images':
                    if isinstance(value, list):
                        print(f"  图像数量: {len(value)}")
                        
                        # 处理图像
                        for img_idx, img_data in enumerate(value):
                            try:
                                if isinstance(img_data, str):
                                    # Base64编码
                                    img_bytes = base64.b64decode(img_data)
                                    pil_image = Image.open(io.BytesIO(img_bytes)).convert('RGB')
                                    print(f"    图像 {img_idx}: {pil_image.size} (base64)")
                                elif hasattr(img_data, 'size'):
                                    # PIL图像
                                    pil_image = img_data
                                    print(f"    图像 {img_idx}: {pil_image.size} (PIL)")
                                else:
                                    print(f"    图像 {img_idx}: 未知格式 {type(img_data)}")
                                    continue
                                
                                # 保存图像
                                img_path = sample_dir / f"image_{img_idx:02d}.png"
                                pil_image.save(img_path)
                                print(f"    💾 保存: {img_path}")
                                
                            except Exception as e:
                                print(f"    ❌ 处理图像 {img_idx} 失败: {e}")
                        
                        sample_info['images'] = len(value)
                
                elif col == 'env_name':
                    print(f"  环境名称: {value}")
                    sample_info['env_name'] = value
                
                else:
                    # 其他字段
                    if isinstance(value, (str, int, float, bool)):
                        print(f"  值: {value}")
                        sample_info[col] = value
                    else:
                        print(f"  类型: {type(value)}, 长度: {len(value) if hasattr(value, '__len__') else 'N/A'}")
                        sample_info[col] = str(type(value))
            
            # 保存样本信息
            info_file = sample_dir / "sample_info.json"
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(sample_info, f, indent=2, ensure_ascii=False)
            
            print(f"📋 样本信息保存到: {info_file}")
        
        # 创建总体摘要
        summary = {
            'timestamp': timestamp,
            'data_file': data_file,
            'total_samples': len(df),
            'analyzed_samples': min(num_samples, len(df)),
            'columns': list(df.columns),
            'env_names': df['env_name'].value_counts().to_dict() if 'env_name' in df.columns else {},
        }
        
        summary_file = full_output_dir / "summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ 分析完成！")
        print(f"📁 结果目录: {full_output_dir}")
        print(f"📋 总结文件: {summary_file}")
        
        # 打印环境名称统计
        if 'env_name' in df.columns:
            print(f"\n📊 环境名称统计:")
            env_counts = df['env_name'].value_counts()
            for env_name, count in env_counts.head(10).items():
                print(f"  {env_name}: {count} 个样本")
        
        return full_output_dir
        
    except Exception as e:
        print(f"❌ 分析数据时出错: {e}")
        import traceback
        traceback.print_exc()

def create_eval_integration():
    """创建集成到训练流程的评估代码"""
    
    integration_code = '''
# 在训练脚本中添加以下代码来启用可视化

# 1. 在导入部分添加
sys.path.append('/app/xiaominl/DeepEyes')
from eval_agent_simple import monkey_patch_for_visualization

# 2. 在训练开始前添加
viz_hook = monkey_patch_for_visualization(output_dir="training_visualization", max_samples=5)

# 3. 训练结束后
viz_hook.create_summary()
'''
    
    integration_file = Path("integration_guide.txt")
    with open(integration_file, 'w') as f:
        f.write(integration_code)
    
    print(f"📝 集成指南保存到: {integration_file}")

def monkey_patch_for_visualization(output_dir: str = "training_visualization", max_samples: int = 5):
    """为训练过程添加可视化功能"""
    
    print(f"🔧 安装训练可视化钩子")
    
    # 这里可以添加实际的monkey patch代码
    # 由于训练过程比较复杂，建议直接在parallel_env.py中添加可视化代码
    
    class TrainingVisualizationHook:
        def __init__(self, output_dir, max_samples):
            self.output_dir = output_dir
            self.max_samples = max_samples
            self.captured_samples = 0
            
            # 创建输出目录
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.full_output_dir = Path(output_dir) / f"training_viz_{timestamp}"
            self.full_output_dir.mkdir(parents=True, exist_ok=True)
            
            print(f"📁 训练可视化输出: {self.full_output_dir}")
        
        def create_summary(self):
            print(f"📋 创建训练可视化摘要...")
            # 创建摘要文件
            return self.full_output_dir
    
    return TrainingVisualizationHook(output_dir, max_samples)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent 数据分析和评估")
    parser.add_argument("--data_file", default="/app/xiaominl/shard-000003.parquet", help="数据文件路径")
    parser.add_argument("--output_dir", default="eval_analysis", help="输出目录")
    parser.add_argument("--num_samples", type=int, default=3, help="分析样本数量")
    
    args = parser.parse_args()
    
    print(f"🎯 Agent 数据分析")
    print(f"📁 数据文件: {args.data_file}")
    print(f"📊 分析样本: {args.num_samples}")
    print(f"📁 输出目录: {args.output_dir}")
    
    # 运行数据分析
    result_dir = analyze_training_data(
        data_file=args.data_file,
        num_samples=args.num_samples,
        output_dir=args.output_dir
    )
    
    if result_dir:
        print(f"\n🎉 分析完成！")
        print(f"📁 查看结果: {result_dir}")
        print(f"🖼️  原始图像已保存到各个样本目录中")
        
        # 创建集成指南
        create_eval_integration()
    else:
        print(f"❌ 分析失败")
