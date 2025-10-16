#!/usr/bin/env python3
"""
调试验证集中对话和参考指标的问题
"""

import sys
import numpy as np

def check_conversation_table_logic():
    """检查对话表格的逻辑"""
    print("="*60)
    print("检查对话表格逻辑")
    print("="*60)
    
    # 模拟数据
    image_histories = [['img1', 'img2'], ['img3', 'img4']]
    conversation_histories = [None, None]  # 可能的问题：为None
    indices = list(range(len(image_histories)))
    
    print(f"len(image_histories) = {len(image_histories)}")
    print(f"len(conversation_histories) = {len(conversation_histories)}")
    print(f"indices = {indices}")
    
    # 检查是否会添加行
    rows_added = 0
    for idx in indices:
        if idx >= len(image_histories):
            continue
        
        img_hist = image_histories[idx]
        if img_hist is None:
            continue
        
        # 检查conversation_history
        if idx < len(conversation_histories) and conversation_histories[idx] is not None:
            print(f"  Sample {idx}: has conversation_history")
            rows_added += 1
        else:
            print(f"  Sample {idx}: NO conversation_history, will try to parse from response")
            # 在实际代码中，会尝试从responses解析
    
    print(f"\n预期添加 {rows_added} 行")
    print()

def check_reference_metrics_logic():
    """检查参考指标计算逻辑"""
    print("="*60)
    print("检查参考指标计算逻辑")
    print("="*60)
    
    # 模拟数据
    image_histories = [
        ['img1', 'img2'],  # 长度=2，工具已执行
        ['img3'],           # 长度=1，工具未执行
    ]
    original_images = [None, None]  # 可能的问题：为None
    
    print(f"len(image_histories) = {len(image_histories)}")
    print(f"len(original_images) = {len(original_images)}")
    
    num_samples = len(image_histories)
    calculated_count = 0
    
    for idx in range(num_samples):
        # 检查original_image
        if idx >= len(original_images) or original_images[idx] is None:
            print(f"  Sample {idx}: NO original_image → SKIP (score=0.0)")
            continue
        
        # 检查image_history
        if idx >= len(image_histories):
            print(f"  Sample {idx}: NO image_history → SKIP (score=0.0)")
            continue
        
        img_hist = image_histories[idx]
        if img_hist is None or not isinstance(img_hist, (list, tuple)) or len(img_hist) < 2:
            print(f"  Sample {idx}: image_history length={len(img_hist) if img_hist else 0} < 2 → SKIP (score=0.0)")
            continue
        
        print(f"  Sample {idx}: ✓ Would calculate metrics")
        calculated_count += 1
    
    print(f"\n预期计算 {calculated_count}/{num_samples} 个样本的参考指标")
    print()

def check_agent_mode_extra_info():
    """检查agent模式下extra_info的interleave逻辑"""
    print("="*60)
    print("检查agent模式下extra_info的interleave")
    print("="*60)
    
    # 训练模式：n=8
    saved_extra_info_list = [
        {'degradation_type': 'blur', 'original_image': 'img1'},
        {'degradation_type': 'noise', 'original_image': 'img2'},
    ]
    sampling_n = 8
    expected_size = len(saved_extra_info_list) * sampling_n
    
    print(f"训练模式: n={sampling_n}, saved={len(saved_extra_info_list)}, expected={expected_size}")
    
    extra_info_array = []
    for i in range(expected_size):
        orig_idx = i // sampling_n if sampling_n > 1 else i
        extra_info = saved_extra_info_list[orig_idx] if orig_idx < len(saved_extra_info_list) else None
        extra_info_array.append(extra_info)
    
    # 检查是否所有extra_info都有original_image
    has_original = sum(1 for e in extra_info_array if e and e.get('original_image'))
    print(f"  结果: {has_original}/{expected_size} 个extra_info有original_image")
    
    # 验证模式：n=1
    sampling_n = 1
    expected_size = len(saved_extra_info_list) * sampling_n
    
    print(f"\n验证模式: n={sampling_n}, saved={len(saved_extra_info_list)}, expected={expected_size}")
    
    extra_info_array = []
    for i in range(expected_size):
        orig_idx = i // sampling_n if sampling_n > 1 else i
        extra_info = saved_extra_info_list[orig_idx] if orig_idx < len(saved_extra_info_list) else None
        extra_info_array.append(extra_info)
    
    # 检查是否所有extra_info都有original_image
    has_original = sum(1 for e in extra_info_array if e and e.get('original_image'))
    print(f"  结果: {has_original}/{expected_size} 个extra_info有original_image")
    print()

if __name__ == "__main__":
    check_conversation_table_logic()
    check_reference_metrics_logic()
    check_agent_mode_extra_info()
    
    print("="*60)
    print("结论")
    print("="*60)
    print("1. 如果conversation_histories为空/None，对话不会显示")
    print("   → 需要检查agent_rollout_loop是否正确保存conversation_history")
    print()
    print("2. 如果original_images为None，参考指标=0")
    print("   → 需要检查extra_info['original_image']是否被正确提取")
    print()
    print("3. extra_info需要被正确interleave以匹配batch_size")
    print("   → 已在parallel_env.py中实现")

