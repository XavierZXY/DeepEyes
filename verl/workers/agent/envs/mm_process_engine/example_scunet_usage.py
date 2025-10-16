#!/usr/bin/env python3
"""
SCUNet 工具使用示例

这个脚本演示了如何在实际项目中使用 SCUNet 工具进行图像去噪。

注意: 此脚本需要 SCUNet 服务正在运行才能执行实际的去噪操作。
"""

import sys
sys.path.insert(0, '/app/xiaominl/DeepEyes_v2')

import os
import argparse
from PIL import Image
from verl.workers.agent.tool_envs import ToolBase


def example1_real_denoising_psnr():
    """
    示例 1: 使用真实图像去噪工具（PSNR优化版本）
    适用于真实拍摄的噪声图像，追求更高的 PSNR 指标
    """
    print("\n" + "="*60)
    print("示例 1: 真实图像去噪（PSNR优化）")
    print("="*60)
    
    # 1. 创建工具实例
    tool = ToolBase.create("scunet_real_denoising_psnr")
    print(f"✓ 工具已创建: {tool.name}")
    print(f"  任务类型: {tool.task_name}")
    print(f"  API 地址: {tool.api_url}")
    
    # 2. 准备测试数据（实际使用时替换为真实图像）
    import numpy as np
    test_img = np.random.randint(50, 200, (256, 256, 3), dtype=np.uint8)
    image = Image.fromarray(test_img)
    
    # 3. 准备提示词和数据
    prompt = [{"role": "user", "content": "Please denoise this noisy photograph."}]
    multi_modal_data = {"image": [image]}
    
    # 4. 重置工具状态
    tool.reset(raw_prompt=prompt, multi_modal_data=multi_modal_data)
    print("✓ 工具已重置")
    
    # 5. 构建工具调用字符串
    action_string = '''
<tool_call>
{"name": "scunet_real_denoising_psnr", "arguments": {}}
</tool_call>
'''
    
    # 6. 执行工具
    print("\n执行去噪操作...")
    obs, reward, done, info = tool.execute(action_string)
    
    # 7. 处理结果
    if info.get("status") == "success":
        print(f"✅ 去噪成功！")
        print(f"   执行时间: {info.get('execution_time')}")
        result_image = obs['multi_modal_data']['image'][0]
        print(f"   结果图像尺寸: {result_image.size}")
        # result_image.save("denoised_psnr.png")  # 保存结果
    else:
        print(f"❌ 去噪失败: {info.get('error')}")
    
    return info.get("status") == "success"


def example2_real_denoising_gan():
    """
    示例 2: 使用真实图像去噪工具（GAN版本）
    适用于真实拍摄的噪声图像，追求更好的视觉效果
    """
    print("\n" + "="*60)
    print("示例 2: 真实图像去噪（GAN版本）")
    print("="*60)
    
    tool = ToolBase.create("scunet_real_denoising_gan")
    print(f"✓ 工具已创建: {tool.name}")
    
    import numpy as np
    test_img = np.random.randint(50, 200, (256, 256, 3), dtype=np.uint8)
    image = Image.fromarray(test_img)
    
    prompt = [{"role": "user", "content": "Denoise this image for better visual quality."}]
    multi_modal_data = {"image": [image]}
    
    tool.reset(raw_prompt=prompt, multi_modal_data=multi_modal_data)
    
    action_string = '''
<tool_call>
{"name": "scunet_real_denoising_gan", "arguments": {}}
</tool_call>
'''
    
    print("\n执行去噪操作...")
    obs, reward, done, info = tool.execute(action_string)
    
    if info.get("status") == "success":
        print(f"✅ 去噪成功！")
        print(f"   执行时间: {info.get('execution_time')}")
        result_image = obs['multi_modal_data']['image'][0]
        print(f"   结果图像尺寸: {result_image.size}")
    else:
        print(f"❌ 去噪失败: {info.get('error')}")
    
    return info.get("status") == "success"


