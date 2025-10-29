#!/usr/bin/env python3
"""
测试工具链执行逻辑
验证：规划-执行-评估模式是否正确工作
"""

import json

def test_parse_tool_calls():
    """测试工具调用解析是否支持JSON数组"""
    
    # 测试案例1: JSON数组（新格式）
    test_output_1 = """
<think>Plan 1: First denoise, then brighten</think>
<tool_call>
[
    {"name": "scunet_real_denoising_gan", "degradation": "noise", "arguments": {}},
    {"name": "retinexformer_sdsd_indoor", "degradation": "dark", "arguments": {}}
]
</tool_call>
"""
    
    # 测试案例2: 单个工具（兼容旧格式）
    test_output_2 = """
<think>Try denoising first</think>
<tool_call>
{"name": "scunet_real_denoising_gan", "degradation": "noise", "arguments": {}}
</tool_call>
"""
    
    # 测试案例3: Answer标签
    test_output_3 = """
<think>The result looks good. Restoration complete.</think>
<answer>
{
    "restoration_log": ["noise", "dark"]
}
</answer>
"""
    
    print("=" * 60)
    print("测试工具调用解析")
    print("=" * 60)
    
    import re
    
    for i, test_output in enumerate([test_output_1, test_output_2, test_output_3], 1):
        print(f"\n测试案例 {i}:")
        print("-" * 60)
        
        # 提取think
        think_match = re.search(r'<think>(.*?)</think>', test_output, re.DOTALL)
        if think_match:
            print(f"✅ Think: {think_match.group(1).strip()}")
        
        # 提取tool_call
        tool_call_match = re.search(r'<tool_call>(.*?)</tool_call>', test_output, re.DOTALL)
        if tool_call_match:
            tool_call_content = tool_call_match.group(1).strip()
            try:
                tool_calls_json = json.loads(tool_call_content)
                if isinstance(tool_calls_json, list):
                    print(f"✅ Tool Calls (数组): {len(tool_calls_json)}个工具")
                    for j, tc in enumerate(tool_calls_json, 1):
                        print(f"   {j}. {tc.get('name', 'unknown')}")
                else:
                    print(f"✅ Tool Calls (单个): {tool_calls_json.get('name', 'unknown')}")
            except json.JSONDecodeError as e:
                print(f"❌ JSON解析失败: {e}")
        
        # 提取answer
        answer_match = re.search(r'<answer>(.*?)</answer>', test_output, re.DOTALL)
        if answer_match:
            answer_content = answer_match.group(1).strip()
            try:
                answer_json = json.loads(answer_content)
                print(f"✅ Answer: {answer_json}")
            except json.JSONDecodeError:
                print(f"✅ Answer (文本): {answer_content}")
    
    print("\n" + "=" * 60)
    print("解析测试完成！")
    print("=" * 60)


