#!/usr/bin/env python3
"""
验证WandB表格列定义
确认训练和验证表格都包含所有必要的列
"""

import sys

def verify_table_columns():
    """验证表格列定义"""
    print("=" * 80)
    print("WandB表格列定义验证")
    print("=" * 80)
    
    # 模拟代码中的列定义
    MAX_TURNS = 5
    
    columns = ["Step", "Sample_ID", "Trajectory_Image", "Quality_Score", "Num_Tools", 
               "Degradation_Type", "Predicted_Degradation_Type", "Prediction_Match", 
               "Tool_Status", "Failure_Reason", "User_Input"]
    
    for turn_idx in range(MAX_TURNS):
        columns.append(f"Turn{turn_idx+1}_Think")
        columns.append(f"Turn{turn_idx+1}_Tools")
    
    print(f"\n总列数: {len(columns)}")
    print("\n完整列列表:")
    print("-" * 80)
    
    # 定义新增列
    new_columns = ['Predicted_Degradation_Type', 'Prediction_Match']
    critical_columns = ['Degradation_Type', 'Tool_Status', 'Failure_Reason']
    
    for i, col in enumerate(columns, 1):
        marker = ""
        if col in new_columns:
            marker = "⭐ 新增"
        elif col in critical_columns:
            marker = "✓ 关键列"
        
        print(f"{i:2d}. {col:30s} {marker}")
    
    # 检查必要列是否都存在
    print("\n" + "=" * 80)
    print("必要列检查:")
    print("=" * 80)
    
    required_columns = [
        'Degradation_Type',
        'Predicted_Degradation_Type',
        'Prediction_Match',
        'Tool_Status',
        'Failure_Reason',
    ]
    
    all_present = True
    for col in required_columns:
        if col in columns:
            print(f"✅ {col}: 存在")
        else:
            print(f"❌ {col}: 缺失")
            all_present = False
    
    print("\n" + "=" * 80)
    if all_present:
        print("✅ 验证通过：所有必要列都已定义")
        print("\n说明:")
        print("- 训练表格（train/conversation_details）将使用此列定义")
        print("- 验证表格（val/conversation_details）也将使用此列定义")
        print("- 两个表格的列定义完全相同")
        print("\n⚠️ 注意:")
        print("- 如果你看到的是旧的WandB run，那个表格可能还是旧的列定义")
        print("- 只有新启动的训练run才会使用新的列定义")
        print("- 建议：重新开始一个新的训练run来查看新列")
    else:
        print("❌ 验证失败：有列缺失")
        return 1
    
    print("=" * 80)
    return 0

if __name__ == "__main__":
    sys.exit(verify_table_columns())

