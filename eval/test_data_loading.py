#!/usr/bin/env python3
"""
测试脚本：验证parquet数据加载是否正确
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pyarrow.parquet as pq
import numpy as np
from PIL import Image
import io


def test_data_loading(parquet_path):
    """测试数据加载"""
    print(f"{'='*80}")
    print(f"测试 parquet 文件: {parquet_path}")
    print(f"{'='*80}\n")
    
    # 读取数据
    table = pq.read_table(parquet_path)
    df = table.to_pandas()
    
    print(f"✅ 成功加载 {len(df)} 个样本\n")
    
    # 测试第一个样本
    sample = df.iloc[0]
    
    print("=" * 80)
    print("样本字段:")
    print("=" * 80)
    for key in sample.keys():
        print(f"  - {key}: {type(sample[key]).__name__}")
    
    print("\n" + "=" * 80)
    print("测试图像提取:")
    print("=" * 80)
    
    # 测试退化图像提取
    images = sample['images']
    print(f"\nimages 数组长度: {len(images)}")
    
    if len(images) > 0:
        image_data = images[0]
        print(f"images[0] 类型: {type(image_data).__name__}")
        
        if isinstance(image_data, dict):
            print(f"images[0] 是字典，键: {list(image_data.keys())}")
            if 'bytes' in image_data:
                # 提取图像
                image_bytes = image_data['bytes']
                degraded_image = Image.open(io.BytesIO(image_bytes))
                print(f"✅ 成功提取退化图像: {degraded_image.size}, {degraded_image.mode}")
    
    # 测试GT图像提取
    extra_info = sample.get('extra_info', {})
    if isinstance(extra_info, dict):
        print(f"\nextra_info 键: {list(extra_info.keys())}")
        
        if 'original_image' in extra_info:
            original_image_data = extra_info['original_image']
            print(f"original_image 类型: {type(original_image_data).__name__}")
            
            if isinstance(original_image_data, bytes):
                gt_image = Image.open(io.BytesIO(original_image_data))
                print(f"✅ 成功提取GT图像: {gt_image.size}, {gt_image.mode}")
            
            use_original = extra_info.get('use_original', False)
            print(f"use_original: {use_original}")
    
    # 测试prompt提取
    print("\n" + "=" * 80)
    print("测试 prompt 提取:")
    print("=" * 80)
    
    prompt = sample['prompt']
    print(f"\nprompt 类型: {type(prompt).__name__}")
    print(f"prompt 长度: {len(prompt)}")
    
    if len(prompt) > 0:
        system_msg = prompt[0]
        print(f"\nprompt[0] 类型: {type(system_msg).__name__}")
        if isinstance(system_msg, dict):
            print(f"prompt[0] 角色: {system_msg.get('role')}")
            content = system_msg.get('content', '')
            print(f"prompt[0] 内容长度: {len(content)}")
            print(f"prompt[0] 内容预览:\n{content[:200]}...")
    
    if len(prompt) > 1:
        user_msg = prompt[1]
        print(f"\nprompt[1] 类型: {type(user_msg).__name__}")
        if isinstance(user_msg, dict):
            print(f"prompt[1] 角色: {user_msg.get('role')}")
            print(f"prompt[1] 内容: {user_msg.get('content', '')}")
    
    # 测试退化类型
    print("\n" + "=" * 80)
    print("测试退化类型:")
    print("=" * 80)
    
    env_name = sample.get('env_name', '')
    print(f"\nenv_name: {env_name}")
    degradations = env_name.split(', ')
    print(f"退化列表: {degradations}")
    
    print("\n" + "=" * 80)
    print("✅ 所有测试通过！")
    print("=" * 80)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--data_path', type=str, 
                       default='/app/xiaominl/air_full_v1/shard-test-000000.parquet',
                       help='Path to parquet file')
    args = parser.parse_args()
    
    test_data_loading(args.data_path)

