#!/usr/bin/env python3
"""
SCUNet Toolbox 测试脚本
测试工具注册、参数构建等功能（不实际调用API）
"""

import sys
sys.path.insert(0, '/app/xiaominl/DeepEyes_v2')

import numpy as np
from PIL import Image
from verl.workers.agent.tool_envs import ToolBase
from verl.workers.agent.envs.mm_process_engine.SCUNetToolbox import (
    SCUNetRealDenoisingPSNRToolbox,
    SCUNetRealDenoisingGANToolbox,
    SCUNetColorDenoisingToolbox,
    SCUNetGrayDenoisingToolbox
)


def test_tool_registration():
    """测试工具是否正确注册"""
    print("\n" + "="*60)
    print("测试 1: 工具注册")
    print("="*60)
    
    registered_tools = list(ToolBase.registry.keys())
    print(f"总共注册了 {len(registered_tools)} 个工具")
    
    scunet_tools = [
        'scunet_real_denoising_psnr',
        'scunet_real_denoising_gan',
        'scunet_color_denoising',
        'scunet_gray_denoising'
    ]
    
    all_passed = True
    for tool_name in scunet_tools:
        if tool_name in registered_tools:
            print(f"  ✓ {tool_name} 已注册")
        else:
            print(f"  ✗ {tool_name} 未注册")
            all_passed = False
    
    return all_passed


def test_tool_creation():
    """测试工具创建和基本属性"""
    print("\n" + "="*60)
    print("测试 2: 工具创建和属性")
    print("="*60)
    
    test_cases = [
        ("scunet_real_denoising_psnr", "real_denoising_psnr", "SCUNetRealDenoisingPSNRToolbox"),
        ("scunet_real_denoising_gan", "real_denoising_gan", "SCUNetRealDenoisingGANToolbox"),
        ("scunet_color_denoising", "color_denoising_25", "SCUNetColorDenoisingToolbox"),
        ("scunet_gray_denoising", "gray_denoising_25", "SCUNetGrayDenoisingToolbox"),
    ]
    
    all_passed = True
    for tool_name, expected_task, expected_class in test_cases:
        try:
            tool = ToolBase.create(tool_name)
            
            # 检查类名
            if tool.__class__.__name__ == expected_class:
                print(f"  ✓ {tool_name}: 类名正确 ({expected_class})")
            else:
                print(f"  ✗ {tool_name}: 类名错误 (期望: {expected_class}, 实际: {tool.__class__.__name__})")
                all_passed = False
            
            # 检查任务名
            if tool.task_name == expected_task:
                print(f"    ✓ 任务名正确: {expected_task}")
            else:
                print(f"    ✗ 任务名错误 (期望: {expected_task}, 实际: {tool.task_name})")
                all_passed = False
            
            # 检查 API URL
            if "5008" in tool.api_url:
                print(f"    ✓ API URL 正确: {tool.api_url}")
            else:
                print(f"    ✗ API URL 错误: {tool.api_url}")
                all_passed = False
                
        except Exception as e:
            print(f"  ✗ {tool_name}: 创建失败 - {e}")
            all_passed = False
    
    return all_passed


