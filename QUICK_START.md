# Wandb图像和对话上传 - 快速开始

## 🎯 已完成的所有功能

### ✅ 自动上传到Wandb

1. **训练过程图像** (train/trajectories)
   - 每个step采样9张图像（2 best + 2 worst + 5 random）
   - 包含：GT + 退化图 + 处理过程 + 复原结果
   - 带对话：User input + Agent多轮对话

2. **验证过程图像** (val/trajectories)  
   - 所有验证样本
   - 完整的图像序列和对话

3. **对话记录表格** (train/conversation_details)
   - 结构化数据
   - 可排序、过滤、搜索

## 🚀 如何查看

### 在Wandb网页

```
1. 打开你的wandb项目
   https://wandb.ai/your-team/agent_vlagent

2. 点击最新的run
   如: debug_for_TIR_IR_bs16_mi300

3. 查看图像
   左侧 → Media → train/trajectories
   
4. 查看对话表格
   搜索框 → 输入 "conversation_details"
   
5. 查看指标
   Charts → critic/score/max（查看最高奖励）
```

### 本地查看（可选）

```bash
# 如果启用了markdown保存
ls outputs/conversations/your_experiment/
cat outputs/conversations/your_experiment/train_step100_*.md
```

## ⚙️ 配置（在IR.sh或config中）

```bash
# 默认配置（推荐）
trainer.log_images_to_wandb=True  # 启用图像上传
# 默认采样: 2 best + 2 worst + 5 random

# 自定义采样（可选）
trainer.num_train_images_to_log=10  # 随机样本数
trainer.num_best_worst_images_to_log=3  # 最好/最差各3个

# 保存markdown（可选）
trainer.save_conversation_markdown=True  # 保存本地文件
```

## 📊 包含的内容

### 每个样本展示

**图像部分**:
```
[Ground Truth] → [Degraded Input] → [Step 1] → [Step 2] → [Restored]
     ↑               ↑                                        ↑
  清晰原图         退化输入                                复原结果
```

**对话部分**:
```
=== USER ===
Restore this image

=== AGENT CONVERSATION HISTORY ===

Turn 1: Think + Tools
Turn 2: Think + Tools
Turn 3: Answer
```

**指标部分**:
```
Quality: 0.856 | SSIM: 0.923 | LPIPS: 0.145 | PSNR: 28.4 [BEST]
```

## 🎯 常见问题

### Q: 我看不到Media tab？
A: 检查：
1. 训练是否还在运行？等几分钟
2. `grep "Successfully logged" logs/*.log` 看是否上传成功
3. 检查网络连接

### Q: 奖励最大值还是0.3？
A: 这是正常的！
- 0.3 = 只有格式奖励（工具未执行）
- 0.6-0.9 = 包含质量奖励（工具已执行）
- 查看 `critic/score/max` 应该能看到>0.3的值

### Q: GT和退化图看起来差不多？
A: 检查：
```bash
grep "DEBUG GT" logs/*.log
```
如果看到"original_image is None"，说明数据集没有提供真正的GT

### Q: 对话记录在哪？
A: 三个地方：
1. Media中的图像上方（文本）
2. conversation_details表格（结构化）
3. 本地markdown（如果启用）

## ✅ 验证清单

训练运行后，检查：

```bash
# 1. 检查日志
./TEST_WANDB_UPLOAD.sh

# 2. 检查wandb文件
find wandb/run-*/files/media/images -name "*.png" | wc -l
# 应该看到多个文件

# 3. 在wandb网页检查
# - Media tab 是否有图像
# - 搜索 "conversation_details" 是否有表格
```

## 📚 详细文档

- `ALL_FIXES_COMPLETE.md` - 所有修复总结
- `CONVERSATION_DISPLAY_GUIDE.md` - 对话展示指南
- `WANDB_LOCATION_GUIDE.md` - Wandb位置详解
- `COMPLETE_DATA_FLOW_EXPLANATION.md` - 完整数据流

## 🎉 功能完整度

- ✅ 训练图像上传
- ✅ 验证图像上传
- ✅ 对话内容展示（图像+表格）
- ✅ 原图GT展示
- ✅ 详细指标（Quality, SSIM, LPIPS, PSNR）
- ✅ 中间处理过程
- ✅ Agent多轮对话
- ✅ 智能采样（best/worst/random）

所有功能已完整实现！
