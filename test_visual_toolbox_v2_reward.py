#!/usr/bin/env python3
"""
测试visual_toolbox_v2 reward计算是否正确
"""

import sys
sys.path.insert(0, '/home/takisobe@amd.com/zxy/codes/DeepEyes')

from verl.utils.reward_score.visual_toolbox_v2_reward import compute_visual_toolbox_v2_score

def test_rewards():
    print("=" * 80)
    print("测试Visual Toolbox V2 Reward计算")
    print("=" * 80)
    
    # Test case 1: 完美格式 + 正确答案
    print("\n[Test 1] 完美格式 + 正确答案 (yes)")
    test_case_1 = """<think>
I see a crack in the surface.
</think>
<location>[{"bbox2d": [100, 150, 200, 250]}]</location>
<type>crack</type>
<answer>yes</answer>"""
    
    ground_truth_1 = {"answer": "yes", "bboxes": [{"bbox2d": [100, 150, 200, 250]}]}
    extra_info_1 = {
        "question": "Does this image contain any defects?",
        "bboxes": [{"bbox2d": [100, 150, 200, 250]}],
    }
    
    result = compute_visual_toolbox_v2_score("defect_detection", test_case_1, ground_truth_1, extra_info_1)
    print(f"Result: {result}")
    print(f"Expected: score=2.0, format_reward=1.0, acc_reward=1.0")
    assert result['score'] == 2.0, f"Expected score=2.0, got {result['score']}"
    assert result['format_reward'] == 1.0, f"Expected format_reward=1.0, got {result['format_reward']}"
    assert result['acc_reward'] == 1.0, f"Expected acc_reward=1.0, got {result['acc_reward']}"
    print("✓ PASS\n")
    
    # Test case 2: 完美格式 + 正确答案 (no)
    print("[Test 2] 完美格式 + 正确答案 (no)")
    test_case_2 = """<think>
The surface is clean and smooth with no visible defects.
</think>
<location>[]</location>
<type>good</type>
<answer>no</answer>"""
    
    ground_truth_2 = {"answer": "no", "bboxes": []}
    extra_info_2 = {
        "question": "Does this image contain any defects?",
        "bboxes": [],
    }
    
    result = compute_visual_toolbox_v2_score("defect_detection", test_case_2, ground_truth_2, extra_info_2)
    print(f"Result: {result}")
    print(f"Expected: score=2.0, format_reward=1.0, acc_reward=1.0")
    assert result['score'] == 2.0
    assert result['format_reward'] == 1.0
    assert result['acc_reward'] == 1.0
    print("✓ PASS\n")
    
    # Test case 3: 格式错误
    print("[Test 3] 格式错误 (缺少</think>)")
    test_case_3 = """<think>
Let me check for defects.
<location>[]</location>
<type>good</type>
<answer>no</answer>"""
    
    result = compute_visual_toolbox_v2_score("defect_detection", test_case_3, ground_truth_2, extra_info_2)
    print(f"Result: {result}")
    print(f"Expected: score=0.0, format_reward=-1.0, acc_reward=1.0")
    assert result['score'] == 0.0, f"Expected score=0.0, got {result['score']}"
    assert result['format_reward'] == -1.0, f"Expected format_reward=-1.0, got {result['format_reward']}"
    assert result['acc_reward'] == 1.0, f"Expected acc_reward=1.0, got {result['acc_reward']}"
    print("✓ PASS\n")
    
    # Test case 4: 正确格式 + 错误答案
    print("[Test 4] 正确格式 + 错误答案")
    test_case_4 = """<think>
I see some anomalies.
</think>
<location>[{"bbox2d": [100, 100, 200, 200]}]</location>
<type>crack</type>
<answer>yes</answer>"""
    
    result = compute_visual_toolbox_v2_score("defect_detection", test_case_4, ground_truth_2, extra_info_2)
    print(f"Result: {result}")
    print(f"Expected: score=1.0, format_reward=1.0, acc_reward=0.0")
    assert result['score'] == 1.0
    assert result['format_reward'] == 1.0
    assert result['acc_reward'] == 0.0
    print("✓ PASS\n")
    
    # Test case 5: 工具请求turn (只检查格式)
    print("[Test 5] 工具请求turn (Format 1)")
    test_case_5 = """<think>
I need to zoom in to check for defects.
</think>
<tool_call>
[{"name": "image_zoom_in_tool", "arguments": {"bbox_2d": [100, 150, 200, 250]}}]
</tool_call>"""
    
    result = compute_visual_toolbox_v2_score("defect_detection", test_case_5, ground_truth_2, extra_info_2)
    print(f"Result: {result}")
    print(f"Expected: 1.0 (只检查格式，不检查accuracy)")
    assert result == 1.0, f"Expected 1.0, got {result}"
    print("✓ PASS\n")
    
    # Test case 6: 工具请求turn + 格式错误
    print("[Test 6] 工具请求turn + 格式错误 (invalid JSON)")
    test_case_6 = """<think>
I need to zoom in.
</think>
<tool_call>
{name: "image_zoom_in_tool", arguments: {bbox_2d: [100, 150, 200, 250]}}
</tool_call>"""
    
    result = compute_visual_toolbox_v2_score("defect_detection", test_case_6, ground_truth_2, extra_info_2)
    print(f"Result: {result}")
    print(f"Expected: -1.0 (格式错误：invalid JSON)")
    assert result == -1.0, f"Expected -1.0, got {result}"
    print("✓ PASS\n")
    
    print("=" * 80)
    print("所有测试通过！✓")
    print("=" * 80)

if __name__ == "__main__":
    test_rewards()

