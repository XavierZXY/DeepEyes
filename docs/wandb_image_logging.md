# Wandb图像轨迹上传功能说明

## ⚠️ 重要说明
**代码Bug已修复！** 如果你之前遇到图像无法上传的问题，请检查 `verl/trainer/ppo/ray_trainer.py` 第965行是否包含 `self.logger = logger`。详见项目根目录的 `BUG_FIX_SUMMARY.md`。

## 功能概述

此功能自动将PPO训练过程中的rollout图像轨迹上传到wandb，包含完整的对话内容和图像恢复过程。

## 主要特性

### 1. 训练阶段（Training）
- **智能采样策略**：
  - 图像质量最高的N个样本（默认2个）
  - 图像质量最低的N个样本（默认2个）
  - 随机采样M个样本（默认5个）
- **目的**：避免上传所有样本，节省存储和带宽

### 2. 验证阶段（Validation）
- **完整上传**：上传所有验证样本的图像轨迹
- **目的**：全面评估模型在验证集上的表现

### 3. 可视化内容

每个上传的图像包含两部分：

**顶部：对话内容**
```
=== SYSTEM (shown once, same for all) ===
[系统提示词 - 只在第一个样本显示]

=== USER ===
[用户输入内容]

=== ASSISTANT ===
[模型输出内容]
```

**底部：图像轨迹**
- 横向排列展示：输入图像 → 中间处理图像 → 最终输出图像
- 最多显示10个步骤的图像

## 配置参数

在训练配置文件中添加以下参数：

```yaml
trainer:
  # 是否启用图像上传到wandb（默认True）
  log_images_to_wandb: true
  
  # 训练时上传的随机样本数量（默认5）
  num_train_images_to_log: 5
  
  # 训练时上传的最好/最差样本数量（默认2）
  num_best_worst_images_to_log: 2
```

## Wandb查看方式

### ⭐ 推荐：查看表格（包含图片和对话）

#### 1. 训练数据表格
- 导航到：`Tables` → `train_conversation_table`
- 列结构：
  - `Step`: 训练步数
  - `Sample_ID`: 样本标识（包含step和索引）
  - `Trajectory_Image`: **图像轨迹**（带标签和工具名）
  - `Quality_Score`: 图像质量分数
  - `Num_Tools`: 工具调用次数
  - `User_Input`: 用户输入
  - `Turn1_Think`, `Turn1_Tools`: 第1轮的思考和工具
  - `Turn2_Think`, `Turn2_Tools`: 第2轮的思考和工具
  - ...（最多5轮）
- 特点：
  - ✅ 可以筛选Step列查看特定训练步的数据
  - ✅ 可以看到所有历史step的数据（累积追加）
  - ✅ 图片在表格中直接显示，点击可放大
  - ✅ 标签：`[BEST]`（最高质量）、`[WORST]`（最低质量）

#### 2. 验证数据表格
- 导航到：`Tables` → `val_conversation_table`
- 列结构同上
- 特点：
  - ✅ 包含所有验证样本
  - ✅ 每次验证都会追加新行

## 技术实现细节

### 数据流
```
parallel_env.py (Agent交互)
    ↓ 收集 image_history
DataProto.non_tensor_batch['image_history']
    ↓ 传递给
reward_fn (计算奖励 + 图像质量分数)
    ↓ 返回
reward_extra_info['image_quality_reward']
    ↓ 传递给
log_rollout_images_to_wandb()
    ↓ 上传到
Wandb
```

### 关键函数

1. **extract_pil_image_from_data()**
   - 从各种格式（PIL.Image, dict, bytes, numpy）提取图像

2. **create_trajectory_visualization()**
   - 创建包含对话文本和图像轨迹的可视化
   - 自动调整图像大小和文本换行

3. **build_conversation_text()**
   - 构建结构化的对话文本
   - System prompt只显示一次（在第一个样本）
   - 自动截断过长的system prompt

4. **log_rollout_images_to_wandb()**
   - 主上传函数
   - 处理训练/验证两种模式
   - 实现智能采样策略

5. **extract_image_quality_scores_from_rewards()**
   - 从reward结果中提取图像质量分数
   - 用于排序和选择最好/最差样本

## 注意事项

### 1. 性能优化
- 训练时只上传部分样本（避免过多I/O）
- 图像会被自动调整大小以适应显示
- 文本会自动换行和截断

### 2. 存储考虑
- 每个epoch可能会上传几十张图像
- 验证集大小会影响验证图像数量
- 建议定期清理旧的wandb runs

### 3. 调试信息
查看日志输出：
```
[DEBUG WANDB IMAGE] Found N image histories
[DEBUG WANDB IMAGE] Selected X worst and Y best samples
[DEBUG WANDB IMAGE] Selected Z random samples
[DEBUG WANDB IMAGE] Logged N training/validation trajectories
```

### 4. 错误处理
- 如果image_history为空，会跳过上传
- 如果对话文本构建失败，仍会上传图像（不含文本）
- 所有错误都会被捕获并打印warning，不影响训练

## 故障排查

### 问题1：没有图像上传
**可能原因**：
- `log_images_to_wandb: false` 配置关闭了功能
- `image_history` 没有被收集（agent未激活）
- wandb logger未初始化

**解决方案**：
- 检查配置文件
- 确保 `agent.activate_agent: true`
- 确保 `trainer.logger` 包含 `wandb`

### 问题2：图像质量显示为None
**可能原因**：
- reward_fn没有返回`image_quality_reward`
- 使用的是非image_quality模式

**解决方案**：
- 确保reward function返回`return_dict=True`
- 检查`reward_extra_info`中是否包含质量分数

### 问题3：对话内容显示不全
**可能原因**：
- System prompt过长被截断（正常行为）
- 图像宽度不足以显示完整文本

**解决方案**：
- 这是预期行为，system prompt只显示前5行
- 可以在wandb中查看完整的generation table

## 示例输出

Wandb中的图像标题格式：
```
训练：Sample 42 | Quality: 0.856 [BEST]
验证：Val Sample 5 | Quality: 0.723
```

## 扩展功能

如需添加更多信息到图像，可修改：
- `build_conversation_text()`: 添加更多对话内容
- `create_trajectory_visualization()`: 调整布局和样式
- `log_rollout_images_to_wandb()`: 修改采样策略

## 相关文件

- `/app/xiaominl/AIR/verl/utils/tracking_image_utils.py` - 图像处理工具
- `/app/xiaominl/AIR/verl/trainer/ppo/ray_trainer.py` - 训练器集成
- `/app/xiaominl/AIR/verl/workers/agent/parallel_env.py` - Agent环境（收集image_history）
- `/app/xiaominl/AIR/verl/utils/reward_score/image_restoration.py` - 图像质量评分


