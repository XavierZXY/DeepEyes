#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速测试单个工具并显示完整指标（支持 Parquet 数据集）
"""

import sys
import os
import io
from pathlib import Path
from PIL import Image
import argparse
import pandas as pd
import numpy as np

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def load_image_from_data(image_data):
    """从各种数据格式加载图像（参考 test_baseline_restoration.py）"""
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
        # numpy array 可能是嵌套的对象数组
        if image_data.dtype == object and image_data.size == 1:
            # 如果是单个对象的数组，递归处理
            return load_image_from_data(image_data.item())
        elif image_data.size > 0 and image_data.dtype != object:
            # 正常的图像数组
            return Image.fromarray(image_data).convert('RGB')
        else:
            raise ValueError(f"Unsupported numpy array: shape={image_data.shape}, dtype={image_data.dtype}")
    else:
        raise ValueError(f"Unsupported image data type: {type(image_data)}")


def quick_test_tool_parquet(tool_name: str, parquet_path: str, sample_idx: int = 0):
    """
    从 parquet 数据集中读取样本并测试单个工具
    
    Args:
        tool_name: 工具名称
        parquet_path: parquet 文件路径
        sample_idx: 样本索引
    """
    print(f"\n{'='*80}")
    print(f"快速测试工具: {tool_name}")
    print(f"数据集: {parquet_path}")
    print(f"样本索引: {sample_idx}")
    print(f"{'='*80}\n")
    
    # 读取 parquet 文件
    if not os.path.exists(parquet_path):
        print(f"[ERROR] Parquet 文件不存在: {parquet_path}")
        return
    
    print(f"1. 加载 parquet 数据...")
    df = pd.read_parquet(parquet_path)
    print(f"  ✓ 数据集加载完成，共 {len(df)} 个样本")
    
    if sample_idx >= len(df):
        print(f"[ERROR] 样本索引 {sample_idx} 超出范围（最大: {len(df)-1}）")
        return
    
    # 获取样本
    row = df.iloc[sample_idx]
    print(f"\n2. 提取样本数据...")
    
    try:
        # 提取退化图和原图
        degraded_image_data = row['images']
        extra_info = row['extra_info']
        reward_model = row.get('reward_model', {})
        
        # 加载图像
        if isinstance(degraded_image_data, list):
            degraded_image = load_image_from_data(degraded_image_data[0])
        else:
            degraded_image = load_image_from_data(degraded_image_data)
        
        original_image = load_image_from_data(extra_info['original_image'])
        
        print(f"  ✓ 退化图已加载: {degraded_image.size}")
        print(f"  ✓ 原图已加载: {original_image.size}")
        
        # 打印退化类型信息
        if 'degradation_types' in extra_info:
            deg_types = extra_info['degradation_types']
            print(f"  📋 退化类型: {deg_types}")
        
    except Exception as e:
        print(f"[ERROR] 提取样本数据失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 初始化指标计算器
    print(f"\n3. 初始化指标计算器...")
    from verl.utils.reward_score.image_quality_metrics import ImageQualityMetrics
    metrics_calculator = ImageQualityMetrics()
    print(f"  ✓ 指标计算器初始化完成")
    
    # 计算基线指标
    print(f"\n4. 计算基线指标（退化图 vs 原图）...")
    baseline_metrics = metrics_calculator.calculate_all_metrics(degraded_image, original_image)
    print(f"  PSNR: {baseline_metrics['psnr']:.2f} dB")
    print(f"  SSIM: {baseline_metrics['ssim']:.4f}")
    print(f"  LPIPS: {baseline_metrics['lpips']:.4f}")
    
    # 加载工具
    print(f"\n5. 加载工具 {tool_name}...")
    try:
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
            'scunet_real_denoising_psnr': (SCUNetRealDenoisingPSNRToolbox, {}),
            'scunet_real_denoising_gan': (SCUNetRealDenoisingGANToolbox, {}),
            'scunet_color_denoising': (SCUNetColorDenoisingToolbox, {}),
            'retinexformer_lol_v1': (RetinexformerLOLv1Toolbox, {}),
            'retinexformer_lol_v2_real': (RetinexformerLOLv2RealToolbox, {}),
            'fbcnn_jpeg_artifact_removal': (FBCNNJpegArtifactRemovalToolbox, {}),
        }
        
        if tool_name not in tool_map:
            print(f"[ERROR] 未知工具: {tool_name}")
            print(f"支持的工具: {list(tool_map.keys())}")
            return
        
        tool_class, tool_params = tool_map[tool_name]
        tool = tool_class(tool_name, "", tool_params)
        print(f"  ✓ 工具加载成功: {tool.__class__.__name__}")
    except Exception as e:
        print(f"[ERROR] 工具加载失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 执行工具
    print(f"\n6. 执行工具...")
    try:
        tool.multi_modal_data = {'image': [degraded_image]}
        action_string = f'<tool_call>{{"name": "{tool_name}", "arguments": {{}}}}</tool_call>'
        
        observation, reward, done, info = tool.execute(action_string)
        
        print(f"  reward: {reward}")
        print(f"  done: {done}")
        print(f"  status: {info.get('status', 'N/A')}")
        
        # 提取修复后的图像
        restored_image = None
        
        # 方法1: observation['multi_modal_data']['image']
        if isinstance(observation, dict) and 'multi_modal_data' in observation:
            mmd = observation['multi_modal_data']
            if isinstance(mmd, dict) and 'image' in mmd:
                if mmd['image'] and len(mmd['image']) > 0:
                    restored_image = mmd['image'][0]
                    print(f"  ✓ 从 observation['multi_modal_data']['image'][0] 获取修复图")
        
        if restored_image is None:
            print(f"[ERROR] 无法提取修复后的图像")
            return
        
        print(f"  ✓ 修复图尺寸: {restored_image.size}")
        
    except Exception as e:
        print(f"[ERROR] 工具执行失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 计算修复后指标
    print(f"\n7. 计算修复后指标（修复图 vs 原图）...")
    restored_metrics = metrics_calculator.calculate_all_metrics(restored_image, original_image)
    print(f"  PSNR: {restored_metrics['psnr']:.2f} dB")
    print(f"  SSIM: {restored_metrics['ssim']:.4f}")
    print(f"  LPIPS: {restored_metrics['lpips']:.4f}")
    
    # 计算改进率
    print(f"\n8. 计算改进率...")
    psnr_improve = ((restored_metrics['psnr'] - baseline_metrics['psnr']) / baseline_metrics['psnr'] * 100) if baseline_metrics['psnr'] > 0 else 0
    ssim_improve = ((restored_metrics['ssim'] - baseline_metrics['ssim']) / baseline_metrics['ssim'] * 100) if baseline_metrics['ssim'] > 0 else 0
    lpips_improve = ((baseline_metrics['lpips'] - restored_metrics['lpips']) / baseline_metrics['lpips'] * 100) if baseline_metrics['lpips'] > 0 else 0
    
    print(f"  PSNR↑: {psnr_improve:+.1f}%")
    print(f"  SSIM↑: {ssim_improve:+.1f}%")
    print(f"  LPIPS↓: {lpips_improve:+.1f}%")
    
    # 生成类似 test_results.md 的表格
    print(f"\n{'='*80}")
    print(f"测试结果（类似 test_results.md 格式）")
    print(f"{'='*80}\n")
    
    print(f"## 基线指标 (退化图 vs 原图)\n")
    print(f"| PSNR (dB) | SSIM   | LPIPS  |")
    print(f"|-----------|--------|--------|")
    print(f"| {baseline_metrics['psnr']:.2f}      | {baseline_metrics['ssim']:.4f} | {baseline_metrics['lpips']:.4f} |\n")
    
    print(f"## 工具修复效果\n")
    print(f"### {tool_name}\n")
    print(f"| PSNR  | SSIM   | LPIPS  | PSNR↑     | SSIM↑     | LPIPS↓    | 状态 |")
    print(f"|-------|--------|--------|-----------|-----------|-----------|------|")
    print(f"| {restored_metrics['psnr']:.2f} | {restored_metrics['ssim']:.4f} | {restored_metrics['lpips']:.4f} | {psnr_improve:+.1f}% | {ssim_improve:+.1f}% | {lpips_improve:+.1f}% | {'✅' if psnr_improve > 0 else '⚠️'} |")
    
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="快速测试单个工具（支持 Parquet 数据集）")
    parser.add_argument('tool_name', type=str, help='工具名称（如: dehazeformer_dehaze）')
    parser.add_argument('--parquet', type=str, 
                       default='/app/xiaominl/datasets/air_sp11np_up3_sample1_nosw/shard-test-000000.parquet',
                       help='Parquet 文件路径')
    parser.add_argument('--sample-idx', type=int, default=0,
                       help='样本索引（默认: 0）')
    
    args = parser.parse_args()
    
    quick_test_tool_parquet(args.tool_name, args.parquet, args.sample_idx)

