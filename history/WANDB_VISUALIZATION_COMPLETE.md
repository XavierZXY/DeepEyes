# Wandb完整可视化功能说明

## ✅ 最终实现的功能

### 1. 完整的图像展示
**图像序列（从左到右）**：
```
┌─────────────┬─────────────┬─────────────┬─────────────┬─────────────┐
│Ground Truth │Degraded     │   Step 1    │   Step 2    │  Restored   │
│             │   Input     │             │             │             │
├─────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│   原图      │  退化输入   │  工具1处理  │  工具2处理  │  最终复原   │
│(GT,未退化)  │ (训练输入)  │             │             │ (用于评估)  │
│来自extra_info│image_hist[0]│image_hist[1]│image_hist[2]│image_hist[-1]│
└─────────────┴─────────────┴─────────────┴─────────────┴─────────────┘
```

### 2. 详细的指标显示
**Caption格式**：
```
训练: Sample 42 | Quality: 0.856 [BEST] | SSIM: 0.923 | LPIPS: 0.145 | PSNR: 28.4
验证: Val Sample 5 | Quality: 0.723 | SSIM: 0.845 | LPIPS: 0.234 | PSNR: 24.1
```

**指标说明**：
- **Quality**: 总体质量分数 (0-1，越高越好)
- **SSIM**: 结构相似性 (0-1，越高越好)
- **LPIPS**: 感知损失 (0-1，越低越好)
- **PSNR**: 峰值信噪比 (dB，越高越好，通常20-40)

### 3. 完整的对话内容
**文本区域（图像上方）**：
```
=== SYSTEM (shown once, same for all) ===
You are a helpful assistant for image restoration...

=== USER ===
Restore this degraded image.

=== ASSISTANT ===
[最终完整响应]

=== AGENT CONVERSATION HISTORY ===

--- Turn 1 ---
[Think] Image exhibits JPEG compression artifacts, which is the highest priority...
[Tools] swinir_jpeg_artifact_removal

--- Turn 2 ---
[Think] After removing compression artifacts, I notice motion blur...
[Tools] xrestormer_motion_deblurring

--- Turn 3 ---
[Think] Image is now fully restored.
[Answer] ✓ Done
```

## 📊 数据来源说明

### Ground Truth (原图)
- **来源**: `extra_info['original_image']` （从parquet数据集）
- **含义**: 未经任何退化的真实原图
- **用途**: 
  - 在有参考模式下用于计算SSIM、LPIPS、PSNR
  - 在可视化中显示为对比基准

### Degraded Input (退化图)
- **来源**: `image_history[0]` （从environment）
- **含义**: 加入退化后的输入图像
- **用途**: 
  - 模型的实际训练输入
  - 展示初始状态

### Step N (处理过程)
- **来源**: `image_history[1:-1]` （从agent工具执行）
- **含义**: 每一步工具处理后的中间结果
- **用途**: 
  - 展示复原过程的渐进改善
  - 帮助理解模型的推理路径

### Restored (最终复原)
- **来源**: `image_history[-1]` （最后一个处理结果）
- **含义**: 完成所有处理后的最终图像
- **用途**: 
  - 用于计算图像质量奖励
  - 与Ground Truth对比评估复原效果

## 🔄 完整数据流

```
1. Dataset (parquet)
   ↓ extra_info['original_image'] → Ground Truth原图
   ↓ images (退化后) → Degraded Input

2. ParallelEnv.reset()
   ↓ extra_info_list[i] = extra_info  # 保存包含original_image的extra_info
   ↓ multi_modal_data_history_list[i] = [退化图]
   ↓ conversation_history[i] = []

3. ParallelEnv.step() - 每轮agent执行
   ↓ conversation_history[i].append({'turn': N, 'response': '...', 'is_done': False})
   ↓ multi_modal_data_history_list[i].append(工具处理后的图)

4. agent_rollout_loop() - 保存并interleave
   ↓ 保存: saved_extra_info_list, saved_image_history_list, saved_conversation_history
   ↓ Interleave (batch_size × n):
   ↓   - original_images (从extra_info['original_image'])
   ↓   - image_history_list (完整处理过程)
   ↓   - conversation_history (所有中间对话)

5. DataProto.non_tensor_batch
   ↓ original_images: [GT_0, GT_0, GT_1, GT_1, ...]  # n=2时复制
   ↓ image_history_list: [[退化_0, 处理1_0, ...], [退化_0, ...], ...]
   ↓ conversation_history: [[{turn:1, ...}, {turn:2, ...}], ...]

6. ray_trainer.py - 传递给wandb logging
   ↓ batch_data = {
   ↓     'original_images': original_images,
   ↓     'image_history': image_history_list,
   ↓     'conversation_history': conversation_history,
   ↓     ...
   ↓ }

7. create_trajectory_visualization()
   ↓ 提取: original_image, image_history, conversation_history
   ↓ 生成可视化:
   ↓   - 图像序列 with 标签
   ↓   - 完整对话 including 中间turns
   ↓   - 合并为一张图

8. wandb.log()
   ↓ wandb.Image(visualization, caption="...")
   ↓ 上传到 train/trajectories 或 val/trajectories
```

