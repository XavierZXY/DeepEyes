# Wandb表格完整分析 - 数据来源和字段说明

## 📋 表格概述

Wandb上传的表格名称：
- **训练**: `train/conversation_details`
- **验证**: `val/conversation_details`

**关键函数**: `_log_conversation_table()` in `verl/utils/tracking_image_utils.py` (第783-1201行)

---

## 🗂️ 表格结构（21列）

### 完整列列表

```python
columns = [
    "Step",                          # 第1列
    "Sample_ID",                     # 第2列
    "Trajectory_Image",              # 第3列  ← 图像可视化
    "Quality_Score",                 # 第4列
    "Num_Tools",                     # 第5列
    "Degradation_Type",              # 第6列  ← GT标签
    "Predicted_Degradation_Type",    # 第7列  ← 模型预测
    "Prediction_Match",              # 第8列  ← 预测是否正确
    "Tool_Status",                   # 第9列  ← 工具执行状态
    "Failure_Reason",                # 第10列 ← 失败原因分析
    "User_Input",                    # 第11列
    # 最多5轮对话，每轮2列 (Think + Tools)
    "Turn1_Think",                   # 第12列
    "Turn1_Tools",                   # 第13列
    "Turn2_Think",                   # 第14列
    "Turn2_Tools",                   # 第15列
    "Turn3_Think",                   # 第16列
    "Turn3_Tools",                   # 第17列
    "Turn4_Think",                   # 第18列
    "Turn4_Tools",                   # 第19列
    "Turn5_Think",                   # 第20列
    "Turn5_Tools",                   # 第21列
]
```

**固定设置**: `MAX_TURNS = 5` (第821行)

---

## 📊 各列详细说明

### 1. Step（第1列）
**数据来源**: 直接传入参数 `step`
```python
row = [step, ...]  # 第1077行
```

**含义**: 当前训练/验证的step数
**示例**: `100`, `200`, `500`

---

### 2. Sample_ID（第2列）
**数据来源**: 构造字符串
```python
f"{mode}_step{step}_idx{idx}"  # 第1078行
```

**含义**: 样本唯一标识符
**示例**: 
- `train_step100_idx5` - 训练第100步的第5个样本
- `val_step5_idx12` - 验证第5步的第12个样本

---

### 3. Trajectory_Image（第3列）⭐ 核心可视化
**数据来源**: 从 `image_histories` 创建
```python
# 第974-991行
trajectory_img = None
if img_hist is not None:
    original_img = original_images[idx] if idx < len(original_images) else None
    conv_hist = conversation_histories[idx] if idx < len(conversation_histories) else None
    
    trajectory_img = create_trajectory_visualization(
        image_history=img_hist,
        conversation_text=None,  # 不添加文本
        original_image=original_img,
        conversation_history=conv_hist
    )
    
    if trajectory_img is not None:
        trajectory_img = wandb.Image(trajectory_img)
```

**输入数据流**:
```
parallel_env.py 
  → image_history_list (Agent执行时收集)
  → DataProto.non_tensor_batch['image_history_list']
  → ray_trainer.py: val_image_histories
  → log_rollout_images_to_wandb()
  → _log_conversation_table(image_histories=...)
```

**含义**: 图像处理轨迹的可视化
- Ground Truth (如果有original_image)
- Degraded Input (初始退化图)
- Step 1, Step 2, ... (每个工具处理后的图像)
- Restored (最终复原图)

**格式**: `wandb.Image` 对象，可点击放大

---

### 4. Quality_Score（第4列）
**数据来源**: 从 `image_quality_scores` 提取
```python
# 第850-853行
quality = 0.0
if image_quality_scores is not None and idx < len(image_quality_scores):
    quality = float(image_quality_scores[idx])
```

**image_quality_scores的来源**:
```python
# ray_trainer.py 第810行
image_quality_scores = extract_image_quality_scores_from_rewards(reward_extra_infos_dict)
```

**extract_image_quality_scores_from_rewards** (第1532-1559行):
```python
# 优先级顺序查找：
for key in ['ir_accuracy_score', 'accuracy_score', 'score', 
            'image_quality_reward', 'quality_score', 'image_quality_score', 
            'restoration_quality']:
    if key in reward_info:
        return scores
```

**含义**: 图像质量分数（总奖励或质量奖励）
**典型值**: 
- `0.0` - 工具未执行
- `0.3` - 仅格式奖励
- `0.6-1.0` - 包含质量奖励

---

