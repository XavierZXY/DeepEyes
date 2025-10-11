#!/usr/bin/env python3
"""Debug why wandb validation table exists but doesn't show in workspace"""

print("="*80)
print("Wandb验证表格不显示问题分析")
print("="*80)

print("""
问题描述：
- wandb网页上有文件：root/media/table/val/conversation_details_0_xxx.table.json
- 但是在workspace中不显示表格
- 训练表格(train)是正常显示的

可能原因分析：
""")

print("\n1️⃣ 原因1: 表格内容全是空字符串（最可能）")
print("-" * 60)
print("""
场景：
- conversation_histories = [] (验证时为空)
- 从responses提取也失败（tokenizer问题或responses格式问题）
- turn_data = {} (空字典)
- 所有Turn列填充为空字符串 ""

结果：
- wandb表格有15列，但Turn1-5的10列全是空字符串
- 只有Step, Sample_ID, Quality_Score, Num_Tools, User_Input有值
- wandb可能认为这是"无意义的表格"而不显示

验证方法：
查看日志中的调试信息：
  [DEBUG CONV TABLE] Sample 0: No conversation_history, extracting from responses
  [DEBUG CONV TABLE] Extracted X turns from response
  
如果X=0，说明从responses提取失败了
""")

print("\n2️⃣ 原因2: 表格累积机制问题")
print("-" * 60)
print("""
代码逻辑：
1. 第一次运行：
   - old_count = 0 (空表格)
   - 添加新行后 new_count = 88
   - new_count > old_count ✓ 上传表格
   
2. 第二次运行（同一个wandb run）：
   - old_count = 88 (从函数属性中获取)
   - 添加新行后 new_count = 176
   - new_count > old_count ✓ 上传更新的表格

问题：
- 如果wandb run被重启，函数属性丢失
- 但wandb云端的表格还在
- 新运行时old_count=0，但应该从云端获取

这可能导致表格版本冲突
""")

print("\n3️⃣ 原因3: Wandb UI渲染问题")
print("-" * 60)
print("""
已知问题：
- 表格列数太多（15列）可能导致UI渲染问题
- 所有数据列都是空字符串，wandb可能过滤掉
- 表格太大（累积很多step的数据）可能加载慢

解决方法：
1. 刷新页面
2. 切换到Table视图而不是默认视图
3. 检查wandb控制台的错误信息
""")

print("\n4️⃣ 原因4: 表格上传的key命名问题")
print("-" * 60)
print("""
代码中上传的key：
- 训练：f"{mode}/conversation_details" → "train/conversation_details"
- 验证：f"{mode}/conversation_details" → "val/conversation_details"

文件路径显示：
- root/media/table/val/conversation_details_0_xxx.table.json

这看起来是正常的。但可能：
- wandb在workspace中的显示路径不对
- 需要在正确的section查找（Tables vs Media）
""")

print("\n" + "="*80)
print("诊断步骤")
print("="*80)

print("""
步骤1：查看运行日志
-------------------
grep "[DEBUG CONV TABLE]" logs/*.log | grep "val mode"

期望看到：
[DEBUG CONV TABLE] val mode: len(conversation_histories)=0, len(responses)=88, len(indices)=88
[DEBUG CONV TABLE] Sample 0: No conversation_history, extracting from responses
[DEBUG CONV TABLE] Extracted 3 turns from response  # 这行很关键！
[DEBUG CONV TABLE] First row data: turn_data_count=3  # 这个应该>0

如果turn_data_count=0，说明从responses提取失败！

步骤2：检查表格是否真的上传了
-------------------
grep "[DEBUG WANDB TABLE] val mode" logs/*.log

期望看到：
[DEBUG WANDB TABLE] val mode: old_count=0, new_count=88, should_upload=True
[DEBUG WANDB TABLE] ✓ Added 88 rows to val/conversation_details

如果看到：
[DEBUG WANDB TABLE] ⚠️  No new rows added, table not uploaded
说明根本没上传！

步骤3：在wandb UI中的正确位置查找
-------------------
1. 进入wandb run页面
2. 点击左侧 "Tables" tab（不是Media）
3. 查找 "val/conversation_details"
4. 如果还是没有，点击 "Media" → "Table" → 查找val相关的

步骤4：检查是否responses解析失败
-------------------
如果日志显示：
[WARNING CONV TABLE] Failed to extract turns from response at idx=0: ...

说明responses解析有问题，可能：
- responses不是tensor
- tokenizer is None
- responses格式不对
""")

print("\n" + "="*80)
print("解决方案")
print("="*80)

print("""
方案1：如果是responses提取失败（最可能）
----------------------------------------
问题：validation时没有conversation_history，且从responses提取也失败

修复：确保responses能正确传递
在ray_trainer.py的_validate方法中检查：
1. val_responses是否正确收集
2. tokenizer是否传递给log函数

临时解决：在validation时也保存conversation_history
（修改agent rollout逻辑）

方案2：如果表格确实全是空数据
----------------------------------------
wandb可能过滤了"无意义"的表格

解决：
1. 至少保证User_Input列有数据
2. 或者不上传全空的表格
3. 在代码中添加检查：
   if len(turn_data) == 0:
       print("[WARNING] No turn data, skip this sample")
       continue  # 不添加这行

方案3：修改表格显示策略
----------------------------------------
1. 减少列数（只保留最重要的）
2. 或者分别记录每个turn的表格
3. 使用wandb.Html()而不是Table()

方案4：刷新wandb UI
----------------------------------------
1. 完全刷新页面（Ctrl+F5）
2. 清除浏览器缓存
3. 切换到其他tab再切回来
4. 检查wandb控制台错误
""")

print("\n" + "="*80)
print("快速验证")
print("="*80)

print("""
运行这个命令查看关键信息：

# 查看val表格的调试信息
grep -A 3 "DEBUG CONV TABLE.*val mode" logs/*.log | head -20

# 查看是否提取到turn数据
grep "Extracted.*turns from response" logs/*.log

# 查看是否上传成功
grep "Added.*rows to val/conversation_details" logs/*.log

# 如果都正常，可能是wandb UI问题，尝试：
1. 在Tables tab而不是Media tab查找
2. 搜索 "conversation_details" 
3. 完全刷新页面
""")

print("\n修复建议：")
print("如果确认是responses提取失败，需要在tracking_image_utils.py中增强错误处理")