## 🎨 可视化效果示例

### 成功案例（Quality: 0.856 [BEST]）
```
=== USER ===
Restore this degraded image.

=== AGENT CONVERSATION HISTORY ===

--- Turn 1 ---
[Think] Detecting JPEG compression artifacts (highest priority)
[Tools] swinir_jpeg_artifact_removal

--- Turn 2 ---
[Think] After compression fix, motion blur is visible
[Tools] xrestormer_motion_deblurring

--- Turn 3 ---
[Think] Image fully restored, no more degradations
[Answer] ✓ Done

┌───────────────────────────────────────────────────────────┐
│ Ground Truth  Degraded Input  Step 1  Step 2  Restored   │
├───────────────────────────────────────────────────────────┤
│    清晰        有压缩+模糊    去压缩  去模糊   完全恢复  │
│    原图        (训练输入)                    (评估用)    │
└───────────────────────────────────────────────────────────┘
```

### 失败案例（Quality: 0.234 [WORST]）
```
=== AGENT CONVERSATION HISTORY ===

--- Turn 1 ---
[Think] Detecting rain degradation  
[Tools] mprnet_deraining  # 错误！实际应该先处理JPEG

--- Turn 2 ---
[Think] Still see artifacts
[Answer] ✓ Done  # 过早结束

┌───────────────────────────────────────────────────────────┐
│ Ground Truth  Degraded Input  Step 1  Restored            │
├───────────────────────────────────────────────────────────┤
│    清晰        压缩+雨滴      去雨    部分恢复            │
│ (对比可见     (处理顺序错误导致效果差)                    │
│  差距很大)                                                │
└───────────────────────────────────────────────────────────┘
```

## 🔍 调试输出示例

### 成功的完整输出
```
# 1. 数据收集
[DEBUG IMAGE_HISTORY] saved_image_history_list length: 2, mm_input_list length: 4
[DEBUG IMAGE_HISTORY] saved_extra_info_list length: 2
[DEBUG IMAGE_HISTORY] saved_conversation_history length: 2
[DEBUG IMAGE_HISTORY] After interleaving: batch_size=2, n=2, expected=4, actual=4
[DEBUG IMAGE_HISTORY] original_images_to_add length: 4, conversation_history_to_add length: 4
[DEBUG IMAGE_HISTORY] ✓ Added image_history_list, original_images, and conversation_history to non_tensors_dict

# 2. Wandb准备上传
[DEBUG WANDB IMAGE] Keys in batch.non_tensor_batch: [..., 'image_history_list', 'original_images', 'conversation_history', ...]
[DEBUG WANDB IMAGE] Found 4 image histories
[DEBUG WANDB IMAGE] Found 4 original images
[DEBUG WANDB IMAGE] Found 4 conversation histories
[DEBUG WANDB IMAGE] Detailed metrics keys: ['ssim_score', 'lpips_score', 'psnr_score', ...]

# 3. 创建可视化（每个样本）
[DEBUG WANDB IMAGE] About to log 9 training images...
[DEBUG WANDB IMAGE] wandb_logger type: <class 'module'>

# 4. 上传完成
[DEBUG WANDB IMAGE] ✓ Successfully logged 9 training trajectories
```

## 🎯 验证清单

运行训练后，检查以下所有项：

### 日志验证
- [ ] `✓ Added image_history_list, original_images, and conversation_history`
- [ ] `Found N original images` 其中 N > 0
- [ ] `Found N conversation histories` 其中 N > 0
- [ ] `Detailed metrics keys: ['ssim_score', 'lpips_score', 'psnr_score']`
- [ ] `✓ Successfully logged N trajectories`

### 文件验证
- [ ] `wandb/run-*/media/images/` 目录存在
- [ ] `.png` 文件大小 > 100KB（包含多张子图和文本）

### Wandb网页验证
- [ ] Media tab 出现
- [ ] train/trajectories 有图像
- [ ] val/trajectories 有图像
- [ ] 图像包含5列：Ground Truth + Degraded + Steps + Restored
- [ ] 每个图像上方有标签
- [ ] Caption包含详细指标（SSIM, LPIPS, PSNR）
- [ ] 文本区域包含完整对话历史（每一轮的Think和Tools）

### 奖励验证
- [ ] 奖励值 > 0.3（包含图像质量奖励）
- [ ] 有样本达到 0.7-1.0 的奖励

