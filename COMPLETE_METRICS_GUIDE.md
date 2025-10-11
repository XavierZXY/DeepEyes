# 完整指标展示指南

## 🎯 双重指标系统

### 奖励计算（训练优化用）
- **模式**: 无参考（No-Reference）
- **指标**: NIQE, BRISQUE, CPBD, CLIP-IQA, Hyper-IQA
- **用途**: 计算奖励，驱动训练
- **优点**: 不需要原图，更灵活

### 评估展示（分析对比用）
- **模式**: 有参考（With-Reference）
- **指标**: PSNR, SSIM, LPIPS
- **用途**: wandb展示，评估效果
- **优点**: 基于真实GT，更准确

## 📊 Wandb中的完整指标

### 按Step组织的Panel

**路径**: `Charts → 搜索 "train/step1/sample0"`

```
train/step1/sample0/
├─ image: [优化后的图像布局]
├─ quality: 0.856 (无参考模式计算的总质量，用于奖励)
│
├─ 有参考指标（基于真实GT）:
│  ├─ ssim_with_gt: 0.923 (结构相似性)
│  ├─ lpips_with_gt: 0.145 (感知损失)
│  └─ psnr_with_gt: 28.4 (峰值信噪比)
│
├─ 无参考指标（不需要GT）:
│  ├─ niqe: 5.71 (自然图像质量评估)
│  ├─ brisque: 43.31 (盲图像质量评估)
│  ├─ cpbd: 0.82 (锐度评估)
│  ├─ clip_iqa: 0.31 (CLIP感知质量)
│  └─ hyper_iqa: 0.34 (深度学习质量)
│
├─ num_tools: 2
└─ conversation: [Html格式对话]
```

### Caption显示

**图像标题**:
```
Sample 42 | Quality: 0.856 [BEST] | SSIM: 0.923 | LPIPS: 0.145 | PSNR: 28.4 | NIQE: 5.71
```

**说明**:
- Quality: 无参考模式的总分（训练奖励）
- SSIM/LPIPS/PSNR: 有参考指标（与GT对比）
- NIQE: 主要的无参考指标

## 🔍 指标解读

### 有参考指标（需要GT）

**PSNR (Peak Signal-to-Noise Ratio)**:
- 单位: dB（分贝）
- 范围: 通常20-40
- 越高越好:
  - <20: 质量差
  - 20-25: 可接受
  - 25-30: 好
  - 30-35: 很好
  - \>35: 优秀

**SSIM (Structural Similarity)**:
- 范围: 0-1
- 越高越好:
  - <0.8: 质量差
  - 0.8-0.9: 可接受
  - 0.9-0.95: 好
  - \>0.95: 优秀

**LPIPS (Learned Perceptual Image Patch Similarity)**:
- 范围: 0-1
- 越低越好:
  - \>0.5: 质量差
  - 0.3-0.5: 可接受
  - 0.1-0.3: 好
  - <0.1: 优秀

### 无参考指标（不需要GT）

**NIQE (Natural Image Quality Evaluator)**:
- 范围: 0-100
- 越低越好:
  - <5: 优秀
  - 5-10: 好
  - 10-20: 可接受
  - \>20: 差

**BRISQUE (Blind/Referenceless Image Spatial Quality Evaluator)**:
- 范围: 0-100  
- 越低越好:
  - <20: 优秀
  - 20-40: 好
  - 40-60: 可接受
  - \>60: 差

**CPBD (Cumulative Probability of Blur Detection)**:
- 范围: 0-1
- 越高越好（锐度）:
  - \>0.8: 清晰
  - 0.6-0.8: 可接受
  - <0.6: 模糊

## 📈 如何使用这些指标

### 分析复原质量

1. **看有参考指标** (SSIM/LPIPS/PSNR):
   - 与真实GT对比，客观评估
   - SSIM >0.9 且 LPIPS <0.2 → 复原很好
   - PSNR >30 → 像素级误差小

2. **看无参考指标** (NIQE/CPBD):
   - 不需要GT，评估绝对质量
   - NIQE <5 → 图像自然
   - CPBD >0.8 → 图像清晰

### 对比不同样本

**在wandb中**:
```
搜索 "train/step1"

sample0: ssim=0.923, lpips=0.145, niqe=5.71 → 很好
sample1: ssim=0.812, lpips=0.234, niqe=12.5 → 一般
sample2: ssim=0.567, lpips=0.567, niqe=25.3 → 差

快速判断：sample0复原效果最好
```

### 追踪训练进展

**横向对比**（同一step）:
```
step1: 平均SSIM=0.85, 平均PSNR=26.5
```

**纵向追踪**（不同step）:
```
step1: SSIM=0.85
step10: SSIM=0.88
step20: SSIM=0.91
→ 模型在进步
```

## 🎨 Wandb展示示例

### Panel视图

```
train/step1/sample0/
  image: [优化布局的图像]
  quality: 0.856 (奖励用)
  
  有参考（与GT对比）:
    ssim_with_gt: 0.923 ↑
    lpips_with_gt: 0.145 ↓
    psnr_with_gt: 28.4 ↑
  
  无参考（绝对质量）:
    niqe: 5.71 ↓
    brisque: 43.31 ↓
    cpbd: 0.82 ↑
    clip_iqa: 0.31
    hyper_iqa: 0.34
  
  num_tools: 2
  conversation: [详细对话]
```

### Caption显示

```
Sample 42 [BEST]
Quality: 0.856 (奖励)
SSIM: 0.923 LPIPS: 0.145 PSNR: 28.4 (有参考)
NIQE: 5.71 (无参考)
```

## ✅ 数据流

```
Reward计算
├─ 使用无参考模式
├─ 计算NIQE, BRISQUE, CPBD, CLIP-IQA, Hyper-IQA
├─ 返回quality score → 训练奖励
└─ 同时额外计算有参考指标（如果有GT）
    ├─ 计算PSNR, SSIM, LPIPS
    └─ 添加到reward_extra_info中

Wandb展示
├─ 提取所有指标
│  ├─ 无参考: niqe_score, brisque_score, cpbd_score, ...
│  └─ 有参考: ssim_score_ref, lpips_score_ref, psnr_score_ref
├─ 按step/sample组织
└─ 在Panel和Caption中都显示
```

## 🚀 运行验证

```bash
bash examples/agent/IR.sh 2>&1 | tee logs/dual_metrics_$(date +%Y%m%d_%H%M%S).log
```

### 预期看到

**日志**:
```
[DEBUG] 使用无参考模式... (计算奖励)
[DEBUG no_ref_image_quality] niqe=5.71, brisque=43.31, cpbd=0.82
[DEBUG] 使用有参考模式... (额外计算)
[DEBUG image_quality] ssim=0.923, lpips=0.145, psnr=28.4
```

**Wandb**:
- Panel中同时有无参考和有参考的所有指标
- Caption显示主要指标（SSIM, LPIPS, PSNR, NIQE）
- 奖励基于无参考指标

所有指标现在都会显示，奖励计算保持原来的模式！🎯

