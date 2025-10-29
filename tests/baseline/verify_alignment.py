#!/usr/bin/env python3
"""
验证 baseline 和 verl 的指标计算是否对齐

用法:
    python verify_alignment.py --image1 path/to/img1.png --image2 path/to/img2.png
    
或使用数据集中的样本:
    python verify_alignment.py --use-dataset --num-samples 5
"""

import os
import sys
import argparse
import io
import numpy as np
from PIL import Image
from pathlib import Path

# 添加项目路径
sys.path.insert(0, '/app/xiaominl/DeepEyes_v2')

# 导入 baseline 版本
from tests.baseline.test_baseline_restoration import (
    calculate_psnr as baseline_psnr,
    calculate_ssim as baseline_ssim,
    calculate_lpips as baseline_lpips
)

# 导入 verl 版本
from verl.utils.reward_score.image_quality_metrics import get_image_quality_metrics


def load_image_from_data(image_data) -> Image.Image:
    """从数据中加载图像（支持多种格式）"""
    try:
        if isinstance(image_data, Image.Image):
            return image_data
        elif isinstance(image_data, bytes):
            return Image.open(io.BytesIO(image_data)).convert('RGB')
        elif isinstance(image_data, np.ndarray):
            # numpy array
            if len(image_data.shape) == 0:
                # 0维数组，可能包含对象
                if image_data.size > 0:
                    return load_image_from_data(image_data.item())
            elif image_data.dtype == np.object_:
                # 对象数组，获取第一个元素
                if image_data.size > 0:
                    return load_image_from_data(image_data.flat[0])
            else:
                # 普通图像数组
                if image_data.dtype in [np.float32, np.float64]:
                    if image_data.max() <= 1.0:
                        image_data = (image_data * 255).astype(np.uint8)
                return Image.fromarray(image_data).convert('RGB')
        elif isinstance(image_data, dict):
            if 'bytes' in image_data:
                return Image.open(io.BytesIO(image_data['bytes'])).convert('RGB')
            elif 'image' in image_data:
                return load_image_from_data(image_data['image'])
        elif isinstance(image_data, list) and len(image_data) > 0:
            return load_image_from_data(image_data[0])
    except Exception as e:
        print(f"[ERROR] Failed to load image: {e}")
        import traceback
        traceback.print_exc()
    
    return None


def compare_metrics(img1: Image.Image, img2: Image.Image, verbose: bool = True) -> dict:
    """
    对比 baseline 和 verl 的指标计算结果
    
    Args:
        img1: 第一张图像
        img2: 第二张图像
        verbose: 是否打印详细信息
        
    Returns:
        包含对比结果的字典
    """
    if verbose:
        print(f"\n图像尺寸: img1={img1.size}, img2={img2.size}")
        print("=" * 80)
    
    # Baseline 版本
    if verbose:
        print("\n[Baseline] 计算中...")
    ssim_baseline = baseline_ssim(img1, img2)
    psnr_baseline = baseline_psnr(img1, img2)
    lpips_baseline = baseline_lpips(img1, img2)
    
    # Verl 版本
    if verbose:
        print("\n[Verl] 计算中...")
    metrics = get_image_quality_metrics()
    ssim_verl = metrics.calculate_ssim(img1, img2)
    psnr_verl = metrics.calculate_psnr(img1, img2)
    lpips_verl = metrics.calculate_lpips(img1, img2)
    
    # 计算差异
    results = {
        'ssim': {
            'baseline': ssim_baseline,
            'verl': ssim_verl,
            'diff': abs(ssim_baseline - ssim_verl),
            'rel_diff_pct': abs(ssim_baseline - ssim_verl) / max(abs(ssim_verl), 1e-6) * 100
        },
        'psnr': {
            'baseline': psnr_baseline,
            'verl': psnr_verl,
            'diff': abs(psnr_baseline - psnr_verl),
            'rel_diff_pct': abs(psnr_baseline - psnr_verl) / max(abs(psnr_verl), 1e-6) * 100
        },
        'lpips': {
            'baseline': lpips_baseline,
            'verl': lpips_verl,
            'diff': abs(lpips_baseline - lpips_verl),
            'rel_diff_pct': abs(lpips_baseline - lpips_verl) / max(abs(lpips_verl), 1e-6) * 100
        }
    }
    
    if verbose:
        print("\n" + "=" * 80)
        print("对比结果:")
        print("=" * 80)
        
        for metric_name, values in results.items():
            print(f"\n{metric_name.upper()}:")
            print(f"  Baseline: {values['baseline']:.6f}")
            print(f"  Verl:     {values['verl']:.6f}")
            print(f"  绝对差异: {values['diff']:.6f}")
            print(f"  相对差异: {values['rel_diff_pct']:.2f}%")
            
            # 判断是否对齐
            if metric_name == 'psnr':
                threshold = 0.5  # PSNR 允许 0.5 dB 差异
                aligned = values['diff'] < threshold
            else:
                threshold = 0.01  # SSIM 和 LPIPS 允许 0.01 差异
                aligned = values['diff'] < threshold
            
            status = "✅ 对齐" if aligned else "❌ 未对齐"
            print(f"  状态: {status} (阈值: {threshold})")
    
    return results


