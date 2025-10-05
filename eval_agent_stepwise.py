#!/usr/bin/env python3
"""
Agent 逐步评估脚本 - 适配实际数据格式
"""

import os
import sys
import json
import pickle
import pandas as pd
import numpy as np
from PIL import Image
from pathlib import Path
from datetime import datetime
import io

# 添加项目路径
sys.path.append('/app/xiaominl/DeepEyes')

from verl.utils import hf_tokenizer, hf_processor

def load_real_data_sample(data_file: str, sample_idx: int = 0):
    """加载真实数据样本"""
    
    print(f"📁 加载数据样本 {sample_idx}")
    
    # 读取parquet文件
    df = pd.read_parquet(data_file)
    print(f"📊 数据文件包含 {len(df)} 个样本")
    
    if sample_idx >= len(df):
        print(f"❌ 样本索引 {sample_idx} 超出范围")
        return None
    
    row = df.iloc[sample_idx]
    
    # 解析数据
    sample_data = {}
    
    # 基本信息
    sample_data['data_source'] = row['data_source']
    sample_data['ability'] = row['ability']
    sample_data['env_name'] = row['env_name']
    
    print(f"📋 环境名称: {sample_data['env_name']}")
    print(f"📋 能力类型: {sample_data['ability']}")
    
    # 解析prompt (numpy数组)
    if isinstance(row['prompt'], np.ndarray):
        prompt_data = row['prompt']
        print(f"📋 prompt数据类型: {type(prompt_data)}, 形状: {prompt_data.shape}")
        
        # 尝试解析prompt内容
        try:
            if prompt_data.dtype == object:
                # 对象数组，可能包含字典或其他数据
                prompt_content = prompt_data.tolist()
                sample_data['prompt'] = prompt_content
                print(f"📋 prompt内容: {prompt_content[:2] if isinstance(prompt_content, list) else str(prompt_content)[:200]}")
            else:
                sample_data['prompt'] = prompt_data.tolist()
        except Exception as e:
            print(f"⚠️  解析prompt失败: {e}")
            sample_data['prompt'] = str(prompt_data)
    
    # 解析images (numpy数组)
    if isinstance(row['images'], np.ndarray):
        images_data = row['images']
        print(f"📋 images数据类型: {type(images_data)}, 形状: {images_data.shape}")
        
        try:
            # 图像数据通常是对象数组
            images_list = images_data.tolist()
            sample_data['images'] = []
            
            for i, img_data in enumerate(images_list):
                if isinstance(img_data, bytes):
                    # 字节数据，尝试解析为图像
                    try:
                        pil_image = Image.open(io.BytesIO(img_data)).convert('RGB')
                        sample_data['images'].append(pil_image)
                        print(f"📷 图像 {i}: {pil_image.size} (从bytes解析)")
                    except Exception as e:
                        print(f"❌ 解析图像 {i} 失败: {e}")
                elif isinstance(img_data, str):
                    # 可能是base64编码
                    try:
                        import base64
                        img_bytes = base64.b64decode(img_data)
                        pil_image = Image.open(io.BytesIO(img_bytes)).convert('RGB')
                        sample_data['images'].append(pil_image)
                        print(f"📷 图像 {i}: {pil_image.size} (从base64解析)")
                    except Exception as e:
                        print(f"❌ 解析base64图像 {i} 失败: {e}")
                else:
                    print(f"📷 图像 {i}: 未知格式 {type(img_data)}")
                    
        except Exception as e:
            print(f"⚠️  解析images失败: {e}")
            sample_data['images'] = []
    
    # 解析extra_info
    if isinstance(row['extra_info'], dict):
        sample_data['extra_info'] = row['extra_info']
        print(f"📋 extra_info: {list(row['extra_info'].keys())}")
    
    return sample_data

def save_sample_for_evaluation(sample_data: dict, output_dir: str, sample_idx: int):
    """保存样本数据用于评估"""
    
    # 创建输出目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    full_output_dir = Path(output_dir) / f"eval_sample_{timestamp}"
    full_output_dir.mkdir(parents=True, exist_ok=True)
    
    sample_dir = full_output_dir / f"sample_{sample_idx:02d}"
    sample_dir.mkdir(exist_ok=True)
    
    # 保存基本信息
    basic_info = {
        'data_source': sample_data.get('data_source'),
        'ability': sample_data.get('ability'),
        'env_name': sample_data.get('env_name'),
        'extra_info': sample_data.get('extra_info', {})
    }
    
    info_file = sample_dir / "basic_info.json"
    with open(info_file, 'w', encoding='utf-8') as f:
        json.dump(basic_info, f, indent=2, ensure_ascii=False)
    
    # 保存prompt
    prompt_file = sample_dir / "prompt.json"
    with open(prompt_file, 'w', encoding='utf-8') as f:
        json.dump(sample_data.get('prompt', []), f, indent=2, ensure_ascii=False)
    
    # 保存图像
    images = sample_data.get('images', [])
    for img_idx, img in enumerate(images):
        if isinstance(img, Image.Image):
            img_path = sample_dir / f"original_image_{img_idx:02d}.png"
            img.save(img_path)
            print(f"💾 保存原始图像: {img_path}")
    
    print(f"📁 样本数据保存到: {sample_dir}")
    
    # 创建README
    readme_content = f"""# Agent 评估样本 {sample_idx}

## 基本信息
- 环境名称: {sample_data.get('env_name')}
- 能力类型: {sample_data.get('ability')}
- 数据源: {sample_data.get('data_source')}

## 文件说明
- `basic_info.json`: 基本信息
- `prompt.json`: 提示数据
- `original_image_XX.png`: 原始图像
- `step_XX/`: 每一步的处理结果（训练时生成）

## 使用方法
1. 将此样本数据用于训练或推理
2. 训练过程中会在 step_XX/ 目录下保存每一步的处理结果
3. 对比原始图像和处理后的图像查看效果

## 预期的处理流程
基于环境名称 '{sample_data.get('env_name')}'，模型应该：
1. 识别图像中的退化类型
2. 选择合适的工具进行处理
3. 逐步改善图像质量
4. 最终输出 <answer>success</answer>
"""
    
    readme_file = sample_dir / "README.md"
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    return sample_dir

