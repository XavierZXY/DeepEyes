#!/usr/bin/env python3
"""
MPRNet工具箱演示脚本

该脚本展示如何使用MPRNet工具箱进行图像修复任务：
- 去噪 (mprnet_denoising)
- 去雨 (mprnet_deraining) 
- 运动去模糊 (mprnet_motion_deblurring)

使用方法:
    python examples/mprnet_demo.py [--test-mode]
    
参数:
    --test-mode: 仅测试工具注册，不实际调用API
"""

import sys
import os
import numpy as np
from PIL import Image
import argparse

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from verl.workers.agent.tool_envs import ToolBase
from verl.workers.agent.envs.mm_process_engine.MPRNetToolbox import (
    MPRNetDenoisingToolbox, 
    MPRNetDeraininingToolbox, 
    MPRNetMotionDeblurringToolbox
)

def create_test_image(size=(256, 256)):
    """创建一个测试图像"""
    # 创建一个带有一些结构的测试图像
    img_array = np.random.randint(50, 200, (*size, 3), dtype=np.uint8)
    
    # 添加一些结构化内容
    h, w = size
    img_array[h//4:3*h//4, w//4:3*w//4] = [100, 150, 200]  # 中心矩形
    img_array[h//2-10:h//2+10, :] = [255, 255, 255]        # 水平线
    img_array[:, w//2-10:w//2+10] = [255, 255, 255]        # 垂直线
    
    return Image.fromarray(img_array)

def test_tool_registration():
    """测试工具注册"""
    print("\n=== 测试MPRNet工具注册 ===")
    registered_tools = list(ToolBase.registry.keys())
    
    mprnet_tools = [
        "mprnet_denoising",
        "mprnet_deraining", 
        "mprnet_motion_deblurring"
    ]
    
    print(f"注册的工具总数: {len(registered_tools)}")
    print(f"所有注册的工具: {registered_tools}")
    
    for tool_name in mprnet_tools:
        if tool_name in registered_tools:
            print(f"✅ {tool_name} - 已注册")
        else:
            print(f"❌ {tool_name} - 未注册")
            
    return all(tool in registered_tools for tool in mprnet_tools)

def test_tool_execution(tool_name, test_image, test_mode=False):
    """测试单个工具的执行"""
    print(f"\n=== 测试 {tool_name} ===")
    
    try:
        # 创建工具实例
        tool = ToolBase.create(tool_name)
        print(f"✅ 工具 {tool_name} 创建成功")
        
        # 准备初始数据
        initial_prompt = [{"role": "user", "content": "Please enhance this image."}]
        initial_data = {"image": [test_image]}
        
        # 重置工具状态
        tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
        print(f"✅ 工具状态重置成功")
        
        if test_mode:
            print(f"🧪 测试模式：跳过实际API调用")
            return True
        
        # 准备工具调用字符串
        action_string = f'''<tool_call>
{{"name": "{tool_name}", "arguments": {{}}}}
</tool_call>'''
        
        print(f"🚀 开始执行工具调用...")
        
        # 执行工具
        obs, reward, done, info = tool.execute(action_string)
        
        if info.get("status") == "success":
            print(f"✅ {tool_name} 执行成功!")
            print(f"   奖励: {reward}")
            print(f"   执行时间: {info.get('execution_time', 'N/A')}")
            
            # 检查输出图像
            if isinstance(obs, dict) and 'multi_modal_data' in obs:
                processed_image = obs['multi_modal_data']['image'][0]
                print(f"   输出图像尺寸: {processed_image.size}")
                return True
            else:
                print(f"   警告: 输出格式异常")
                return False
        else:
            print(f"❌ {tool_name} 执行失败: {info.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ {tool_name} 测试出错: {str(e)}")
        if "Failed to connect" in str(e) or "SERVICE UNAVAILABLE" in str(e):
            print(f"   💡 提示: 这可能是因为MPRNet API服务未运行")
        return False

def main():
    parser = argparse.ArgumentParser(description='MPRNet工具箱演示')
    parser.add_argument('--test-mode', action='store_true', 
                       help='仅测试工具注册，不实际调用API')
    args = parser.parse_args()
    
    print("🚀 MPRNet工具箱演示")
    print("=" * 50)
    
    # 1. 测试工具注册
    if not test_tool_registration():
        print("❌ 工具注册测试失败，退出")
        sys.exit(1)
    
    print("\n✅ 所有MPRNet工具注册成功!")
    
    if args.test_mode:
        print("\n🧪 测试模式：跳过API调用测试")
        return
    
    # 2. 创建测试图像
    print("\n=== 创建测试图像 ===")
    test_image = create_test_image()
    print(f"✅ 测试图像创建成功，尺寸: {test_image.size}")
    
    # 3. 测试各个工具
    tools_to_test = [
        "mprnet_denoising",
        "mprnet_deraining", 
        "mprnet_motion_deblurring"
    ]
    
    results = {}
    for tool_name in tools_to_test:
        success = test_tool_execution(tool_name, test_image, args.test_mode)
        results[tool_name] = success
    
    # 4. 总结结果
    print("\n" + "=" * 50)
    print("🎯 测试结果总结:")
    
    for tool_name, success in results.items():
        status = "✅ 成功" if success else "❌ 失败"
        print(f"   {tool_name}: {status}")
    
    successful_count = sum(results.values())
    total_count = len(results)
    
    print(f"\n📊 成功率: {successful_count}/{total_count} ({100*successful_count/total_count:.1f}%)")
    
    if successful_count == total_count:
        print("🎉 所有工具测试通过!")
    else:
        print("⚠️  部分工具测试失败，请检查MPRNet API服务状态")

if __name__ == "__main__":
    main()
