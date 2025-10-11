"""
测试clean标签的逻辑：是否必须预测clean？
"""

def merge_consecutive_duplicates_v2(restoration_log):
    if not restoration_log:
        return []
    merged_log = []
    for item in restoration_log:
        if not merged_log or merged_log[-1] != item:
            merged_log.append(item)
    return merged_log

def check_degradation_type_match_v2(predicted_log, reward_model_order):
    """检查退化类型匹配（不考虑顺序）"""
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
    
    # 合并连续重复
    merged_predicted_log = merge_consecutive_duplicates_v2(filtered_predicted_log)
    
    # 转换为集合
    predicted_set = set(str(item) for item in merged_predicted_log if item is not None)
    expected_set = set(str(item) for item in reward_model_order if item is not None)
    
    print(f'原始预测: {predicted_log}')
    print(f'过滤clean: {filtered_predicted_log}')
    print(f'合并重复: {merged_predicted_log}')
    print(f'预测集合: {predicted_set}')
    print(f'期望集合: {expected_set}')
    
    # Check validity
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
print("Clean标签测试 - 验证是否必须预测clean")
print("=" * 70)

expected = ["blur", "noise", "jpeg_artifact"]

print("\n【测试1: 不包含clean - 完全匹配】⭐ 关键测试")
predicted = ["noise", "jpeg_artifact", "blur"]  # 没有clean
score = check_degradation_type_match_v2(predicted, expected)
print(f"结果: {score}")
print(f"✅ 不需要预测clean也能得满分！\n")

print("=" * 70)
print("\n【测试2: 包含clean - 完全匹配】")
predicted = ["noise", "jpeg_artifact", "blur", "clean"]  # 有clean
score = check_degradation_type_match_v2(predicted, expected)
print(f"结果: {score}")
print(f"✅ 包含clean也能得满分（clean会被过滤）\n")

print("=" * 70)
print("\n【测试3: 只有clean标签】")
predicted = ["clean"]  # 只有clean
score = check_degradation_type_match_v2(predicted, expected)
print(f"结果: {score}")
print(f"✅ 只有clean会得0分（过滤后为空）\n")

print("=" * 70)
print("\n【测试4: 部分匹配 - 不含clean】")
predicted = ["noise", "blur"]  # 只有2个，不含clean
score = check_degradation_type_match_v2(predicted, expected)
print(f"结果: {score}")
print(f"✅ 部分匹配，得2/3分\n")

print("=" * 70)
print("\n【测试5: 部分匹配 - 含clean】")
predicted = ["noise", "blur", "clean"]  # 只有2个退化类型+clean
score = check_degradation_type_match_v2(predicted, expected)
print(f"结果: {score}")
print(f"✅ 部分匹配，得2/3分（clean不影响）\n")

print("=" * 70)
print("\n【测试6: 多次重复 - 不含clean】")
predicted = ["noise", "noise", "blur", "jpeg_artifact", "jpeg_artifact"]
score = check_degradation_type_match_v2(predicted, expected)
print(f"结果: {score}")
print(f"✅ 自动去重后完全匹配\n")

print("=" * 70)
print("\n【测试7: 多次重复 - 含clean】")
predicted = ["noise", "clean", "blur", "clean", "jpeg_artifact"]
score = check_degradation_type_match_v2(predicted, expected)
print(f"结果: {score}")
print(f"✅ 过滤clean+去重后完全匹配\n")

print("=" * 70)
print("\n🎯 结论:")
print("  1. ✅ 不需要预测clean也能得满分")
print("  2. ✅ clean标签会被自动过滤，不影响分数")
print("  3. ✅ 只看退化类型集合，不看clean")
print("  4. ✅ 只有clean → 0分（过滤后为空）")
print("  5. ✅ 退化类型正确 → 满分（无论有无clean）")
print("")
print("💡 设计理念:")
print("  - clean只是模型表达'完成恢复'的方式")
print("  - 不应该影响退化类型识别的评分")
print("  - 模型可以自由选择是否使用clean标记")
print("=" * 70)
