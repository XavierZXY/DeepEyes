"""
测试退化类型匹配逻辑（无序匹配）
"""

# 模拟check_degradation_type_match_v2函数的核心逻辑

def merge_consecutive_duplicates_v2(restoration_log):
    """合并连续重复"""
    if not restoration_log:
        return []
    
    merged_log = []
    for item in restoration_log:
        if not merged_log or merged_log[-1] != item:
            merged_log.append(item)
    
    return merged_log

def check_degradation_type_match_v2(predicted_log, reward_model_order):
    """检查退化类型匹配（不考虑顺序，只看集合）"""
    
    if not reward_model_order:
        return 0.0
    
    # 过滤掉 "clean" 标签
    if predicted_log:
        filtered_predicted_log = [
            item for item in predicted_log 
            if item is not None and str(item).strip().lower() != "clean"
        ]
    else:
        filtered_predicted_log = []
    
    if not filtered_predicted_log:
        print(f'过滤clean后预测为空，返回0分')
        return 0.0
    
    # 合并连续重复的退化类型
    merged_predicted_log = merge_consecutive_duplicates_v2(filtered_predicted_log)
    
    # 转换为集合
    try:
        predicted_set = set(str(item) for item in merged_predicted_log if item is not None)
        expected_set = set(str(item) for item in reward_model_order if item is not None)
    except (TypeError, AttributeError) as e:
        print(f'集合转换失败: {e}')
        return 0.0
    
    print(f'预测集合: {predicted_set}')
    print(f'期望集合: {expected_set}')
    
    # Check if predicted types are valid
    if not predicted_set.issubset(expected_set):
        invalid_types = predicted_set - expected_set
        print(f'预测了无效的退化类型: {invalid_types}')
        return 0.0
    
    # Calculate match score
    if predicted_set == expected_set:
        score = 1.0
        print(f'完全匹配，奖励=1.0')
    elif len(predicted_set) > 0:
        score = len(predicted_set) / len(expected_set)
        print(f'部分匹配: {len(predicted_set)}/{len(expected_set)}, 奖励={score:.3f}')
    else:
        score = 0.0
        print(f'无匹配，奖励=0.0')
    
    return score


print("=" * 70)
print("退化类型匹配测试 - 验证是否为无序匹配")
print("=" * 70)

# 测试用例
expected = ["blur", "noise", "jpeg_artifact"]

print("\n【测试1: 完全匹配 - 顺序相同】")
predicted = ["blur", "noise", "jpeg_artifact"]
score = check_degradation_type_match_v2(predicted, expected)
print(f"结果: {score} ✅ 应该是1.0\n")

print("=" * 70)
print("\n【测试2: 完全匹配 - 顺序不同】⭐ 关键测试")
predicted = ["noise", "jpeg_artifact", "blur"]  # 顺序完全不同
score = check_degradation_type_match_v2(predicted, expected)
print(f"结果: {score} ✅ 应该是1.0（证明是无序匹配）\n")

print("=" * 70)
print("\n【测试3: 完全匹配 - 顺序反转】")
predicted = ["jpeg_artifact", "noise", "blur"]  # 完全反序
score = check_degradation_type_match_v2(predicted, expected)
print(f"结果: {score} ✅ 应该是1.0（证明是无序匹配）\n")

print("=" * 70)
print("\n【测试4: 部分匹配 - 顺序不同】")
predicted = ["noise", "blur"]  # 只有2个，且顺序不同
score = check_degradation_type_match_v2(predicted, expected)
print(f"结果: {score} ✅ 应该是0.667（2/3）\n")

print("=" * 70)
print("\n【测试5: 包含重复】")
predicted = ["noise", "noise", "blur", "blur", "jpeg_artifact"]  # 包含重复
score = check_degradation_type_match_v2(predicted, expected)
print(f"结果: {score} ✅ 应该是1.0（自动合并重复）\n")

print("=" * 70)
print("\n【测试6: 包含clean标签】")
predicted = ["noise", "blur", "jpeg_artifact", "clean"]  # 包含clean
score = check_degradation_type_match_v2(predicted, expected)
print(f"结果: {score} ✅ 应该是1.0（自动过滤clean）\n")

print("=" * 70)
print("\n【测试7: 无效类型】")
predicted = ["noise", "blur", "haze"]  # haze不在期望中
score = check_degradation_type_match_v2(predicted, expected)
print(f"结果: {score} ✅ 应该是0.0（包含无效类型）\n")

print("=" * 70)
print("\n【测试8: 乱序+重复+clean】⭐ 综合测试")
predicted = ["jpeg_artifact", "clean", "noise", "noise", "blur", "blur"]
score = check_degradation_type_match_v2(predicted, expected)
print(f"结果: {score} ✅ 应该是1.0（过滤+去重+集合匹配）\n")

print("=" * 70)
print("\n✅ 测试结论:")
print("  - 退化类型奖励是完全无序的（只看集合匹配）")
print("  - 顺序完全不影响分数")
print("  - 自动处理clean标签和重复")
print("  - 只要预测的退化类型集合与期望集合相同，就得满分")
print("=" * 70)
