# Wandb图像上传功能 - 最终验证清单

## ✅ 已完成的所有修复

### 1. Wandb Logger Bug修复
- [x] `verl/trainer/ppo/ray_trainer.py` 第965行
- [x] 添加 `self.logger = logger`

### 2. Image History Size Mismatch修复
- [x] `verl/workers/agent/parallel_env.py` 第698-730行
- [x] 正确的interleaving逻辑

### 3. 原图收集和传递
- [x] `verl/workers/agent/parallel_env.py` 第609行 - 保存original_images
- [x] `verl/workers/agent/parallel_env.py` 第714-726行 - Interleave并添加到DataProto
- [x] `verl/trainer/ppo/ray_trainer.py` 第575行 - 初始化val_original_images列表
- [x] `verl/trainer/ppo/ray_trainer.py` 第663-669行 - 收集validation原图
- [x] `verl/trainer/ppo/ray_trainer.py` 第1188行 - 添加到train batch_data
- [x] `verl/trainer/ppo/ray_trainer.py` 第719行 - 添加到val batch_data

### 4. 详细指标传递
- [x] `verl/trainer/ppo/ray_trainer.py` 第1196-1201行 - 提取训练指标
- [x] `verl/trainer/ppo/ray_trainer.py` 第722-728行 - 提取验证指标
- [x] `verl/trainer/ppo/ray_trainer.py` 第1220、736行 - 传递给logging函数

### 5. 可视化增强
- [x] `verl/utils/tracking_image_utils.py` 第79行 - 添加original_image参数
- [x] `verl/utils/tracking_image_utils.py` 第102-106行 - 提取并添加原图
- [x] `verl/utils/tracking_image_utils.py` 第120-176行 - 添加图像标签
- [x] `verl/utils/tracking_image_utils.py` 第252行 - 添加detailed_metrics参数
- [x] `verl/utils/tracking_image_utils.py` 第374-393行 - Validation caption添加指标
- [x] `verl/utils/tracking_image_utils.py` 第478-506行 - Training caption添加指标

### 6. 调试输出增强
- [x] `verl/workers/agent/parallel_env.py` 第695-696行 - 打印size信息
- [x] `verl/utils/tracking_image_utils.py` 第292-294行 - 打印数据和指标
- [x] `verl/utils/tracking_image_utils.py` 第327-330、426-429行 - 详细上传日志

## 🚀 运行验证

### 步骤1: 重新运行训练
```bash
bash examples/agent/IR.sh 2>&1 | tee logs/final_test_$(date +%Y%m%d_%H%M%S).log
```

### 步骤2: 实时监控日志
```bash
# 在另一个终端运行
tail -f logs/final_test_*.log | grep -E "DEBUG IMAGE_HISTORY|DEBUG WANDB IMAGE|DEBUG IMAGE QUALITY"
```

### 步骤3: 预期看到的关键日志

#### A. Image History收集成功
```
[DEBUG IMAGE_HISTORY] saved_image_history_list length: 2, mm_input_list length: 4
[DEBUG IMAGE_HISTORY] saved_original_images length: 2
[DEBUG IMAGE_HISTORY] After interleaving: batch_size=2, n=2, expected=4, actual=4
[DEBUG IMAGE_HISTORY] ✓ Added image_history_list and original_images to non_tensors_dict
```
✅ **如果看到这个**: Size匹配成功，数据已添加

#### B. 图像质量计算成功
```
[DEBUG IMAGE QUALITY] extra_info keys: ['image_history', ...]
[DEBUG IMAGE QUALITY] image_history 类型: <class 'list'>, 长度: 3
[DEBUG] 开始图像质量计算... 模式: 无参考
[DEBUG] compute_image_quality_reward_v2 返回值: 0.7234
```
✅ **如果看到这个**: 图像质量奖励正常计算

#### C. Wandb上传成功
```
[DEBUG WANDB IMAGE] Keys in batch.non_tensor_batch: [..., 'image_history_list', 'original_images', ...]
[DEBUG WANDB IMAGE] Found 4 image histories
[DEBUG WANDB IMAGE] Found 4 original images
[DEBUG WANDB IMAGE] Detailed metrics keys: ['ssim_score', 'lpips_score', 'psnr_score']
[DEBUG WANDB IMAGE] About to log 9 training images...
[DEBUG WANDB IMAGE] ✓ Successfully logged 9 training trajectories
```
✅ **如果看到这个**: Wandb上传成功

