#!/usr/bin/env python3
"""
检查数据集中图像的实际尺寸
"""

import pandas as pd
from PIL import Image
import io

print("=" * 80)
print("检查数据集中的图像尺寸")
print("=" * 80)

parquet_file = '/app/datasets/air_v13/shards/shard-train-000000.parquet'
df = pd.read_parquet(parquet_file)

print(f"\n数据集: {parquet_file}")
print(f"总样本数: {len(df)}")
print(f"列: {df.columns.tolist()}")

# 检查前5个样本
print("\n" + "=" * 80)
print("检查前5个样本的图像尺寸")
print("=" * 80)

for idx in range(min(5, len(df))):
    row = df.iloc[idx]
    
    print(f"\n样本 {idx}:")
    print("-" * 80)
    
    # 退化图
    try:
        degraded_img_data = row['images'][0]
        if isinstance(degraded_img_data, dict) and 'bytes' in degraded_img_data:
            degraded_img = Image.open(io.BytesIO(degraded_img_data['bytes']))
        elif isinstance(degraded_img_data, bytes):
            degraded_img = Image.open(io.BytesIO(degraded_img_data))
        else:
            degraded_img = degraded_img_data
        
        print(f"  退化图尺寸: {degraded_img.size if hasattr(degraded_img, 'size') else 'N/A'}")
    except Exception as e:
        print(f"  退化图: 无法读取 - {e}")
    
    # GT原图
    try:
        extra = row['extra_info']
        if 'original_image' in extra and extra['original_image']:
            orig_data = extra['original_image']
            if isinstance(orig_data, bytes):
                orig_img = Image.open(io.BytesIO(orig_data))
            elif isinstance(orig_data, dict) and 'bytes' in orig_data:
                orig_img = Image.open(io.BytesIO(orig_data['bytes']))
            else:
                print(f"  GT原图类型: {type(orig_data)}")
                orig_img = None
            
            if orig_img:
                print(f"  GT原图尺寸: {orig_img.size}")
                
                # 检查尺寸关系
                if degraded_img.size == orig_img.size:
                    print(f"  ✅ 尺寸一致")
                else:
                    deg_w, deg_h = degraded_img.size
                    orig_w, orig_h = orig_img.size
                    
                    # 检查是否是倍数关系
                    if orig_w % deg_w == 0 and orig_h % deg_h == 0:
                        scale = orig_w // deg_w
                        if orig_h // deg_h == scale:
                            print(f"  🔍 倍数关系: GT是退化图的 {scale}x")
                    else:
                        print(f"  ⚠️  尺寸不同且不是倍数关系")
                        print(f"     差异: width {orig_w - deg_w}, height {orig_h - deg_h}")
        else:
            print(f"  GT原图: None")
    except Exception as e:
        print(f"  GT原图: 无法读取 - {e}")
    
    # env_name和reward_model
    try:
        print(f"  env_name: {row['env_name']}")
        print(f"  reward_model: {row['reward_model']}")
    except:
        pass

print("\n" + "=" * 80)
print("检查完成")
print("=" * 80)