### 5. Num_Tools（第5列）
**数据来源**: 从 `image_history` 长度计算
```python
# 第855-858行
num_tools = 0
if img_hist is not None and isinstance(img_hist, (list, tuple)):
    num_tools = max(0, len(img_hist) - 1)
```

**计算逻辑**:
- `image_history = [degraded_img, tool1_result, tool2_result]`
- `num_tools = len(image_history) - 1 = 2`

**含义**: 模型调用的工具数量
**典型值**: `0`, `1`, `2`, `3`

---

### 6. Degradation_Type（第6列）⭐ Ground Truth
**数据来源**: 从 `reward_extra_infos_dict` 提取
```python
# 第860-864行
degradation_type = "unknown"
if reward_extra_infos_dict and 'degradation_type' in reward_extra_infos_dict:
    if idx < len(reward_extra_infos_dict['degradation_type']):
        degradation_type = reward_extra_infos_dict['degradation_type'][idx]
```

**reward_extra_infos_dict的来源**:
```python
# ray_trainer.py 第656行
result = self.val_reward_fn(test_batch, return_dict=True)
reward_tensor = result["reward_tensor"]
if "reward_extra_info" in result:
    for key, lst in result["reward_extra_info"].items():
        reward_extra_infos_dict[key].extend(lst)
```

**含义**: 真实的退化类型标签（Ground Truth）
**示例**: 
- `"motion blur"` - 运动模糊
- `"noise, motion blur"` - 多种退化组合
- `"haze"` - 雾霾
- `"unknown"` - 未知

---

### 7. Predicted_Degradation_Type（第7列）⭐ 模型预测
**数据来源**: 从 `conversation_histories` 中的工具调用提取
```python
# 第866-918行
predicted_degradation_types = []
if idx < len(conversation_histories) and conversation_histories[idx] is not None:
    conv_hist = conversation_histories[idx]
    if isinstance(conv_hist, list):
        # 遍历所有turn
        for turn in conv_hist:
            response = turn.get('response', '')
            if '<tool_call>' in response:
                # 提取工具名称
                tools = json.loads(tool_match.group(1).strip())
                tool_name = tool_dict.get('name', '')
                # 映射工具名称到退化类型
                deg_type = get_degradation_type_from_tool(tool_name)
                if deg_type and deg_type not in predicted_degradation_types:
                    predicted_degradation_types.append(deg_type)

predicted_degradation_type_str = ", ".join(predicted_degradation_types) or "none"
```

**工具到退化类型的映射** (第876-888行):
```python
tool_map = {
    "swinir_denoising": "noise",
    "mprnet_denoising": "noise",
    "restormer_motion_deblurring": "motion blur",
    "xrestormer_motion_deblurring": "motion blur",
    "drbnet_defocus_deblurring": "defocus blur",
    "restormer_deraining": "rain",
    "swinir_jpeg_artifact_removal": "jpeg compression artifact",
    "dehazeformer_dehaze": "haze",
    "histogram_equalization": "dark",
    # ... 更多映射
}
```

**含义**: 模型通过调用的工具推断出的退化类型
**示例**: 
- `"motion blur, noise"` - 调用了去模糊和去噪工具
- `"haze"` - 仅调用去雾工具
- `"none"` - 未调用任何工具

---

### 8. Prediction_Match（第8列）⭐ 预测准确性
**数据来源**: 比较GT和预测的退化类型
```python
# 第920-947行
prediction_match = "❓"  # 默认未知

if degradation_type and degradation_type.lower() != "unknown":
    # 解析GT和预测为集合
    gt_types_set = set([t.strip() for t in degradation_type.split(',')])
    pred_types_set = set([t.strip() for t in predicted_degradation_type_str.split(',')]) if predicted_degradation_type_str != "none" else set()
    
    # 集合匹配（顺序无关）
    if pred_types_set == gt_types_set:
        prediction_match = "✅"  # 完全匹配
    elif len(pred_types_set) > 0 and pred_types_set.issubset(gt_types_set):
        prediction_match = "⚠️"  # 部分正确（预测的都对，但没预测全）
    elif len(pred_types_set) > 0 and len(pred_types_set & gt_types_set) > 0:
        prediction_match = "⚠️"  # 部分正确（有交集）
    else:
        prediction_match = "❌"  # 完全错误或未预测
```

