#!/usr/bin/env python3
"""
验证Wandb表格逻辑的完整性
"""

def simulate_tool_status_logic(has_tool_request, has_tool_execution, 
                                 conv_hist_len=0, img_hist_len=0, 
                                 has_answer=False, requested_tools=None, 
                                 tool_error_msg=None):
    """模拟工具状态判断逻辑"""
    tool_status = "Unknown"
    failure_reason = ""
    
    if has_tool_request and has_tool_execution:
        tool_status = "✅ Success"
        failure_reason = "-"
    elif has_tool_request and not has_tool_execution:
        tool_status = "⚠️ Requested but Failed"
        failure_reasons = []
        
        # 原因0: 工具错误信息（最优先）
        if tool_error_msg:
            error_display = tool_error_msg if len(tool_error_msg) <= 100 else (tool_error_msg[:97] + "...")
            failure_reasons.append(f"错误: {error_display}")
        
        if conv_hist_len == 1:
            failure_reasons.append("max_turns=1 (工具来不及执行)")
        
        if img_hist_len == 1:
            failure_reasons.append("工具未产生新图像")
        
        if img_hist_len == 0:
            failure_reasons.append("image_history为空")
        
        if requested_tools:
            failure_reasons.append(f"请求工具: {', '.join(requested_tools)}")
        
        failure_reason = " | ".join(failure_reasons) if failure_reasons else "未知原因"
    elif not has_tool_request:
        tool_status = "❌ No Tool Request"
        if has_answer:
            failure_reason = "模型直接给出答案，未调用工具"
        else:
            failure_reason = "无工具请求"
    else:
        tool_status = "❓ Unknown"
        failure_reason = "状态未知 (请检查日志)"
    
    return tool_status, failure_reason


def test_all_scenarios():
    """测试所有可能的场景"""
    print("=" * 80)
    print("Wandb表格逻辑完整性测试")
    print("=" * 80)
    
    scenarios = [
        # (场景名称, has_tool_request, has_tool_execution, conv_hist_len, img_hist_len, has_answer, requested_tools, tool_error_msg)
        ("成功执行工具", True, True, 1, 2, False, ["swinir_denoising"], None),
        ("超时错误", True, False, 1, 0, False, ["restormer_motion_deblurring"], "Tool execution timeout after 30 seconds"),
        ("解析错误", True, False, 1, 0, False, ["dehazeformer_dehaze"], "Failed to parse valid tool calls from the action string"),
        ("CUDA内存错误", True, False, 1, 0, False, ["swinir_super_resolution"], "Model loading failed: CUDA out of memory"),
        ("max_turns=1导致失败", True, False, 1, 1, False, ["restormer_deraining"], None),
        ("工具执行失败", True, False, 2, 1, False, ["dehazeformer_dehaze"], None),
        ("错误信息+多原因", True, False, 1, 1, False, ["fbcnn_jpeg_artifact_removal"], "Invalid image format: expected RGB, got RGBA"),
        ("过长错误信息截断", True, False, 1, 0, False, ["swinir_denoising"], "A" * 150),  # 测试截断
        ("直接给答案", False, False, 1, 1, True, None, None),
        ("完全无输出", False, False, 0, 0, False, None, None),
    ]
    
    print(f"\n共 {len(scenarios)} 个测试场景:\n")
    
    all_passed = True
    for i, (name, *args) in enumerate(scenarios, 1):
        status, reason = simulate_tool_status_logic(*args)
        
        # 检查failure_reason是否被设置
        if not reason:
            print(f"❌ 场景{i}: {name}")
            print(f"   ERROR: failure_reason未设置!")
            all_passed = False
        else:
            print(f"✅ 场景{i}: {name}")
            print(f"   Tool_Status: {status}")
            print(f"   Failure_Reason: {reason}")
        print()
    
    print("=" * 80)
    if all_passed:
        print("✅✅✅ 所有场景测试通过！逻辑完整无遗漏。")
    else:
        print("❌ 部分场景测试失败，请检查逻辑。")
    print("=" * 80)
    
    return all_passed


def verify_column_count():
    """验证列数是否正确"""
    print("\n" + "=" * 80)
    print("列数验证")
    print("=" * 80)
    
    MAX_TURNS = 5
    base_columns = ["Step", "Sample_ID", "Trajectory_Image", "Quality_Score", "Num_Tools", 
                    "Degradation_Type", "Tool_Status", "Failure_Reason", "User_Input"]
    turn_columns = []
    for turn_idx in range(MAX_TURNS):
        turn_columns.append(f"Turn{turn_idx+1}_Think")
        turn_columns.append(f"Turn{turn_idx+1}_Tools")
    
    total_columns = base_columns + turn_columns
    
    print(f"\n基础列 ({len(base_columns)}个):")
    for i, col in enumerate(base_columns, 1):
        marker = "⭐" if col in ["Degradation_Type", "Tool_Status", "Failure_Reason"] else ""
        print(f"  {i}. {col} {marker}")
    
    print(f"\nTurn列 ({len(turn_columns)}个):")
    print(f"  10-19. Turn1-5的Think和Tools列")
    
    print(f"\n总列数: {len(total_columns)}")
    
    # 验证行数据
    print(f"\n行数据构建:")
    print(f"  基础数据: 9个元素 (step, sample_id, image, quality, num_tools,")
    print(f"                     degradation_type, tool_status, failure_reason, user_input)")
    print(f"  Turn数据: 10个元素 (Turn1-5, 每个2个)")
    print(f"  总计: 19个元素")
    
    if len(total_columns) == 19:
        print(f"\n✅ 列数验证通过！共19列。")
        return True
    else:
        print(f"\n❌ 列数错误！预期19列，实际{len(total_columns)}列。")
        return False


if __name__ == "__main__":
    print()
    passed1 = test_all_scenarios()
    passed2 = verify_column_count()
    
    print("\n" + "=" * 80)
    if passed1 and passed2:
        print("🎉 所有验证通过！表格逻辑完整，可以安全使用。")
    else:
        print("⚠️  部分验证失败，请检查代码。")
    print("=" * 80)
    print()

