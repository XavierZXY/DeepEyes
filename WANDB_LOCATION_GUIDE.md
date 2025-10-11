# Wandb中训练Rollout结果的位置指南

## 📍 训练结果在Wandb中的位置

### 1️⃣ **图像和对话可视化** - Media Tab

**路径**: 
```
Run页面 → Media (左侧导航栏) → train/trajectories
```

**内容**:
- 图像序列：[Ground Truth] → [Degraded Input] → [Processing Steps] → [Restored]
- 对话内容：User input + Agent多轮对话（Think + Tools）
- 图像标签：每个图像上方标注含义
- Caption：Sample ID | Quality | SSIM | LPIPS | PSNR | [BEST/WORST]

**采样策略**:
- 质量最高的N个样本（默认2个）[BEST]
- 质量最低的N个样本（默认2个）[WORST]
- 随机M个样本（默认5个）
- **总计**: 每个step最多9张图像

**查看方式**:
1. 打开wandb run页面
2. 左侧导航栏找到 **Media** tab
3. 点击展开 `train/trajectories`
4. 点击任一图像查看大图和caption
5. 对话内容在图像上方的文本区域

---

### 2️⃣ **对话记录表格** - Charts/Tables

**路径**:
```
Run页面 → 搜索框输入 "conversation_details" 
或
Charts → train/conversation_details
```

**表格列**:
| 列名 | 说明 | 示例 |
|------|------|------|
| Step | 训练步数 | 100 |
| Sample_ID | 样本ID | train_42 |
| Quality | 质量分数 | 0.856 |
| Num_Tools | 执行工具数 | 2 |
| User_Input | 用户输入 | "Restore this..." |
| Agent_Turns | Agent执行摘要 | "T1: swinir_jpeg... \| T2: xrestormer..." |
| Final_Response | 最终响应 | "\<think\>...\<answer\>..." |

**功能**:
- ✅ **排序**: 点击列标题按Quality/Num_Tools排序
- ✅ **过滤**: 只看执行了工具的样本
- ✅ **搜索**: 查找特定工具名称
- ✅ **导出**: 下载为CSV

**用途**:
- 分析最好/最差样本的工具使用模式
- 统计工具使用率
- 找出常见错误

---

### 3️⃣ **标量指标** - Charts

**路径**: 
```
Run页面 → Charts (默认视图)
```

**训练相关指标**:

#### 奖励指标
- `critic/score/mean` - 平均奖励
- `critic/score/max` - **最大奖励**（应该能看到>0.3）
- `critic/score/min` - 最小奖励

#### 图像质量相关
- `ir_has_processed_image` - 有工具处理图像的样本比例
- `ir_quality_reward_zero` - 质量奖励为0的样本比例
- `ir_quality_reward_positive` - 质量奖励>0的样本比例
- `ir_total_reward_value` - 总奖励值

#### Agent执行统计
- `agent/tool_call_mean` - 平均工具调用次数
- `agent/tool_call_max` - 最大工具调用次数
- `degradation_*_total` - 各种退化类型的统计
- `final_answer` - 以answer结束的样本比例

#### 格式和准确性
- `format_score` - 格式分数
- `accuracy_score` - 准确性分数
- `degradation_order_score` - 退化类型顺序分数

**查看方式**:
1. 在Charts页面搜索指标名称
2. 查看曲线变化趋势
3. 比较不同run的表现

---

### 4️⃣ **本地Markdown文件**（可选）

**路径**: 
```
outputs/conversations/{experiment_name}/train_step{N}_{timestamp}.md
```

**需要配置**:
```yaml
trainer:
  save_conversation_markdown: true
```

**内容**: 完整的对话记录，无截断

---

## 🔍 如何查找特定类型的Rollout结果

### 场景A: 查看最好的rollout结果

**方法1 - 通过Media**:
1. Media → train/trajectories
2. 找标记为 [BEST] 的图像
3. 查看图像序列和对话

**方法2 - 通过Table**:
1. 搜索 "conversation_details"
2. 按 Quality 列降序排序
3. 查看最高分样本的 Agent_Turns

**方法3 - 通过Charts**:
1. 查看 `critic/score/max` 曲线
2. 找到最高点对应的step
3. 去Media中查看该step的图像

### 场景B: 分析工具使用情况

**查看工具执行率**:
```
Charts → agent/tool_call_mean
```

**查看具体使用了哪些工具**:
```
conversation_details表格 → Agent_Turns列
搜索特定工具名称
```

**查看工具执行是否成功**:
```
ir_has_processed_image - 成功率
ir_quality_reward_positive - 有质量奖励的比例
```

### 场景C: 对比不同退化类型

**查看退化类型统计**:
```
Charts → 搜索 "degradation_"
degradation_jpeg_compression_total
degradation_motion_blur_total
degradation_haze_total
...
```

**查看每种退化的复原效果**:
```
在conversation_details表格中
过滤特定工具（如"swinir_jpeg"）
查看对应的Quality分数
```

---

## 📊 Wandb页面导航路径

### 快速访问

