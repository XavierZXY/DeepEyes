#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试单个工具在整个 Parquet 数据集上的效果
"""

import sys
import os
import io
import json
from pathlib import Path
from PIL import Image
import argparse
import pandas as pd
import numpy as np
from tqdm import tqdm
from datetime import datetime

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def load_image_from_data(image_data):
    """从各种数据格式加载图像"""
    if isinstance(image_data, bytes):
        return Image.open(io.BytesIO(image_data)).convert('RGB')
    elif isinstance(image_data, dict):
        if 'bytes' in image_data:
            return Image.open(io.BytesIO(image_data['bytes'])).convert('RGB')
        elif 'image' in image_data:
            return load_image_from_data(image_data['image'])
    elif isinstance(image_data, list) and len(image_data) > 0:
        return load_image_from_data(image_data[0])
    elif isinstance(image_data, np.ndarray):
        if image_data.dtype == object and image_data.size == 1:
            return load_image_from_data(image_data.item())
        elif image_data.size > 0 and image_data.dtype != object:
            return Image.fromarray(image_data).convert('RGB')
        else:
            raise ValueError(f"Unsupported numpy array: shape={image_data.shape}, dtype={image_data.dtype}")
    else:
        raise ValueError(f"Unsupported image data type: {type(image_data)}")


def load_tool(tool_name: str):
    """加载工具"""
    from verl.workers.agent.envs.mm_process_engine.DehazeFormerToolbox import DehazeFormerToolbox
    from verl.workers.agent.envs.mm_process_engine.DeblurToolbox import DeblurToolbox
    from verl.workers.agent.envs.mm_process_engine.SwinIRToolbox import (
        SwinIRDenoisingToolbox, SwinIRJpegArtifactRemovalToolbox, SwinIRSrToolbox
    )
    from verl.workers.agent.envs.mm_process_engine.MPRNetToolbox import (
        MPRNetDenoisingToolbox, MPRNetDeraininingToolbox, MPRNetMotionDeblurringToolbox
    )
    from verl.workers.agent.envs.mm_process_engine.RestormerToolbox import (
        RestormerMotionDeblurringToolbox, RestormerDefocusDeblurringToolbox, RestormerDerrainingToolbox
    )
    from verl.workers.agent.envs.mm_process_engine.SCUNetToolbox import (
        SCUNetRealDenoisingPSNRToolbox, SCUNetRealDenoisingGANToolbox, SCUNetColorDenoisingToolbox
    )
    from verl.workers.agent.envs.mm_process_engine.RetinexformerToolbox import (
        RetinexformerLOLv1Toolbox, RetinexformerLOLv2RealToolbox
    )
    from verl.workers.agent.envs.mm_process_engine.FBCNNToolbox import FBCNNJpegArtifactRemovalToolbox
    from verl.workers.agent.envs.mm_process_engine.XRestormerToolbox import (
        XRestormerMotionDeblurringToolbox, XRestormerDerainToolbox
    )
    
    tool_map = {
        'dehazeformer_dehaze': (DehazeFormerToolbox, {}),
        'drbnet_defocus_deblurring': (DeblurToolbox, {}),
        'swinir_denoising': (SwinIRDenoisingToolbox, {}),
        'swinir_jpeg_artifact_removal': (SwinIRJpegArtifactRemovalToolbox, {}),
        'swinir_super_resolution': (SwinIRSrToolbox, {}),
        'mprnet_denoising': (MPRNetDenoisingToolbox, {}),
        'mprnet_deraining': (MPRNetDeraininingToolbox, {}),
        'mprnet_motion_deblurring': (MPRNetMotionDeblurringToolbox, {}),
        'restormer_motion_deblurring': (RestormerMotionDeblurringToolbox, {}),
        'restormer_defocus_deblurring': (RestormerDefocusDeblurringToolbox, {}),
        'restormer_deraining': (RestormerDerrainingToolbox, {}),
        'xrestormer_motion_deblurring': (XRestormerMotionDeblurringToolbox, {}),
        'xrestormer_deraining': (XRestormerDerainToolbox, {}),
        'scunet_real_denoising_psnr': (SCUNetRealDenoisingPSNRToolbox, {}),
        'scunet_real_denoising_gan': (SCUNetRealDenoisingGANToolbox, {}),
        'scunet_color_denoising': (SCUNetColorDenoisingToolbox, {}),
        'retinexformer_lol_v1': (RetinexformerLOLv1Toolbox, {}),
        'retinexformer_lol_v2_real': (RetinexformerLOLv2RealToolbox, {}),
        'fbcnn_jpeg_artifact_removal': (FBCNNJpegArtifactRemovalToolbox, {}),
    }
    
    if tool_name not in tool_map:
        raise ValueError(f"未知工具: {tool_name}。支持的工具: {list(tool_map.keys())}")
    
    tool_class, tool_params = tool_map[tool_name]
    tool = tool_class(tool_name, "", tool_params)
    return tool


def test_tool_on_parquet(tool_name: str, parquet_path: str, num_samples: int = None, output_dir: str = None):
    """
    测试单个工具在整个 Parquet 数据集上的效果
    
    Args:
        tool_name: 工具名称
        parquet_path: parquet 文件路径
        num_samples: 测试的样本数量（None=全部）
        output_dir: 输出目录
    """
    print(f"\n{'='*80}")
    print(f"测试工具: {tool_name}")
    print(f"数据集: {parquet_path}")
    print(f"{'='*80}\n")
    
    # 读取 parquet 文件
    if not os.path.exists(parquet_path):
        print(f"[ERROR] Parquet 文件不存在: {parquet_path}")
        return
    
    print(f"1. 加载 Parquet 数据...")
    df = pd.read_parquet(parquet_path)
    total_samples = len(df)
    print(f"  ✓ 数据集加载完成，共 {total_samples} 个样本")
    
    # 确定测试样本数
    if num_samples is None or num_samples > total_samples:
        num_samples = total_samples
    print(f"  ✓ 将测试 {num_samples} 个样本")
    
    # 初始化指标计算器
    print(f"\n2. 初始化指标计算器...")
    from verl.utils.reward_score.image_quality_metrics import ImageQualityMetrics
    metrics_calculator = ImageQualityMetrics()
    print(f"  ✓ 指标计算器初始化完成")
    
    # 加载工具
    print(f"\n3. 加载工具 {tool_name}...")
    try:
        tool = load_tool(tool_name)
        print(f"  ✓ 工具加载成功: {tool.__class__.__name__}")
    except Exception as e:
        print(f"[ERROR] 工具加载失败: {e}")
        return
    
    # 测试所有样本
    print(f"\n4. 测试样本...")
    results = []
    
    for idx in tqdm(range(num_samples), desc="处理样本"):
        try:
            row = df.iloc[idx]
            
            # 提取图像
            degraded_image_data = row['images']
            extra_info = row['extra_info']
            
            degraded_image = load_image_from_data(degraded_image_data)
            original_image = load_image_from_data(extra_info['original_image'])
            
            # 计算基线指标
            baseline_metrics = metrics_calculator.calculate_all_metrics(degraded_image, original_image)
            
            # 执行工具
            tool.multi_modal_data = {'image': [degraded_image]}
            action_string = f'<tool_call>{{"name": "{tool_name}", "arguments": {{}}}}</tool_call>'
            
            observation, reward, done, info = tool.execute(action_string)
            
            # 提取修复后的图像
            restored_image = None
            if isinstance(observation, dict) and 'multi_modal_data' in observation:
                mmd = observation['multi_modal_data']
                if isinstance(mmd, dict) and 'image' in mmd:
                    if mmd['image'] and len(mmd['image']) > 0:
                        restored_image = mmd['image'][0]
            
            if restored_image is None:
                print(f"\n[WARNING] 样本 {idx}: 无法提取修复后的图像")
                continue
            
            # 计算修复后指标
            restored_metrics = metrics_calculator.calculate_all_metrics(restored_image, original_image)
            
            # 计算改进率
            psnr_improve = ((restored_metrics['psnr'] - baseline_metrics['psnr']) / baseline_metrics['psnr'] * 100) if baseline_metrics['psnr'] > 0 else 0
            ssim_improve = ((restored_metrics['ssim'] - baseline_metrics['ssim']) / baseline_metrics['ssim'] * 100) if baseline_metrics['ssim'] > 0 else 0
            lpips_improve = ((baseline_metrics['lpips'] - restored_metrics['lpips']) / baseline_metrics['lpips'] * 100) if baseline_metrics['lpips'] > 0 else 0
            
            # 保存结果
            results.append({
                'sample_idx': idx,
                'baseline_psnr': baseline_metrics['psnr'],
                'baseline_ssim': baseline_metrics['ssim'],
                'baseline_lpips': baseline_metrics['lpips'],
                'restored_psnr': restored_metrics['psnr'],
                'restored_ssim': restored_metrics['ssim'],
                'restored_lpips': restored_metrics['lpips'],
                'improve_psnr': psnr_improve,
                'improve_ssim': ssim_improve,
                'improve_lpips': lpips_improve,
            })
            
        except Exception as e:
            print(f"\n[ERROR] 样本 {idx} 处理失败: {e}")
            continue
    
    if not results:
        print("\n[ERROR] 没有成功处理的样本！")
        return
    
    # 计算统计数据
    print(f"\n{'='*80}")
    print(f"测试完成！成功处理 {len(results)}/{num_samples} 个样本")
    print(f"{'='*80}\n")
    
    # 计算平均值
    avg_baseline_psnr = np.mean([r['baseline_psnr'] for r in results])
    avg_baseline_ssim = np.mean([r['baseline_ssim'] for r in results])
    avg_baseline_lpips = np.mean([r['baseline_lpips'] for r in results])
    
    avg_restored_psnr = np.mean([r['restored_psnr'] for r in results])
    avg_restored_ssim = np.mean([r['restored_ssim'] for r in results])
    avg_restored_lpips = np.mean([r['restored_lpips'] for r in results])
    
    avg_improve_psnr = np.mean([r['improve_psnr'] for r in results])
    avg_improve_ssim = np.mean([r['improve_ssim'] for r in results])
    avg_improve_lpips = np.mean([r['improve_lpips'] for r in results])
    
    # 计算标准差
    std_baseline_psnr = np.std([r['baseline_psnr'] for r in results])
    std_baseline_ssim = np.std([r['baseline_ssim'] for r in results])
    std_baseline_lpips = np.std([r['baseline_lpips'] for r in results])
    
    std_restored_psnr = np.std([r['restored_psnr'] for r in results])
    std_restored_ssim = np.std([r['restored_ssim'] for r in results])
    std_restored_lpips = np.std([r['restored_lpips'] for r in results])
    
    std_improve_psnr = np.std([r['improve_psnr'] for r in results])
    std_improve_ssim = np.std([r['improve_ssim'] for r in results])
    std_improve_lpips = np.std([r['improve_lpips'] for r in results])
    
    # 打印统计结果（类似 test_results.md 格式）
    print(f"## 测试工具: {tool_name}")
    print(f"\n### 基线指标 (退化图 vs 原图)\n")
    print(f"| 指标      | 平均值 | 标准差 |")
    print(f"|-----------|--------|--------|")
    print(f"| PSNR (dB) | {avg_baseline_psnr:.2f}  | ±{std_baseline_psnr:.2f} |")
    print(f"| SSIM      | {avg_baseline_ssim:.4f} | ±{std_baseline_ssim:.4f} |")
    print(f"| LPIPS     | {avg_baseline_lpips:.4f} | ±{std_baseline_lpips:.4f} |")
    
    print(f"\n### 修复后指标 (修复图 vs 原图)\n")
    print(f"| 指标      | 平均值 | 标准差 |")
    print(f"|-----------|--------|--------|")
    print(f"| PSNR (dB) | {avg_restored_psnr:.2f}  | ±{std_restored_psnr:.2f} |")
    print(f"| SSIM      | {avg_restored_ssim:.4f} | ±{std_restored_ssim:.4f} |")
    print(f"| LPIPS     | {avg_restored_lpips:.4f} | ±{std_restored_lpips:.4f} |")
    
    print(f"\n### 改进率\n")
    print(f"| 指标   | 平均改进 | 标准差 | 状态 |")
    print(f"|--------|---------|--------|------|")
    print(f"| PSNR↑  | {avg_improve_psnr:+.1f}%  | ±{std_improve_psnr:.1f}% | {'✅' if avg_improve_psnr > 0 else '⚠️'} |")
    print(f"| SSIM↑  | {avg_improve_ssim:+.1f}%  | ±{std_improve_ssim:.1f}% | {'✅' if avg_improve_ssim > 0 else '⚠️'} |")
    print(f"| LPIPS↓ | {avg_improve_lpips:+.1f}% | ±{std_improve_lpips:.1f}% | {'✅' if avg_improve_lpips > 0 else '⚠️'} |")
    
    print(f"\n成功率: {len(results)}/{num_samples} ({len(results)/num_samples*100:.1f}%)")
    
    # 保存详细结果
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 保存 JSON
        json_file = output_path / f"{tool_name}_{timestamp}.json"
        with open(json_file, 'w') as f:
            json.dump({
                'tool_name': tool_name,
                'parquet_path': parquet_path,
                'num_samples': num_samples,
                'success_count': len(results),
                'statistics': {
                    'baseline': {
                        'psnr': {'mean': float(avg_baseline_psnr), 'std': float(std_baseline_psnr)},
                        'ssim': {'mean': float(avg_baseline_ssim), 'std': float(std_baseline_ssim)},
                        'lpips': {'mean': float(avg_baseline_lpips), 'std': float(std_baseline_lpips)}
                    },
                    'restored': {
                        'psnr': {'mean': float(avg_restored_psnr), 'std': float(std_restored_psnr)},
                        'ssim': {'mean': float(avg_restored_ssim), 'std': float(std_restored_ssim)},
                        'lpips': {'mean': float(avg_restored_lpips), 'std': float(std_restored_lpips)}
                    },
                    'improvement': {
                        'psnr': {'mean': float(avg_improve_psnr), 'std': float(std_improve_psnr)},
                        'ssim': {'mean': float(avg_improve_ssim), 'std': float(std_improve_ssim)},
                        'lpips': {'mean': float(avg_improve_lpips), 'std': float(std_improve_lpips)}
                    }
                },
                'detailed_results': results
            }, f, indent=2)
        print(f"\n✓ 详细结果已保存到: {json_file}")
        
        # 保存 CSV
        csv_file = output_path / f"{tool_name}_{timestamp}.csv"
        df_results = pd.DataFrame(results)
        df_results.to_csv(csv_file, index=False)
        print(f"✓ CSV 结果已保存到: {csv_file}")
        
        # 保存 Markdown 报告
        md_file = output_path / f"{tool_name}_{timestamp}.md"
        with open(md_file, 'w') as f:
            f.write(f"# {tool_name} 测试报告\n\n")
            f.write(f"**数据集**: {parquet_path}\n")
            f.write(f"**测试样本数**: {num_samples}\n")
            f.write(f"**成功样本数**: {len(results)}\n")
            f.write(f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write(f"## 基线指标 (退化图 vs 原图)\n\n")
            f.write(f"| 指标      | 平均值 | 标准差 |\n")
            f.write(f"|-----------|--------|--------|\n")
            f.write(f"| PSNR (dB) | {avg_baseline_psnr:.2f}  | ±{std_baseline_psnr:.2f} |\n")
            f.write(f"| SSIM      | {avg_baseline_ssim:.4f} | ±{std_baseline_ssim:.4f} |\n")
            f.write(f"| LPIPS     | {avg_baseline_lpips:.4f} | ±{std_baseline_lpips:.4f} |\n")
            
            f.write(f"\n## 修复后指标 (修复图 vs 原图)\n\n")
            f.write(f"| 指标      | 平均值 | 标准差 |\n")
            f.write(f"|-----------|--------|--------|\n")
            f.write(f"| PSNR (dB) | {avg_restored_psnr:.2f}  | ±{std_restored_psnr:.2f} |\n")
            f.write(f"| SSIM      | {avg_restored_ssim:.4f} | ±{std_restored_ssim:.4f} |\n")
            f.write(f"| LPIPS     | {avg_restored_lpips:.4f} | ±{std_restored_lpips:.4f} |\n")
            
            f.write(f"\n## 改进率\n\n")
            f.write(f"| 指标   | 平均改进 | 标准差 | 状态 |\n")
            f.write(f"|--------|---------|--------|------|\n")
            f.write(f"| PSNR↑  | {avg_improve_psnr:+.1f}%  | ±{std_improve_psnr:.1f}% | {'✅' if avg_improve_psnr > 0 else '⚠️'} |\n")
            f.write(f"| SSIM↑  | {avg_improve_ssim:+.1f}%  | ±{std_improve_ssim:.1f}% | {'✅' if avg_improve_ssim > 0 else '⚠️'} |\n")
            f.write(f"| LPIPS↓ | {avg_improve_lpips:+.1f}% | ±{std_improve_lpips:.1f}% | {'✅' if avg_improve_lpips > 0 else '⚠️'} |\n")
            
            f.write(f"\n## 详细结果\n\n")
            f.write(f"| 样本 | 基线PSNR | 修复PSNR | PSNR↑ | 基线SSIM | 修复SSIM | SSIM↑ | 基线LPIPS | 修复LPIPS | LPIPS↓ |\n")
            f.write(f"|------|---------|---------|-------|---------|---------|-------|----------|----------|--------|\n")
            for r in results:
                f.write(f"| {r['sample_idx']:3d}  | {r['baseline_psnr']:7.2f} | {r['restored_psnr']:7.2f} | {r['improve_psnr']:+6.1f}% | {r['baseline_ssim']:7.4f} | {r['restored_ssim']:7.4f} | {r['improve_ssim']:+6.1f}% | {r['baseline_lpips']:8.4f} | {r['restored_lpips']:8.4f} | {r['improve_lpips']:+7.1f}% |\n")
        
        print(f"✓ Markdown 报告已保存到: {md_file}")
    
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="测试单个工具在整个 Parquet 数据集上的效果")
    parser.add_argument('tool_name', type=str, help='工具名称（如: dehazeformer_dehaze）')
    parser.add_argument('--parquet', type=str, 
                       default='/app/xiaominl/datasets/air_sp11np_up3_sample1_nosw/shard-test-000000.parquet',
                       help='Parquet 文件路径')
    parser.add_argument('--num-samples', type=int, default=None,
                       help='测试的样本数量（默认: 全部）')
    parser.add_argument('--output', type=str, default='./parquet_test_results',
                       help='输出目录（默认: ./parquet_test_results）')
    
    args = parser.parse_args()
    
    test_tool_on_parquet(args.tool_name, args.parquet, args.num_samples, args.output)

