# 数据集迁移指南：从数据集1到数据集2

## 📊 数据集对比

### 数据集1: Image Restoration (图像复原)
- **位置**: `/home/takisobe@amd.com/zxy/data/shard-train-*.parquet`
- **env_name**: `noise`, `motion_blur`, `haze`, `rain`, 等
- **任务**: 图像复原，恢复退化的图像
- **工具**: SwinIR, MPRNet, Restormer, XRestormer, DehazeFormer等
- **工具行为**: 链式处理（使用上一个工具处理后的图像）
- **reward组成**:
  - `format_score`: 1.0 或 -1.0
  - `quality_score`: 0.0 ~ 1.0 (图像质量指标)
  - `degradation_type_score`: 0.0 ~ 1.0 (可选)

### 数据集2: Industrial Defect Detection (工业缺陷检测)
- **位置**: `/home/takisobe@amd.com/zxy/codes/DeepEyes/data/train/train_dataset.parquet`
- **env_name**: `visual_toolbox_v2`
- **data_source**: `vstar_visual_toolbox_v2`
- **任务**: 工业缺陷检测，判断是否有缺陷(yes/no)
- **工具**: `image_zoom_in_tool`, `image_rotate_tool`
- **工具行为**: 独立处理（始终使用原始输入图，不使用上一个工具的输出）
- **reward组成**:
  - `format_reward`: -1 或 1
  - `acc_reward`: 0 或 1
  - **总分**: format_reward + acc_reward (-1 到 2)

---

## 🔧 已完成的修改

### 1️⃣ Reward计算系统

**文件**: `verl/utils/reward_score/__init__.py`

添加了对`visual_toolbox_v2`的支持：

```python
elif data_source in ["visual_toolbox_v2", "defect_detection", "vstar_visual_toolbox_v2"]:
    from . import visual_toolbox_v2_reward
    
    print(f"[INFO] Using visual_toolbox_v2 reward (format: -1/1, accuracy: 0/1)")
    res = visual_toolbox_v2_reward.compute_visual_toolbox_v2_score(
        data_source,
        solution_str,
        ground_truth,
        extra_info
    )
```

**Reward函数**: `verl/utils/reward_score/visual_toolbox_v2_reward.py`

特点：
- ✅ 格式检查：`-1`（有错误）或`1`（完美格式）
- ✅ 准确性匹配：直接匹配yes/no，不使用LLM judge
- ✅ 两种模式：
  - Format 1 (工具请求)：只返回format_reward
  - Format 2/3 (最终答案)：返回format_reward + acc_reward

### 2️⃣ Reward Manager

**文件**: `verl/workers/reward_manager/naive.py`

添加了对`visual_toolbox_v2`的统计：

```python
elif data_source in ["visual_toolbox_v2", "vstar_visual_toolbox_v2"]:
    # 数据集2：缺陷检测任务
    if isinstance(score, dict):
        format_score = score.get("format_reward", 0.0)  # -1 或 1
        accuracy_score = score.get("acc_reward", 0.0)   # 0 或 1
        degradation_score = 0.0  # 数据集2不使用退化类型
```

并将`format_reward`和`acc_reward`添加到`reward_extra_info`中，供wandb使用。

### 3️⃣ Wandb上传系统

**文件**: `verl/utils/tracking_image_utils.py`

已支持数据集2的指标显示：

```python
# 检测数据集类型
is_image_restoration = reward_extra_infos_dict and 'degradation_type' in reward_extra_infos_dict
is_visual_toolbox_v2 = reward_extra_infos_dict and 'format_reward' in reward_extra_infos_dict

# 添加reward组件列（根据数据集类型）
if is_visual_toolbox_v2:
    # 数据集2：format和accuracy
    columns.extend(["Format_Reward", "Acc_Reward"])
elif is_image_restoration:
    # 数据集1：quality、degradation type等
    columns.extend(["Quality_Score", "Degradation_Type", ...])
```

**Caption显示**:
```
Sample 42 | Quality: 0.856 | Format: 1.0 | Acc: 1.0
```

**文件**: `verl/trainer/ppo/metric_utils.py`

已支持数据集2的指标统计：