def example3_color_denoising_with_levels():
    """
    示例 3: 使用彩色图像去噪工具，测试不同噪声等级
    适用于已知噪声等级的彩色图像
    """
    print("\n" + "="*60)
    print("示例 3: 彩色图像去噪（不同噪声等级）")
    print("="*60)
    
    tool = ToolBase.create("scunet_color_denoising")
    print(f"✓ 工具已创建: {tool.name}")
    
    import numpy as np
    test_img = np.random.randint(50, 200, (256, 256, 3), dtype=np.uint8)
    image = Image.fromarray(test_img)
    
    prompt = [{"role": "user", "content": "Remove noise from this color image."}]
    multi_modal_data = {"image": [image]}
    
    # 测试不同的噪声等级
    noise_levels = [15, 25, 50]
    
    for noise_level in noise_levels:
        print(f"\n--- 测试噪声等级: {noise_level} ---")
        
        tool.reset(raw_prompt=prompt, multi_modal_data=multi_modal_data)
        
        action_string = f'''
<tool_call>
{{"name": "scunet_color_denoising", "arguments": {{"noise_level": {noise_level}}}}}
</tool_call>
'''
        
        print(f"执行去噪操作（噪声等级 {noise_level}）...")
        obs, reward, done, info = tool.execute(action_string)
        
        if info.get("status") == "success":
            print(f"✅ 去噪成功！噪声等级: {noise_level}")
            result_image = obs['multi_modal_data']['image'][0]
            # result_image.save(f"denoised_color_{noise_level}.png")
        else:
            print(f"❌ 去噪失败: {info.get('error')}")
    
    return True


def example4_gray_denoising():
    """
    示例 4: 使用灰度图像去噪工具
    适用于灰度图像的去噪
    """
    print("\n" + "="*60)
    print("示例 4: 灰度图像去噪")
    print("="*60)
    
    tool = ToolBase.create("scunet_gray_denoising")
    print(f"✓ 工具已创建: {tool.name}")
    
    import numpy as np
    # 创建灰度图像（但仍然使用 RGB 格式，服务端会转换）
    test_img = np.random.randint(50, 200, (256, 256, 3), dtype=np.uint8)
    image = Image.fromarray(test_img)
    
    prompt = [{"role": "user", "content": "Denoise this grayscale image."}]
    multi_modal_data = {"image": [image]}
    
    tool.reset(raw_prompt=prompt, multi_modal_data=multi_modal_data)
    
    action_string = '''
<tool_call>
{"name": "scunet_gray_denoising", "arguments": {"noise_level": 25}}
</tool_call>
'''
    
    print("\n执行去噪操作...")
    obs, reward, done, info = tool.execute(action_string)
    
    if info.get("status") == "success":
        print(f"✅ 去噪成功！")
        print(f"   执行时间: {info.get('execution_time')}")
        result_image = obs['multi_modal_data']['image'][0]
        print(f"   结果图像尺寸: {result_image.size}")
    else:
        print(f"❌ 去噪失败: {info.get('error')}")
    
    return info.get("status") == "success"


def example5_error_handling():
    """
    示例 5: 错误处理
    演示工具如何处理各种错误情况
    """
    print("\n" + "="*60)
    print("示例 5: 错误处理演示")
    print("="*60)
    
    tool = ToolBase.create("scunet_color_denoising")
    
    import numpy as np
    test_img = np.random.randint(50, 200, (256, 256, 3), dtype=np.uint8)
    image = Image.fromarray(test_img)
    
    prompt = [{"role": "user", "content": "Denoise this image."}]
    multi_modal_data = {"image": [image]}
    
    # 测试 1: 无效的 JSON 格式
    print("\n--- 测试 1: 无效的 JSON 格式 ---")
    tool.reset(raw_prompt=prompt, multi_modal_data=multi_modal_data)
    
    invalid_json = '''
<tool_call>
{invalid json here}
</tool_call>
'''
    
    obs, reward, done, info = tool.execute(invalid_json)
    print(f"结果: status={info.get('status')}, error={info.get('error', 'None')[:50]}...")
    
    # 测试 2: 错误的工具名称
    print("\n--- 测试 2: 错误的工具名称 ---")
    tool.reset(raw_prompt=prompt, multi_modal_data=multi_modal_data)
    
    wrong_tool = '''
<tool_call>
{"name": "wrong_tool_name", "arguments": {}}
</tool_call>
'''
    
    obs, reward, done, info = tool.execute(wrong_tool)
    print(f"结果: status={info.get('status')}, error={info.get('error', 'None')[:50]}...")
    
    # 测试 3: 无效的噪声等级（应该自动回退到默认值）
    print("\n--- 测试 3: 无效的噪声等级 ---")
    tool.reset(raw_prompt=prompt, multi_modal_data=multi_modal_data)
    
    invalid_noise = '''
<tool_call>
{"name": "scunet_color_denoising", "arguments": {"noise_level": 999}}
</tool_call>
'''
    
    print("注意: 这个应该会自动回退到默认值 25")
    obs, reward, done, info = tool.execute(invalid_noise)
    print(f"结果: status={info.get('status')}")
    
    return True


