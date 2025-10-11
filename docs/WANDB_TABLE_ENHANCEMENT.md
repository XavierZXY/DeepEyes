# Wandb表格增强功能说明

## 🎯 新增功能

### 1️⃣ **新增列：Degradation_Type（退化类别）**

**显示内容**：原始图像的退化类型（从数据集的reward_model字段获取）

**示例值**：
- `motion_blur` - 运动模糊
- `jpeg_artifact` - JPEG压缩伪影
- `low_resolution` - 低分辨率
- `haze` - 雾霾
- `rain` - 雨滴
- `noise` - 噪声
- `unknown` - 未知（如果无法获取）

**用途**：
- ✅ 了解样本的原始退化类型
- ✅ 分析不同退化类型的处理效果
- ✅ 筛选特定类型的样本

---

### 2️⃣ **新增列：Tool_Status（工具执行状态）**

**显示内容**：工具请求和执行的综合状态

**可能的值**：

| 状态 | 含义 | 说明 |
|------|------|------|
| `✅ Success` | 成功 | 模型请求了工具，且工具成功执行并产生了新图像 |
| `⚠️ Requested but Failed` | 请求但失败 | 模型请求了工具，但工具没有成功执行或没产生新图像 |
| `❌ No Tool Request` | 无工具请求 | 模型直接给出了答案，没有请求工具 |

**判断逻辑**：
```python
# 检查是否有工具请求（从conversation_history）
has_tool_request = '<tool_call>' in response

# 检查是否有工具执行（从image_history）
has_tool_execution = len(image_history) > 1  # 有新图像产生

# 综合判断
if has_tool_request and has_tool_execution:
    tool_status = "✅ Success"
elif has_tool_request and not has_tool_execution:
    tool_status = "⚠️ Requested but Failed"
else:
    tool_status = "❌ No Tool Request"
```

**用途**：
- ✅ 快速识别工具执行问题
- ✅ 统计工具成功率
- ✅ 调试训练问题

---

### 3️⃣ **改进：Turn_Tools列显示完整Answer内容**

**之前的行为**：
```
Turn1_Tools: [ANSWER]  ← 只显示标记，看不到内容
```

**现在的行为**：
```
Turn1_Tools: <answer>{"restoration_log": ["motion_blur", "noise"]}</answer>
            ← 显示完整的answer内容，用<answer>标签包围
```

**优势**：
- ✅ 可以直接查看模型给出的答案
- ✅ 了解模型识别的退化类型
- ✅ 保持原有的标签格式，易于识别

---

## 📊 新表格结构

### 列结构（从左到右）

```
| Step | Sample_ID | Trajectory_Image | Quality_Score | Num_Tools | 
  Degradation_Type | Tool_Status | User_Input |
  Turn1_Think | Turn1_Tools | Turn2_Think | Turn2_Tools | ... |
```

**完整列表**：
1. `Step` - 训练步数
2. `Sample_ID` - 样本ID
3. `Trajectory_Image` - 图像轨迹可视化
4. `Quality_Score` - 质量分数
5. `Num_Tools` - 实际执行的工具数量
6. **`Degradation_Type`** ⭐ 新增 - 原始退化类型
7. **`Tool_Status`** ⭐ 新增 - 工具执行状态
8. `User_Input` - 用户输入prompt
9. `Turn1_Think` ~ `Turn5_Think` - 每轮的思考内容
10. `Turn1_Tools` ~ `Turn5_Tools` - 每轮的工具/答案（完整内容）⭐ 改进

---

## 🔍 使用场景

### 场景1: 分析工具执行问题

**筛选条件**：`Tool_Status = "⚠️ Requested but Failed"`

**目的**：找出工具请求但未执行的样本

**可能的原因**：
- 工具配置问题
- 图像处理失败
- max_turns限制（只有1轮，来不及执行）
- 环境依赖缺失

**调试步骤**：
1. 查看这些样本的`Turn1_Tools`列，看请求了什么工具
2. 查看日志中对应样本的错误信息
3. 检查工具是否正确安装和配置

---

### 场景2: 分析不同退化类型的处理效果

**筛选条件**：`Degradation_Type = "motion_blur"`

**目的**：查看运动模糊类型的样本处理情况

**分析维度**：
- `Quality_Score` - 质量分数分布
- `Tool_Status` - 工具执行成功率
- `Num_Tools` - 平均使用的工具数量
- `Turn1_Tools` - 常用的工具选择

