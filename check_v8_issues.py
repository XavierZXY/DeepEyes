#!/usr/bin/env python3
"""
检查v8分支是否存在今天发现的所有问题
"""

print("="*80)
print("检查air_v8-2分支的问题")
print("="*80)

issues = []

# 读取parallel_env.py
with open('verl/workers/agent/parallel_env.py', 'r') as f:
    content = f.read()

print("\n1. 检查工具链执行模式")
print("-"*80)
if 'def execute_tool_call' in content:
    if '工具链执行：逐个应用' in content or '按序列执行工具链' in content:
        print("✅ 使用工具链执行模式（规划-执行-评估）")
    elif '# 逐个执行工具' in content or 'Execute tools sequentially' in content:
        print("❌ 使用旧的逐个执行模式")
        issues.append("工具链执行模式是旧的逐个执行")
else:
    print("⚠️  未找到execute_tool_call函数")

print("\n2. 检查fetch_image污染问题")
print("-"*80)
if 'multi_modal_data_for_reward' in content:
    print("✅ 保存了multi_modal_data_for_reward（原始PIL）")
else:
    print("❌ 没有multi_modal_data_for_reward")
    issues.append("没有保存multi_modal_data_for_reward，fetch_image会污染")

print("\n3. 检查初始化时的数据源")
print("-"*80)
import re
reset_pattern = r'image_history = \[deepcopy\((.*?)\)\]'
matches = re.findall(reset_pattern, content)
if matches:
    for match in matches:
        if 'origin_multi_modal_data' in match:
            print(f"✅ 初始化使用origin_multi_modal_data: {match}")
        elif 'multi_modal_data' in match and 'origin' not in match:
            print(f"❌ 初始化使用multi_modal_data（fetch后）: {match}")
            issues.append("初始化使用了fetch后的multi_modal_data")
else:
    print("⚠️  未找到image_history初始化代码")

print("\n4. 检查extra_info的索引逻辑")
print("-"*80)
if 'orig_idx = i // sampling_params.n' in content:
    # 检查是否在extra_info添加时使用
    extra_info_section = content[content.find("添加extra_info"):content.find("添加extra_info")+500] if "添加extra_info" in content else ""
    if 'orig_idx = i // sampling_params.n' in extra_info_section:
        print("❌ extra_info使用了interleave逻辑（可能错位）")
        issues.append("extra_info使用interleave可能导致索引错位")
    else:
        print("✅ extra_info可能使用了正确的索引")
else:
    print("⚠️  代码结构可能不同")

print("\n5. 检查原图数据传递")
print("-"*80)
if 'origin_multi_modal_data=self.origin_multi_modal_data_list[idx]' in content:
    print("✅ 传递了origin_multi_modal_data给execute_tool_call")
else:
    print("❌ 没有传递origin_multi_modal_data")
    issues.append("execute_tool_call缺少origin_multi_modal_data，工具链无法执行")

print("\n6. 检查工具调用统计逻辑")
print("-"*80)
if 'executed_tools' in content and 'len(executed_tools) > 0' in content:
    print("✅ 统计逻辑检查executed_tools（只有成功执行才计数）")
else:
    print("⚠️  统计逻辑可能还是旧的（只要有tool_call就计数）")
    issues.append("统计逻辑可能不准确")

print("\n" + "="*80)
print("总结")
print("="*80)

if issues:
    print(f"\n❌ 发现 {len(issues)} 个问题:\n")
    for i, issue in enumerate(issues, 1):
        print(f"  {i}. {issue}")
    
    print(f"\n建议:")
    print("  选项1: 从air_v7合并修复")
    print("    git merge air_v7")
    print()
    print("  选项2: Cherry-pick相关提交")
    print("    git cherry-pick <commit-hash>")
    print()
    print("  选项3: 手动应用所有修复")
    print("    参考air_v7分支的修改")
else:
    print("\n✅ 所有修复都已包含")

print("\n" + "="*80)

