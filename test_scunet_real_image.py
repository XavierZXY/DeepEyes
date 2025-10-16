#!/usr/bin/env python3
"""
测试 SCUNet 工具在真实噪声图像上的效果
比较去噪前后的 PSNR 和 SSIM
"""

import sys
sys.path.insert(0, '/app/xiaominl/DeepEyes_v2')

import os
import numpy as np
from PIL import Image
from skimage.metrics import peak_signal_noise_ratio as psnr
from skimage.metrics import structural_similarity as ssim
import time

from verl.workers.agent.tool_envs import ToolBase
# 导入 SCUNet 工具类以触发自动注册
from verl.workers.agent.envs.mm_process_engine.SCUNetToolbox import (
    SCUNetRealDenoisingPSNRToolbox,
    SCUNetRealDenoisingGANToolbox,
    SCUNetColorDenoisingToolbox,
    SCUNetGrayDenoisingToolbox
)


def calculate_metrics(img1, img2):
    """
    计算两张图像之间的 PSNR 和 SSIM
    
    Args:
        img1: PIL Image 或 numpy array
        img2: PIL Image 或 numpy array
        
    Returns:
        dict: {'psnr': float, 'ssim': float}
    """
    # 转换为 numpy array
    if isinstance(img1, Image.Image):
        img1 = np.array(img1)
    if isinstance(img2, Image.Image):
        img2 = np.array(img2)
    
    # 确保两张图像尺寸相同
    if img1.shape != img2.shape:
        print(f"警告: 图像尺寸不同 - img1: {img1.shape}, img2: {img2.shape}")
        # 调整到相同尺寸
        min_h = min(img1.shape[0], img2.shape[0])
        min_w = min(img1.shape[1], img2.shape[1])
        img1 = img1[:min_h, :min_w]
        img2 = img2[:min_h, :min_w]
    
    # 计算 PSNR
    psnr_value = psnr(img1, img2, data_range=255)
    
    # 计算 SSIM
    if len(img1.shape) == 3:  # 彩色图像
        ssim_value = ssim(img1, img2, data_range=255, channel_axis=2)
    else:  # 灰度图像
        ssim_value = ssim(img1, img2, data_range=255)
    
    return {
        'psnr': psnr_value,
        'ssim': ssim_value
    }


