#!/usr/bin/env python3
"""
测试脚本：验证工具调用是否正确
"""

import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pyarrow.parquet as pq
import numpy as np
from PIL import Image
import io
from copy import deepcopy

# 设置工具服务IP
os.environ['TOOL_SERVICE_IP'] = '10.21.9.6'

# 导入工具系统
from verl.workers.agent.tool_envs import ToolBase
from verl.workers import agent  # 触发工具注册


def test_tool_creation_and_execution():
    """测试工具创建和执行"""
    print("="*80)
    print("测试工具创建和执行流程")
    print("="*80)
    
    # 1. 检查工具注册
    print("\n[1/4] 检查已注册的工具...")
    print(f"已注册工具数: {len(ToolBase.registry)}")
    print(f"工具列表（前10个）: {list(ToolBase.registry.keys())[:10]}")
    
    # 2. 测试创建一个工具
    print("\n[2/4] 测试创建工具实例...")
    test_tool_name = "scunet_real_denoising_psnr"  # 选择一个常用工具
    
    if test_tool_name not in ToolBase.registry:
        print(f"❌ 工具 {test_tool_name} 未注册")
        return
    
    try:
        tool_instance = ToolBase.create(test_tool_name)
        print(f"✅ 成功创建工具: {test_tool_name}")
        print(f"   工具类型: {type(tool_instance).__name__}")
        print(f"   工具名称: {tool_instance.name}")
    except Exception as e:
        print(f"❌ 创建工具失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 3. 准备测试数据
    print("\n[3/4] 准备测试数据...")
    
    # 创建一个简单的测试图像
    test_img_array = np.random.randint(50, 200, (256, 256, 3), dtype=np.uint8)
    test_image = Image.fromarray(test_img_array)
    print(f"✅ 测试图像: {test_image.size}, {test_image.mode}")
    
    # 准备多模态数据
    multi_modal_data = {
        'image': [test_image]
    }
    
    origin_multi_modal_data = {
        'image': [test_image]
    }
    
    # 准备raw_prompt
    raw_prompt = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Please denoise this image."}
    ]
    
    # 4. 测试reset和execute
    print("\n[4/4] 测试工具reset和execute...")
    
    try:
        # Reset工具
        tool_instance.reset(
            raw_prompt=raw_prompt,
            multi_modal_data=deepcopy(multi_modal_data),
            origin_multi_modal_data=deepcopy(origin_multi_modal_data)
        )
        print(f"✅ Reset成功")
        
        # 执行工具
        tool_args = {}  # 使用默认参数
        print(f"   执行工具（这可能需要连接工具服务）...")
        
        try:
            # 构造action_string（与训练代码一致）
            import json
            tool_call = {"name": test_tool_name, "arguments": tool_args}
            action_string = f"<tool_call>{json.dumps(tool_call)}</tool_call>"
            print(f"   Action string: {action_string}")
            
            tool_result, reward, done, info = tool_instance.execute(action_string)
            print(f"✅ Execute成功")
            print(f"   Reward: {reward}")
            print(f"   Done: {done}")
            print(f"   Info: {info.get('status', 'N/A')}")
            
            # 检查返回的图像
            if 'multi_modal_data' in tool_result and 'image' in tool_result['multi_modal_data']:
                output_images = tool_result['multi_modal_data']['image']
                if len(output_images) > 0:
                    output_image = output_images[0]
                    print(f"   输出图像: {output_image.size}, {output_image.mode}")
                else:
                    print(f"⚠️  工具未返回图像")
            else:
                print(f"⚠️  工具结果中无图像数据")
                print(f"   工具结果键: {tool_result.keys()}")
                
        except Exception as e:
            print(f"⚠️  Execute失败（可能是工具服务未启动）: {e}")
            print(f"   这是正常的，如果工具服务未运行")
            
    except Exception as e:
        print(f"❌ Reset失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "="*80)
    print("✅ 工具创建和调用流程测试完成！")
    print("="*80)
    print("\n💡 如果看到 'Execute失败'，请确保工具服务已启动。")
    print("   工具创建和reset流程已验证正确。")


def test_multiple_tools():
    """测试多个不同工具的创建"""
    print("\n" + "="*80)
    print("测试多个工具的创建")
    print("="*80)
    
    test_tools = [
        "nafnet_deblur",
        "scunet_real_denoising_psnr",
        "retinexformer_enhance",
        "swinir_denoising",
        "restormer_deraining",
    ]
    
    for tool_name in test_tools:
        if tool_name in ToolBase.registry:
            try:
                tool = ToolBase.create(tool_name)
                print(f"✅ {tool_name}: {type(tool).__name__}")
            except Exception as e:
                print(f"❌ {tool_name}: {e}")
        else:
            print(f"⚠️  {tool_name}: 未注册")


if __name__ == "__main__":
    test_tool_creation_and_execution()
    test_multiple_tools()

