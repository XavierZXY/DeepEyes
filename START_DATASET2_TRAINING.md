# 🚀 数据集2训练启动指南
# Quick Start Guide for Dataset 2

---

## 第1步：验证环境
## Step 1: Verify Environment

```bash
cd /home/takisobe@amd.com/zxy/codes/DeepEyes

# 测试reward计算
# Test reward calculation
python3 test_visual_toolbox_v2_reward.py
```

**预期输出 / Expected Output**:
```
✓ Test 1: PASS
✓ Test 2: PASS
✓ Test 3: PASS
✓ Test 4: PASS
✓ Test 5: PASS
✓ Test 6: PASS
所有测试通过！✓
```

---

## 第2步：配置检查
## Step 2: Configuration Check

```bash
# 检查数据集路径
# Check dataset path
ls -lh data/train/train_dataset.parquet

# 检查验证集（如果有）
# Check validation set (if available)
ls -lh data/val/val_dataset.parquet
```

**如果数据集不存在 / If dataset doesn't exist**:
```bash
# 修改训练脚本中的路径
# Edit the path in training script
nano examples/agent/visual_toolbox_v2.sh

# 修改这两行:
TRAIN_DATASET=/path/to/your/train_dataset.parquet
VAL_DATASET=/path/to/your/val_dataset.parquet
```

---

## 第3步：启动训练
## Step 3: Start Training

```bash
# 方式1：直接运行
# Method 1: Direct run
bash examples/agent/visual_toolbox_v2.sh

# 方式2：后台运行并保存日志
# Method 2: Background run with logging
nohup bash examples/agent/visual_toolbox_v2.sh > logs/dataset2_training.log 2>&1 &

# 查看日志
# View logs
tail -f logs/dataset2_training.log
```

---

## 第4步：监控训练
## Step 4: Monitor Training

### Wandb网页 / Wandb Web
```
1. 访问 / Visit: https://wandb.ai
2. 项目 / Project: visual_toolbox_v2
3. 运行 / Run: defect_detection_train
```

### 关键指标 / Key Metrics

**格式收敛 / Format Convergence**:
```
Charts → reward/format_correct_ratio
目标 / Target: >0.95
```

**准确率 / Accuracy**:
```
Charts → reward/accuracy_ratio
目标 / Target: >0.80
```

**总分 / Total Score**:
```
Charts → critic/score/mean
目标 / Target: >1.5
```

### 图像查看 / View Images
```
Media → train/trajectories
  ↓
点击图像查看详情
Click images for details
```

### 对话表格 / Conversation Table
```
Charts → 搜索 "conversation_details"
Charts → Search "conversation_details"
  ↓
查看Format_Reward和Acc_Reward列
Check Format_Reward and Acc_Reward columns
```

---

## 第5步：调试（如需要）
## Step 5: Debug (If Needed)

### 检查reward计算
### Check reward calculation
```bash
# 查看reward日志
# View reward logs
grep "visual_toolbox_v2.*Score breakdown" logs/*.log | tail -20

# 预期看到:
# Expected to see:
# [visual_toolbox_v2] Score breakdown: format=1.00, acc=1.00, final=2.00
```

### 检查工具执行
### Check tool execution
```bash
# 查看工具调用
# View tool calls
grep "DEBUG.*SUCCESS ACTION\|DEBUG.*Execute WRONG" logs/*.log | tail -20
```

### 检查wandb上传
### Check wandb upload
```bash
# 查看wandb图像上传
# View wandb image upload
grep "DEBUG WANDB IMAGE" logs/*.log | tail -20

# 预期看到:
# Expected to see:
# [DEBUG WANDB IMAGE] ✓ Uploaded X images to train/trajectories
# [DEBUG WANDB IMAGE] ✓ Successfully logged X training samples to table
```

---

## 常见问题 / FAQ

### Q1: Reward始终是1.0
### Q1: Reward is always 1.0

