#!/usr/bin/env python3
"""
测试SCUNet和Retinexformer工具是否已添加到格式检查的允许工具列表中
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verl.utils.reward_score.image_restoration import (
    check_multiturn_format_v2,
    check_response_format_strict_v2,
    check_response_format_v2
)


def test_scunet_tools():
    """测试SCUNet工具是否在允许列表中"""
    print("\n" + "="*70)
    print("测试 SCUNet 工具")
    print("="*70)
    
    scunet_tools = [
        "scunet_real_denoising_psnr",
        "scunet_real_denoising_gan",
        "scunet_color_denoising",
        "scunet_gray_denoising",
    ]
    
    for tool_name in scunet_tools:
        # 测试严格格式检查（多轮）
        test_response = f"""<think>Image has noise artifacts that need to be removed.</think>
<tool_call>
[
  {{"name": "{tool_name}", "arguments": {{"noise_level": 25}}}}
]
</tool_call>"""
        
        result = check_multiturn_format_v2(test_response, is_clean_sample=False)
        status = "✅ PASS" if result == 1.0 else "❌ FAIL"
        print(f"{status} - {tool_name}: format_score={result}")
        
        if result != 1.0:
            print(f"  Error: Tool {tool_name} should be allowed but got score {result}")
            return False
    
    print("\n所有 SCUNet 工具测试通过！")
    return True


def test_retinexformer_tools():
    """测试Retinexformer工具是否在允许列表中"""
    print("\n" + "="*70)
    print("测试 Retinexformer 工具")
    print("="*70)
    
    retinexformer_tools = [
        "retinexformer_enhance",
        "retinexformer_lol_v1",
        "retinexformer_lol_v2_real",
        "retinexformer_lol_v2_synthetic",
        "retinexformer_sdsd_indoor",
        "retinexformer_sdsd_outdoor",
        "retinexformer_sid",
        "retinexformer_smid",
        "retinexformer_fivek",
    ]
    
    for tool_name in retinexformer_tools:
        # 测试严格格式检查（多轮）
        test_response = f"""<think>Image is too dark and needs low-light enhancement.</think>
<tool_call>
[
  {{"name": "{tool_name}", "arguments": {{"task": "LOL_v2_real"}}}}
]
</tool_call>"""
        
        result = check_multiturn_format_v2(test_response, is_clean_sample=False)
        status = "✅ PASS" if result == 1.0 else "❌ FAIL"
        print(f"{status} - {tool_name}: format_score={result}")
        
        if result != 1.0:
            print(f"  Error: Tool {tool_name} should be allowed but got score {result}")
            return False
    
    print("\n所有 Retinexformer 工具测试通过！")
    return True


def test_invalid_tool():
    """测试不在允许列表中的工具会被拒绝"""
    print("\n" + "="*70)
    print("测试无效工具（应该被拒绝）")
    print("="*70)
    
    invalid_tool_name = "nonexistent_tool_12345"
    test_response = f"""<think>This should fail because the tool is not in the allowed list.</think>
<tool_call>
[
  {{"name": "{invalid_tool_name}", "arguments": {{}}}}
]
</tool_call>"""
    
    result = check_multiturn_format_v2(test_response, is_clean_sample=False)
    status = "✅ PASS" if result == -1.0 else "❌ FAIL"
    print(f"{status} - {invalid_tool_name}: format_score={result} (应该是-1.0)")
    
    if result != -1.0:
        print(f"  Error: Invalid tool should be rejected but got score {result}")
        return False
    
    print("\n无效工具正确被拒绝！")
    return True


def test_gradual_format_checker():
    """测试渐进式格式检查器也包含新工具"""
    print("\n" + "="*70)
    print("测试渐进式格式检查器")
    print("="*70)
    
    # 测试一个SCUNet工具
    test_response = """<think>Image has high noise level that needs SCUNet processing.</think>
<tool_call>
[
  {"name": "scunet_color_denoising", "arguments": {"noise_level": 50}}
]
</tool_call>"""
    
    result = check_response_format_v2(test_response)
    status = "✅ PASS" if result > 0.5 else "❌ FAIL"
    print(f"{status} - scunet_color_denoising (gradual): format_score={result:.2f}")
    
    # 测试一个Retinexformer工具
    test_response2 = """<think>Image is very dark and requires low-light enhancement using Retinexformer.</think>