```python
# 格式奖励统计 - 支持数据集1 (ir_format_score) 和数据集2 (format_reward)
if 'format_reward' in reward_extra_infos_dict:
    format_score_key = 'format_reward'  # 数据集2
    
# 准确性奖励统计 - 支持数据集2 (acc_reward)
if 'acc_reward' in reward_extra_infos_dict:
    quality_score_key = 'acc_reward'  # 数据集2
    
    # 添加准确率（对于数据集2特别重要）
    if quality_score_key == 'acc_reward':
        correct_count = sum(1 for s in quality_scores if s == 1.0)
        metrics['reward/accuracy_ratio'] = correct_count / len(quality_scores)
```

### 4️⃣ 工具实现

**文件**: `verl/workers/agent/envs/mm_process_engine/visual_toolbox_v2.py`

✅ 已正确实现：
- 使用`self.origin_multi_modal_data['image'][0]`获取原始输入图
- **不使用**上一个工具处理后的图
- 支持`image_zoom_in_tool`和`image_rotate_tool`

```python
def execute(self, action_string: str, **kwargs):
    if tool_name == "image_zoom_in_tool":
        # 始终从原始输入图开始处理（数据集2要求）
        img = self.origin_multi_modal_data['image'][0]  # ✓ 正确
        cropped_img = img.crop(bbox)
        current_image = cropped_img
```

---

## 🚀 使用方法

### 训练脚本

**文件**: `examples/agent/visual_toolbox_v2.sh`

```bash
# 运行训练
bash examples/agent/visual_toolbox_v2.sh
```

**关键配置**:
```bash
# 数据集路径
TRAIN_DATASET=/home/takisobe@amd.com/zxy/codes/DeepEyes/data/train/train_dataset.parquet
VAL_DATASET=/home/takisobe@amd.com/zxy/codes/DeepEyes/data/val/val_dataset.parquet

# Agent配置
actor_rollout_ref.rollout.agent.activate_agent=True
actor_rollout_ref.rollout.agent.tool_name_key=env_name  # 使用env_name字段
actor_rollout_ref.rollout.agent.max_turns=5  # 允许多轮交互

# Wandb配置
trainer.logger=['console','wandb','rl_logging_board']
+trainer.log_images_to_wandb=True
+trainer.num_train_images_to_log=5
+trainer.num_best_worst_images_to_log=2
```

---

## 📊 Wandb中的指标

### 训练指标 (Charts)

**奖励组成**:
- `reward/format_correct_ratio` - 格式正确率（format=1的比例）
- `reward/format_violation_ratio` - 格式违规率（format=-1的比例）
- `reward/format_score_mean` - 格式分数均值
- `reward/accuracy_mean` - 准确性均值
- `reward/accuracy_ratio` - 准确率（acc=1的比例）

**总奖励**:
- `critic/score/mean` - 平均总分
- `critic/score/max` - 最大总分（应该是2.0）
- `critic/score/min` - 最小总分（可能是-1.0）

### 图像可视化 (Media → train/trajectories)

显示内容：
- 原始输入图
- 工具处理后的图像（zoom或rotate）
- Caption包含：Sample ID | Quality | Format | Acc

### 对话表格 (Charts → train/conversation_details)

表格列：
- `Step` - 训练步数
- `Sample_ID` - 样本ID
- `Trajectory_Image` - 图像轨迹（可点击）
- `Total_Score` - 总分(-1到2)
- `Num_Tools` - 工具调用次数
- `Format_Reward` - 格式奖励(-1或1)
- `Acc_Reward` - 准确性奖励(0或1)
- `Tool_Status` - 工具执行状态
- `Failure_Reason` - 失败原因（如果有）
- `User_Input` - 用户输入
- `Turn1_Think`, `Turn1_Tools` - 第1轮思考和工具
- `Turn2_Think`, `Turn2_Tools` - 第2轮思考和工具
- ... (最多5轮)

---

## ✅ 测试验证

运行测试脚本验证reward计算：

```bash
python3 test_visual_toolbox_v2_reward.py
```

**预期输出**:
```
✓ Test 1: 完美格式 + 正确答案 (yes) → score=2.0
✓ Test 2: 完美格式 + 正确答案 (no) → score=2.0
✓ Test 3: 格式错误 → score=0.0 (format=-1, acc=1)
✓ Test 4: 正确格式 + 错误答案 → score=1.0
✓ Test 5: 工具请求turn → score=1.0 (只检查格式)
✓ Test 6: 格式错误的工具请求 → score=-1.0
```