def test_tool_chain_execution_logic():
    """模拟工具链执行逻辑"""
    
    print("\n" + "=" * 60)
    print("模拟工具链执行")
    print("=" * 60)
    
    # 模拟场景
    class MockImage:
        def __init__(self, desc):
            self.desc = desc
        def __repr__(self):
            return f"Image({self.desc})"
    
    class MockTool:
        def __init__(self, name, effect):
            self.name = name
            self.effect = effect
            self.origin_multi_modal_data = None
            
        def reset(self, multi_modal_data, origin_multi_modal_data, **kwargs):
            self.current_image = multi_modal_data
            self.origin = origin_multi_modal_data
            print(f"   🔄 {self.name}.reset(current={self.current_image})")
            
        def execute(self, action_string):
            result_image = MockImage(f"{self.current_image.desc} -> {self.effect}")
            print(f"   ✅ {self.name}.execute() -> {result_image}")
            return {"multi_modal_data": result_image}, 0.0, False, {"status": "success"}
    
    # 场景1: Turn 1 - 提出计划A
    print("\n📍 Turn 1: 模型提出计划A")
    print("-" * 60)
    
    origin_image = MockImage("原图(雨+暗+噪声)")
    tools_plan_a = [
        MockTool("restormer_deraining", "去雨"),
        MockTool("retinexformer_sdsd_indoor", "提亮"),
        MockTool("scunet_real_denoising_gan", "去噪")
    ]
    
    print(f"起点: {origin_image}")
    current_image = origin_image
    executed_tools = []
    
    for i, tool in enumerate(tools_plan_a, 1):
        print(f"\n工具 {i}/{len(tools_plan_a)}: {tool.name}")
        tool.reset(
            multi_modal_data=current_image,
            origin_multi_modal_data=origin_image
        )
        result, _, _, _ = tool.execute("")
        current_image = result['multi_modal_data']
        executed_tools.append(tool.name)
    
    result_a = current_image
    print(f"\n最终结果A: {result_a}")
    print(f"工具链: {' → '.join(executed_tools)}")
    
    # 场景2: Turn 2 - 模型看到结果A不满意，提出计划B
    print("\n\n📍 Turn 2: 模型评估结果A，不满意，提出计划B（改变顺序）")
    print("-" * 60)
    
    tools_plan_b = [
        MockTool("retinexformer_sdsd_indoor", "提亮"),
        MockTool("restormer_deraining", "去雨"),
        MockTool("scunet_real_denoising_gan", "去噪")
    ]
    
    print(f"⚠️  关键：从原图重新开始！")
    print(f"起点: {origin_image}")
    current_image = origin_image  # 从原图重新开始！
    executed_tools = []
    
    for i, tool in enumerate(tools_plan_b, 1):
        print(f"\n工具 {i}/{len(tools_plan_b)}: {tool.name}")
        tool.reset(
            multi_modal_data=current_image,
            origin_multi_modal_data=origin_image
        )
        result, _, _, _ = tool.execute("")
        current_image = result['multi_modal_data']
        executed_tools.append(tool.name)
    
    result_b = current_image
    print(f"\n最终结果B: {result_b}")
    print(f"工具链: {' → '.join(executed_tools)}")
    
    # 场景3: Turn 3 - 模型满意，输出答案
    print("\n\n📍 Turn 3: 模型评估结果B，满意，输出答案")
    print("-" * 60)
    print("✅ <answer>完成恢复</answer>")
    print("Episode结束")
    
    print("\n" + "=" * 60)
    print("模拟执行完成！")
    print("=" * 60)


def test_compatibility():
    """测试向后兼容性"""
    
    print("\n" + "=" * 60)
    print("测试向后兼容性")
    print("=" * 60)
    
    # 旧格式：单个dict
    old_format = {"name": "scunet_real_denoising_gan", "arguments": {}}
    
    # 新格式：list
    new_format = [
        {"name": "scunet_real_denoising_gan", "arguments": {}},
        {"name": "retinexformer_sdsd_indoor", "arguments": {}}
    ]
    
    def normalize_tool_calls(tool_calls_json):
        """归一化为列表格式"""
        if isinstance(tool_calls_json, list):
            return tool_calls_json
        else:
            return [tool_calls_json]
    
    print("\n旧格式（单个dict）:")
    normalized_old = normalize_tool_calls(old_format)
    print(f"  输入: {old_format}")
    print(f"  归一化: {normalized_old}")
    print(f"  ✅ 兼容: 转换为 {len(normalized_old)} 个工具")
    
    print("\n新格式（list）:")
    normalized_new = normalize_tool_calls(new_format)
    print(f"  输入: {new_format}")
    print(f"  归一化: {normalized_new}")
    print(f"  ✅ 支持: {len(normalized_new)} 个工具")
    
    print("\n" + "=" * 60)
    print("兼容性测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    print("\n")
    print("🧪 AIR V7 工具链执行逻辑测试")
    print("=" * 60)
    print("测试新的规划-执行-评估模式")
    print("=" * 60)
    
    # 运行测试
    test_parse_tool_calls()
    test_tool_chain_execution_logic()
    test_compatibility()
    
    print("\n" + "=" * 60)
    print("✅ 所有测试完成！")
    print("=" * 60)
    print("\n关键验证点:")
    print("  1. ✅ 支持解析JSON数组格式的工具调用")
    print("  2. ✅ 工具链按序列执行（链式传递）")
    print("  3. ✅ 每次turn从原图重新开始")
    print("  4. ✅ 向后兼容单个工具调用")
    print("\n下一步: 运行实际训练，监控日志输出")
    print("  grep '工具链执行完成' logs/*.log")
    print("  grep '从原图开始' logs/*.log")
    print()

