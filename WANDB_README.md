# Wandb图像和对话上传功能 - 使用指南

## 🎯 功能概述

自动将训练和验证过程的rollout结果上传到wandb，包括：
- ✅ 图像序列（GT + 退化 + 处理过程 + 复原）
- ✅ 完整对话（每轮Think和Tools）
- ✅ 双重指标（有参考PSNR/SSIM/LPIPS + 无参考NIQE/BRISQUE等）
- ✅ 优化排版（边框、彩色标签）

## 📍 在Wandb中查看

### Training Rollout
1. **Media** → `train/trajectories` - 图像可视化
2. **Charts** → `train/conversation_details` - 对话表格

### Validation Rollout  
1. **Charts** → `val/step5/sample0/` - 按step组织的panel
2. **Charts** → `val/conversation_details` - 对话表格

## 📊 显示的内容

### 图像（优化排版）
```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│Ground Truth ┃│  │Degraded Input│  │  Restored  ┃ │
│(浅蓝背景)    │  │(浅黄背景)    │  │(浅绿背景)    │
└──────────────┘  └──────────────┘  └──────────────┘
```

### Caption
```
Sample 42 [BEST] | Quality: 0.856 | SSIM: 0.923 | LPIPS: 0.145 | PSNR: 28.4 | NIQE: 5.71
```

### Table
| Step | Sample_ID | Quality | Num_Tools | Turn1_Think | Turn1_Tools | Turn2_Think | Turn2_Tools |
|------|-----------|---------|-----------|-------------|-------------|-------------|-------------|
| 1 | step1_idx0 | 0.856 | 2 | 完整内容... | 完整JSON... | 完整内容... | [ANSWER] |

## ⚙️ 配置

```yaml
trainer:
  log_images_to_wandb: true  # 启用上传（默认true）
  num_train_images_to_log: 5  # 训练随机样本数
  num_best_worst_images_to_log: 2  # 最好/最差各2个
```

## 📈 指标说明

### 奖励指标（无参考，训练用）
- **Quality**: 总质量分数（0-1）
- **NIQE**: 自然度（越低越好，<5好）
- **BRISQUE**: 盲质量（越低越好，<40好）
- **CPBD**: 锐度（越高越好，>0.8好）

### 评估指标（有参考，基于真实GT）
- **PSNR**: 峰值信噪比（dB，>30好）
- **SSIM**: 结构相似性（0-1，>0.9好）
- **LPIPS**: 感知损失（0-1，<0.2好）

**注意**: 有参考指标只在工具执行后才有值，工具未执行时为None

## 🚀 快速开始

```bash
# 运行训练
bash examples/agent/IR.sh

# 查看wandb
# 1. Media → train/trajectories
# 2. 搜索 "val/step5" (validation按step查看)
# 3. 搜索 "conversation_details" (对话表格)
```

## 📚 详细文档

- `FINAL_IMPLEMENTATION_SUMMARY.md` - 完整实现说明
- `COMPLETE_METRICS_GUIDE.md` - 所有指标详解
- `TABLE_FORMAT_GUIDE.md` - Table格式说明
- `ALL_ISSUES_RESOLVED.md` - Bug修复记录

## ✅ 功能完整度

- ✅ 9个Bug全部修复
- ✅ Training和Validation都支持
- ✅ 图像、对话、指标完整
- ✅ 按step组织（validation）
- ✅ Table累积保存
- ✅ 资源优化（无重复计算）

所有功能已完整实现！🎉

