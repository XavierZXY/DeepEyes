"""
测试退化类型分数统计逻辑
"""
import numpy as np

# 模拟reward_extra_infos_dict
reward_extra_infos_dict = {
    'ir_degradation_type_score': [
        0.0,    # Clean样本或未启用
        1.0,    # 完全匹配
        0.667,  # 2/3匹配
        0.0,    # Clean样本
        1.0,    # 完全匹配
        0.5,    # 1/2匹配
        0.0,    # 未启用
        1.0,    # 完全匹配
    ]
}

print("=" * 70)
print("退化类型分数统计测试")
print("=" * 70)

degradation_type_scores = reward_extra_infos_dict['ir_degradation_type_score']

print(f"\n原始分数: {degradation_type_scores}")
print(f"总样本数: {len(degradation_type_scores)}")

# 过滤掉0.0的分数（clean样本或未启用）
non_zero_scores = [s for s in degradation_type_scores if s > 0.0]

print(f"\n有效分数（>0）: {non_zero_scores}")
print(f"有效样本数: {len(non_zero_scores)}")

if len(non_zero_scores) > 0:
    print(f"\n📊 有效样本统计:")
    print(f"  mean: {np.mean(non_zero_scores):.3f}")
    print(f"  max:  {np.max(non_zero_scores):.3f}")
    print(f"  min:  {np.min(non_zero_scores):.3f}")
    print(f"  std:  {np.std(non_zero_scores):.3f}")
    print(f"  valid_samples: {len(non_zero_scores)}")
    print(f"  valid_ratio: {len(non_zero_scores) / len(degradation_type_scores):.3f}")

print(f"\n📊 所有样本统计（包括0分）:")
print(f"  mean_all: {np.mean(degradation_type_scores):.3f}")

print("\n" + "=" * 70)
print("✅ WandB将记录以下指标:")
print("=" * 70)
print("reward/degradation_type_score_mean       # 有效样本的平均分")
print("reward/degradation_type_score_max        # 最高分")
print("reward/degradation_type_score_min        # 最低分（有效样本中）")
print("reward/degradation_type_score_std        # 标准差")
print("reward/degradation_type_valid_samples    # 有效样本数")
print("reward/degradation_type_valid_ratio      # 有效样本比例")
print("reward/degradation_type_score_mean_all   # 所有样本平均（包括0分）")
print("=" * 70)

print("\n💡 说明:")
print("  - 有效样本：degradation_type_score > 0.0")
print("  - 0分样本：clean样本或退化类型奖励未启用")
print("  - mean/max/min/std 只统计有效样本")
print("  - mean_all 统计所有样本（包括0分）")
print("")
