#!/usr/bin/env python3
"""
测试 SCUNet 在不同噪声等级上的效果
"""

import sys
sys.path.insert(0, '/app/xiaominl/DeepEyes_v2')

# 修改原测试脚本，测试不同噪声等级
import subprocess
import os

noise_levels = {
    'low_level1': '/app/xiaominl/datasets/degraded_datasets/degraded_dataset/noise/low/000001_level1.png',
    'low_level2': '/app/xiaominl/datasets/degraded_datasets/degraded_dataset/noise/low/000001_level2.png',
    'medium_level3': '/app/xiaominl/datasets/degraded_datasets/degraded_dataset/noise/medium/000001_level3.png',
    'high_level4': '/app/xiaominl/datasets/degraded_datasets/degraded_dataset/noise/high/000001_level4.png',
}

original_path = '/app/xiaominl/datasets/degraded_datasets/degraded_dataset/original/000001.png'

# 导入测试函数
from test_scunet_real_image import test_scunet_denoising, calculate_metrics
from PIL import Image
import numpy as np

print("\n" + "="*80)
print("SCUNet 不同噪声等级测试")
print("="*80)

results = {}

for level_name, noisy_path in noise_levels.items():
    if not os.path.exists(noisy_path):
        print(f"\n跳过 {level_name}: 文件不存在")
        continue
    
    print(f"\n{'='*80}")
    print(f"测试噪声等级: {level_name}")
    print(f"{'='*80}")
    
    # 读取图像并计算初始指标
    noisy_img = Image.open(noisy_path).convert("RGB")
    orig_img = Image.open(original_path).convert("RGB")
    
    initial_metrics = calculate_metrics(noisy_img, orig_img)
    print(f"初始指标 (去噪前):")
    print(f"  PSNR: {initial_metrics['psnr']:.4f} dB")
    print(f"  SSIM: {initial_metrics['ssim']:.4f}")
    
    # 使用PSNR优化版本测试
    result = test_scunet_denoising(noisy_path, original_path, "scunet_real_denoising_psnr")
    
    if result:
        results[level_name] = {
            'before': initial_metrics,
            'after': result['after'],
            'improvement': result['improvement']
        }

# 总结
print("\n" + "="*80)
print("所有噪声等级对比总结")
print("="*80)

print(f"\n{'噪声等级':<20} | {'去噪前PSNR':<15} | {'去噪后PSNR':<15} | {'PSNR改进':<15} | {'去噪前SSIM':<15} | {'去噪后SSIM':<15} | {'SSIM改进':<15}")
print("-" * 135)

for level_name, data in results.items():
    before_psnr = data['before']['psnr']
    after_psnr = data['after']['psnr']
    psnr_imp = data['improvement']['psnr']
    before_ssim = data['before']['ssim']
    after_ssim = data['after']['ssim']
    ssim_imp = data['improvement']['ssim']
    
    psnr_symbol = "↑" if psnr_imp > 0 else "↓"
    ssim_symbol = "↑" if ssim_imp > 0 else "↓"
    
    print(f"{level_name:<20} | {before_psnr:>13.4f} | {after_psnr:>13.4f} | "
          f"{psnr_symbol} {abs(psnr_imp):>11.4f} | {before_ssim:>13.4f} | "
          f"{after_ssim:>13.4f} | {ssim_symbol} {abs(ssim_imp):>11.4f}")

print("\n" + "="*80)