### 步骤4: 验证wandb本地文件
```bash
# 检查最新的run
ls -lth wandb/run-*/media/images/ 2>/dev/null | head -20
```
✅ **预期**: 看到多个.png文件，文件大小>100KB

### 步骤5: 验证wandb网页界面
1. 打开 https://wandb.ai/your-team/your-project
2. 点击最新的run
3. ✅ **左侧导航出现Media tab**
4. 点击Media → train/trajectories
5. ✅ **看到图像，每个包含多张子图（原图、退化图、处理过程、复原图）**
6. ✅ **Caption显示详细指标**

### 步骤6: 验证奖励值
```bash
# 查看wandb指标
grep "total_score\|image_quality_reward" logs/final_test_*.log | tail -20
```
✅ **预期**: 看到奖励值 > 0.3（不再只有格式奖励）

## 🔧 如果仍有问题

### 问题A: "✗ saved_image_history_list is empty"
**原因**: 工具没有执行  
**检查**: `grep "tool_cnt" logs/*.log`  
**解决**: 检查模型是否生成tool_call

### 问题B: "✗ Size mismatch"
**原因**: batch_size或n的计算错误  
**检查**: 日志中的expected vs actual值  
**解决**: 检查sampling_params.n配置

### 问题C: "No original images"
**原因**: Dataset中没有origin_multi_modal_data  
**影响**: 不影响功能，只是可视化中缺少Ground Truth列  
**解决**: 检查数据集是否包含原图字段

### 问题D: 没有详细指标（SSIM等）
**原因**: 使用无参考模式（use_no_reference=True）  
**说明**: 这是正常的，无参考模式只有Quality分数  
**如需详细指标**: 设置 `use_no_reference=False`（需要原图）

### 问题E: Wandb网页仍无Media tab
**原因**: wandb.log()调用失败  
**检查**: 
```bash
grep "Successfully logged\|About to log" logs/*.log
grep "Exception\|Error" logs/*.log | grep -i wandb
```
**解决**: 检查网络连接、wandb版本、API key

## 📊 预期的Wandb界面

### 在Media Panel中
```
train/trajectories (点击展开)
├─ Sample 15 | Quality: 0.923 [BEST] | SSIM: 0.945 | LPIPS: 0.123 | PSNR: 32.5
├─ Sample 42 | Quality: 0.856 | SSIM: 0.889 | LPIPS: 0.156 | PSNR: 28.9
├─ Sample 8 | Quality: 0.734 | SSIM: 0.812 | LPIPS: 0.234 | PSNR: 24.3
├─ Sample 3 | Quality: 0.234 [WORST] | SSIM: 0.567 | LPIPS: 0.567 | PSNR: 18.1
└─ ...

val/trajectories (点击展开)
├─ Val Sample 0 | Quality: 0.845 | SSIM: 0.901 | LPIPS: 0.145 | PSNR: 29.8
├─ Val Sample 1 | Quality: 0.778 | SSIM: 0.834 | LPIPS: 0.198 | PSNR: 26.4
└─ ...
```

### 点击任一图像查看
```
┌────────────────────────────────────────────────────────────┐
│ === SYSTEM ===                                             │
│ You are a helpful assistant...                             │
│ === USER ===                                               │
│ Restore this degraded image...                             │
│ === ASSISTANT ===                                          │
│ <think>...</think><tool_call>...</tool_call>               │
├────────────────────────────────────────────────────────────┤
│ [GT] [Degraded] [Step1] [Step2] [Restored]                │
│  ↑     ↑         ↑       ↑        ↑                       │
│ 原图  退化输入  处理过程          最终结果                   │
└────────────────────────────────────────────────────────────┘
```

## 🎯 成功标志

如果看到以下所有项，说明功能完全正常：

1. ✅ 日志中有 "✓ Added image_history_list and original_images"
2. ✅ 日志中有 "image_history 长度: N" 其中N>1
3. ✅ 日志中有 "✓ Successfully logged N trajectories"
4. ✅ `wandb/run-*/media/images/` 中有.png文件
5. ✅ Wandb网页有Media tab
6. ✅ 图像包含Ground Truth列
7. ✅ Caption包含SSIM/LPIPS/PSNR指标（如果使用有参考模式）
8. ✅ 训练奖励值 > 0.3

如果所有项都满足，功能就完美了！🎉

