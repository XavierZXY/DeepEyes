# Wandb Conversation Table格式说明

## 📊 新的Table结构

### 列结构

```
| Step | Sample_ID | Quality_Score | Num_Tools | User_Input | Turn1_Think | Turn1_Tools | Turn2_Think | Turn2_Tools | Turn3_Think | Turn3_Tools | ...
```

### 示例数据

| Step | Sample_ID | Quality_Score | Num_Tools | User_Input | Turn1_Think | Turn1_Tools | Turn2_Think | Turn2_Tools | Turn3_Think | Turn3_Tools |
|------|-----------|---------------|-----------|------------|-------------|-------------|-------------|-------------|-------------|-------------|
| 100 | train_42 | 0.8564 | 2 | Restore this degraded image | JPEG压缩伪影检测... | [{"name":"swinir_jpeg_artifact_removal",...}] | 去除压缩后可见运动模糊... | [{"name":"xrestormer_motion_deblurring",...}] | 图像已完全恢复 | [ANSWER] |
| 100 | train_15 | 0.300 | 0 | Restore this image | 图像看起来干净 | [ANSWER] | | | | |

## 🎯 关键改进

### 1. 质量分数准确

**之前**: 可能全是0（提取字段错误）

**现在**: 
- 从`ir_accuracy_score`提取（图像复原的质量分数）
- Fallback顺序：ir_accuracy_score → accuracy_score → score
- 保持原始精度，不round

### 2. 每个Turn单独列

**之前**: 所有turn挤在一起，难以阅读

**现在**:
- Turn1_Think | Turn1_Tools
- Turn2_Think | Turn2_Tools
- Turn3_Think | Turn3_Tools
- ...

**提前结束的样本**: 后面的列自动留空

### 3. 对话不截断

**之前**: 
- Think内容截断到100字符
- Tools截断到简单名称
- User input截断到200字符

**现在**:
- Think: 完整内容
- Tools: 完整JSON（包含参数）
- User input: 完整内容

### 4. Tools显示完整JSON

**之前**: 只显示工具名称列表
```
Tools: swinir_jpeg_artifact_removal, xrestormer_motion_deblurring
```

**现在**: 完整JSON（包含参数）
```json
[
  {
    "name": "swinir_jpeg_artifact_removal",
    "arguments": {"jpeg": 40}
  }
]
```

或者如果是answer:
```
[ANSWER]
```

## 📍 在Wandb中的位置

### 位置1: 搜索查看
```
Run页面 → 顶部搜索框 → 输入 "conversation_details"
```

### 位置2: Charts浏览
```
Run页面 → Charts tab → 向下滚动找到 "train/conversation_details"
```

### Table功能

- **排序**: 点击Quality_Score列标题，按质量排序
- **过滤**: 点击Num_Tools列，过滤执行了工具的样本
- **搜索**: 在Turn_Tools列中搜索特定工具名称
- **导出**: 点击右上角导出为CSV
- **全屏**: 点击表格右上角放大按钮

## 🔍 使用场景

### 场景1: 找最好的工具使用模式

1. 按Quality_Score降序排序
2. 查看高分样本的Turn1_Think和Turn1_Tools
3. 总结pattern：
   - 是否先处理了高优先级退化（JPEG）
   - 是否遵循LIFO原则
   - Think内容是否准确

### 场景2: 分析失败原因

1. 按Quality_Score升序排序（最差的在前）
2. 查看Num_Tools：
   - 如果=0：模型没调用工具（可能是clean样本或训练不足）
   - 如果>0：查看Tools列，分析工具选择是否正确

### 场景3: 统计特定工具效果

1. 在Turn1_Tools列搜索 "swinir"
2. 查看所有使用该工具的样本
3. 对比Quality_Score，评估效果

### 场景4: 找提前结束的样本

1. 查看Turn2_Think或Turn3_Think列为空的样本
2. 分析为什么提前结束
3. 是合理的（图像已恢复）还是错误（应该继续处理）

## 📊 与图像的关联

**结合使用**:

1. 在Table中找到有趣的样本（如最高分或最低分）
2. 记下Sample_ID和Step
3. 去Media → train/trajectories找对应的图像
4. 对照图像序列和对话，完整理解

**示例**:
```
Table中看到:
Sample_ID: train_42
Quality: 0.856
Turn1_Tools: swinir_jpeg...
Turn2_Tools: xrestormer...

然后去Media中:
找Step 100的图像，查看Sample 42
看到: [GT清晰] → [退化模糊] → [去JPEG] → [去模糊] → [复原清晰]
对照理解整个过程
```

## 🎨 Table预览

```
╔══════╦═══════════╦═══════════════╦═══════════╦════════════════╦═════════════════╦═══════════════════════════╦═════════════════╦═══════════════════════════╗
║ Step ║ Sample_ID ║ Quality_Score ║ Num_Tools ║ User_Input     ║ Turn1_Think     ║ Turn1_Tools               ║ Turn2_Think     ║ Turn2_Tools               ║
╠══════╬═══════════╬═══════════════╬═══════════╬════════════════╬═════════════════╬═══════════════════════════╬═════════════════╬═══════════════════════════╣
║ 100  ║ train_42  ║ 0.8564        ║ 2         ║ Restore this...║ JPEG压缩伪影... ║ [{"name":"swinir_jpeg...}]║ 运动模糊可见... ║ [{"name":"xrestormer...}] ║
╠══════╬═══════════╬═══════════════╬═══════════╬════════════════╬═════════════════╬═══════════════════════════╬═════════════════╬═══════════════════════════╣
║ 100  ║ train_15  ║ 0.300         ║ 0         ║ Restore this...║ 图像干净       ║ [ANSWER]                  ║                 ║                           ║
╚══════╩═══════════╩═══════════════╩═══════════╩════════════════╩═════════════════╩═══════════════════════════╩═════════════════╩═══════════════════════════╝
```

**说明**:
- 样本42: 执行了2个工具，2个turn有内容，Turn3为空
- 样本15: 没执行工具，只有Turn1，Turn2和Turn3为空

## 📝 关于质量分数的说明

### 分数来源

代码会按顺序查找：
1. `ir_accuracy_score` - 图像复原准确性（首选）
2. `accuracy_score` - 通用准确性
3. `score` - 总分（格式+质量）

### 分数含义

- **0.300**: 只有格式奖励（30%），工具未执行
- **0.3-0.6**: 格式奖励 + 部分质量奖励
- **0.6-0.9**: 格式奖励 + 高质量奖励
- **0.9+**: 接近完美复原

### 如果都是0

检查：
```bash
grep "Using.*from reward_info" logs/*.log
```

看使用了哪个字段，以及是否为空。

## ✅ 现在的Table特点

- ✅ 每个turn单独列
- ✅ 对话完整，不截断
- ✅ 质量分数准确
- ✅ 提前结束的样本自动留空
- ✅ 工具显示完整JSON
- ✅ 可排序、过滤、搜索

重新运行训练后应该看到完整、清晰的对话记录表格！

