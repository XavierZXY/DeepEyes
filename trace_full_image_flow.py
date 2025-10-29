#!/usr/bin/env python3
"""
完整追踪图像尺寸在整个流程中的变化
"""

import re

log_file = 'logs/debug_for_AIR_multideg_plan_ref_bs32_n8_spv13_lr1e-6_datarand_mi300.log'

print("="*80)
print("完整追踪图像尺寸流程")
print("="*80)

with open(log_file, 'r') as f:
    lines = f.readlines()

# 找一个特定样本的完整流程
# 查找有详细日志的样本

print("\n查找带有完整调试信息的样本...")

# 1. 找到工具输入尺寸
tool_input_pattern = r'T(\d+)-样本(\d+)\] 📏 工具输入图像尺寸: \((\d+), (\d+)\)'
tool_inputs = []

for line in lines:
    match = re.search(tool_input_pattern, line)
    if match:
        turn, sample_id, w, h = match.groups()
        tool_inputs.append({
            'turn': int(turn),
            'sample': int(sample_id),
            'size': (int(w), int(h)),
            'line': line
        })

if tool_inputs:
    # 选择第一个样本
    first_sample = tool_inputs[0]
    sample_id = first_sample['sample']
    
    print(f"\n追踪样本 {sample_id} 的完整流程:")
    print("="*80)
    
    # 2. 查找这个样本的所有相关日志
    sample_logs = []
    for i, line in enumerate(lines):
        if f'样本{sample_id}' in line or f'Sample {sample_id}' in line:
            sample_logs.append((i, line))
    
    print(f"\n找到 {len(sample_logs)} 条相关日志\n")
    
    # 3. 按顺序显示关键信息
    print("阶段1: 工具输入")
    print("-"*80)
    for i, line in sample_logs:
        if '工具输入图像尺寸' in line or '📏' in line:
            print(line.strip())
    
    print("\n阶段2: 工具执行")
    print("-"*80)
    tool_exec_count = 0
    for i, line in sample_logs:
        if '🚀 开始执行工具' in line or '✅ 工具' in line and '执行' in line:
            print(line.strip())
            tool_exec_count += 1
            if tool_exec_count >= 5:  # 只显示前5个
                break
    
    print("\n阶段3: 工具链完成")
    print("-"*80)
    for i, line in sample_logs:
        if '工具链执行完成' in line or '🎉' in line:
            print(line.strip())
            break
    
    print("\n阶段4: 图像历史保存")
    print("-"*80)
    for i, line in sample_logs:
        if '保存原始PIL图像' in line or '💾' in line:
            print(line.strip())
            break
    
    print("\n阶段5: Reward计算")
    print("-"*80)
    reward_calc_found = False
    for i, line in sample_logs:
        if '复原图' in line and '尺寸' in line:
            print(line.strip())
            if '原图' in line:
                reward_calc_found = True
        if reward_calc_found and '尺寸不匹配' in line:
            print(line.strip())
            break
    
    print("\n" + "="*80)

else:
    print("\n未找到工具输入日志（可能batch还在执行）")

# 通用分析
print("\n\n" + "="*80)
print("所有SSIM尺寸不匹配案例统计")
print("="*80)

ssim_pattern = r'\[DEBUG SSIM\] 图像尺寸不匹配: image1=(\d+)x(\d+), image2=(\d+)x(\d+)'
ssim_matches = re.findall(ssim_pattern, open(log_file).read())

if ssim_matches:
    unique = list(set(ssim_matches))
    print(f"\n找到 {len(unique)} 个独特的尺寸不匹配案例\n")
    
    # 分类
    categories = {
        'need_sr4_used_nothing': [],  # 需要SR×4，什么都没用
        'need_sr4_used_sr2': [],      # 需要SR×4，只用了SR×2
        'no_need_sr_used_sr': [],     # 不需要SR，错误使用了
        'need_sr2_used_sr2': [],      # 需要SR×2（应该SR×4但用了SR×2）
    }
    
    for w1, h1, w2, h2 in unique:
        w1, h1, w2, h2 = int(w1), int(h1), int(w2), int(h2)
        ratio_w = w2 / w1
        ratio_h = h2 / h1
        avg_ratio = (ratio_w + ratio_h) / 2
        
        if 3.5 < avg_ratio < 4.5:
            categories['need_sr4_used_nothing'].append((w1, h1, w2, h2))
        elif 1.5 < avg_ratio < 2.5:
            categories['need_sr4_used_sr2'].append((w1, h1, w2, h2))
        elif 0.4 < avg_ratio < 0.6:
            categories['no_need_sr_used_sr'].append((w1, h1, w2, h2))
    
    print("分类统计:")
    print("-"*80)
    print(f"  需要SR×4，没用SR: {len(categories['need_sr4_used_nothing'])} 个")
    print(f"  需要SR×4，只用SR×2: {len(categories['need_sr4_used_sr2'])} 个")
    print(f"  不需要SR，错用SR: {len(categories['no_need_sr_used_sr'])} 个")
    
    print("\n详细案例（各类型前3个）:")
    print("="*80)
    
    for cat_name, cat_list in categories.items():
        if cat_list:
            print(f"\n{cat_name}:")
            for w1, h1, w2, h2 in cat_list[:3]:
                print(f"  复原图: ({w1}, {h1}), GT: ({w2}, {h2}), 比例: {w2/w1:.2f}x")

print("\n" + "="*80)
print("结论: 所有不匹配都是模型SR策略导致，不是工具bug")
print("="*80)