**示例分析**：
```
motion_blur样本:
- 平均Quality: 0.756
- 成功率: 85% (✅ Success)
- 常用工具: restormer_motion_deblurring, mprnet_motion_deblurring
```

---

### 场景3: 查看模型直接给答案的样本

**筛选条件**：`Tool_Status = "❌ No Tool Request"`

**目的**：分析模型为什么没有调用工具

**查看内容**：
- `Turn1_Tools` - 查看完整的answer内容
- `Degradation_Type` - 是否是clean样本
- `Quality_Score` - 直接给答案的质量如何

**可能的原因**：
- 样本是clean的，不需要修复
- 模型判断无法修复
- 模型策略问题（需要调整训练）

---

### 场景4: 对比成功和失败的样本

**筛选条件1**：`Tool_Status = "✅ Success" AND Degradation_Type = "jpeg_artifact"`

**筛选条件2**：`Tool_Status = "⚠️ Requested but Failed" AND Degradation_Type = "jpeg_artifact"`

**对比维度**：
- `Turn1_Think` - 思考内容有何不同
- `Turn1_Tools` - 工具选择有何不同
- `Quality_Score` - 质量差异

---

## 📝 示例表格行

### 示例1: 成功执行工具
```
Step: 100
Sample_ID: train_step100_idx42
Quality_Score: 0.856
Num_Tools: 1
Degradation_Type: motion_blur
Tool_Status: ✅ Success
User_Input: "Restore the blurred image..."
Turn1_Think: "I observe motion blur in the image..."
Turn1_Tools: [{"name": "restormer_motion_deblurring", "arguments": {...}}]
```

### 示例2: 工具请求但失败
```
Step: 100
Sample_ID: train_step100_idx15
Quality_Score: 0.321
Num_Tools: 0
Degradation_Type: haze
Tool_Status: ⚠️ Requested but Failed
User_Input: "Remove haze from the image..."
Turn1_Think: "The image has haze..."
Turn1_Tools: [{"name": "dehazeformer_dehaze", "arguments": {...}}]
```

### 示例3: 直接给答案
```
Step: 100
Sample_ID: train_step100_idx8
Quality_Score: 0.0
Num_Tools: 0
Degradation_Type: clean
Tool_Status: ❌ No Tool Request
User_Input: "Restore the image..."
Turn1_Think: "The image appears to be clean..."
Turn1_Tools: <answer>{"restoration_log": []}</answer>
```

---

## 🎯 调试建议

### 如果看到大量"⚠️ Requested but Failed"

**可能原因**：
1. `max_turns=1` 太少，工具来不及执行
2. 工具环境配置问题
3. 图像处理依赖缺失

**解决方案**：
```bash
# 增加max_turns
actor_rollout_ref.rollout.agent.max_turns=3

# 检查工具依赖
pip list | grep -E "torch|PIL|cv2|skimage"

# 查看详细错误日志
grep -i "error\|failed" logs/*.log | grep -i tool
```

---

### 如果看到大量"❌ No Tool Request"

**可能原因**：
1. 模型策略问题，倾向于直接给答案
2. 样本太简单（clean样本比例高）
3. 奖励信号问题，不鼓励使用工具

**解决方案**：
1. 检查奖励函数配置
2. 检查数据集质量
3. 调整format_weight和accuracy_weight的比例

---

## 💡 数据分析技巧

### 在Wandb中使用筛选和分组

1. **按退化类型分组**：
   - 在Wandb Table中，选择`Degradation_Type`列
   - 点击"Group by"
   - 查看每种类型的统计

2. **按工具状态筛选**：
   - 点击`Tool_Status`列的筛选图标
   - 选择想查看的状态
   - 分析特定状态的样本

3. **按质量排序**：
   - 点击`Quality_Score`列标题
   - 升序：查看最差样本
   - 降序：查看最好样本

---

## 🔄 版本历史

### v2.0 (当前版本)
- ✅ 新增`Degradation_Type`列
- ✅ 新增`Tool_Status`列
- ✅ `Turn_Tools`列显示完整answer内容

### v1.0 (之前版本)
- 基础对话表格
- Turn按列显示
- 图像轨迹嵌入

---

## 📚 相关文档

- [图像轨迹可视化](./TRAJECTORY_VISUALIZATION_LAYOUT.md)
- [Wandb奖励指标](./WANDB_REWARD_METRICS.md)
- [图像质量奖励配置](../IMAGE_QUALITY_REWARD_CONFIG.md)

---

**更新时间**: 2025-10-11  
**版本**: v2.0