def test_scunet_denoising(noisy_image_path, original_image_path, tool_name="scunet_real_denoising_psnr"):
    """
    测试 SCUNet 去噪效果
    
    Args:
        noisy_image_path: 噪声图像路径
        original_image_path: 原始图像路径
        tool_name: 使用的工具名称
    """
    print("\n" + "="*80)
    print(f"SCUNet 去噪效果测试 - {tool_name}")
    print("="*80)
    
    # 检查文件是否存在
    if not os.path.exists(noisy_image_path):
        print(f"❌ 噪声图像不存在: {noisy_image_path}")
        return None
    
    if not os.path.exists(original_image_path):
        print(f"❌ 原始图像不存在: {original_image_path}")
        return None
    
    # 读取图像
    print(f"\n📁 读取图像...")
    noisy_image = Image.open(noisy_image_path).convert("RGB")
    original_image = Image.open(original_image_path).convert("RGB")
    
    print(f"  ✓ 噪声图像: {noisy_image_path}")
    print(f"    尺寸: {noisy_image.size}, 模式: {noisy_image.mode}")
    print(f"  ✓ 原始图像: {original_image_path}")
    print(f"    尺寸: {original_image.size}, 模式: {original_image.mode}")
    
    # 计算噪声图像与原始图像的指标（去噪前）
    print(f"\n📊 计算去噪前的指标...")
    noisy_array = np.array(noisy_image)
    original_array = np.array(original_image)
    
    print(f"  噪声图像统计: mean={noisy_array.mean():.2f}, std={noisy_array.std():.2f}")
    print(f"  原始图像统计: mean={original_array.mean():.2f}, std={original_array.std():.2f}")
    
    metrics_before = calculate_metrics(noisy_image, original_image)
    print(f"\n  去噪前 (噪声图像 vs 原始图像):")
    print(f"    PSNR: {metrics_before['psnr']:.4f} dB")
    print(f"    SSIM: {metrics_before['ssim']:.4f}")
    
    # 创建 SCUNet 工具
    print(f"\n🔧 创建 SCUNet 工具: {tool_name}")
    try:
        tool = ToolBase.create(tool_name)
        print(f"  ✓ 工具已创建")
        print(f"    任务类型: {tool.task_name}")
        print(f"    API 地址: {tool.api_url}")
    except Exception as e:
        print(f"  ❌ 工具创建失败: {e}")
        return None
    
    # 准备工具调用
    prompt = [{"role": "user", "content": "Please denoise this image."}]
    multi_modal_data = {"image": [noisy_image]}
    
    tool.reset(raw_prompt=prompt, multi_modal_data=multi_modal_data)
    
    # 构建工具调用字符串
    if "color" in tool_name or "gray" in tool_name:
        # 彩色或灰度去噪，使用 noise_level 参数
        action_string = f'''
<tool_call>
{{"name": "{tool_name}", "arguments": {{"noise_level": 25}}}}
</tool_call>
'''
    else:
        # 真实图像去噪，不需要参数
        action_string = f'''
<tool_call>
{{"name": "{tool_name}", "arguments": {{}}}}
</tool_call>
'''
    
    # 执行去噪
    print(f"\n🚀 执行去噪操作...")
    start_time = time.time()
    
    try:
        obs, reward, done, info = tool.execute(action_string)
        execution_time = time.time() - start_time
        
        if info.get("status") == "success":
            print(f"  ✅ 去噪成功！")
            print(f"    执行时间: {execution_time:.2f}s")
            
            # 获取去噪后的图像
            denoised_image = obs['multi_modal_data']['image'][0]
            print(f"    去噪图像尺寸: {denoised_image.size}")
            
            denoised_array = np.array(denoised_image)
            print(f"    去噪图像统计: mean={denoised_array.mean():.2f}, std={denoised_array.std():.2f}")
            
            # 计算去噪后的指标
            print(f"\n📊 计算去噪后的指标...")
            metrics_after = calculate_metrics(denoised_image, original_image)
            print(f"  去噪后 (去噪图像 vs 原始图像):")
            print(f"    PSNR: {metrics_after['psnr']:.4f} dB")
            print(f"    SSIM: {metrics_after['ssim']:.4f}")
            
            # 计算改进
            print(f"\n📈 改进情况:")
            psnr_improvement = metrics_after['psnr'] - metrics_before['psnr']
            ssim_improvement = metrics_after['ssim'] - metrics_before['ssim']
            
            psnr_symbol = "↑" if psnr_improvement > 0 else "↓"
            ssim_symbol = "↑" if ssim_improvement > 0 else "↓"
            
            print(f"    PSNR: {psnr_symbol} {abs(psnr_improvement):.4f} dB ({psnr_improvement:+.2f}%)")
            print(f"    SSIM: {ssim_symbol} {abs(ssim_improvement):.4f} ({ssim_improvement*100:+.2f}%)")
            
            # 保存结果
            output_dir = "/app/xiaominl/DeepEyes_v2/scunet_test_results"
            os.makedirs(output_dir, exist_ok=True)
            
            base_name = os.path.basename(noisy_image_path).replace('.png', '')
            denoised_path = os.path.join(output_dir, f"{base_name}_denoised_{tool_name}.png")
            denoised_image.save(denoised_path)
            print(f"\n💾 结果已保存:")
            print(f"    {denoised_path}")
            
            # 保存对比信息
            comparison_path = os.path.join(output_dir, f"{base_name}_metrics_{tool_name}.txt")
            with open(comparison_path, 'w') as f:
                f.write(f"SCUNet 去噪效果测试结果\n")
                f.write(f"{'='*60}\n\n")
                f.write(f"工具: {tool_name}\n")
                f.write(f"噪声图像: {noisy_image_path}\n")
                f.write(f"原始图像: {original_image_path}\n")
                f.write(f"执行时间: {execution_time:.2f}s\n\n")
                f.write(f"去噪前指标 (噪声图像 vs 原始图像):\n")
                f.write(f"  PSNR: {metrics_before['psnr']:.4f} dB\n")
                f.write(f"  SSIM: {metrics_before['ssim']:.4f}\n\n")
                f.write(f"去噪后指标 (去噪图像 vs 原始图像):\n")
                f.write(f"  PSNR: {metrics_after['psnr']:.4f} dB\n")
                f.write(f"  SSIM: {metrics_after['ssim']:.4f}\n\n")
                f.write(f"改进情况:\n")
                f.write(f"  PSNR: {psnr_symbol} {abs(psnr_improvement):.4f} dB ({psnr_improvement:+.2f}%)\n")
                f.write(f"  SSIM: {ssim_symbol} {abs(ssim_improvement):.4f} ({ssim_improvement*100:+.2f}%)\n")
            
            print(f"    {comparison_path}")
            
            return {
                'before': metrics_before,
                'after': metrics_after,
                'improvement': {
                    'psnr': psnr_improvement,
                    'ssim': ssim_improvement
                },
                'denoised_image': denoised_image
            }
            
        else:
            print(f"  ❌ 去噪失败: {info.get('error')}")
            return None
            
    except Exception as e:
        print(f"  ❌ 执行出错: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """主函数"""
    # 定义图像路径
    noisy_image_path = "/app/xiaominl/datasets/degraded_datasets/degraded_dataset/noise/low/000001_level1.png"
    original_image_path = "/app/xiaominl/datasets/degraded_datasets/degraded_dataset/original/000001.png"
    
    print("\n" + "="*80)
    print("SCUNet 真实图像去噪测试")
    print("="*80)
    print(f"\n测试图像:")
    print(f"  噪声图像: {noisy_image_path}")
    print(f"  原始图像: {original_image_path}")
    
    # 测试不同的 SCUNet 工具
    tools_to_test = [
        "scunet_real_denoising_psnr",  # 真实图像去噪（PSNR优化）
        "scunet_real_denoising_gan",   # 真实图像去噪（GAN版本）
        "scunet_color_denoising",      # 彩色图像去噪
    ]
    
    results = {}
    
    for tool_name in tools_to_test:
        print(f"\n{'='*80}")
        print(f"测试工具: {tool_name}")
        print(f"{'='*80}")
        
        result = test_scunet_denoising(noisy_image_path, original_image_path, tool_name)
        
        if result:
            results[tool_name] = result
        
        # 等待一下，避免 API 过载
        time.sleep(2)
    
    # 总结对比
    if results:
        print("\n" + "="*80)
        print("所有工具对比总结")
        print("="*80)
        
        print(f"\n{'工具名称':<35} | {'PSNR (dB)':<15} | {'SSIM':<15} | {'PSNR 改进':<15} | {'SSIM 改进':<15}")
        print("-" * 110)
        
        for tool_name, result in results.items():
            psnr_after = result['after']['psnr']
            ssim_after = result['after']['ssim']
            psnr_imp = result['improvement']['psnr']
            ssim_imp = result['improvement']['ssim']
            
            psnr_symbol = "↑" if psnr_imp > 0 else "↓"
            ssim_symbol = "↑" if ssim_imp > 0 else "↓"
            
            print(f"{tool_name:<35} | {psnr_after:>13.4f} | {ssim_after:>13.4f} | "
                  f"{psnr_symbol} {abs(psnr_imp):>11.4f} | {ssim_symbol} {abs(ssim_imp):>11.4f}")
        
        # 找出最佳工具
        best_psnr_tool = max(results.items(), key=lambda x: x[1]['after']['psnr'])
        best_ssim_tool = max(results.items(), key=lambda x: x[1]['after']['ssim'])
        
        print(f"\n🏆 最佳结果:")
        print(f"  PSNR 最高: {best_psnr_tool[0]} ({best_psnr_tool[1]['after']['psnr']:.4f} dB)")
        print(f"  SSIM 最高: {best_ssim_tool[0]} ({best_ssim_tool[1]['after']['ssim']:.4f})")
    
    print("\n" + "="*80)
    print("测试完成！")
    print(f"结果已保存到: /app/xiaominl/DeepEyes_v2/scunet_test_results/")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()

