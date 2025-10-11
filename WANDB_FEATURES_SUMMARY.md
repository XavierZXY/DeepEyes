# Wandb功能完整总结

## 🎉 已完成的所有功能

### 1️⃣ **图像轨迹可视化上传**

#### 布局（精简版）
```
┌────────┬────────┬────────┬────────┐
│ Ground │Degraded│ Step 1 │Restored│  ← 顶部标签(30px)
│ Truth  │ Input  │        │        │
├────────┼────────┼────────┼────────┤
│  原图   │  退化图 │  处理1  │  最终图 │  ← 图像
├────────┼────────┼────────┼────────┤
│        │        │ tool_A │        │  ← 工具名称(40px) ✨
└────────┴────────┴────────┴────────┘
```

#### 查看位置
**Wandb → Tables → `train_conversation_table` / `val_conversation_table`**

表格列：
- `Step`: 训练步数
- `Sample_ID`: 样本标识
- `Trajectory_Image`: **图像轨迹**（可点击放大）✨
- `Quality_Score`: 图像质量分数
- `Num_Tools`: 工具调用次数
- `User_Input`: 用户输入
- `Turn1_Think`, `Turn1_Tools`: 第1轮思考和工具
- `Turn2_Think`, `Turn2_Tools`: 第2轮思考和工具
- ...（最多5轮）

#### 特点
- ✅ 所有历史step的数据都保留（累积追加）
- ✅ 可按Step列筛选查看特定step
- ✅ 图片直接在表格中显示
- ✅ 对话内容在同一行显示
- ✅ 标签标注最好/最差样本

---

### 2️⃣ **训练采样策略**

智能采样，避免上传所有数据：
- **最高质量**：2个样本（默认）
- **最低质量**：2个样本（默认）
- **随机采样**：5个样本（默认）

配置：
```yaml
trainer:
  num_train_images_to_log: 5
  num_best_worst_images_to_log: 2
```

---

### 3️⃣ **验证全量上传**

验证时上传**所有验证样本**，方便全面评估。

---

### 4️⃣ **奖励组成部分统计**

#### 新增Wandb指标

**格式奖励**（`reward/format_*`）：
- `reward/format_correct_ratio` - 格式正确率（0-1）
- `reward/format_violation_ratio` - 格式违规率（0-1）
- `reward/format_score_mean` - 格式分数均值（-1到1）

**图像质量奖励**（`reward/quality_*`）：
- `reward/quality_score_mean` - 质量分数均值（0-1）
- `reward/quality_score_max` - 质量分数最大值
- `reward/quality_score_min` - 质量分数最小值
- `reward/quality_score_std` - 质量分数标准差

**验证指标**：所有指标加`val/`前缀，如`val/reward/format_correct_ratio`

---

### 5️⃣ **工具调用统计修复**

**修复的Bug**：
- 原问题：`max_turns=1`时，工具调用计数为0
- 修复：将工具调用统计移到done判断之前，基于实际的`<tool_call>`标签计数

**新增指标**：
- `agent/tool_call_mean` - 平均工具调用次数
- `agent/tool_call_max` - 最大工具调用次数
- `agent/tool_call_min` - 最小工具调用次数

---

### 6️⃣ **有参考图像质量指标**

显示在Caption中（如果lpips已安装）：
- `SSIM`: 结构相似度（0-1，越大越好）
- `LPIPS`: 感知相似度（0-1，越小越好）
- `PSNR`: 峰值信噪比（dB，越大越好）

**注意**：需要安装lpips库
```bash
pip install lpips
```

---

## 📊 **完整的Wandb指标列表**

### 核心奖励指标
```
critic/rewards/mean              # 总奖励
critic/rewards/max
critic/rewards/min
critic/score/mean                # 序列得分
critic/score/max
critic/score/min
```

### 新增：奖励分解指标
```
reward/format_correct_ratio      # 格式正确率
reward/format_violation_ratio    # 格式违规率  
reward/format_score_mean         # 格式分数
reward/quality_score_mean        # 质量分数
reward/quality_score_max
reward/quality_score_min
reward/quality_score_std
```

### 验证指标（加val/前缀）
```
val/reward/format_correct_ratio
val/reward/quality_score_mean
...
```

### Agent指标
```
agent/tool_call_mean             # 工具调用统计
agent/tool_call_max
agent/tool_call_min
```

### 其他PPO指标
```
actor/pg_loss
actor/lr
critic/vf_loss
critic/lr
perf/throughput
perf/mfu/actor
perf/mfu/critic
...
```

---

## 🔧 **使用指南**

### 训练时查看
1. 打开Wandb项目
2. 进入`Tables`标签
3. 选择`train_conversation_table`
4. 可以：
   - 按Step列排序/筛选
   - 点击Trajectory_Image查看大图
   - 查看每个样本的完整对话
   - 对比[BEST]和[WORST]样本

### 验证时查看
1. 同样进入`Tables`
2. 选择`val_conversation_table`
3. 查看所有验证样本的完整信息

