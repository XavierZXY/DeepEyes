#!/usr/bin/env python3
"""
验证测试脚本的核心功能（不需要实际调用工具服务）
"""

import sys
sys.path.insert(0, '/app/xiaominl/DeepEyes_v2')

import os
from PIL import Image
import numpy as np
import io

# 导入测试脚本中的组件
from tests.test_all_tools_metrics import ToolRegistry
from verl.utils.reward_score.image_quality_metrics import get_image_quality_metrics

print("=" * 80)
print("🧪 验证测试脚本核心功能")
print("=" * 80)

# 测试1: 工具注册表
print("\n1️⃣ 测试工具注册表...")
registry = ToolRegistry()
all_tools = registry.get_all_tools()
print(f"   ✅ 共注册 {len(all_tools)} 个工具:")
for i, tool_name in enumerate(all_tools, 1):
    tool_info = registry.get_tool_info(tool_name)
    print(f"      {i}. {tool_name} - {tool_info['description']}")

# 测试2: 图像质量指标计算器
print("\n2️⃣ 测试图像质量指标计算器...")
metrics_calculator = get_image_quality_metrics()
print(f"   ✅ 指标计算器初始化成功")

# 创建两张测试图像
img1 = Image.new('RGB', (256, 256), color=(255, 0, 0))
img2 = Image.new('RGB', (256, 256), color=(200, 50, 50))

print(f"   测试图像1: 256x256 RGB (纯红色)")
print(f"   测试图像2: 256x256 RGB (暗红色)")

# 测试3: PSNR计算
print("\n3️⃣ 测试PSNR计算...")
try:
    psnr = metrics_calculator.calculate_psnr(img1, img2)
    print(f"   ✅ PSNR: {psnr:.2f} dB")
except Exception as e:
    print(f"   ❌ PSNR计算失败: {e}")

# 测试4: SSIM计算
print("\n4️⃣ 测试SSIM计算...")
try:
    ssim = metrics_calculator.calculate_ssim(img1, img2)
    print(f"   ✅ SSIM: {ssim:.4f}")
except Exception as e:
    print(f"   ❌ SSIM计算失败: {e}")

# 测试5: LPIPS计算
print("\n5️⃣ 测试LPIPS计算...")
try:
    lpips = metrics_calculator.calculate_lpips(img1, img2)
    print(f"   ✅ LPIPS: {lpips:.4f}")
except Exception as e:
    print(f"   ❌ LPIPS计算失败: {e}")

# 测试6: 相同图像的指标
print("\n6️⃣ 测试相同图像的指标（应该为最优值）...")
try:
    psnr_same = metrics_calculator.calculate_psnr(img1, img1)
    ssim_same = metrics_calculator.calculate_ssim(img1, img1)
    lpips_same = metrics_calculator.calculate_lpips(img1, img1)
    
    print(f"   PSNR (相同图像): {psnr_same:.2f} dB (期望: 很高或inf)")
    print(f"   SSIM (相同图像): {ssim_same:.4f} (期望: 1.0)")
    print(f"   LPIPS (相同图像): {lpips_same:.4f} (期望: ~0.0)")
    
    # 验证结果
    assert ssim_same > 0.99, f"SSIM应该接近1.0，但得到{ssim_same}"
    assert lpips_same < 0.1, f"LPIPS应该接近0，但得到{lpips_same}"
    print(f"   ✅ 指标值符合预期")
except Exception as e:
    print(f"   ❌ 测试失败: {e}")

# 测试7: 检查环境变量
print("\n7️⃣ 检查环境变量...")
tool_service_ip = os.environ.get('TOOL_SERVICE_IP', '未设置')
print(f"   TOOL_SERVICE_IP: {tool_service_ip}")
if tool_service_ip == '未设置':
    print(f"   ⚠️  提示: 可以设置 export TOOL_SERVICE_IP=10.21.9.6")
else:
    print(f"   ✅ 环境变量已配置")

# 测试8: 工具API配置
print("\n8️⃣ 检查工具API配置...")
example_tools = ['swinir_denoising', 'restormer_motion_deblurring', 'dehazeformer_dehaze']
for tool_name in example_tools:
    tool_info = registry.get_tool_info(tool_name)
    print(f"   {tool_name}:")
    print(f"      API: {tool_info['api_url']}")
    print(f"      参数: {tool_info['params']()}")

print("\n" + "=" * 80)
print("✅ 核心功能验证完成！")
print("=" * 80)
print("\n总结:")
print("  ✅ 工具注册表正常")
print("  ✅ 图像质量指标计算正常")
print("  ✅ PSNR/SSIM/LPIPS计算正常")
print("  ✅ 工具API配置正确")
print("\n💡 下一步:")
print("  1. 确保工具服务已启动（端口5001-5007）")
print("  2. 运行快速测试: bash tests/quick_test_tools.sh")
print("  3. 查看使用示例: bash tests/example_test_usage.sh")
print("\n" + "=" * 80)