```
项目主页
  └─ Runs (运行列表)
      └─ 点击你的run名称（如 "debug_for_TIR_IR_bs16_mi300"）
          ├─ Overview (概览) - 显示所有charts
          ├─ **Media** - 📸 图像和对话在这里！
          │   ├─ train/trajectories ← **训练rollout图像**
          │   └─ val/trajectories ← 验证rollout图像
          ├─ Charts (指标图表)
          │   ├─ critic/score/max ← **最高奖励**
          │   ├─ agent/tool_call_mean ← 工具使用率
          │   ├─ train/conversation_details ← **对话表格**
          │   └─ ... (其他指标)
          ├─ System (系统资源)
          ├─ Model (模型检查点)
          ├─ Files (文件)
          └─ Logs (日志)
```

---

## 🎨 可视化示例

### Media Panel中的训练图像

```
┌────────────────────────────────────────────────────────────┐
│ train/trajectories                                         │
├────────────────────────────────────────────────────────────┤
│ ▼ Step 1 (9 images)                                        │
│   [缩略图] Sample 42 | Quality: 0.856 [BEST] | SSIM:...   │
│   [缩略图] Sample 15 | Quality: 0.734 | SSIM:...           │
│   [缩略图] Sample 3 | Quality: 0.234 [WORST] | ...         │
│   ...                                                       │
│                                                             │
│ ▼ Step 2 (9 images)                                        │
│   [缩略图] Sample 38 | Quality: 0.892 [BEST] | ...         │
│   ...                                                       │
└────────────────────────────────────────────────────────────┘
```

点击任一图像 → 查看大图 + 对话内容

### conversation_details Table

```
┌──────┬───────────┬─────────┬──────────┬────────────┬──────────────────┬──────────────┐
│ Step │ Sample_ID │ Quality │Num_Tools │ User_Input │   Agent_Turns    │Final_Response│
├──────┼───────────┼─────────┼──────────┼────────────┼──────────────────┼──────────────┤
│  1   │ train_42  │  0.856  │    2     │ Restore... │ T1: swinir... |  │ <think>...   │
│      │           │         │          │            │ T2: xrestormer..│              │
├──────┼───────────┼─────────┼──────────┼────────────┼──────────────────┼──────────────┤
│  1   │ train_15  │  0.234  │    0     │ Restore... │                  │ <think>...   │
├──────┼───────────┼─────────┼──────────┼────────────┼──────────────────┼──────────────┤
│  2   │ train_38  │  0.892  │    3     │ Restore... │ T1: swinir... |  │ <think>...   │
│      │           │         │          │            │ T2: xrestormer..|│              │
│      │           │         │          │            │ T3: mprnet...    │              │
└──────┴───────────┴─────────┴──────────┴────────────┴──────────────────┴──────────────┘
```

---

## ⚙️ 配置控制

### 控制上传频率和数量

```yaml
trainer:
  # 图像上传配置
  log_images_to_wandb: true  # 是否启用（默认true）
  num_train_images_to_log: 5  # 随机样本数
  num_best_worst_images_to_log: 2  # 最好/最差各N个
  
  # Markdown保存（可选）
  save_conversation_markdown: false  # 默认false（避免文件太多）
```

### 示例：只看最好的样本

```yaml
trainer:
  num_train_images_to_log: 0  # 不要随机样本
  num_best_worst_images_to_log: 5  # 只要top5和bottom5
```

### 示例：保存更多样本

```yaml
trainer:
  num_train_images_to_log: 10  # 更多随机样本
  num_best_worst_images_to_log: 3  # top3和bottom3
  # 每个step最多: 10 + 3 + 3 = 16张图
```

---

## 📝 总结

### 训练Rollout结果位置

| 内容类型 | Wandb位置 | 说明 |
|---------|----------|------|
| **图像+对话** | Media → train/trajectories | 图文一体可视化 |
| **对话表格** | Charts → train/conversation_details | 结构化数据，可排序过滤 |
| **奖励曲线** | Charts → critic/score/* | 训练进展 |
| **工具统计** | Charts → agent/tool_call_* | 工具使用情况 |
| **退化统计** | Charts → degradation_* | 各类退化的处理 |

### Validation结果位置

| 内容类型 | Wandb位置 | 说明 |
|---------|----------|------|
| **图像+对话** | Media → val/trajectories | 所有验证样本 |
| **对话表格** | Charts → val/conversation_details | 结构化数据 |
| **生成结果** | Charts → val/generations | 文本table |
| **指标** | Charts → val-core/* | 验证指标 |

### 本地文件（可选）

| 内容类型 | 本地位置 | 说明 |
|---------|----------|------|
| **对话Markdown** | outputs/conversations/{exp}/train_*.md | 完整对话 |
| **验证Markdown** | outputs/conversations/{exp}/val_*.md | 验证对话 |

## 🚀 快速定位

**想看图像** → Media tab → train/trajectories  
**想看表格** → 搜索 "conversation_details"  
**想看指标** → Charts → 搜索metric名称  
**想看详细对话** → conversation_details表格或本地markdown

现在所有训练rollout结果都会自动上传到wandb，包括图像、对话、指标全都有！🎉