---

## 🔑 关键差异总结

| 特性 | 数据集1 (Image Restoration) | 数据集2 (Defect Detection) |
|------|----------------------------|---------------------------|
| **任务类型** | 图像复原 | 缺陷检测 |
| **env_name** | noise, blur, haze等 | visual_toolbox_v2 |
| **data_source** | image_restoration_v2 | vstar_visual_toolbox_v2 |
| **工具处理** | 链式（使用上一个工具输出） | 独立（始终用原始输入） |
| **Format奖励** | 1.0 或 -1.0 | -1 或 1 |
| **质量/准确性** | 0.0~1.0 (连续) | 0 或 1 (离散) |
| **总分范围** | -1.0 ~ 2.0 | -1 到 2 |
| **指标名称** | format_score, quality_score | format_reward, acc_reward |
| **LLM Judge** | 可选 | 不需要（直接yes/no匹配）|

---

## 📁 修改文件清单

1. ✅ `verl/utils/reward_score/__init__.py` - 添加visual_toolbox_v2分支
2. ✅ `verl/utils/reward_score/visual_toolbox_v2_reward.py` - reward计算（已存在）
3. ✅ `verl/workers/reward_manager/naive.py` - 添加visual_toolbox_v2统计
4. ✅ `verl/workers/agent/envs/mm_process_engine/visual_toolbox_v2.py` - 工具实现（已正确）
5. ✅ `verl/utils/tracking_image_utils.py` - wandb上传（已支持）
6. ✅ `verl/trainer/ppo/metric_utils.py` - 指标统计（已支持）
7. ✅ `examples/agent/visual_toolbox_v2.sh` - 训练脚本（新建）
8. ✅ `test_visual_toolbox_v2_reward.py` - 测试脚本（新建）

---

## 🎯 快速开始

```bash
# 1. 验证reward计算
python3 test_visual_toolbox_v2_reward.py

# 2. 运行训练
bash examples/agent/visual_toolbox_v2.sh

# 3. 查看Wandb
# - Media → train/trajectories (图像可视化)
# - Charts → train/conversation_details (对话表格)
# - Charts → reward/format_correct_ratio (格式正确率)
# - Charts → reward/accuracy_ratio (准确率)
```

---

## 🐛 故障排查

### 问题1: reward始终为1.0或-1.0
**原因**: 可能只有format_reward，没有acc_reward  
**检查**: 查看日志中是否有"[visual_toolbox_v2] Score breakdown"  
**解决**: 确保模型输出包含`<answer>`标签

### 问题2: wandb表格中Format_Reward列为空
**原因**: reward_extra_info中没有format_reward  
**检查**: 日志中搜索"DEBUG.*score字典键"  
**解决**: 确认reward函数返回了dict而非float

### 问题3: 工具始终使用上一个处理后的图
**原因**: 使用了错误的工具类  
**检查**: 确认env_name='visual_toolbox_v2'  
**解决**: visual_toolbox_v2.py已正确实现，使用origin_multi_modal_data

---

## 📈 预期训练效果

### 早期（前100步）
- `reward/format_correct_ratio` > 0.7 (格式快速学习)
- `reward/accuracy_ratio` ~ 0.5 (随机猜测水平)
- `critic/score/mean` ~ 0.5

### 中期（100-1000步）
- `reward/format_correct_ratio` > 0.9
- `reward/accuracy_ratio` > 0.6
- `critic/score/mean` > 1.0

### 后期（>1000步）
- `reward/format_correct_ratio` > 0.95
- `reward/accuracy_ratio` > 0.8
- `critic/score/max` → 2.0 (完美样本)

---

## 🎉 迁移完成！

所有代码已修改完成，支持数据集2训练。主要特点：

1. ✅ **独立的reward函数**：visual_toolbox_v2_reward.py
2. ✅ **简化的奖励**：format (-1/1) + accuracy (0/1)
3. ✅ **正确的工具行为**：始终处理原始输入图
4. ✅ **完整的wandb支持**：图像、表格、指标全都有
5. ✅ **向后兼容**：不影响数据集1的训练

现在可以直接运行`bash examples/agent/visual_toolbox_v2.sh`开始训练！

