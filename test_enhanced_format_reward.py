#!/usr/bin/env python3
"""
测试增强格式奖励模式的脚本

新的增强格式检查模式增加了以下约束：
1. Answer必须在最后一轮对话中（如果存在）
2. Tool_call总数必须 >= 退化数量（对于非clean样本）
"""

import os
import sys

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from verl.utils.reward_score.image_restoration import check_multiturn_format_v3_enhanced

def test_enhanced_format_cases():
    """测试各种增强格式检查的情况"""
    
    print("=" * 80)
    print("测试增强格式奖励模式")
    print("=" * 80)
    
    # 测试用例1: 正确格式 - Answer在最后一轮，tool_call数量足够
    test_case_1 = """
<think>
我需要分析这张图片的退化情况。看起来有模糊和噪声问题。
</think>

<tool_call>
[{"name": "restormer_motion_deblurring", "arguments": {}}]
</tool_call>

<think>
去模糊后，我还需要处理噪声问题。
</think>

<tool_call>
[{"name": "scunet_real_denoising_psnr", "arguments": {}}]
</tool_call>

<think>
现在图片质量已经得到改善，可以给出最终答案。
</think>

<answer>
{"restoration_log": ["motion_blur", "noise"]}
</answer>
"""
    
    print("\n测试用例1: 正确格式 - Answer在最后一轮，tool_call数量足够")
    print("退化数量: 2, Tool_call数量: 2")
    result = check_multiturn_format_v3_enhanced(test_case_1, degradation_count=2, is_clean_sample=False)
    print(f"结果: {result} ({'通过' if result == 1.0 else '失败'})")
    
    # 测试用例2: 错误格式 - Answer不在最后一轮
    test_case_2 = """
<think>
我需要分析这张图片的退化情况。
</think>

<answer>
{"restoration_log": ["motion_blur", "noise"]}
</answer>

<think>
等等，我还需要再处理一下。
</think>

<tool_call>
[{"name": "scunet_real_denoising_psnr", "arguments": {}}]
</tool_call>
"""
    
    print("\n测试用例2: 错误格式 - Answer不在最后一轮")
    result = check_multiturn_format_v3_enhanced(test_case_2, degradation_count=2, is_clean_sample=False)
    print(f"结果: {result} ({'通过' if result == 1.0 else '失败'})")
    
    # 测试用例3: 错误格式 - Tool_call数量不足
    test_case_3 = """
<think>
我需要分析这张图片的退化情况。看起来有多种问题。
</think>

<tool_call>
[{"name": "restormer_motion_deblurring", "arguments": {}}]
</tool_call>

<think>
处理完成，给出答案。
</think>

<answer>
{"restoration_log": ["motion_blur", "noise", "low_light"]}
</answer>
"""
    
    print("\n测试用例3: 错误格式 - Tool_call数量不足")
    print("退化数量: 3, Tool_call数量: 1")
    result = check_multiturn_format_v3_enhanced(test_case_3, degradation_count=3, is_clean_sample=False)
    print(f"结果: {result} ({'通过' if result == 1.0 else '失败'})")
    
    # 测试用例4: 正确格式 - 多个tool_call在一轮中
    test_case_4 = """
<think>
我需要同时处理多个退化问题。
</think>

<tool_call>
[
    {"name": "restormer_motion_deblurring", "arguments": {}},
    {"name": "scunet_real_denoising_psnr", "arguments": {}},
    {"name": "retinexformer_enhance", "arguments": {}}
]
</tool_call>

<think>
所有处理完成，给出最终答案。
</think>

<answer>
{"restoration_log": ["motion_blur", "noise", "low_light"]}
</answer>
"""
    
    print("\n测试用例4: 正确格式 - 多个tool_call在一轮中")
    print("退化数量: 3, Tool_call数量: 3")
    result = check_multiturn_format_v3_enhanced(test_case_4, degradation_count=3, is_clean_sample=False)
    print(f"结果: {result} ({'通过' if result == 1.0 else '失败'})")
    
    # 测试用例5: Clean样本 - 不需要检查tool_call数量
    test_case_5 = """
<think>
这是一张干净的图片，不需要任何处理。
</think>

<answer>
{"restoration_log": []}
</answer>
"""
    
    print("\n测试用例5: Clean样本 - 不需要检查tool_call数量")
    result = check_multiturn_format_v3_enhanced(test_case_5, degradation_count=0, is_clean_sample=True)
    print(f"结果: {result} ({'通过' if result == 1.0 else '失败'})")
    
    # 测试用例6: 错误格式 - Answer出现在多个轮次
    test_case_6 = """
<think>
我先给一个初步答案。
</think>

<answer>
{"restoration_log": ["motion_blur"]}
</answer>

<think>
等等，我需要修正答案。
</think>

<answer>
{"restoration_log": ["motion_blur", "noise"]}
</answer>
"""
    
    print("\n测试用例6: 错误格式 - Answer出现在多个轮次")
    result = check_multiturn_format_v3_enhanced(test_case_6, degradation_count=2, is_clean_sample=False)
    print(f"结果: {result} ({'通过' if result == 1.0 else '失败'})")

def test_integration_with_reward_system():
    """测试与奖励系统的集成"""
    
    print("\n" + "=" * 80)
    print("测试与奖励系统的集成")
    print("=" * 80)
    
    # 设置环境变量启用增强格式检查
    os.environ['USE_ENHANCED_FORMAT'] = 'True'
    os.environ['FORMAT_REWARD_WEIGHT'] = '0.3'
    os.environ['QUALITY_REWARD_WEIGHT'] = '0.7'
    
    from verl.utils.reward_score import compute_reward_score
    
    # 测试数据
    solution_str = """
<think>
我需要处理这张图片的模糊和噪声问题。
</think>

<tool_call>
[{"name": "restormer_motion_deblurring", "arguments": {}}]
</tool_call>

<think>
去模糊后，现在处理噪声。
</think>

<tool_call>
[{"name": "scunet_real_denoising_psnr", "arguments": {}}]
</tool_call>

<think>
处理完成，给出最终答案。
</think>

<answer>
{"restoration_log": ["motion_blur", "noise"]}
</answer>
"""
    
    ground_truth = {
        "reward_model": [
            {"degradation_type": "motion_blur"},
            {"degradation_type": "noise"}
        ],
        "env_name": "motion_blur,noise"
    }
    
    print("测试完整的奖励计算（启用增强格式检查）...")
    try:
        result = compute_reward_score(
            solution_str=solution_str,
            ground_truth=ground_truth,
            data_source="image_restoration"
        )
        
        if isinstance(result, dict):
            print(f"总分: {result.get('score', 'N/A')}")
            print(f"格式分数: {result.get('format_score', 'N/A')}")
            print(f"质量分数: {result.get('quality_score', 'N/A')}")
        else:
            print(f"总分: {result}")
            
        print("✅ 增强格式检查集成成功！")
        
    except Exception as e:
        print(f"❌ 集成测试失败: {e}")
    
    # 恢复环境变量
    os.environ['USE_ENHANCED_FORMAT'] = 'False'

if __name__ == "__main__":
    test_enhanced_format_cases()
    test_integration_with_reward_system()
    
    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80)
    print("\n使用方法:")
    print("1. 设置环境变量 USE_ENHANCED_FORMAT=True 启用增强格式检查")
    print("2. 增强格式检查会验证:")
    print("   - Answer必须在最后一轮对话中")
    print("   - Tool_call总数 >= 退化数量（非clean样本）")
    print("   - 继承所有原有格式检查规则")
    print("3. 只有满足所有条件才给1分，否则给-1分")