<tool_call>
[
  {"name": "retinexformer_enhance", "arguments": {"task": "LOL_v2_real"}}
]
</tool_call>"""
    
    result2 = check_response_format_v2(test_response2)
    status2 = "✅ PASS" if result2 > 0.5 else "❌ FAIL"
    print(f"{status2} - retinexformer_enhance (gradual): format_score={result2:.2f}")
    
    if result > 0.5 and result2 > 0.5:
        print("\n渐进式格式检查器测试通过！")
        return True
    else:
        print("\n渐进式格式检查器测试失败！")
        return False


def test_strict_format_checker():
    """测试严格格式检查器也包含新工具"""
    print("\n" + "="*70)
    print("测试严格格式检查器")
    print("="*70)
    
    # 测试一个SCUNet工具
    test_response = """<think>Real-world noise detected, using SCUNet GAN version for better visual quality.</think>
<tool_call>
[
  {"name": "scunet_real_denoising_gan", "arguments": {}}
]
</tool_call>"""
    
    result = check_response_format_strict_v2(test_response, content_aware=False)
    status = "✅ PASS" if result == 1.0 else "❌ FAIL"
    print(f"{status} - scunet_real_denoising_gan (strict): format_score={result}")
    
    # 测试一个Retinexformer工具
    test_response2 = """<think>Extremely dark scene requiring SID model for low-light enhancement.</think>
<tool_call>
[
  {"name": "retinexformer_sid", "arguments": {}}
]
</tool_call>"""
    
    result2 = check_response_format_strict_v2(test_response2, content_aware=False)
    status2 = "✅ PASS" if result2 == 1.0 else "❌ FAIL"
    print(f"{status2} - retinexformer_sid (strict): format_score={result2}")
    
    if result == 1.0 and result2 == 1.0:
        print("\n严格格式检查器测试通过！")
        return True
    else:
        print("\n严格格式检查器测试失败！")
        return False


def main():
    print("\n" + "="*70)
    print("开始测试新工具是否已添加到格式检查允许列表")
    print("="*70)
    
    all_passed = True
    
    # 测试SCUNet工具
    if not test_scunet_tools():
        all_passed = False
    
    # 测试Retinexformer工具
    if not test_retinexformer_tools():
        all_passed = False
    
    # 测试无效工具被拒绝
    if not test_invalid_tool():
        all_passed = False
    
    # 测试渐进式格式检查器
    if not test_gradual_format_checker():
        all_passed = False
    
    # 测试严格格式检查器
    if not test_strict_format_checker():
        all_passed = False
    
    # 总结
    print("\n" + "="*70)
    if all_passed:
        print("🎉 所有测试通过！SCUNet和Retinexformer工具已成功添加到允许列表！")
        print("="*70)
        
        # 打印工具清单
        print("\n新增工具清单:")
        print("\nSCUNet 工具 (4个):")
        print("  1. scunet_real_denoising_psnr - 真实图像去噪(PSNR优化)")
        print("  2. scunet_real_denoising_gan - 真实图像去噪(GAN版本)")
        print("  3. scunet_color_denoising - 彩色图像去噪(支持15/25/50噪声等级)")
        print("  4. scunet_gray_denoising - 灰度图像去噪(支持15/25/50噪声等级)")
        
        print("\nRetinexformer 工具 (9个):")
        print("  1. retinexformer_enhance - 通用低光增强(推荐)")
        print("  2. retinexformer_lol_v1 - LOL-v1数据集模型")
        print("  3. retinexformer_lol_v2_real - LOL-v2真实场景模型")
        print("  4. retinexformer_lol_v2_synthetic - LOL-v2合成数据模型")
        print("  5. retinexformer_sdsd_indoor - SDSD室内静态场景模型")
        print("  6. retinexformer_sdsd_outdoor - SDSD室外静态场景模型")
        print("  7. retinexformer_sid - SID数据集模型")
        print("  8. retinexformer_smid - SMID静态多场景模型")
        print("  9. retinexformer_fivek - MIT Adobe FiveK模型")
        
        print("\n总计新增: 13个工具")
        print("="*70)
        return 0
    else:
        print("❌ 部分测试失败！请检查上面的错误信息。")
        print("="*70)
        return 1


if __name__ == "__main__":
    sys.exit(main())