def test_with_images(img1_path: str, img2_path: str):
    """使用指定的图像进行测试"""
    print(f"\n加载图像:")
    print(f"  Image 1: {img1_path}")
    print(f"  Image 2: {img2_path}")
    
    img1 = Image.open(img1_path).convert('RGB')
    img2 = Image.open(img2_path).convert('RGB')
    
    results = compare_metrics(img1, img2)
    return results


def test_with_dataset(data_path: str, num_samples: int = 5):
    """使用数据集中的样本进行测试"""
    import pandas as pd
    import io
    
    print(f"\n从数据集加载样本: {data_path}")
    df = pd.read_parquet(data_path)
    
    num_samples = min(num_samples, len(df))
    print(f"测试 {num_samples} 个样本")
    
    all_results = []
    
    for idx in range(num_samples):
        print(f"\n{'='*80}")
        print(f"样本 {idx + 1}/{num_samples}")
        print(f"{'='*80}")
        
        row = df.iloc[idx]
        
        # 加载退化图像
        degraded_image_data = row['images']
        if isinstance(degraded_image_data, list):
            degraded_image_data = degraded_image_data[0]
        
        degraded_image = load_image_from_data(degraded_image_data)
        if degraded_image is None:
            print(f"[SKIP] 无法解析退化图像数据类型: {type(degraded_image_data)}")
            continue
        
        # 加载原始图像
        extra_info = row['extra_info']
        original_image_data = extra_info['original_image']
        
        original_image = load_image_from_data(original_image_data)
        if original_image is None:
            print(f"[SKIP] 无法解析原始图像数据类型: {type(original_image_data)}")
            continue
        
        results = compare_metrics(degraded_image, original_image)
        all_results.append(results)
    
    # 统计汇总
    print(f"\n{'='*80}")
    print("汇总统计")
    print(f"{'='*80}")
    
    if not all_results:
        print("\n⚠️ 没有成功处理的样本，无法生成统计信息")
        return all_results
    
    for metric_name in ['ssim', 'psnr', 'lpips']:
        diffs = [r[metric_name]['diff'] for r in all_results]
        rel_diffs = [r[metric_name]['rel_diff_pct'] for r in all_results]
        
        print(f"\n{metric_name.upper()}:")
        print(f"  平均绝对差异: {np.mean(diffs):.6f} ± {np.std(diffs):.6f}")
        print(f"  平均相对差异: {np.mean(rel_diffs):.2f}% ± {np.std(rel_diffs):.2f}%")
        print(f"  最大差异: {np.max(diffs):.6f}")
        print(f"  最小差异: {np.min(diffs):.6f}")
        
        # 判断对齐率
        if metric_name == 'psnr':
            threshold = 0.5
        else:
            threshold = 0.01
        
        aligned_count = sum(1 for d in diffs if d < threshold)
        aligned_rate = aligned_count / len(diffs) * 100
        print(f"  对齐率: {aligned_rate:.1f}% ({aligned_count}/{len(diffs)} 样本)")
    
    return all_results


def main():
    parser = argparse.ArgumentParser(description='验证 baseline 和 verl 的指标对齐')
    parser.add_argument('--image1', type=str, help='第一张图像路径')
    parser.add_argument('--image2', type=str, help='第二张图像路径')
    parser.add_argument('--use-dataset', action='store_true', help='使用数据集测试')
    parser.add_argument('--data-path', type=str,
                        default='/app/xiaominl/datasets/air_sp11np_up3_sample1_nosw/shard-test-000000.parquet',
                        help='数据集路径')
    parser.add_argument('--num-samples', type=int, default=5, help='测试样本数量')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Baseline vs Verl 指标对齐验证")
    print("=" * 80)
    
    if args.use_dataset:
        # 使用数据集测试
        results = test_with_dataset(args.data_path, args.num_samples)
    elif args.image1 and args.image2:
        # 使用指定图像测试
        results = test_with_images(args.image1, args.image2)
    else:
        print("\n错误: 请指定 --image1 和 --image2，或使用 --use-dataset")
        parser.print_help()
        return
    
    print("\n" + "=" * 80)
    print("验证完成!")
    print("=" * 80)


if __name__ == '__main__':
    main()