**含义**: 预测是否正确的标记
**可能值**:
- `"✅"` - 完全正确（预测的退化类型与GT完全一致）
- `"⚠️"` - 部分正确（有重叠但不完全匹配）
- `"❌"` - 完全错误（预测错误或未预测）
- `"❓"` - 未知（GT标签缺失）

---

### 9. Tool_Status（第9列）⭐ 工具执行状态
**数据来源**: 综合分析 `conversation_histories` 和 `image_history`
```python
# 第993-1074行
tool_status = "Unknown"
has_tool_request = False    # 是否有工具请求
has_tool_execution = False  # 是否有工具执行

# 检查是否有工具请求（从conversation_history）
if '<tool_call>' in response:
    has_tool_request = True

# 检查是否有工具执行（从image_history）
if len(img_hist) > 1:
    has_tool_execution = True

# 判断状态
if has_tool_request and has_tool_execution:
    tool_status = "✅ Success"
elif has_tool_request and not has_tool_execution:
    tool_status = "⚠️ Requested but Failed"
elif not has_tool_request:
    tool_status = "❌ No Tool Request"
else:
    tool_status = "❓ Unknown"
```

**含义**: 工具调用的执行情况
**可能值**:
- `"✅ Success"` - 工具请求并成功执行
- `"⚠️ Requested but Failed"` - 请求了工具但执行失败
- `"❌ No Tool Request"` - 未请求工具（直接给答案）
- `"❓ Unknown"` - 未知状态

---

### 10. Failure_Reason（第10列）⭐ 失败原因分析
**数据来源**: 根据Tool_Status进行详细分析
```python
# 第995-1074行
failure_reason = ""

if tool_status == "✅ Success":
    failure_reason = "-"  # 成功，无失败原因

elif tool_status == "⚠️ Requested but Failed":
    failure_reasons = []
    
    # 原因1: max_turns限制
    if len(conv_hist) == 1:
        failure_reasons.append("max_turns=1 (工具来不及执行)")
    
    # 原因2: image_history存在但长度为1
    if len(img_hist) == 1:
        failure_reasons.append("工具未产生新图像")
    
    # 原因3: image_history为None
    if img_hist is None:
        failure_reasons.append("image_history为空")
    
    # 原因4: 显示请求的工具名称
    if requested_tool_names:
        failure_reasons.append(f"请求工具: {', '.join(requested_tool_names)}")
    
    failure_reason = " | ".join(failure_reasons)

elif tool_status == "❌ No Tool Request":
    if '<answer>' in response:
        failure_reason = "模型直接给出答案，未调用工具"
    else:
        failure_reason = "无工具请求"
```

**含义**: 工具执行失败的详细原因
**典型示例**:
- `"-"` - 成功执行，无失败
- `"max_turns=1 (工具来不及执行) | 请求工具: swinir_denoising"` - max_turns限制
- `"模型直接给出答案，未调用工具"` - 模型跳过了工具调用
- `"无工具请求"` - 模型没有请求任何工具

---

### 11. User_Input（第11列）
**数据来源**: 从 `raw_prompts` 提取
```python
# 第949-972行
user_input = ""
if idx < len(raw_prompts):
    raw_prompt = raw_prompts[idx]
    
    # 处理OpenAI消息格式（列表）
    if isinstance(raw_prompt, list):
        for msg in raw_prompt:
            if isinstance(msg, dict) and msg.get('role') == 'user':
                user_input = msg.get('content', '')
                break
    # 处理字符串格式
    elif isinstance(raw_prompt, str):
        user_input = raw_prompt
    # 处理其他格式
    elif raw_prompt is not None:
        user_input = str(raw_prompt)
```

**raw_prompts的来源**:
```python
# ray_trainer.py 第700-705行
if 'raw_prompt' in test_batch.non_tensor_batch:
    raw_prompts = test_batch.non_tensor_batch['raw_prompt']
    val_raw_prompts.extend(raw_prompts)
```

**含义**: 用户的原始输入（任务描述）
**示例**: 
- `"Restore this degraded image to its original quality."`
- `"Please enhance this image."`

---

### 12-21. Turn N Think/Tools（第12-21列）⭐ 对话详情

