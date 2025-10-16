# Wandb图像上传完整修复指南

## 🎯 所有修复内容总结

### 修复1: Wandb Logger Bug
**文件**: `verl/trainer/ppo/ray_trainer.py` 第965行  
**修复**: 添加 `self.logger = logger`

### 修复2: Image History Size Mismatch  
**文件**: `verl/workers/agent/parallel_env.py` 第698-730行  
**修复**: 正确的interleaving逻辑匹配`mm_input_list`结构

### 修复3: 添加原图和详细指标支持
**文件**: 
- `verl/workers/agent/parallel_env.py` 第609行、第714-726行
- `verl/trainer/ppo/ray_trainer.py` 第1188行、第1196-1201行、第709-719行
- `verl/utils/tracking_image_utils.py` 第79行、第102-106行、第132-176行、第385-393行、第499-506行

**新增功能**:
1. **原图展示**: 在可视化中添加Ground Truth（未退化的原图）
2. **详细指标**: Caption中显示SSIM、LPIPS、PSNR等指标
3. **图像标签**: 每个图像上方标注其含义（Ground Truth、Degraded Input、Step N、Restored）

## 📊 完整的数据流

```
1. DataLoader
   ↓ origin_multi_modal_data (原图，未退化)
   ↓ multi_modal_data (退化后的输入图)

2. ParallelEnv.reset()
   ↓ multi_modal_data_history_list[i] = [退化图]
   ↓ origin_multi_modal_data_list[i] = 原图

3. ParallelEnv.step() (每次工具调用)
   ↓ multi_modal_data_history_list[i].append(处理后的图)
   ↓ 结果: [退化图, 工具1处理, 工具2处理, ...]

4. agent_rollout_loop() - 保存数据
   ↓ saved_image_history_list = multi_modal_data_history_list.copy()
   ↓ saved_original_images = origin_multi_modal_data_list.copy()

5. Interleaving (匹配mm_input_list)
   ↓ for i in batch_size:
   ↓     for _ in n:
   ↓         image_history_to_add.append(saved_image_history_list[i])
   ↓         original_images_to_add.append(saved_original_images[i])

6. 添加到DataProto
   ↓ non_tensors_dict["image_history_list"] = image_history_to_add
   ↓ non_tensors_dict["original_images"] = original_images_to_add

7. Reward计算
   ↓ image_history = batch.non_tensor_batch["image_history_list"][i]
   ↓ restored_image = image_history[-1]
   ↓ 计算质量指标 (SSIM, LPIPS, PSNR)
   ↓ reward_extra_infos_dict["ssim_score"].append(...)

8. Wandb上传
   ↓ batch_data = {
   ↓     'image_history': [...],
   ↓     'original_images': [...],
   ↓     ...
   ↓ }
   ↓ detailed_metrics = {
   ↓     'ssim_score': [...],
   ↓     'lpips_score': [...],
   ↓     'psnr_score': [...]
   ↓ }
   ↓ log_rollout_images_to_wandb(batch_data, detailed_metrics)

9. 创建可视化
   ↓ create_trajectory_visualization(
   ↓     image_history=[退化图, 工具1, 工具2, ...],
   ↓     original_image=原图
   ↓ )
   ↓ 
   ↓ 布局: [原图] [退化图] [Step 1] [Step 2] ... [Restored]
   ↓        ↑GT    ↑输入   ↑处理过程         ↑最终结果
```

## 🖼️ 可视化结构

### 图像布局（从左到右）
```
┌─────────────┬─────────────┬─────────────┬─────────────┬─────────────┐
│Ground Truth │Degraded     │   Step 1    │   Step 2    │  Restored   │
│             │   Input     │             │             │             │
├─────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│   原图      │  退化输入   │  工具1处理  │  工具2处理  │  最终复原   │
│ (GT, 未退化)│ (训练输入)  │             │             │ (用于评估)  │
└─────────────┴─────────────┴─────────────┴─────────────┴─────────────┘
```

### Caption格式
```
训练: Sample 42 | Quality: 0.856 [BEST] | SSIM: 0.923 | LPIPS: 0.145 | PSNR: 28.4
验证: Val Sample 5 | Quality: 0.723 | SSIM: 0.845 | LPIPS: 0.234 | PSNR: 24.1
```

### 对话内容（图像上方）
```
=== SYSTEM (shown once, same for all) ===
[系统提示词 - 只在第一个样本显示]

=== USER ===
[用户输入内容]

=== ASSISTANT ===
[模型输出内容]
```

## ✅ 预期的日志输出

