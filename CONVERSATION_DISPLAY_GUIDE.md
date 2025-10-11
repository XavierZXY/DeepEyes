# 对话记录展示完整指南

## 📊 三种展示方式

### 1. 图像上方的文本（默认开启）

**位置**: 在wandb Media panel的图像上方

**内容**:
```
=== USER ===
Restore this degraded image

=== AGENT CONVERSATION HISTORY ===

--- Turn 1 ---
[Think] JPEG compression artifacts detected...
[Tools] swinir_jpeg_artifact_removal

--- Turn 2 ---
[Think] Motion blur visible...
[Tools] xrestormer_motion_deblurring

--- Turn 3 ---
[Answer] ✓ Done
```

**优点**: 图文一体，容易关联
**缺点**: 空间有限，文本可能被截断

### 2. Wandb Table（现在已添加）

**位置**: `train/conversation_details` 和 `val/conversation_details`

**查看方式**:
1. 进入wandb run页面
2. 点击左侧 **Charts** 或搜索 "conversation_details"
3. 看到表格视图

**表格列**:
| Step | Sample_ID | Quality | Num_Tools | User_Input | Agent_Turns | Final_Response |
|------|-----------|---------|-----------|------------|-------------|----------------|
| 100 | train_42 | 0.856 | 2 | Restore... | T1: swinir_jpeg... \| T2: xrestormer... | \<think\>... |
| 100 | train_15 | 0.234 | 0 | Restore... | | \<think\>... |

**优点**: 
- 表格形式清晰
- 可搜索、过滤、排序
- 支持导出CSV

**缺点**: 
- 文本截断（每列最多200-300字符）

### 3. Markdown文件（可选，需要配置）

**位置**: `outputs/conversations/{experiment_name}/`

**文件名格式**: `train_step100_20251010_123456.md` 或 `val_step5_20251010_123456.md`

**内容示例**:
```markdown
# TRAIN Conversations - Step 100

Generated at: 2025-10-10 12:34:56
Total samples: 9

---

## Sample 42

**Quality Score**: 0.856 | **Tools Used**: 2
**Metrics**: SSIM=0.923 LPIPS=0.145 PSNR=28.4

### 用户输入
```
Restore this degraded image
```

### Agent执行过程

**Turn 1**
- **Think**: JPEG compression artifacts detected (highest priority)
- **Tool**: swinir_jpeg_artifact_removal
  - Args: {"jpeg": 40}

**Turn 2**
- **Think**: After removing compression, motion blur is visible
- **Tool**: xrestormer_motion_deblurring
  - Args: {}

**Turn 3**
- **Answer**: ✓ Done

### 最终响应
```
<think>...</think><tool_call>...</tool_call>...
```

---
```

**优点**: 
- 完整内容，无截断
- 本地查看方便
- 可以用编辑器搜索

**缺点**: 
- 需要手动打开文件
- 占用磁盘空间

## ⚙️ 配置

### 启用Markdown保存（可选）

在训练配置中添加：

```yaml
trainer:
  save_conversation_markdown: true  # 启用markdown保存
  log_images_to_wandb: true  # wandb图像和table（默认启用）
```

### 默认配置（已启用）

```yaml
trainer:
  log_images_to_wandb: true  # 图像+对话在图上
  # save_conversation_markdown: false（默认关闭，避免太多文件）
```

## 📁 查看方式

### Wandb网页查看

#### 方式A: 图像 + 对话文本
1. 打开wandb run
2. 点击 **Media** tab
3. 选择 `train/trajectories` 或 `val/trajectories`
4. 点击任一图像
5. 对话内容在图像上方

#### 方式B: 对话表格（新增）
1. 打开wandb run
2. 在搜索框输入 "conversation_details"
3. 或者点击 **Charts** → 找到 `train/conversation_details`
4. 看到表格，可以：
   - 按Quality排序找最好/最差样本
   - 按Num_Tools过滤找执行了工具的样本
   - 搜索特定工具名称
   - 导出为CSV

### 本地Markdown查看（如果启用）

```bash
# 查看生成的markdown文件
ls outputs/conversations/your_experiment_name/

# 打开查看
cat outputs/conversations/your_experiment_name/train_step100_*.md

# 或用编辑器打开
code outputs/conversations/your_experiment_name/train_step100_*.md
```

## 📊 对话内容包含什么？

### 完整信息

对于每个样本，包含：

1. **用户输入**: 初始prompt
2. **每一轮Agent执行**:
   - Turn 1: Think + Tools
   - Turn 2: Think + Tools
   - Turn N: Answer
3. **最终响应**: 完整的模型输出
4. **质量指标**: Quality, SSIM, LPIPS, PSNR
5. **工具统计**: 执行了几个工具

### 示例场景

**成功案例**（Quality: 0.856）:
```
Turn 1: 检测到JPEG压缩 → 调用swinir_jpeg_artifact_removal
Turn 2: 去除压缩后看到模糊 → 调用xrestormer_motion_deblurring
Turn 3: 完全恢复 → 给出Answer
```

**失败案例**（Quality: 0.300）:
```
Turn 1: 直接给Answer（没有调用工具）
```

## 🎨 Wandb可视化总览

现在你在wandb中可以看到：

### Media Panel
- `train/trajectories` - 训练图像（图像序列 + 对话文本）
- `val/trajectories` - 验证图像

### Charts/Tables
- `train/conversation_details` - 训练对话表格（新增）
- `val/conversation_details` - 验证对话表格（新增）
- `val/generations` - 验证生成结果（已有）

### 本地文件（可选）
- `outputs/conversations/` - Markdown格式对话记录

## 🚀 使用建议

### 分析最好的样本
1. 在 `conversation_details` 表格中按Quality排序
2. 找到最高分样本（如0.856）
3. 查看 Agent_Turns 列，学习正确的工具使用模式
4. 在 Media 中查看对应图像，验证复原效果

### 分析最差的样本
1. 找到最低分样本（如0.300）
2. 查看 Num_Tools：
   - 如果=0：模型没学会使用工具
   - 如果>0：工具选择或顺序错误
3. 查看 Agent_Turns 了解错误模式

### 调试特定工具
1. 在 conversation_details 表格中搜索工具名称
2. 找到所有使用该工具的样本
3. 对比Quality分数，评估该工具的效果

## 📝 快速开始

### 最小配置（推荐）

```yaml
trainer:
  log_images_to_wandb: true  # 默认true
  # 不开启markdown（避免文件太多）
```

**查看**: 
- Wandb Media: 图像 + 对话
- Wandb Table: `conversation_details`

### 完整配置（需要详细分析时）

```yaml
trainer:
  log_images_to_wandb: true
  save_conversation_markdown: true  # 额外保存markdown
  num_train_images_to_log: 10  # 多保存一些样本
```

**查看**:
- Wandb: 所有内容
- 本地Markdown: 完整对话细节

## ✅ 验证

运行训练后，检查：

```bash
# 1. Wandb table
# 在wandb网页搜索 "conversation_details"

# 2. 本地markdown（如果启用）
ls outputs/conversations/*/
cat outputs/conversations/*/train_step*.md | head -100
```

现在对话记录有多种展示方式，选择最适合你的！🎨

