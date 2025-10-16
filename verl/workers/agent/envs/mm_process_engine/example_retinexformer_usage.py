"""
Retinexformer Low-light Enhancement Toolbox - Usage Examples
演示如何在不同场景下使用Retinexformer工具进行低光图像增强
"""

import numpy as np
from PIL import Image
import os
import sys

# 添加项目路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from verl.workers.agent.envs.tool_envs import ToolBase

def create_dark_test_image(width=512, height=512, brightness_range=(20, 80)):
    """创建一张模拟的低光测试图片"""
    # 创建低亮度图片
    img_array = np.random.randint(brightness_range[0], brightness_range[1], 
                                   (height, width, 3), dtype=np.uint8)
    return Image.fromarray(img_array)

def print_section(title):
    """打印分节标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def example1_generic_tool():
    """示例1: 使用通用Retinexformer工具（推荐）"""
    print_section("示例1: 使用通用Retinexformer工具")
    
    # 创建测试图片
    test_image = create_dark_test_image()
    print(f"创建了一张低光测试图片，尺寸: {test_image.size}")
    print(f"平均亮度: {np.mean(np.array(test_image)):.2f}")
    
    # 初始化数据
    initial_prompt = [{"role": "user", "content": "Please enhance this low-light image."}]
    initial_data = {"image": [test_image]}
    
    try:
        # 创建工具实例
        tool = ToolBase.create("retinexformer_enhance")
        print(f"✓ 成功创建工具: {tool.name}")
        
        # 重置工具状态
        tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
        print("✓ 工具状态已重置")
        
        # 构造工具调用字符串（模拟LLM输出）
        # 使用 LOL_v2_real 模型（适合真实场景）
        tool_call_string = """<tool_call>
{
    "name": "retinexformer_enhance",
    "arguments": {
        "task": "LOL_v2_real"
    }
}
</tool_call>"""
        
        print("\n执行工具调用...")
        print(f"请求模型: LOL_v2_real")
        
        # 执行工具
        obs, reward, done, info = tool.execute(tool_call_string)
        
        # 检查执行结果
        if info.get("status") == "success":
            print(f"✓ 工具执行成功!")
            print(f"  - 执行时间: {info.get('execution_time', 0):.2f}秒")
            
            # 获取增强后的图片
            enhanced_image = obs['multi_modal_data']['image'][0]
            print(f"  - 增强后图片尺寸: {enhanced_image.size}")
            
            enhanced_array = np.array(enhanced_image)
            enhanced_brightness = np.mean(enhanced_array)
            print(f"  - 增强后平均亮度: {enhanced_brightness:.2f}")
            
            # 可以保存图片
            # enhanced_image.save("enhanced_output.png")
            # print("  - 已保存到: enhanced_output.png")
            
        else:
            print(f"✗ 工具执行失败: {info.get('error')}")
            
    except Exception as e:
        print(f"✗ 发生错误: {e}")
        print("提示: 请确保Retinexformer服务正在运行 (端口5009)")

def example2_specific_models():
    """示例2: 使用特定的预训练模型"""
    print_section("示例2: 测试不同的预训练模型")
    
    test_image = create_dark_test_image(width=256, height=256)
    initial_data = {"image": [test_image]}
    initial_prompt = [{"role": "user", "content": "Enhance this image."}]
    
    # 测试不同的模型
    models_to_test = [
        ("LOL_v1", "LOL-v1数据集（经典）"),
        ("LOL_v2_real", "LOL-v2真实场景（推荐）"),
        ("LOL_v2_synthetic", "LOL-v2合成数据"),
        ("SDSD_indoor", "室内静态场景"),
        ("SDSD_outdoor", "室外静态场景"),
    ]
    
    tool = ToolBase.create("retinexformer_enhance")
    
    for task_name, description in models_to_test:
        print(f"\n测试模型: {task_name} - {description}")
        print("-" * 50)
        
        try:
            tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
            
            tool_call_string = f"""<tool_call>
{{
    "name": "retinexformer_enhance",
    "arguments": {{
        "task": "{task_name}"
    }}
}}
</tool_call>"""
            
            obs, reward, done, info = tool.execute(tool_call_string)
            
            if info.get("status") == "success":
                enhanced_image = obs['multi_modal_data']['image'][0]
                brightness = np.mean(np.array(enhanced_image))
                print(f"  ✓ 成功! 增强后亮度: {brightness:.2f}")
            else:
                print(f"  ✗ 失败: {info.get('error')}")
                
        except Exception as e:
            print(f"  ✗ 错误: {e}")

def example3_using_specific_tool_classes():
    """示例3: 使用特定的工具类（每个模型一个类）"""
    print_section("示例3: 使用特定的工具类")
    
    test_image = create_dark_test_image(width=256, height=256)
    initial_data = {"image": [test_image]}
    initial_prompt = [{"role": "user", "content": "Enhance this image."}]
    
    # 使用LOL_v1专用工具
    print("\n使用 retinexformer_lol_v1 工具...")
    try:
        lol_v1_tool = ToolBase.create("retinexformer_lol_v1")
        lol_v1_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
        
        # 注意：使用特定工具类时，不需要指定task参数
        tool_call_string = """<tool_call>
{
    "name": "retinexformer_lol_v1",
    "arguments": {}
}
</tool_call>"""
        
        obs, reward, done, info = lol_v1_tool.execute(tool_call_string)
        
        if info.get("status") == "success":
            print("  ✓ LOL_v1工具执行成功!")
        else:
            print(f"  ✗ 执行失败: {info.get('error')}")
            
    except Exception as e:
        print(f"  ✗ 错误: {e}")
    
    # 使用SDSD_indoor专用工具
    print("\n使用 retinexformer_sdsd_indoor 工具...")
    try:
        indoor_tool = ToolBase.create("retinexformer_sdsd_indoor")
        indoor_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
        
        tool_call_string = """<tool_call>
{
    "name": "retinexformer_sdsd_indoor",
    "arguments": {}
}
</tool_call>"""
        
        obs, reward, done, info = indoor_tool.execute(tool_call_string)
        
        if info.get("status") == "success":
            print("  ✓ SDSD_indoor工具执行成功!")
        else:
            print(f"  ✗ 执行失败: {info.get('error')}")
            
    except Exception as e:
        print(f"  ✗ 错误: {e}")

def example4_check_available_tools():
    """示例4: 检查所有可用的Retinexformer工具"""
    print_section("示例4: 检查所有可用的Retinexformer工具")
    
    retinexformer_tools = [
        ("retinexformer_enhance", "通用工具（推荐）", "支持所有模型"),
        ("retinexformer_lol_v1", "LOL-v1", "经典LOL数据集"),
        ("retinexformer_lol_v2_real", "LOL-v2真实", "真实场景拍摄"),
        ("retinexformer_lol_v2_synthetic", "LOL-v2合成", "合成数据"),
        ("retinexformer_sdsd_indoor", "SDSD室内", "室内静态场景"),
        ("retinexformer_sdsd_outdoor", "SDSD室外", "室外静态场景"),
        ("retinexformer_sid", "SID", "See in the Dark数据集"),
        ("retinexformer_smid", "SMID", "静态多场景数据集"),
        ("retinexformer_fivek", "FiveK", "MIT Adobe FiveK数据集"),
    ]
    
    print("\n已注册的Retinexformer工具:")
    print("-" * 70)
    
    registry = ToolBase.registry
    
    for tool_name, display_name, description in retinexformer_tools:
        if tool_name in registry:
            print(f"✓ {tool_name:35s} - {display_name:20s} ({description})")
        else:
            print(f"✗ {tool_name:35s} - 未注册")
    
    print("\n总计: {} / {} 工具已注册".format(
        sum(1 for t, _, _ in retinexformer_tools if t in registry),
        len(retinexformer_tools)
    ))

def example5_error_handling():
    """示例5: 错误处理和异常情况"""
    print_section("示例5: 错误处理")
    
    test_image = create_dark_test_image(width=128, height=128)
    initial_data = {"image": [test_image]}
    initial_prompt = [{"role": "user", "content": "Test error handling."}]
    
    tool = ToolBase.create("retinexformer_enhance")
    tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
    
    # 测试1: 无效的任务名称
    print("\n测试1: 使用无效的任务名称...")
    invalid_task_call = """<tool_call>
{
    "name": "retinexformer_enhance",
    "arguments": {
        "task": "INVALID_TASK_NAME"
    }
}
</tool_call>"""
    
    obs, reward, done, info = tool.execute(invalid_task_call)
    print(f"  状态: {info.get('status')}")
    if info.get('status') != 'success':
        print(f"  预期的错误: {info.get('error')}")
    
    # 测试2: 无效的JSON格式
    print("\n测试2: 使用无效的JSON格式...")
    invalid_json_call = """<tool_call>
{
    "name": "retinexformer_enhance",
    "arguments": {
        "task": "LOL_v1"  // 这个注释会导致JSON解析失败
    }
}
</tool_call>"""
    
    obs, reward, done, info = tool.execute(invalid_json_call)
    print(f"  状态: {info.get('status')}")
    if info.get('status') != 'success':
        print(f"  预期的错误 (JSON解析): 正常捕获")
    
    # 测试3: 缺少工具调用标签
    print("\n测试3: 缺少<tool_call>标签...")
    no_tag_call = "Just some text without tags"
    
    obs, reward, done, info = tool.execute(no_tag_call)
    print(f"  状态: {info.get('status')}")
    if info.get('status') != 'success':
        print(f"  预期的错误: {info.get('error')}")

def example6_performance_comparison():
    """示例6: 性能比较（模拟）"""
    print_section("示例6: 不同模型的性能特点")
    
    print("""