### 成功的完整流程
```
# 1. 收集image_history和original_images
[DEBUG IMAGE_HISTORY] saved_image_history_list length: 2, mm_input_list length: 4
[DEBUG IMAGE_HISTORY] saved_original_images length: 2
[DEBUG IMAGE_HISTORY] After interleaving: batch_size=2, n=2, expected=4, actual=4
[DEBUG IMAGE_HISTORY] ✓ Added image_history_list and original_images to non_tensors_dict

# 2. 计算图像质量奖励
[DEBUG IMAGE QUALITY] image_history 类型: <class 'list'>, 长度: 3
[DEBUG] 开始图像质量计算... 模式: 无参考
[DEBUG no_ref_image_quality] continuous_reward=0.7234
[DEBUG] compute_image_quality_reward_v2 返回值: {'image_quality_reward': 0.72, 'ssim_score': 0.923, ...}

# 3. Wandb图像上传
[DEBUG WANDB IMAGE] Keys in batch.non_tensor_batch: [..., 'image_history_list', 'original_images', ...]
[DEBUG WANDB IMAGE] Using key 'image_history_list' for image history
[DEBUG WANDB IMAGE] Found 4 image histories
[DEBUG WANDB IMAGE] Found 4 original images
[DEBUG WANDB IMAGE] Detailed metrics keys: ['ssim_score', 'lpips_score', 'psnr_score', ...]
[DEBUG WANDB IMAGE] About to log 9 training images...
[DEBUG WANDB IMAGE] wandb_logger type: <class 'module'>
[DEBUG WANDB IMAGE] ✓ Successfully logged 9 training trajectories
```

## 🔍 验证步骤

### 1. 检查日志
```bash
# 查看最新日志
tail -500 logs/debug_for_TIR_IR_bs16_mi300.log | grep "DEBUG IMAGE_HISTORY\|DEBUG WANDB IMAGE\|DEBUG IMAGE QUALITY"

# 预期看到:
# ✓ Added image_history_list and original_images
# ✓ image_history 长度: 3 (或其他 >1 的数字)
# ✓ Successfully logged N training trajectories
```

### 2. 检查wandb本地文件
```bash
# 查看是否生成了图像文件
ls -la wandb/run-*/media/images/ 2>/dev/null | head -20

# 预期看到: .png 文件
```

### 3. 查看wandb网页
1. 打开 wandb.ai
2. 进入你的项目和run
3. 左侧导航应该出现 **Media** tab
4. 点击后选择 `train/trajectories` 或 `val/trajectories`

### 4. 验证图像内容
在wandb中，每个图像应该显示：
- **图像标签**: Ground Truth, Degraded Input, Step 1, ..., Restored
- **Caption**: 包含Quality、SSIM、LPIPS、PSNR等指标
- **对话内容**: System/User/Assistant的完整对话

## 🎨 可视化示例

### 图像序列
```
[原图GT] → [退化输入] → [处理Step1] → [处理Step2] → [最终复原]
    ↑           ↑             ↑              ↑            ↑
  未退化      训练输入       工具处理过程              奖励评估用
```

### 指标含义
- **Quality**: 总体质量分数 (0-1)
- **SSIM**: 结构相似性 (0-1, 越高越好)
- **LPIPS**: 感知损失 (0-1, 越低越好)
- **PSNR**: 峰值信噪比 (dB, 越高越好，通常20-40)

## 🔧 配置要求

```yaml
actor_rollout_ref:
  rollout:
    n: 2  # 必须 >1 以触发interleaving
    agent:
      activate_agent: True  # 必须启用

trainer:
  logger: ['console', 'wandb']  # 必须包含wandb
  log_images_to_wandb: true
  num_train_images_to_log: 5
  num_best_worst_images_to_log: 2
  test_freq: 10  # 定期做validation
```

## 🚀 重新运行训练

```bash
# 停止当前训练（如果在运行）
# Ctrl+C

# 重新启动
bash examples/agent/IR.sh 2>&1 | tee logs/debug_with_original_$(date +%Y%m%d_%H%M%S).log
```

## 📝 故障排查

### 问题: 仍然没有original_images
**原因**: 数据集中没有origin_multi_modal_data  
**检查**:
```bash
grep "origin_multi_modal_data" logs/*.log
```
**解决**: 确保dataset中包含origin_multi_modal_data字段

### 问题: 详细指标缺失
**原因**: 使用无参考模式（no_reference）时不计算SSIM/LPIPS/PSNR  
**检查**:
```bash
grep "mode.*no_reference\|mode.*reference" logs/*.log
```
**说明**: 无参考模式只有Quality分数，没有SSIM等指标（这是正常的）

### 问题: Caption太长
**解决**: Caption中的指标可以选择性显示，代码会自动跳过不存在的指标

## 📊 完整功能对比

### 修复前
- ❌ Media tab不出现
- ❌ 图像质量奖励为0
- ❌ 只有格式奖励（0.3）
- ❌ 没有原图对比
- ❌ 没有详细指标

### 修复后
- ✅ Media tab正常显示
- ✅ 图像质量奖励正常计算
- ✅ 完整奖励（格式0.3 + 质量0.7）
- ✅ 显示Ground Truth原图
- ✅ 显示完整处理过程（退化图→处理步骤→复原图）
- ✅ Caption包含详细指标（SSIM、LPIPS、PSNR）
- ✅ 包含完整对话内容

## 🎉 预期结果

重新运行训练后：
1. **奖励值增加**: 从最大0.3 → 0.3~1.0 (取决于图像质量)
2. **Wandb Media**: 出现Media tab，显示所有rollout图像
3. **完整信息**: 每个样本包含原图、退化图、处理过程、最终复原图和详细指标

