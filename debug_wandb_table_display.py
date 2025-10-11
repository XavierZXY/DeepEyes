#!/usr/bin/env python3
"""Debug why wandb table exists but doesn't display"""

import wandb

def check_wandb_table_structure():
    """检查wandb表格结构"""
    
    print("="*80)
    print("模拟wandb表格创建和显示逻辑")
    print("="*80)
    
    # 模拟表格列
    MAX_TURNS = 5
    columns = ["Step", "Sample_ID", "Quality_Score", "Num_Tools", "User_Input"]
    for turn_idx in range(MAX_TURNS):
        columns.append(f"Turn{turn_idx+1}_Think")
        columns.append(f"Turn{turn_idx+1}_Tools")
    
    print(f"\n表格列数: {len(columns)}")
    print(f"列名: {columns}")
    
    # 场景1: 所有数据都是空字符串的表格
    print("\n" + "="*80)
    print("场景1: 所有turn数据都是空字符串")
    print("="*80)
    
    empty_row = [
        100,  # step
        "val_step100_idx0",  # sample_id
        0.5,  # quality
        0,    # num_tools
        "Please restore this degraded image.",  # user_input
        "", "", "", "", "", "", "", "", "", ""  # 所有turn都是空
    ]
    
    print(f"行数据长度: {len(empty_row)}")
    print(f"是否匹配列数: {len(empty_row) == len(columns)}")
    print(f"行内容: {empty_row[:6]}... (前6列)")
    
    # 场景2: 有实际数据的表格
    print("\n" + "="*80)
    print("场景2: 有实际turn数据")
    print("="*80)
    
    valid_row = [
        100,  # step
        "val_step100_idx0",  # sample_id
        0.5,  # quality
        2,    # num_tools
        "Please restore this degraded image.",  # user_input
        "I need to denoise first", '{"name":"ImageProcessor"}',  # Turn1
        "Now enhance", '{"name":"EnhanceImage"}',  # Turn2
        "", "", "", "", "", ""  # Turn3-5为空
    ]
    
    print(f"行数据长度: {len(valid_row)}")
    print(f"是否匹配列数: {len(valid_row) == len(columns)}")
    print(f"Turn1数据: Think='{valid_row[5][:30]}...', Tools='{valid_row[6][:30]}...'")
    
    # 场景3: validation时可能的数据状态
    print("\n" + "="*80)
    print("场景3: Validation实际情况分析")
    print("="*80)
    
    # 模拟validation数据收集
    val_conversation_histories = []  # 验证时通常为空列表
    val_responses = [[1234, 5678, 9012]]  # tensor列表
    
    print(f"conversation_histories长度: {len(val_conversation_histories)}")
    print(f"responses长度: {len(val_responses)}")
    
    # 模拟条件检查
    idx = 0
    turn_data_from_conv = {}
    
    if idx < len(val_conversation_histories) and val_conversation_histories[idx] is not None:
        print("✓ 会从conversation_histories提取")
    else:
        print("❌ 不会从conversation_histories提取（条件不满足）")
        print(f"   原因: idx({idx}) < len(val_conversation_histories)({len(val_conversation_histories)}) = {idx < len(val_conversation_histories)}")
    
    if len(turn_data_from_conv) == 0 and idx < len(val_responses):
        print("✓ 应该从responses提取（turn_data为空且有responses）")
    else:
        print("❌ 不会从responses提取")
    
    # 场景4: 检查wandb显示限制
    print("\n" + "="*80)
    print("场景4: Wandb显示限制检查")
    print("="*80)
    
    print("""
Wandb表格显示可能的问题：
1. ✓ 列数过多（15列）- wandb应该能处理
2. ❌ 所有数据列（Turn*_Think, Turn*_Tools）都是空字符串
   - wandb可能会显示表格但看起来是空的
   - 建议：至少有User_Input和Quality_Score应该显示
3. ⚠️  表格累积问题
   - 每次运行会向同一个表格添加行
   - 如果first_run时old_count=0，应该会上传
4. 🔍 关键检查：
   - conversation_histories是否真的被收集？
   - responses能否正确decode？
   - turn_data是否真的为空？
""")
    
    # 场景5: 提供解决方案
    print("\n" + "="*80)
    print("解决方案")
    print("="*80)
    
    print("""
问题根因：validation时conversation_histories为空列表[]

修复方案：
1. 检查validation流程是否收集了conversation_history
   - 在ray_trainer.py的_validate方法中添加调试
   - 确认test_batch.non_tensor_batch中是否有'conversation_history'

2. 如果validation确实没有conversation_history，确保从responses提取
   - 条件应该改为：
     if (len(conversation_histories) == 0 or 
         idx >= len(conversation_histories) or 
         conversation_histories[idx] is None or 
         (isinstance(conversation_histories[idx], list) and len(conversation_histories[idx]) == 0)):
         # 尝试从responses提取

3. 验证tokenizer和responses是否正确传入
   - responses应该是tensor列表
   - tokenizer应该不为None
""")

if __name__ == "__main__":
    check_wandb_table_structure()

