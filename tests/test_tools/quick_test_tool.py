#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速测试单个工具并显示完整指标（类似test_results.md）
"""

import sys
import os
from pathlib import Path
from PIL import Image
import argparse

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def quick_test_tool(tool_name: str, degraded_image_path: str, original_image_path: str):
    """
    快速测试单个工具并显示完整指标
    
    Args:
        tool_name: 工具名称
        degraded_image_path: 退化图路径
        original_image_path: 原图路径
    """
    print(f"\n{'='*80}")
    print(f"快速测试工具: {tool_name}")
    print(f"{'='*80}\n")
    
    # 加载图像
    if not os.path.exists(degraded_image_path):
        print(f"[ERROR] 退化图不存在: {degraded_image_path}")
        return
    if not os.path.exists(original_image_path):
        print(f"[ERROR] 原图不存在: {original_image_path}")
        return
    
    degraded_image = Image.open(degraded_image_path).convert('RGB')
    original_image = Image.open(original_image_path).convert('RGB')
    
    print(f"✓ 退化图已加载: {degraded_image.size}")
    print(f"✓ 原图已加载: {original_image.size}")
    
    # 初始化指标计算器
    print(f"\n1. 初始化指标计算器...")
    from verl.utils.reward_score.image_quality_metrics import ImageQualityMetrics
    metrics_calculator = ImageQualityMetrics()
    print(f"✓ 指标计算器初始化完成")
    
    # 计算基线指标
    print(f"\n2. 计算基线指标（退化图 vs 原图）...")
    baseline_metrics = metrics_calculator.calculate_all_metrics(degraded_image, original_image)
    print(f"  PSNR: {baseline_metrics['psnr']:.2f} dB")
    print(f"  SSIM: {baseline_metrics['ssim']:.4f}")
    print(f"  LPIPS: {baseline_metrics['lpips']:.4f}")
    
    # 加载工具
    print(f"\n3. 加载工具 {tool_name}...")
    try:
        from verl.workers.agent.envs.mm_process_engine.DehazeFormerToolbox import DehazeFormerToolbox
        from verl.workers.agent.envs.mm_process_engine.DeblurToolbox import DeblurToolbox
        from verl.workers.agent.envs.mm_process_engine.SwinIRToolbox import SwinIRDenoisingToolbox
        from verl.workers.agent.envs.mm_process_engine.MPRNetToolbox import MPRNetDenoisingToolbox
        from verl.workers.agent.envs.mm_process_engine.RestormerToolbox import RestormerMotionDeblurringToolbox
        
        tool_map = {
            'dehazeformer_dehaze': DehazeFormerToolbox,
            'drbnet_defocus_deblurring': DeblurToolbox,
            'swinir_denoising': SwinIRDenoisingToolbox,
            'mprnet_denoising': MPRNetDenoisingToolbox,
            'restormer_motion_deblurring': RestormerMotionDeblurringToolbox,
        }
        
        if tool_name not in tool_map:
            print(f"[ERROR] 未知工具: {tool_name}")
            print(f"支持的工具: {list(tool_map.keys())}")
            return
        
        tool = tool_map[tool_name](tool_name, "", {})
        print(f"✓ 工具加载成功: {tool.__class__.__name__}")
    except Exception as e:
        print(f"[ERROR] 工具加载失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 执行工具
    print(f"\n4. 执行工具...")
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
                    print(f"✓ 从 observation['multi_modal_data']['image'][0] 获取修复图")
        
        if restored_image is None:
            print(f"[ERROR] 无法提取修复后的图像")
            return
        
        print(f"✓ 修复图尺寸: {restored_image.size}")
        
    except Exception as e:
        print(f"[ERROR] 工具执行失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 计算修复后指标
    print(f"\n5. 计算修复后指标（修复图 vs 原图）...")
    restored_metrics = metrics_calculator.calculate_all_metrics(restored_image, original_image)
    print(f"  PSNR: {restored_metrics['psnr']:.2f} dB")
    print(f"  SSIM: {restored_metrics['ssim']:.4f}")
    print(f"  LPIPS: {restored_metrics['lpips']:.4f}")
    
    # 计算改进率
    print(f"\n6. 计算改进率...")
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
    parser = argparse.ArgumentParser(description="快速测试单个工具并显示完整指标")
    parser.add_argument('tool_name', type=str, help='工具名称（如: dehazeformer_dehaze）')
    parser.add_argument('degraded_image', type=str, help='退化图路径')
    parser.add_argument('original_image', type=str, help='原图路径')
    
    args = parser.parse_args()
    
    quick_test_tool(args.tool_name, args.degraded_image, args.original_image)
