#!/usr/bin/env python3
"""
全面验证v8-3分支是否包含所有修复
"""

import re

print("="*80)
print("验证air_v8-3分支 - 完整检查")
print("="*80)

with open('verl/workers/agent/parallel_env.py', 'r') as f:
    content = f.read()

issues = []
fixes = []

print("\n1. ✓ 工具链执行模式")
print("-"*80)
if 'origin_multi_modal_data = sample.get' in content and 'raw_prompt = sample.get' in content:
    print("✅ execute_tool_call接收origin_multi_modal_data和raw_prompt")
    fixes.append("工具链数据传递")
else:
    print("❌ 缺少origin_multi_modal_data传递")
    issues.append("工具链数据传递缺失")

if 'current_image_data = origin_multi_modal_data' in content:
    print("✅ 从原图开始执行工具链")
    fixes.append("工具链从原图开始")
else:
    print("❌ 不是从原图开始")
    issues.append("工具链执行逻辑是旧的")

print("\n2. ✓ GT索引修复")
print("-"*80)
if 'needs_interleave' in content:
    print("✅ 添加了needs_interleave自动检测")
    fixes.append("GT索引自动检测")
else:
    print("❌ 缺少needs_interleave检测")
    issues.append("GT索引可能错位")

if 'Added extra_info (直接对应)' in content or ('extra_info_array[i] = saved_extra_info_list[i]' in content and 'orig_idx = i // sampling_params.n' not in content.split('extra_info_array[i]')[0].split('extra_info_array[i]')[-1][:200]):
    print("✅ extra_info使用直接索引（已修复）")
    fixes.append("extra_info索引修复")
else:
    print("⚠️  extra_info可能还在使用interleave")

print("\n3. ✓ 统计逻辑")
print("-"*80)
if 'executed_tools' in content and "len(executed_tools) > 0" in content:
    print("✅ 统计逻辑检查executed_tools（只有成功才计数）")
    fixes.append("统计逻辑修复")
else:
    print("❌ 统计逻辑还是旧的")
    issues.append("统计逻辑不准确")

print("\n4. ✓ 调试功能")
print("-"*80)
if 'size_anomaly_records' in content:
    print("✅ 添加了尺寸异常检测")
    fixes.append("尺寸异常检测")
else:
    print("⚠️  没有尺寸异常检测")

if 'DEBUG GT SIZE' in content:
    print("✅ 添加了GT SIZE验证日志")
    fixes.append("GT SIZE验证")
else:
    print("⚠️  没有GT SIZE验证")

print("\n5. ✓ 初始化和数据保存（关键）")
print("-"*80)
# 检查初始化
reset_pattern = r'image_history = \[deepcopy\((.*?)\)\]'
matches = re.findall(reset_pattern, content)
has_origin_init = False
has_multi_init = False
for match in matches:
    if 'origin_multi_modal_data' in match:
        has_origin_init = True
    elif 'multi_modal_data' in match and 'origin' not in match:
        has_multi_init = True

if has_origin_init:
    print("✅ 初始化使用origin_multi_modal_data（原始PIL）")
    fixes.append("初始化数据源正确")
elif has_multi_init:
    print("❌ 初始化使用multi_modal_data（fetch后）")
    issues.append("初始化数据源错误")
else:
    print("⚠️  未找到初始化代码")

print("\n" + "="*80)
print("总结")
print("="*80)

print(f"\n✅ 已包含的修复: {len(fixes)}")
for i, fix in enumerate(fixes, 1):
    print(f"  {i}. {fix}")

if issues:
    print(f"\n❌ 仍存在的问题: {len(issues)}")
    for i, issue in enumerate(issues, 1):
        print(f"  {i}. {issue}")
    print("\n⚠️  v8-3分支还需要进一步修复")
else:
    print("\n✅ 所有修复都已包含！")
    print("   v8-3分支可以使用！")

print("\n" + "="*80)