不同Retinexformer模型的特点和使用场景：

1. LOL_v1 (经典模型)
   - 适用场景: 通用低光增强
   - 特点: 较为保守，不会过度增强
   - 推荐: 不确定场景时的默认选择

2. LOL_v2_real (真实场景) ⭐ 推荐
   - 适用场景: 真实拍摄的低光照片
   - 特点: 对真实噪声和光照变化处理好
   - 推荐: 手机/相机拍摄的低光照片

3. LOL_v2_synthetic (合成数据)
   - 适用场景: 合成降质的图片
   - 特点: 对人工降低亮度的图片效果好
   - 推荐: 测试和实验环境

4. SDSD_indoor (室内场景)
   - 适用场景: 室内弱光环境
   - 特点: 针对室内光源特性优化
   - 推荐: 室内监控、室内摄影

5. SDSD_outdoor (室外场景)
   - 适用场景: 夜间户外场景
   - 特点: 处理户外夜景效果好
   - 推荐: 夜间街景、户外监控

6. SID (See in the Dark)
   - 适用场景: 极低光场景
   - 特点: 处理极端低光情况
   - 推荐: RAW图像、极暗场景

7. SMID (多场景)
   - 适用场景: 多样化场景
   - 特点: 泛化能力强
   - 推荐: 场景不确定时使用

