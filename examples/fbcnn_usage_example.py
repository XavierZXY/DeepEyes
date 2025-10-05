#!/usr/bin/env python3
"""
FBCNN工具使用示例
演示如何在代理环境中使用FBCNN工具进行JPEG压缩伪影去除
"""

import sys
import os
import json
from PIL import Image
import numpy as np

# 添加项目路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

def create_sample_jpeg_image(output_path: str, quality: int = 30):
    """创建一个带有JPEG压缩伪影的示例图像"""
    # 创建一个高质量的测试图像
    img_array = np.zeros((512, 512, 3), dtype=np.uint8)
    
    # 添加一些几何图案，这些图案在JPEG压缩后会产生明显的伪影
    for i in range(0, 512, 64):
        for j in range(0, 512, 64):
            if (i // 64 + j // 64) % 2 == 0:
                img_array[i:i+64, j:j+64] = [255, 255, 255]  # 白色
            else:
                img_array[i:i+64, j:j+64] = [0, 0, 0]  # 黑色
    
    # 添加一些细节
    for i in range(100, 400):
        for j in range(100, 400):
            if (i + j) % 10 < 5:
                img_array[i, j] = [128, 128, 128]  # 灰色线条
    
    # 保存为高质量PNG
    high_quality_img = Image.fromarray(img_array)
    
    # 转换为JPEG以引入压缩伪影
    jpeg_img = high_quality_img.convert('RGB')
    jpeg_img.save(output_path, 'JPEG', quality=quality, optimize=True)
    
    print(f"创建了带有JPEG压缩伪影的示例图像: {output_path} (质量: {quality})")
    return output_path

def demonstrate_fbcnn_usage():
    """演示FBCNN工具的使用"""
    print("🎯 FBCNN工具使用示例")
    print("=" * 50)
    
    try:
        # 导入必要的模块
        from verl.workers.agent.tool_envs import ToolBase
        # 导入FBCNN工具以触发自动注册
        from verl.workers.agent.envs.mm_process_engine.FBCNNToolbox import (
            FBCNNJpegArtifactRemovalToolbox,
            FBCNNBlindQualityAssessmentToolbox
        )
        
        # 1. 创建示例图像
        print("\n📸 创建示例图像...")
        sample_image_path = "/tmp/sample_jpeg_artifacts.jpg"
        create_sample_jpeg_image(sample_image_path, quality=20)  # 低质量JPEG
        
        # 加载图像
        test_image = Image.open(sample_image_path).convert('RGB')
        print(f"加载图像尺寸: {test_image.size}")
        
        # 2. 准备环境数据
        print("\n🔧 准备环境数据...")
        initial_prompt = [
            {"role": "user", "content": "这张图像有明显的JPEG压缩伪影，请帮我去除这些伪影以提升图像质量。"}
        ]
        initial_data = {"image": [test_image]}
        
        # 3. 演示FBCNN JPEG伪影去除工具
        print("\n🛠️  演示FBCNN JPEG伪影去除工具...")
        
        # 创建工具实例
        fbcnn_tool = ToolBase.create("fbcnn_jpeg_artifact_removal")
        fbcnn_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
        
        # 演示不同的使用方式
        usage_examples = [
            {
                "name": "盲预测模式",
                "description": "让FBCNN自动检测和去除伪影",
                "arguments": {"qf": "blind", "queue": True}
            },
            {
                "name": "指定质量因子模式",
                "description": "指定原始JPEG的质量因子为30",
                "arguments": {"qf": "30", "queue": True}
            },
            {
                "name": "指定GPU模式",
                "description": "指定使用GPU 0进行处理",
                "arguments": {"qf": "blind", "gpu": "0", "queue": False}
            }
        ]
        
        for example in usage_examples:
            print(f"\n--- {example['name']} ---")
            print(f"描述: {example['description']}")
            
            # 构建工具调用
            tool_call_json = json.dumps([{
                "name": "fbcnn_jpeg_artifact_removal",
                "arguments": example['arguments']
            }])
            action_string = f"<tool_call>{tool_call_json}</tool_call>"
            
            print(f"工具调用: {tool_call_json}")
            
            # 测试参数构建（不实际调用API）
            params = fbcnn_tool.build_params(example['arguments'])
            print(f"API参数: {params}")
            
            # 如果要实际执行，取消下面的注释
            # obs, reward, done, info = fbcnn_tool.execute(action_string)
            # if info.get("status") == "success":
            #     print("✅ 工具执行成功")
            #     processed_image = obs['multi_modal_data']['image'][0]
            #     processed_image.save(f"/tmp/fbcnn_result_{example['name'].replace(' ', '_')}.png")
            # else:
            #     print(f"❌ 工具执行失败: {info.get('error')}")
        
        # 4. 演示盲质量评估工具
        print("\n🔍 演示FBCNN盲质量评估工具...")
        
        quality_tool = ToolBase.create("fbcnn_blind_quality_assessment")
        quality_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
        
        # 构建质量评估调用
        quality_call = json.dumps([{
            "name": "fbcnn_blind_quality_assessment",
            "arguments": {}
        }])
        
        print(f"质量评估调用: {quality_call}")
        params = quality_tool.build_params({})
        print(f"API参数: {params}")
        
        # 5. 演示错误处理
        print("\n⚠️  演示错误处理...")
        
        # 无效工具名称
        invalid_tool_call = json.dumps([{
            "name": "invalid_tool_name",
            "arguments": {}
        }])
        invalid_action = f"<tool_call>{invalid_tool_call}</tool_call>"
        
        obs, reward, done, info = fbcnn_tool.execute(invalid_action)
        if info.get("status") == "failed":
            print(f"✅ 正确处理了无效工具名称错误: {info.get('error')}")
        
        # 无效JSON格式
        invalid_json_action = "<tool_call>invalid json format</tool_call>"
        obs, reward, done, info = fbcnn_tool.execute(invalid_json_action)
        if info.get("status") == "failed":
            print(f"✅ 正确处理了无效JSON格式错误")
        
        # 6. 演示答案提取
        print("\n📝 演示答案提取...")
        
        answer_action = "<answer>图像的JPEG压缩伪影已经成功去除，图像质量得到了显著改善。</answer>"
        obs, reward, done, info = fbcnn_tool.execute(answer_action)
        if done:
            print("✅ 正确识别并处理了最终答案")
        
        print("\n🎉 FBCNN工具使用示例演示完成！")
        
        # 清理临时文件
        if os.path.exists(sample_image_path):
            os.remove(sample_image_path)
            print(f"清理临时文件: {sample_image_path}")
        
    except Exception as e:
        print(f"❌ 示例演示过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

def show_integration_tips():
    """显示集成提示"""
    print("\n💡 集成提示:")
    print("=" * 30)
    print("1. 确保FBCNN服务运行在 http://172.18.148.193:5005")
    print("2. 工具会自动注册到ToolBase.registry中")
    print("3. 支持的工具:")
    print("   - fbcnn_jpeg_artifact_removal: JPEG伪影去除")
    print("   - fbcnn_blind_quality_assessment: 盲质量评估")
    print("4. 参数说明:")
    print("   - qf: 质量因子，'blind'或1-100的整数")
    print("   - gpu: 指定GPU ID（可选）")
    print("   - queue: 是否启用队列，默认true")
    print("   - format: 返回格式，默认'base64'")
    print("5. 错误处理:")
    print("   - 自动验证QF参数，无效值会回退到blind模式")
    print("   - 处理API连接错误和超时")
    print("   - 提供详细的错误信息")

if __name__ == "__main__":
    demonstrate_fbcnn_usage()
    show_integration_tips()
