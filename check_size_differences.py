#!/usr/bin/env python3
"""
检查数据集中细微的尺寸差异
"""

import pandas as pd
from PIL import Image
import io

print("=" * 80)
print("检查数据集中的细微尺寸差异")
print("=" * 80)

parquet_file = '/app/datasets/air_v13/shards/shard-train-000000.parquet'
df = pd.read_parquet(parquet_file)

print(f"\n检查所有样本...")
print("-" * 80)

size_patterns = {
    'exact_match': [],
    'scale_2x': [],
    'scale_3x': [],
    'scale_4x': [],
    'small_diff': [],  # 小差异（<5%）
    'medium_diff': [],  # 中等差异（5-20%）
    'large_diff': [],   # 大差异（>20%）
}

for idx in range(len(df)):
    row = df.iloc[idx]
    
    try:
        # 退化图
        degraded_img_data = row['images'][0]
        if isinstance(degraded_img_data, dict) and 'bytes' in degraded_img_data:
            degraded_img = Image.open(io.BytesIO(degraded_img_data['bytes']))
        else:
            continue
        
        # GT原图
        extra = row['extra_info']
        if not extra or 'original_image' not in extra or not extra['original_image']:
            continue
            
        orig_data = extra['original_image']
        if isinstance(orig_data, bytes):
            orig_img = Image.open(io.BytesIO(orig_data))
        else:
            continue
        
        deg_w, deg_h = degraded_img.size
        orig_w, orig_h = orig_img.size
        
        # 分类
        if deg_w == orig_w and deg_h == orig_h:
            size_patterns['exact_match'].append((idx, degraded_img.size, orig_img.size))
        elif orig_w == deg_w * 2 and orig_h == deg_h * 2:
            size_patterns['scale_2x'].append((idx, degraded_img.size, orig_img.size))
        elif orig_w == deg_w * 3 and orig_h == deg_h * 3:
            size_patterns['scale_3x'].append((idx, degraded_img.size, orig_img.size))
        elif orig_w == deg_w * 4 and orig_h == deg_h * 4:
            size_patterns['scale_4x'].append((idx, degraded_img.size, orig_img.size))
        else:
            # 计算差异百分比
            w_diff = abs(orig_w - deg_w)
            h_diff = abs(orig_h - deg_h)
            w_ratio = w_diff / max(orig_w, deg_w)
            h_ratio = h_diff / max(orig_h, deg_h)
            max_ratio = max(w_ratio, h_ratio)
            
            info = {
                'idx': idx,
                'degraded': degraded_img.size,
                'original': orig_img.size,
                'diff_w': w_diff,
                'diff_h': h_diff,
                'ratio': max_ratio,
                'env_name': row['env_name']
            }
            
            if max_ratio < 0.05:
                size_patterns['small_diff'].append(info)
            elif max_ratio < 0.20:
                size_patterns['medium_diff'].append(info)
            else:
                size_patterns['large_diff'].append(info)
                
    except Exception as e:
        continue

# 打印统计
print(f"\n统计结果:")
print(f"  ✅ 尺寸完全一致: {len(size_patterns['exact_match'])} 个")
print(f"  🔍 2倍关系: {len(size_patterns['scale_2x'])} 个")
print(f"  🔍 3倍关系: {len(size_patterns['scale_3x'])} 个")
print(f"  🔍 4倍关系: {len(size_patterns['scale_4x'])} 个")
print(f"  ⚠️  小差异(<5%): {len(size_patterns['small_diff'])} 个")
print(f"  ⚠️  中差异(5-20%): {len(size_patterns['medium_diff'])} 个")
print(f"  ⚠️  大差异(>20%): {len(size_patterns['large_diff'])} 个")

# 详细分析小差异的样本
if size_patterns['small_diff']:
    print(f"\n{'='*80}")
    print(f"小差异样本详情 (前10个):")
    print(f"{'='*80}")
    for info in size_patterns['small_diff'][:10]:
        print(f"\n样本 {info['idx']}:")
        print(f"  退化图: {info['degraded']}")
        print(f"  GT原图: {info['original']}")
        print(f"  差异: width={info['diff_w']}, height={info['diff_h']}")
        print(f"  差异比例: {info['ratio']*100:.2f}%")
        print(f"  env_name: {info['env_name']}")
        
        # 检查是否能被28整除（Vision Transformer的patch size）
        deg_w, deg_h = info['degraded']
        orig_w, orig_h = info['original']
        
        print(f"  退化图能否被28整除: width={deg_w%28==0}, height={deg_h%28==0}")
        print(f"  GT原图能否被28整除: width={orig_w%28==0}, height={orig_h%28==0}")

print(f"\n{'='*80}")
print(f"分析完成")
print(f"{'='*80}")

