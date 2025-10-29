#!/usr/bin/env python3
"""
调试工具注册
检查工具是否正确注册到ToolBase.registry
"""

import sys
sys.path.insert(0, '/app/xiaominl/DeepEyes_v2')

print("=" * 80)
print("检查工具注册情况")
print("=" * 80)

# 导入ToolBase
from verl.workers.agent.tool_envs import ToolBase

print(f"\n1. ToolBase导入成功")
print(f"   初始注册表大小: {len(ToolBase.registry)}")

# 导入agent模块（会触发工具注册）
print("\n2. 导入agent模块（触发工具注册）...")
from verl.workers import agent

print(f"   导入后注册表大小: {len(ToolBase.registry)}")

# 列出所有已注册的工具
print("\n3. 已注册的工具列表:")
print("-" * 80)
for i, (name, cls) in enumerate(sorted(ToolBase.registry.items()), 1):
    print(f"   {i:2d}. {name:40s} -> {cls.__name__}")

# 检查system prompt中提到的工具
print("\n4. 检查System Prompt中的工具:")
print("-" * 80)

expected_tools = [
    "dehazeformer_dehaze",
    "restormer_defocus_deblurring",
    "restormer_motion_deblurring",
    "retinexformer_sdsd_indoor",
    "restormer_deraining",
    "fbcnn_jpeg_artifact_removal",
    "swinir_super_resolution",
    "scunet_real_denoising_gan",
]

all_found = True
for tool_name in expected_tools:
    if tool_name in ToolBase.registry:
        print(f"   ✅ {tool_name}")
    else:
        print(f"   ❌ {tool_name} - 未找到！")
        all_found = False

if all_found:
    print("\n✅ 所有期望的工具都已注册")
else:
    print("\n❌ 某些工具未注册，请检查导入")

# 测试工具创建
print("\n5. 测试工具创建:")
print("-" * 80)

test_tool = "restormer_deraining"
if test_tool in ToolBase.registry:
    try:
        tool_instance = ToolBase.create(test_tool)
        print(f"   ✅ {test_tool} 创建成功")
        print(f"      类型: {type(tool_instance)}")
        print(f"      名称: {tool_instance.name}")
    except Exception as e:
        print(f"   ❌ {test_tool} 创建失败: {e}")
else:
    print(f"   ❌ {test_tool} 未在注册表中")

print("\n" + "=" * 80)
print("检查完成")
print("=" * 80)