def create_evaluation_template():
    """创建评估模板脚本"""
    
    template_content = '''#!/usr/bin/env python3
"""
使用准备好的样本数据进行Agent评估
"""

import sys
sys.path.append('/app/xiaominl/DeepEyes')

from verl.workers.agent.parallel_env_v2 import ParallelEnv, _parse_model_output_for_tools
from verl.utils import hf_tokenizer, hf_processor
from PIL import Image
import json
from pathlib import Path

def evaluate_with_real_model(sample_dir: str, model_path: str):
    """使用真实模型评估样本"""
    
    print(f"🎯 使用真实模型评估")
    print(f"📁 样本目录: {sample_dir}")
    print(f"🤖 模型路径: {model_path}")
    
    # 加载tokenizer和processor
    tokenizer = hf_tokenizer(model_path)
    processor = hf_processor(model_path)
    
    # 加载样本数据
    sample_path = Path(sample_dir)
    
    # 读取基本信息
    with open(sample_path / "basic_info.json", 'r', encoding='utf-8') as f:
        basic_info = json.load(f)
    
    # 读取图像
    images = []
    for img_file in sorted(sample_path.glob("original_image_*.png")):
        img = Image.open(img_file).convert('RGB')
        images.append(img)
    
    print(f"📷 加载了 {len(images)} 张图像")
    print(f"📋 环境名称: {basic_info['env_name']}")
    
    # TODO: 这里集成真实的模型推理
    # 1. 构建输入prompt
    # 2. 调用VLLM生成
    # 3. 解析输出
    # 4. 调用工具
    # 5. 保存每一步的结果
    
    print(f"💡 提示: 需要集成真实的VLLM推理逻辑")
    print(f"📁 结果将保存在: {sample_path}/step_XX/")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample_dir", required=True, help="样本目录路径")
    parser.add_argument("--model_path", default="/app/models/Qwen2.5-VL-7B-Instruct", help="模型路径")
    
    args = parser.parse_args()
    
    evaluate_with_real_model(args.sample_dir, args.model_path)
'''
    
    template_file = Path("eval_template.py")
    with open(template_file, 'w') as f:
        f.write(template_content)
    
    os.chmod(template_file, 0o755)
    print(f"📝 创建评估模板: {template_file}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent 数据分析和样本准备")
    parser.add_argument("--data_file", default="/app/datasets/IRdataset/shard-000003.parquet", help="数据文件路径")
    parser.add_argument("--output_dir", default="eval_samples", help="输出目录")
    parser.add_argument("--sample_idx", type=int, default=0, help="样本索引")
    parser.add_argument("--num_samples", type=int, default=3, help="处理样本数量")
    
    args = parser.parse_args()
    
    print(f"🎯 Agent 样本准备")
    print(f"📁 数据文件: {args.data_file}")
    print(f"📊 处理样本: {args.num_samples}")
    
    try:
        # 处理多个样本
        for i in range(args.num_samples):
            sample_idx = args.sample_idx + i
            print(f"\n{'='*60}")
            print(f"🔍 处理样本 {sample_idx}")
            
            # 加载样本数据
            sample_data = load_real_data_sample(args.data_file, sample_idx)
            
            if sample_data:
                # 保存样本
                sample_dir = save_sample_for_evaluation(sample_data, args.output_dir, sample_idx)
                print(f"✅ 样本 {sample_idx} 准备完成: {sample_dir}")
            else:
                print(f"❌ 样本 {sample_idx} 加载失败")
        
        # 创建评估模板
        create_evaluation_template()
        
        print(f"\n🎉 样本准备完成！")
        print(f"💡 下一步:")
        print(f"   1. 查看准备好的样本数据")
        print(f"   2. 使用 eval_template.py 进行真实模型评估")
        print(f"   3. 或者集成到训练流程中实时保存图像")
        
    except Exception as e:
        print(f"❌ 处理过程中出错: {e}")
        import traceback
        traceback.print_exc()