def test_parameter_building():
    """测试参数构建"""
    print("\n" + "="*60)
    print("测试 3: 参数构建")
    print("="*60)
    
    all_passed = True
    
    # 测试真实图像去噪（PSNR）
    try:
        tool = ToolBase.create("scunet_real_denoising_psnr")
        params = tool.build_params({})
        expected = {"task": "real_denoising_psnr", "format": "base64"}
        if params == expected:
            print(f"  ✓ scunet_real_denoising_psnr: 参数正确 {params}")
        else:
            print(f"  ✗ scunet_real_denoising_psnr: 参数错误")
            print(f"    期望: {expected}")
            print(f"    实际: {params}")
            all_passed = False
    except Exception as e:
        print(f"  ✗ scunet_real_denoising_psnr: {e}")
        all_passed = False
    
    # 测试真实图像去噪（GAN）
    try:
        tool = ToolBase.create("scunet_real_denoising_gan")
        params = tool.build_params({})
        expected = {"task": "real_denoising_gan", "format": "base64"}
        if params == expected:
            print(f"  ✓ scunet_real_denoising_gan: 参数正确 {params}")
        else:
            print(f"  ✗ scunet_real_denoising_gan: 参数错误")
            all_passed = False
    except Exception as e:
        print(f"  ✗ scunet_real_denoising_gan: {e}")
        all_passed = False
    
    # 测试彩色图像去噪（不同噪声等级）
    try:
        tool = ToolBase.create("scunet_color_denoising")
        
        # 测试默认参数
        params = tool.build_params({})
        if params["task"] == "color_denoising_25":
            print(f"  ✓ scunet_color_denoising (默认): {params}")
        else:
            print(f"  ✗ scunet_color_denoising (默认): 参数错误 {params}")
            all_passed = False
        
        # 测试不同噪声等级
        for noise_level in [15, 25, 50]:
            params = tool.build_params({"noise_level": noise_level})
            expected_task = f"color_denoising_{noise_level}"
            if params["task"] == expected_task:
                print(f"  ✓ scunet_color_denoising (noise={noise_level}): {params}")
            else:
                print(f"  ✗ scunet_color_denoising (noise={noise_level}): 参数错误 {params}")
                all_passed = False
        
        # 测试无效噪声等级（应该回退到默认值）
        params = tool.build_params({"noise_level": 100})
        if params["task"] == "color_denoising_25":
            print(f"  ✓ scunet_color_denoising (无效noise=100, 回退到25): {params}")
        else:
            print(f"  ✗ scunet_color_denoising (无效noise=100): 参数错误 {params}")
            all_passed = False
            
    except Exception as e:
        print(f"  ✗ scunet_color_denoising: {e}")
        all_passed = False
    
    # 测试灰度图像去噪
    try:
        tool = ToolBase.create("scunet_gray_denoising")
        
        # 测试不同噪声等级
        for noise_level in [15, 25, 50]:
            params = tool.build_params({"noise_level": noise_level})
            expected_task = f"gray_denoising_{noise_level}"
            if params["task"] == expected_task:
                print(f"  ✓ scunet_gray_denoising (noise={noise_level}): {params}")
            else:
                print(f"  ✗ scunet_gray_denoising (noise={noise_level}): 参数错误 {params}")
                all_passed = False
                
    except Exception as e:
        print(f"  ✗ scunet_gray_denoising: {e}")
        all_passed = False
    
    return all_passed


def test_reset_functionality():
    """测试 reset 功能"""
    print("\n" + "="*60)
    print("测试 4: Reset 功能")
    print("="*60)
    
    all_passed = True
    
    try:
        # 创建测试图像
        test_img_array = np.random.randint(0, 200, (128, 128, 3), dtype=np.uint8)
        test_image = Image.fromarray(test_img_array)
        
        initial_prompt = [{"role": "user", "content": "Please denoise this image."}]
        initial_data = {"image": [test_image]}
        
        # 测试每个工具的 reset
        for tool_name in ['scunet_real_denoising_psnr', 'scunet_color_denoising']:
            tool = ToolBase.create(tool_name)
            tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
            
            if tool.multi_modal_data is not None and 'image' in tool.multi_modal_data:
                print(f"  ✓ {tool_name}: reset 成功")
            else:
                print(f"  ✗ {tool_name}: reset 失败")
                all_passed = False
                
    except Exception as e:
        print(f"  ✗ Reset 测试失败: {e}")
        all_passed = False
    
    return all_passed


def test_action_parsing():
    """测试 action 字符串解析"""
    print("\n" + "="*60)
    print("测试 5: Action 字符串解析")
    print("="*60)
    
    all_passed = True
    
    try:
        tool = ToolBase.create("scunet_real_denoising_psnr")
        
        # 测试 tool_call 提取
        action_string = """
<tool_call>
{"name": "scunet_real_denoising_psnr", "arguments": {}}
</tool_call>
"""
        action = tool.extract_action(action_string)
        if action and "scunet_real_denoising_psnr" in action:
            print(f"  ✓ 成功提取 tool_call")
        else:
            print(f"  ✗ tool_call 提取失败")
            all_passed = False
        
        # 测试 answer 提取
        answer_string = "<answer>This image has been denoised.</answer>"
        answer = tool.extract_answer(answer_string)
        if answer and "denoised" in answer:
            print(f"  ✓ 成功提取 answer")
        else:
            print(f"  ✗ answer 提取失败")
            all_passed = False
            
    except Exception as e:
        print(f"  ✗ Action 解析测试失败: {e}")
        all_passed = False
    
    return all_passed


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("SCUNet Toolbox 测试套件")
    print("="*60)
    
    results = []
    
    # 运行所有测试
    results.append(("工具注册", test_tool_registration()))
    results.append(("工具创建", test_tool_creation()))
    results.append(("参数构建", test_parameter_building()))
    results.append(("Reset功能", test_reset_functionality()))
    results.append(("Action解析", test_action_parsing()))
    
    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {status}: {test_name}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ 所有测试通过！")
    else:
        print("❌ 部分测试失败")
    print("="*60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

