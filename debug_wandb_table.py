#!/usr/bin/env python3
"""Debug wandb conversation table issue"""

import re

def test_conversation_extraction():
    """测试从response中提取对话的逻辑"""
    
    # 模拟一个validation response（包含多个turn）
    test_response = """<think>I need to analyze this degraded image first.</think>
<tool_call>{"name": "ImageProcessor", "arguments": {"image": "<image>", "operation": "denoise"}}</tool_call>
<tool_response>Image processed successfully</tool_response>
<think>Now I'll enhance the quality further.</think>
<tool_call>{"name": "ImageProcessor", "arguments": {"image": "<image>", "operation": "sharpen"}}</tool_call>
<tool_response>Image sharpened</tool_response>
<think>The image looks good now.</think>
<answer>The image has been restored successfully.</answer>"""
    
    print("="*80)
    print("测试1: 从response中提取多个turn")
    print("="*80)
    
    # 模拟_log_conversation_table中的逻辑
    turn_data = {}
    turn_matches = list(re.finditer(r'<think>(.*?)</think>', test_response, re.DOTALL))
    
    print(f"找到 {len(turn_matches)} 个think标签")
    
    for turn_idx, match in enumerate(turn_matches):
        turn_num = turn_idx + 1
        # 找这个turn的范围
        start_pos = match.start()
        end_pos = turn_matches[turn_idx + 1].start() if turn_idx + 1 < len(turn_matches) else len(test_response)
        turn_content = test_response[start_pos:end_pos]
        
        # 提取think
        think_match = re.search(r'<think>(.*?)</think>', turn_content, re.DOTALL)
        think_text = think_match.group(1).strip() if think_match else ""
        
        # 提取tools
        tools_text = ""
        tool_match = re.search(r'<tool_call>(.*?)</tool_call>', turn_content, re.DOTALL)
        if tool_match:
            tools_text = tool_match.group(1).strip()
        elif '<answer>' in turn_content:
            tools_text = "[ANSWER]"
        
        turn_data[turn_num] = {'think': think_text, 'tools': tools_text}
        
        print(f"\nTurn {turn_num}:")
        print(f"  Think: {think_text[:50]}...")
        print(f"  Tools: {tools_text[:50]}...")
    
    print(f"\n✓ 成功提取 {len(turn_data)} 个turn")
    
    # 测试2: 空的conversation_history
    print("\n" + "="*80)
    print("测试2: conversation_history为空列表的情况")
    print("="*80)
    
    conversation_histories = [[]]  # 空列表
    idx = 0
    
    # 模拟_log_conversation_table的逻辑
    turn_data_from_conv = {}
    if idx < len(conversation_histories) and conversation_histories[idx] is not None:
        conv_hist = conversation_histories[idx]
        print(f"conversation_histories[{idx}] = {conv_hist}")
        print(f"isinstance(conv_hist, list) = {isinstance(conv_hist, list)}")
        print(f"len(conv_hist) = {len(conv_hist)}")
        
        if isinstance(conv_hist, list) and len(conv_hist) > 0:
            print("进入for循环提取turn")
            for turn in conv_hist:
                # 这里不会执行，因为conv_hist是空列表
                pass
        else:
            print("❌ 条件不满足：len(conv_hist) > 0 为False")
    
    print(f"len(turn_data_from_conv) = {len(turn_data_from_conv)}")
    print(f"是否应该从responses提取: {len(turn_data_from_conv) == 0}")
    
    # 测试3: 检查表格是否会被上传
    print("\n" + "="*80)
    print("测试3: 表格上传逻辑")
    print("="*80)
    
    # 模拟现有表格
    class MockTable:
        def __init__(self, data_count):
            self.data = ['mock_row'] * data_count
    
    existing_table = MockTable(10)  # 10行
    
    # 场景1: 成功添加了新行
    new_table_success = MockTable(12)  # 12行
    should_upload_1 = len(new_table_success.data) > len(existing_table.data)
    print(f"场景1: 新表12行 > 旧表10行 → 是否上传: {should_upload_1} ✓")
    
    # 场景2: 没有添加新行（所有conversation_history为空且从responses也提取不出）
    new_table_fail = MockTable(10)  # 10行（没变）
    should_upload_2 = len(new_table_fail.data) > len(existing_table.data)
    print(f"场景2: 新表10行 = 旧表10行 → 是否上传: {should_upload_2} ❌")
    
    print("\n问题分析:")
    print("1. 如果conversation_history全是空列表 []")
    print("2. 且从responses中无法提取（比如responses为None或不是有效的token ids）")
    print("3. 那么turn_data始终为空 {}")
    print("4. 所有行都会被填充空字符串")
    print("5. 但仍然会调用new_table.add_data(*row)，添加空行")
    print("6. 所以len(new_table.data)应该会增加")
    print()
    print("但如果row根本没有被添加（比如在add_data前有continue），")
    print("那么表格就不会有新数据，也就不会上传")
    
    # 测试4: 检查是否有continue导致不添加行
    print("\n" + "="*80)
    print("测试4: 检查代码中是否有跳过添加行的逻辑")
    print("="*80)
    
    # 模拟_log_conversation_table中的行添加逻辑
    indices = [0, 1, 2]
    image_histories = [None, [], ['img1', 'img2']]  # 第0个为None，第1个空列表，第2个有数据
    
    rows_added = 0
    for idx in indices:
        print(f"\n处理idx={idx}:")
        
        # 第一个检查
        if idx >= len(image_histories):
            print(f"  ❌ continue: idx >= len(image_histories)")
            continue
        
        img_hist = image_histories[idx]
        print(f"  img_hist = {img_hist}")
        
        # 第二个检查
        if img_hist is None:
            print(f"  ❌ continue: img_hist is None")
            continue
        
        # 如果通过了检查，添加行
        print(f"  ✓ 添加行")
        rows_added += 1
    
    print(f"\n总共添加了 {rows_added} 行（期望3行，实际{rows_added}行）")
    print(f"问题：如果image_histories[0]为None，该行会被跳过！")

if __name__ == "__main__":
    test_conversation_extraction()
    
    print("\n" + "="*80)
    print("结论：问题可能出在以下几个地方")
    print("="*80)
    print("""
1. ❌ image_histories包含None值 → 这些样本的行会被跳过（continue）
   → 导致表格没有新增行 → 不上传

2. ❌ conversation_history全是空列表[] → turn_data为空
   → 但如果responses也无法解析 → 行会被添加但全是空字符串
   → 这种情况表格应该会上传（有新行），但内容为空

3. ✓ 需要检查：
   - image_histories是否包含None
   - responses是否正确传入（tensor列表）
   - tokenizer是否正确传入
   
4. 🔍 关键检查点：
   - 第841行: if img_hist is None: continue
   这会导致None样本被跳过，不添加行
   
建议：移除或修改None检查逻辑，允许为None的样本也添加行（只是没有图片数据）
""")