### 监控训练进度
在`Charts`中查看：
- `reward/format_correct_ratio` - 格式是否逐步提升
- `reward/quality_score_mean` - 质量是否持续增长
- `reward/quality_score_std` - 稳定性是否改善
- `critic/rewards/mean` - 总奖励趋势

---

## 🐛 **已修复的Bug**

### Bug 1: 工具调用统计为0
- **问题**：`max_turns=1`时，`agent/tool_call_max`显示为0
- **原因**：统计代码在`continue`之后，永远不执行
- **修复**：将统计移到done判断之前，基于`<tool_call>`标签计数
- **文件**：`verl/workers/agent/parallel_env.py` 第568-583行

### Bug 2: LPIPS指标始终为0
- **问题**：SSIM、PSNR正常，但LPIPS始终0.000
- **原因**：lpips库未安装
- **修复**：`pip install lpips`
- **验证**：重启训练后LPIPS应显示正常值（0.1-0.5）

---

## 📁 **相关文件**

### 核心代码
- `verl/utils/tracking_image_utils.py` - 图像处理和表格上传
- `verl/trainer/ppo/ray_trainer.py` - 训练器集成
- `verl/trainer/ppo/metric_utils.py` - 指标计算
- `verl/workers/agent/parallel_env.py` - Agent环境（收集数据）

### 文档
- `docs/wandb_image_logging.md` - 图像上传功能说明
- `docs/WANDB_REWARD_METRICS.md` - 奖励指标说明
- `docs/TRAJECTORY_VISUALIZATION_LAYOUT.md` - 可视化布局说明
- `DEBUG_REFERENCE_METRICS.md` - 调试指南

---

## ⚙️ **配置示例**

```yaml
trainer:
  # Wandb基础配置
  logger: wandb
  project_name: your_project
  experiment_name: your_experiment
  
  # 图像上传配置
  log_images_to_wandb: true          # 是否启用（默认true）
  num_train_images_to_log: 5         # 训练随机采样数
  num_best_worst_images_to_log: 2    # 最好/最差数量
  
  # 验证频率
  test_freq: 100                     # 每100步验证一次
```

---

## 🎯 **预期效果**

### Wandb表格示例

| Step | Sample_ID | Trajectory_Image | Quality | Num_Tools | User_Input | Turn1_Think | Turn1_Tools |
|------|-----------|------------------|---------|-----------|------------|-------------|-------------|
| 0 | train_step0_idx42 | [图片] | 0.856 | 1 | Restore... | JPEG detected | swinir_jpeg |
| 0 | train_step0_idx15 | [图片] | 0.321 | 0 | Restore... | Image clean | [ANSWER] |
| 100 | train_step100_idx23 | [图片] | 0.765 | 2 | Restore... | Haze and blur | dehazeformer |
| ... | ... | ... | ... | ... | ... | ... | ... |

点击Trajectory_Image列的图片，可以看到：
```
[GT原图] → [退化图] → [修复图]
                     swinir_jpeg
```

---

## 📈 **监控建议**

### 训练早期（前1000步）
重点关注：
- `reward/format_correct_ratio` > 0.7（格式快速收敛）
- `agent/tool_call_mean` > 0.5（开始调用工具）

### 训练中期（1000-5000步）
重点关注：
- `reward/quality_score_mean`持续上升
- `reward/quality_score_std`逐渐下降
- `reward/format_violation_ratio` < 0.1

### 训练后期（>5000步）
重点关注：
- `reward/format_correct_ratio` > 0.9
- `reward/quality_score_mean` > 0.7
- 验证集和训练集指标接近（不过拟合）

---

## 🔍 **调试命令**

### 查看最新训练日志
```bash
tail -f logs/debug_*.log | grep "DEBUG WANDB\|DEBUG REF METRICS\|DEBUG TOOL"
```

### 检查工具调用统计
```bash
grep "DEBUG TOOL CNT" logs/debug_*.log | tail -20
```

### 检查表格上传
```bash
grep "DEBUG WANDB TABLE" logs/debug_*.log | tail -10
```

### 检查有参考指标计算
```bash
grep "DEBUG REF METRICS.*Summary" logs/debug_*.log -A 15 | tail -20
```

---

## ✅ **功能清单**

- [x] 图像轨迹可视化（横向排列）
- [x] 顶部标签（Ground Truth / Degraded Input / Step X / Restored）
- [x] 底部工具名称（显示每步使用的工具）
- [x] 训练智能采样（最好/最差/随机）
- [x] 验证全量上传
- [x] 集成到Wandb表格（不是独立Media）
- [x] 格式奖励分别统计
- [x] 图像质量奖励分别统计
- [x] 工具调用统计修复
- [x] 有参考指标计算和显示（SSIM/LPIPS/PSNR）
- [x] 详细调试日志
- [x] 完整文档

---

## 🚀 **立即可用**

所有功能已完成并通过语法检查，可以直接运行训练！

运行后在Wandb中查看：
1. **Tables** → `train_conversation_table` - 训练数据（含图片）
2. **Tables** → `val_conversation_table` - 验证数据（含图片）
3. **Charts** → `reward/*` - 奖励分解指标

