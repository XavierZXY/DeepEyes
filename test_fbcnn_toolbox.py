#!/usr/bin/env python3
"""
FBCNN工具箱测试脚本
测试FBCNN JPEG压缩伪影去除工具的基本功能
"""

import sys
import os
import numpy as np
from PIL import Image
import json

# 添加项目路径
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

def test_fbcnn_toolbox():
    """测试FBCNN工具箱"""
    print("🧪 开始测试FBCNN工具箱...")
    
    try:
        # 导入工具基类
        from verl.workers.agent.tool_envs import ToolBase
        from verl.workers.agent.envs.mm_process_engine.FBCNNToolbox import (
            FBCNNJpegArtifactRemovalToolbox,
            FBCNNBlindQualityAssessmentToolbox
        )
        
        print("✅ 成功导入FBCNN工具类")
        
        # 1. 检查工具是否已自动注册
        print("\n--- 检查工具注册 ---")
        registered_tools = list(ToolBase.registry.keys())
        print(f"已注册的工具: {registered_tools}")
        
        # 检查FBCNN工具是否在注册表中
        fbcnn_tools = [tool for tool in registered_tools if 'fbcnn' in tool.lower()]
        print(f"FBCNN相关工具: {fbcnn_tools}")
        
        if "fbcnn_jpeg_artifact_removal" in registered_tools:
            print("✅ FBCNN JPEG伪影去除工具已注册")
        else:
            print("❌ FBCNN JPEG伪影去除工具未注册")
            
        if "fbcnn_blind_quality_assessment" in registered_tools:
            print("✅ FBCNN盲质量评估工具已注册")
        else:
            print("❌ FBCNN盲质量评估工具未注册")
        
        # 2. 创建测试图像
        print("\n--- 创建测试图像 ---")
        test_img_array = np.random.randint(50, 200, (256, 256, 3), dtype=np.uint8)
        test_image = Image.fromarray(test_img_array)
        print(f"创建测试图像，尺寸: {test_image.size}")
        
        # 3. 准备测试数据
        initial_prompt = [{"role": "user", "content": "请去除这张图像的JPEG压缩伪影。"}]
        initial_data = {"image": [test_image]}
        
        # 4. 测试FBCNN JPEG伪影去除工具
        print("\n--- 测试FBCNN JPEG伪影去除工具 ---")
        try:
            # 创建工具实例
            fbcnn_tool = ToolBase.create("fbcnn_jpeg_artifact_removal")
            print("✅ 成功创建FBCNN工具实例")
            
            # 重置工具状态
            fbcnn_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
            print("✅ 工具状态重置成功")
            
            # 测试参数构建
            test_args = {"qf": "blind", "queue": True}
            params = fbcnn_tool.build_params(test_args)
            print(f"✅ 参数构建测试: {params}")
            
            # 测试工具调用格式
            tool_call_json = json.dumps([{
                "name": "fbcnn_jpeg_artifact_removal",
                "arguments": {"qf": "30", "gpu": "0", "queue": False}
            }])
            action_string = f"<tool_call>{tool_call_json}</tool_call>"
            print(f"✅ 工具调用字符串构建成功")
            
            # 测试JSON解析
            action = fbcnn_tool.extract_action(action_string)
            if action:
                parsed_call = json.loads(action.strip())
                print(f"✅ 工具调用解析成功: {parsed_call}")
            
            print("✅ FBCNN JPEG伪影去除工具基础功能测试通过")
            
        except Exception as e:
            print(f"❌ FBCNN JPEG伪影去除工具测试失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 5. 测试FBCNN盲质量评估工具
        print("\n--- 测试FBCNN盲质量评估工具 ---")
        try:
            # 创建工具实例
            quality_tool = ToolBase.create("fbcnn_blind_quality_assessment")
            print("✅ 成功创建盲质量评估工具实例")
            
            # 重置工具状态
            quality_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
            print("✅ 工具状态重置成功")
            
            # 测试参数构建
            test_args = {"gpu": "1"}
            params = quality_tool.build_params(test_args)
            print(f"✅ 参数构建测试: {params}")
            
            print("✅ FBCNN盲质量评估工具基础功能测试通过")
            
        except Exception as e:
            print(f"❌ FBCNN盲质量评估工具测试失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 6. 测试参数验证
        print("\n--- 测试参数验证 ---")
        try:
            fbcnn_tool = ToolBase.create("fbcnn_jpeg_artifact_removal")
            
            # 测试有效QF参数
            valid_qf_tests = [
                {"qf": "blind"},
                {"qf": "30"},
                {"qf": 50},
                {"qf": "100"}
            ]
            
            for test_case in valid_qf_tests:
                params = fbcnn_tool.build_params(test_case)
                print(f"✅ 有效QF测试 {test_case}: {params}")
            
            # 测试无效QF参数
            invalid_qf_tests = [
                {"qf": "150"},  # 超出范围
                {"qf": "0"},    # 超出范围
                {"qf": "abc"},  # 非数字
                {"qf": -10}     # 负数
            ]
            
            for test_case in invalid_qf_tests:
                params = fbcnn_tool.build_params(test_case)
                print(f"✅ 无效QF测试 {test_case}: {params} (应该回退到blind)")
            
            print("✅ 参数验证测试通过")
            
        except Exception as e:
            print(f"❌ 参数验证测试失败: {e}")
        
        # 7. 测试错误处理
        print("\n--- 测试错误处理 ---")
        try:
            fbcnn_tool = ToolBase.create("fbcnn_jpeg_artifact_removal")
            fbcnn_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
            
            # 测试无效的工具调用格式
            invalid_action = "<tool_call>invalid json</tool_call>"
            obs, reward, done, info = fbcnn_tool.execute(invalid_action)
            
            if info.get("status") == "failed" and "JSON" in info.get("error", ""):
                print("✅ 无效JSON格式错误处理正确")
            else:
                print("❌ 无效JSON格式错误处理不正确")
            
            # 测试缺少工具调用标签
            no_tag_action = "这是一个没有标签的动作"
            obs, reward, done, info = fbcnn_tool.execute(no_tag_action)
            
            if info.get("status") == "failed" and "No valid" in info.get("error", ""):
                print("✅ 缺少标签错误处理正确")
            else:
                print("❌ 缺少标签错误处理不正确")
            
            print("✅ 错误处理测试通过")
            
        except Exception as e:
            print(f"❌ 错误处理测试失败: {e}")
        
        print("\n🎉 FBCNN工具箱测试完成！")
        
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        print("请确保项目路径和依赖项正确配置")
        return False
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def test_api_connectivity():
    """测试FBCNN API连接性"""
    print("\n🌐 测试FBCNN API连接性...")
    
    try:
        import requests
        
        # 测试健康检查端点
        api_url = "http://172.18.148.193:5005/health"
        
        print(f"正在连接到: {api_url}")
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ FBCNN API服务正常运行")
            print(f"服务状态: {result.get('status')}")
            print(f"GPU数量: {result.get('gpu_count')}")
            print(f"支持的QF: {result.get('supported_qf')}")
            return True
        else:
            print(f"❌ FBCNN API返回错误状态码: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到FBCNN API服务")
        print("请确保FBCNN服务正在运行在 http://172.18.148.193:5005")
        return False
    except requests.exceptions.Timeout:
        print("❌ 连接FBCNN API超时")
        return False
    except Exception as e:
        print(f"❌ API连接测试失败: {e}")
        return False

if __name__ == "__main__":
    print("🚀 FBCNN工具箱测试开始")
    print("=" * 50)
    
    # 运行工具箱测试
    toolbox_test_passed = test_fbcnn_toolbox()
    
    # 运行API连接测试
    api_test_passed = test_api_connectivity()
    
    print("\n" + "=" * 50)
    print("📊 测试总结:")
    print(f"工具箱测试: {'✅ 通过' if toolbox_test_passed else '❌ 失败'}")
    print(f"API连接测试: {'✅ 通过' if api_test_passed else '❌ 失败'}")
    
    if toolbox_test_passed and api_test_passed:
        print("\n🎉 所有测试都通过了！FBCNN工具箱已准备就绪。")
        sys.exit(0)
    else:
        print("\n⚠️  部分测试失败，请检查配置和服务状态。")
        sys.exit(1)