## 🚀 运行命令

```bash
# 重新运行训练
bash examples/agent/IR.sh 2>&1 | tee logs/final_with_gt_$(date +%Y%m%d_%H%M%S).log

# 实时监控（另一个终端）
tail -f logs/final_with_gt_*.log | grep -E "DEBUG IMAGE_HISTORY|DEBUG WANDB|original_images"

# 检查结果
grep "✓ Added.*original_images.*conversation_history" logs/final_with_gt_*.log
grep "Successfully logged" logs/final_with_gt_*.log
ls -lh wandb/run-*/media/images/ | head -20
```

## 📝 关键改进总结

### 相比之前的版本

| 功能 | 之前 | 现在 |
|------|------|------|
| 原图展示 | ❌ 无 | ✅ 显示Ground Truth（来自extra_info） |
| 图像序列 | ⚠️  只有处理过程 | ✅ GT + 退化 + 处理 + 复原 |
| 图像标签 | ❌ 无 | ✅ 每个图上方标注含义 |
| 详细指标 | ⚠️  只有总分 | ✅ SSIM, LPIPS, PSNR单独显示 |
| 中间对话 | ❌ 只有最终响应 | ✅ 每一轮的Think和Tools |
| 对比分析 | ❌ 难以判断 | ✅ GT对比一目了然 |

### 数据完整性

| 数据项 | 来源 | 用途 |
|--------|------|------|
| Ground Truth | extra_info['original_image'] | 对比基准、计算有参考指标 |
| Degraded Input | image_history[0] | 展示初始状态 |
| Processing Steps | image_history[1:-1] | 展示复原过程 |
| Restored | image_history[-1] | 最终结果、计算奖励 |
| Conversation | conversation_history | 理解模型推理过程 |
| Metrics | reward_extra_infos_dict | 量化评估效果 |

## 🎓 使用建议

### 分析最好的样本 [BEST]
1. 对比GT和Restored，看复原质量
2. 查看SSIM/LPIPS/PSNR，理解哪个指标最重要
3. 阅读conversation history，学习正确的推理模式
4. 观察processing steps，理解有效的工具使用顺序

### 分析最差的样本 [WORST]
1. 对比GT和Restored，找出差异
2. 检查是否执行了工具（processing steps数量）
3. 阅读conversation，找出推理错误
4. 确定是顺序错误还是工具选择错误

### 调整训练策略
- 如果WORST样本都是"没执行工具"→ 增加工具使用奖励
- 如果WORST样本都是"顺序错误" → 增强LIFO原则提示
- 如果SSIM高但LPIPS低 → 模型重视结构但忽略感知质量

## 🐛 已知问题和限制

### 1. extra_info['original_image'] 可能为None
**症状**: 日志显示 `原图数据类型: <class 'NoneType'>`  
**原因**: 部分数据集样本没有提供original_image  
**影响**: 可视化中缺少Ground Truth列，但不影响功能  
**解决**: 检查数据集生成脚本，确保包含original_image

### 2. 无参考模式没有SSIM等指标
**症状**: Caption中只有Quality，没有SSIM/LPIPS/PSNR  
**原因**: `use_no_reference=True` 时只计算无参考指标  
**影响**: 无法详细分析各项指标  
**解决**: 设置 `use_no_reference=False` （需要original_image）

### 3. 对话历史截断
**症状**: Think内容显示 "..."  
**原因**: 过长的think内容被截断（>150字符）  
**影响**: 无法看到完整推理过程  
**解决**: 调整 tracking_image_utils.py 第324行的截断长度

### 4. 图像过多导致宽度过大
**症状**: 可视化图像太宽，难以查看  
**原因**: 某些样本执行了很多步工具  
**影响**: 显示效果不佳  
**解决**: 已限制 max_steps=10，可根据需要调整

## 📈 性能考虑

### 存储开销
- 每个epoch: ~10-50张图像（取决于batch_size和采样策略）
- 每张图像: ~500KB-2MB（包含多个子图和文本）
- 建议: 定期清理旧的wandb runs

### 上传速度
- 首次上传: 可能较慢（建立连接）
- 后续上传: 通常<10秒
- 如果太慢: 减少 `num_train_images_to_log`

### 内存使用
- 图像创建: 临时占用内存
- 已优化: 创建后立即上传并释放
- 不影响训练性能

## 🎉 总结

现在你的wandb可视化包含：
1. ✅ **完整的图像序列** - GT、退化、处理、复原全过程
2. ✅ **详细的指标** - Quality、SSIM、LPIPS、PSNR
3. ✅ **中间对话** - 每一轮的Think和Tools
4. ✅ **智能采样** - Best/Worst/Random
5. ✅ **易于对比** - Ground Truth一目了然

这是一个**完整的训练可视化和分析工具**！🎨