def example6_from_file(image_path: str):
    """
    示例 6: 从文件读取图像并去噪
    
    Args:
        image_path: 图像文件路径
    """
    print("\n" + "="*60)
    print("示例 6: 从文件读取图像")
    print("="*60)
    
    if not os.path.exists(image_path):
        print(f"❌ 文件不存在: {image_path}")
        print("使用测试图像代替...")
        import numpy as np
        test_img = np.random.randint(50, 200, (256, 256, 3), dtype=np.uint8)
        image = Image.fromarray(test_img)
    else:
        print(f"✓ 读取图像: {image_path}")
        image = Image.open(image_path)
    
    print(f"  图像尺寸: {image.size}")
    print(f"  图像模式: {image.mode}")
    
    # 使用真实图像去噪（GAN版本）获得最佳视觉效果
    tool = ToolBase.create("scunet_real_denoising_gan")
    
    prompt = [{"role": "user", "content": "Please denoise this image."}]
    multi_modal_data = {"image": [image]}
    
    tool.reset(raw_prompt=prompt, multi_modal_data=multi_modal_data)
    
    action_string = '''
<tool_call>
{"name": "scunet_real_denoising_gan", "arguments": {}}
</tool_call>
'''
    
    print("\n执行去噪操作...")
    obs, reward, done, info = tool.execute(action_string)
    
    if info.get("status") == "success":
        print(f"✅ 去噪成功！")
        result_image = obs['multi_modal_data']['image'][0]
        
        # 保存结果
        output_path = image_path.replace('.', '_denoised.')
        result_image.save(output_path)
        print(f"✓ 结果已保存: {output_path}")
    else:
        print(f"❌ 去噪失败: {info.get('error')}")
    
    return info.get("status") == "success"


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='SCUNet 工具使用示例')
    parser.add_argument('--example', type=int, choices=[1,2,3,4,5,6], 
                        help='运行指定的示例（1-6）')
    parser.add_argument('--all', action='store_true', 
                        help='运行所有示例（不包括示例6）')
    parser.add_argument('--image', type=str, 
                        help='用于示例6的图像文件路径')
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("SCUNet 工具使用示例")
    print("="*60)
    print("\n注意: 这些示例需要 SCUNet 服务运行在 http://{TOOL_SERVICE_IP}:5008")
    print("      如果服务未运行，工具调用将会失败。")
    
    if args.all:
        print("\n运行所有示例...")
        example1_real_denoising_psnr()
        example2_real_denoising_gan()
        example3_color_denoising_with_levels()
        example4_gray_denoising()
        example5_error_handling()
    elif args.example == 1:
        example1_real_denoising_psnr()
    elif args.example == 2:
        example2_real_denoising_gan()
    elif args.example == 3:
        example3_color_denoising_with_levels()
    elif args.example == 4:
        example4_gray_denoising()
    elif args.example == 5:
        example5_error_handling()
    elif args.example == 6:
        if args.image:
            example6_from_file(args.image)
        else:
            print("错误: 示例6需要 --image 参数")
    else:
        # 默认运行示例1
        print("\n未指定示例，运行示例1...")
        print("使用 --help 查看所有选项\n")
        example1_real_denoising_psnr()
    
    print("\n" + "="*60)
    print("示例完成")
    print("="*60)


if __name__ == "__main__":
    main()

