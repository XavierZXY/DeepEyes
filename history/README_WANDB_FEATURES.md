# Wandb图像和对话上传功能 - 完整说明

## 🎯 功能总览

### ✅ 已实现的所有功能

1. **训练和验证Rollout图像上传**
   - 优化的图片排版（边框、彩色标签、间距）
   - Ground Truth + 退化输入 + 处理过程 + 复原结果
   - 按step组织，方便对比

2. **完整的对话历史**
   - 每一轮Agent的Think和Tools
   - 按turn单独列显示
   - 内容完整不截断
   - Table累积保存

3. **双重指标系统**
   - **有参考指标**: PSNR, SSIM, LPIPS（基于真实GT）
   - **无参考指标**: NIQE, BRISQUE, CPBD, CLIP-IQA, Hyper-IQA
   - 奖励计算用无参考（灵活）
   - Wandb展示两种都有（全面）

## 📍 Wandb中的位置

### 训练Rollout

#### 1. 按Step组织的Panel
**路径**: `Charts → 搜索 "train/step1"`

每个样本独立panel：
```
train/step1/sample0/
  - image: 优化后的图像
  - quality: 0.856
  - ssim_with_gt, lpips_with_gt, psnr_with_gt (有参考)
  - niqe, brisque, cpbd, clip_iqa, hyper_iqa (无参考)
  - num_tools: 2
  - conversation: Html对话
```

#### 2. 对话记录表格
**路径**: `Charts → 搜索 "conversation_details"`

| Step | Sample_ID | Quality | Num_Tools | User_Input | Turn1_Think | Turn1_Tools | Turn2_Think | Turn2_Tools |
|------|-----------|---------|-----------|------------|-------------|-------------|-------------|-------------|
| 1 | step1_idx0 | 0.856 | 2 | Restore... | JPEG... | [{"name":"swinir...",...}] | Blur... | [{"name":"xrestormer...",...}] |

### 验证Rollout

同样的结构：
- `val/step1/sample0/...`
- `val/conversation_details`

## 🎨 优化的图片排版

```
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Ground Truth ┃    │  │ Degraded Input ┃ │  │   Restored   ┃    │
│ (浅蓝色背景)      │  │ (浅黄色背景)    │  │ (浅绿色背景)      │
├──────────────────┤  ├──────────────────┤  ├──────────────────┤
│ ┏━━━━━━━━━━┓    │  │ ┏━━━━━━━━━━┓    │  │ ┏━━━━━━━━━━┓    │
│ ┃ 清晰原图   ┃    │  │ ┃ 模糊+压缩 ┃    │  │ ┃ 完全复原   ┃    │
│ ┗━━━━━━━━━━┛    │  │ ┗━━━━━━━━━━┛    │  │ ┗━━━━━━━━━━┛    │
│ (灰色边框)        │  │ (灰色边框)      │  │ (灰色边框)        │
└──────────────────┘  └──────────────────┘  └──────────────────┘
     15px间距              15px间距
```

## 📊 所有指标说明

### 奖励指标（训练用）
- **quality**: 综合质量分数（无参考模式，0-1）

### 有参考指标（需要GT，评估用）
- **ssim_with_gt**: 结构相似性（0-1，>0.9好）
- **lpips_with_gt**: 感知损失（0-1，<0.2好）
- **psnr_with_gt**: 峰值信噪比（dB，>30好）

### 无参考指标（不需要GT，绝对质量）
- **niqe**: 自然度（0-100，<5好）
- **brisque**: 盲质量（0-100，<40好）
- **cpbd**: 锐度（0-1，>0.8好）
- **clip_iqa**: CLIP感知质量（0-1）
- **hyper_iqa**: 深度学习质量（0-1）

## 🔍 如何查看

### 场景1: 对比同一step的不同样本

```
1. 搜索 "train/step1"
2. 看到所有sample0, sample1, ...
3. 并排对比：
   - 图像质量
   - 所有指标（有参考+无参考）
   - 对话内容
```

### 场景2: 追踪特定样本

```
1. 搜索 "sample0"
2. 看到：step1/sample0, step2/sample0, ...
3. 追踪该位置样本的进展
```

### 场景3: 分析指标趋势

```
1. 搜索 "ssim_with_gt"
2. 看到所有样本的SSIM分布
3. 对比训练进展
```

### 场景4: 查看详细对话

```
1. 点击 "train/step1/sample0/conversation"
2. Html panel显示格式化对话
3. 每个turn单独显示，清晰易读
```

## ✅ 验证清单

运行训练后，检查：

- [ ] Media有train和val目录
- [ ] 搜索"step1"看到按step组织的panel
- [ ] 每个sample有image, quality, ssim_with_gt等指标
- [ ] Caption显示SSIM/LPIPS/PSNR/NIQE
- [ ] conversation_details表格有数据
- [ ] Table中Turn列有内容（不为空）
- [ ] Quality不全是0

## 🚀 快速开始

```bash
# 运行训练
bash examples/agent/IR.sh

# 查看wandb
# 1. Media → train/trajectories (图像)
# 2. 搜索 "train/step1" (按step查看)
# 3. 搜索 "conversation_details" (对话表格)
```

所有功能已完整实现！
- ✅ 优化图片排版
- ✅ 真实GT计算PSNR/SSIM/LPIPS
- ✅ 同时显示有参考和无参考指标
- ✅ 按step组织数据
- ✅ 完整对话展示
- ✅ Table累积保存

🎉