#### 数据来源1: conversation_histories（训练时）
```python
# 第1083-1118行
turn_data = {}

if idx < len(conversation_histories) and conversation_histories[idx] is not None:
    conv_hist = conversation_histories[idx]
    for turn in conv_hist:
        turn_num = turn.get('turn', 1)
        response = turn.get('response', '')
        
        # 提取think
        think_text = ""
        think_match = re.search(r'<think>(.*?)</think>', response, re.DOTALL)
        if think_match:
            think_text = think_match.group(1).strip()
        
        # 提取tools
        tools_text = ""
        tool_match = re.search(r'<tool_call>(.*?)</tool_call>', response, re.DOTALL)
        if tool_match:
            tools_text = tool_match.group(1).strip()
        elif '<answer>' in response:
            answer_match = re.search(r'<answer>(.*?)</answer>', response, re.DOTALL)
            if answer_match:
                tools_text = f"<answer>{answer_match.group(1).strip()}</answer>"
        
        turn_data[turn_num] = {
            'think': think_text,
            'tools': tools_text
        }
```

**conversation_histories的来源**:
```python
# parallel_env.py 第425-430行, 第1056行
# 每次Agent交互时保存
observation_dict['conversation_history'] = [
    {
        'turn': current_turn,
        'response': response_str
    }
]
```

#### 数据来源2: responses（验证时，如果没有conversation_history）
```python
# 第1120-1170行
if not has_conv_hist and idx < len(responses) and tokenizer:
    response_ids = responses[idx]
    full_response = tokenizer.decode(response_ids, skip_special_tokens=True)
    
    # 分割多个turn
    turn_matches = list(re.finditer(r'<think>(.*?)</think>', full_response, re.DOTALL))
    for turn_idx, match in enumerate(turn_matches):
        # 提取每个turn的think和tools
        ...
```

#### Turn N Think（偶数列：12, 14, 16, 18, 20）
**含义**: 第N轮的思考内容
**示例**:
```
The image appears to suffer from motion blur. I should use a deblurring tool to restore sharpness.
```

#### Turn N Tools（奇数列：13, 15, 17, 19, 21）
**含义**: 第N轮的工具调用或最终答案
**工具调用示例**:
```json
[{"name": "restormer_motion_deblurring", "arguments": {}}]
```

**最终答案示例**:
```xml
<answer>{"restoration_log": ["restormer_motion_deblurring", "swinir_denoising"]}</answer>
```

---

## 🔄 完整数据流图

```
┌─────────────────────────────────────────────────────────────┐
│                    训练/验证开始                              │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ parallel_env.py - Agent执行循环                              │
│  - agent_rollout_loop()                                      │
│  - 每个turn保存conversation_history                          │
│  - 收集image_history_list                                    │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ DataProto.non_tensor_batch                                   │
│  - image_history_list: List[List]  ← 图像轨迹                 │
│  - conversation_history: List[Dict]  ← 对话记录               │
│  - original_images: List  ← 原图GT                           │
│  - raw_prompt: List  ← 用户输入                              │
│  - env_name: List  ← 环境名称                                │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ ray_trainer.py - _validate()                                │
│  - 收集所有batch数据到列表                                    │
│  - val_image_histories = []                                  │
│  - val_conversation_histories = []                           │
│  - val_raw_prompts = []                                      │
│  - val_original_images = []                                  │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ reward_fn - 计算奖励                                          │
│  result = reward_fn(test_batch, return_dict=True)           │
│  - reward_tensor                                             │
│  - reward_extra_info:                                        │
│    • degradation_type  ← GT标签                              │
│    • image_quality_reward  ← 质量分数                         │
│    • ssim_score, lpips_score, psnr_score  ← 有参考指标        │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ log_rollout_images_to_wandb()                               │
│  - 提取image_quality_scores                                  │
│  - 准备batch_data字典                                        │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ _log_conversation_table()                                   │
│  输入参数:                                                   │
│  - image_histories: List                                     │
│  - raw_prompts: List                                         │
│  - responses: List                                           │
│  - conversation_histories: List                              │
│  - original_images: List                                     │
│  - image_quality_scores: List[float]                         │
│  - reward_extra_infos_dict: Dict[str, List]                 │
│  - tokenizer                                                 │
│  - step: int                                                 │
│  - mode: str (train/val)                                     │
│  - indices: List[int]                                        │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ 对每个样本构建表格行                                           │
│  1. 提取Step, Sample_ID                                      │
│  2. 创建Trajectory_Image (create_trajectory_visualization) │
│  3. 提取Quality_Score                                        │
│  4. 计算Num_Tools                                            │
│  5. 提取Degradation_Type (GT)                                │
│  6. 从conversation提取Predicted_Degradation_Type            │
│  7. 比较计算Prediction_Match                                 │
│  8. 分析Tool_Status                                          │
│  9. 分析Failure_Reason                                       │
│  10. 提取User_Input                                          │
│  11. 提取Turn 1-5的Think和Tools                             │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ 累积更新wandb.Table                                          │
│  - 使用函数静态变量保存历史table                               │
│  - new_table = wandb.Table(columns, data=existing_table.data)│
│  - new_table.add_data(*row)                                  │
│  - wandb_logger.log({f"{mode}/conversation_details": new_table})│
└─────────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│ Wandb网页显示                                                 │
│  - 导航到: Tables → train/conversation_details               │
│  - 或: Tables → val/conversation_details                     │
│  - 所有历史step的数据累积保存                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 关键设计特点

### 1. 累积表格策略
```python
# 第830-840行
table_key = f"{mode}_conversation_table"
if not hasattr(_log_conversation_table, table_key):
    setattr(_log_conversation_table, table_key, wandb.Table(columns=columns))