8. FiveK (专业调色)
   - 适用场景: 需要专业级调色的照片
   - 特点: MIT Adobe FiveK专业数据集训练
   - 推荐: 摄影作品后期处理

选择建议:
- 一般用途: LOL_v2_real (真实场景)
- 室内照片: SDSD_indoor
- 夜景照片: SDSD_outdoor
- 极暗环境: SID
- 专业后期: FiveK
""")

# ====================== 主函数 ======================
def main():
    """运行所有示例"""
    print("\n" + "=" * 70)
    print("  Retinexformer Low-light Enhancement Toolbox - 使用示例")
    print("=" * 70)
    print("\n本脚本演示如何使用Retinexformer工具进行低光图像增强")
    print("确保Retinexformer服务正在运行 (默认端口: 5009)\n")
    
    # 检查工具注册
    example4_check_available_tools()
    
    # 基础使用示例
    example1_generic_tool()
    
    # 不同模型测试
    # example2_specific_models()
    
    # 特定工具类使用
    # example3_using_specific_tool_classes()
    
    # 错误处理
    # example5_error_handling()
    
    # 性能比较
    example6_performance_comparison()
    
    print("\n" + "=" * 70)
    print("  所有示例运行完成!")
    print("=" * 70)
    print("\n提示:")
    print("1. 取消注释其他示例函数以查看更多用法")
    print("2. 修改 TOOL_SERVICE_IP 环境变量以连接到不同的服务器")
    print("3. 查看 RetinexformerToolbox.py 了解实现细节")
    print()

if __name__ == "__main__":
    main()