**原因 / Cause**: 只有format，没有accuracy  
**解决 / Solution**: 检查模型是否输出了`<answer>`标签

### Q2: Wandb没有Format_Reward列
### Q2: No Format_Reward column in Wandb

**原因 / Cause**: reward_extra_info中缺少format_reward  
**解决 / Solution**: 
```bash
# 检查是否正确识别数据集类型
grep "Using visual_toolbox_v2 reward" logs/*.log
```

### Q3: 工具使用了上一个处理后的图
### Q3: Tool uses previous processed image

**原因 / Cause**: env_name设置错误  
**解决 / Solution**: 确认数据集的env_name='visual_toolbox_v2'
```bash
python3 -c "import pandas as pd; df=pd.read_parquet('data/train/train_dataset.parquet'); print(df.iloc[0]['env_name'])"
```

---

## 训练参数调优建议
## Training Parameter Tuning

### 学习率 / Learning Rate
```yaml
# 默认 / Default
actor_rollout_ref.actor.optim.lr=1e-6

# 如果收敛慢 / If slow convergence
actor_rollout_ref.actor.optim.lr=5e-6

# 如果不稳定 / If unstable
actor_rollout_ref.actor.optim.lr=5e-7
```

### Batch Size
```yaml
# 默认 / Default
data.train_batch_size=16

# GPU内存充足 / If enough GPU memory
data.train_batch_size=32

# GPU内存不足 / If GPU OOM
data.train_batch_size=8
```

### 采样数量 / Sampling per prompt
```yaml
# 默认 / Default
actor_rollout_ref.rollout.n=4

# 提高多样性 / Increase diversity
actor_rollout_ref.rollout.n=8

# 减少计算量 / Reduce computation
actor_rollout_ref.rollout.n=2
```

---

## 成功标志 / Success Indicators

训练成功的标志 / Signs of successful training:

1. ✅ **格式快速收敛**  
   Format convergence: `reward/format_correct_ratio` > 0.9 (前100步)

2. ✅ **准确率提升**  
   Accuracy improvement: `reward/accuracy_ratio` 持续上升

3. ✅ **工具使用合理**  
   Tool usage: `agent/tool_call_mean` 在0.5-2之间

4. ✅ **Wandb图像正常显示**  
   Wandb images: Media tab有图像且caption正确

5. ✅ **无大量错误日志**  
   No massive errors: 日志中无大量WARNING/ERROR

---

## 保存和恢复
## Save and Resume

### 检查点保存
### Checkpoint Saving
```bash
# 检查点位置
# Checkpoint location
ls -lh /app/xiaominl/models/verl_checkpoints/visual_toolbox_v2/defect_detection_train/

# 每20步保存一次（可在脚本中修改）
# Saved every 20 steps (configurable in script)
```

### 从检查点恢复
### Resume from Checkpoint
```bash
# 在训练脚本中添加
# Add to training script
actor_rollout_ref.actor.checkpoint.load_path=/path/to/checkpoint
```

---

## 🎉 开始训练！
## 🎉 Start Training!

```bash
bash examples/agent/visual_toolbox_v2.sh
```

**监控命令 / Monitor Commands**:
```bash
# 实时查看日志
# Real-time log viewing
tail -f logs/defect_detection_train.log

# 查看GPU使用
# View GPU usage
watch -n 1 nvidia-smi  # 或 rocm-smi (AMD GPU)

# 查看wandb
# View wandb
# 浏览器打开 / Open in browser: https://wandb.ai
```

---

## 📚 参考文档
## 📚 Reference Documents

- **快速参考**: `QUICK_REFERENCE_DATASET2.md`
- **迁移指南**: `MIGRATION_DATASET2_GUIDE.md`
- **详细对比**: `DATASET_COMPARISON.md`
- **完成报告**: `DATASET2_MIGRATION_COMPLETE.md`
- **Wandb功能**: `WANDB_FEATURES_SUMMARY.md`

---

Good luck with training! 🚀
祝训练顺利！🎉