existing_table = getattr(_log_conversation_table, table_key)
new_table = wandb.Table(columns=columns, data=existing_table.data)
```

**优点**:
- 所有历史step的数据都保留
- 可以按Step列筛选查看特定step
- 方便追踪训练过程中的变化

### 2. 智能失败原因分析
系统会自动检测：
- max_turns限制导致工具来不及执行
- 工具被调用但未产生新图像
- image_history为空
- 模型直接给答案跳过工具

### 3. 退化类型预测匹配
通过工具名称映射推断模型的预测，并与GT进行集合匹配（顺序无关）

### 4. 多数据源适配
- 训练时从conversation_history提取
- 验证时如果没有conversation_history，从final response提取

---

## 📝 使用示例

### 在Wandb中查看表格

1. 打开wandb run页面
2. 导航到 **Tables** tab (不是Media)
3. 找到表格:
   - `train/conversation_details` - 训练数据
   - `val/conversation_details` - 验证数据

### 常用筛选操作

**按Step筛选**:
```
Step = 100
```
查看特定训练步的所有样本

**按Tool_Status筛选**:
```
Tool_Status contains "Failed"
```
查看所有工具执行失败的样本

**按Prediction_Match筛选**:
```
Prediction_Match = "✅"
```
查看预测完全正确的样本

**按Num_Tools排序**:
点击Num_Tools列标题，降序查看使用工具最多的样本

---

## 🔍 调试技巧

### 查看日志中的调试信息

训练时会打印详细日志：
```bash
grep "DEBUG CONV TABLE" logs/*.log
grep "DEBUG WANDB TABLE" logs/*.log
```

### 关键调试输出

```python
# 第808-818行 - 输入数据验证
[DEBUG CONV TABLE] val mode: len(image_histories)=88, len(conversation_histories)=88...

# 第1184行 - 第一行数据内容
[DEBUG CONV TABLE] First row data: quality=0.856, num_tools=2, degradation=motion blur...

# 第1192-1200行 - 上传状态
[DEBUG WANDB TABLE] val mode: old_count=0, new_count=88, rows_added=88
[DEBUG WANDB TABLE] ✓ Added 88 rows to val/conversation_details (total: 88 rows)
```

---

## 📈 性能优化考虑

### 1. 图像处理
```python
# 第974-991行
# 只在有image_history时创建trajectory图像
if img_hist is not None:
    trajectory_img = create_trajectory_visualization(...)
```

### 2. 文本提取
```python
# 第1083-1170行
# 优先从conversation_history提取（更快）
# 仅当缺失时才从response解码提取
```

### 3. 累积更新
```python
# 第1189-1200行
# 只在有新数据时上传
if new_count > old_count:
    wandb_logger.log({f"{mode}/conversation_details": new_table}, step=step)
```

---

## ✅ 总结

wandb表格提供了一个**完整的训练监控界面**，包括：

1. ✅ 图像轨迹可视化
2. ✅ 质量分数追踪
3. ✅ 退化类型GT和预测对比
4. ✅ 工具执行状态监控
5. ✅ 失败原因自动分析
6. ✅ 完整的对话历史（最多5轮）
7. ✅ 所有历史step数据累积保存

**数据来自**:
- Agent执行过程（parallel_env.py）
- 奖励计算结果（reward_fn）
- 原始输入数据（DataProto）

**关键函数**:
- `_log_conversation_table()` - 表格创建和上传
- `create_trajectory_visualization()` - 图像可视化
- `extract_image_quality_scores_from_rewards()` - 质量分数提取

所有信息都是**自动收集、自动分析、自动上传**，无需手动操作！

