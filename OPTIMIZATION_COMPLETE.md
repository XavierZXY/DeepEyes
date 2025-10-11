# 🎨 Wandb可视化完整优化

## ✅ 三大优化

### 优化1: 图片排版优化

**改进内容**:
- ✅ 增加图像间距（10px → 15px）
- ✅ 添加灰色边框（2px）突出每个图像
- ✅ 彩色标签背景：
  - Ground Truth: 浅蓝色
  - Restored: 浅绿色  
  - 其他: 浅黄色
- ✅ 更大的标签字体（12px → 14px）
- ✅ 更高的标签区域（25px → 30px）

**视觉效果**:
```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Ground Truth ┃   │  │ Degraded Input ┃ │  │   Restored   ┃   │
│ (浅蓝色背景)    │  │ (浅黄色背景)    │  │ (浅绿色背景)    │
├─────────────────┤  ├─────────────────┤  ├─────────────────┤
│ ┏━━━━━━━━━┓    │  │ ┏━━━━━━━━━┓    │  │ ┏━━━━━━━━━┓    │
│ ┃  清晰原图  ┃    │  │ ┃  退化图像  ┃    │  │ ┃  复原结果  ┃    │
│ ┗━━━━━━━━━┛    │  │ ┗━━━━━━━━━┛    │  │ ┗━━━━━━━━━┛    │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### 优化2: 使用真正原图计算PSNR/SSIM/LPIPS

**修改位置**: `verl/utils/reward_score/__init__.py` 第90行

**之前**:
```python
use_no_reference=True  # 默认无参考模式
# 只有Quality分数，没有PSNR/SSIM/LPIPS
```

**现在**:
```python
use_no_reference=False  # 有参考模式
# 计算PSNR/SSIM/LPIPS，使用extra_info['original_image']作为参考
```

**效果**:
- ✅ PSNR: 峰值信噪比（dB，通常20-40）
- ✅ SSIM: 结构相似性（0-1，越高越好）
- ✅ LPIPS: 感知损失（0-1，越低越好）
- ✅ 所有指标都基于**真正的原图**（extra_info['original_image']）

**注意**: 需要数据集提供`extra_info['original_image']`，否则会报错

### 优化3: 按Step组织数据

**新的Wandb结构**:

```
Charts
├─ train/step1/
│   ├─ sample0/
│   │   ├─ image (图像)
│   │   ├─ quality (质量分数)
│   │   ├─ ssim (SSIM)
│   │   ├─ lpips (LPIPS)
│   │   ├─ psnr (PSNR)
│   │   ├─ num_tools (工具数量)
│   │   └─ conversation (对话Html)
│   ├─ sample1/
│   │   └─ ... (同上)
│   └─ ...
├─ train/step2/
│   ├─ sample0/
│   └─ ...
└─ train/conversation_details (汇总表格)
```

**对比方式**:

在wandb中，可以：
1. **横向对比同一step的不同样本**:
   - 搜索 "train/step1"
   - 看到所有step1的样本（sample0, sample1, ...）
   - 对比质量、指标、对话

2. **纵向对比同一样本在不同step**:
   - 搜索 "sample0"
   - 看到step1/sample0, step2/sample0, ...
   - 追踪同一位置样本的进展

3. **查看具体样本的完整信息**:
   - 点击 `train/step1/sample0`
   - 看到：图像 + quality + ssim + lpips + psnr + conversation

## 📊 Wandb中的新布局

### A. 按Step查看（Panel视图）

**路径**: `Charts → 搜索 "train/step1"`

```
train/step1/sample0/
  image: [GT][Degraded][Step1][Restored] ← 优化后的图像
  quality: 0.856
  ssim: 0.923
  lpips: 0.145  
  psnr: 28.4
  num_tools: 2
  conversation: [Html面板显示对话]
    Turn 1: Think... Tools...
    Turn 2: Think... [ANSWER]

train/step1/sample1/
  image: [GT][Degraded][Restored]
  quality: 0.622
  ...
```

### B. Table汇总视图

**路径**: `Charts → 搜索 "conversation_details"`

| Step | Sample_ID | Quality | Num_Tools | SSIM | LPIPS | PSNR | Turn1_Think | Turn1_Tools | Turn2_Think | Turn2_Tools |
|------|-----------|---------|-----------|------|-------|------|-------------|-------------|-------------|-------------|
| 1 | step1_idx0 | 0.856 | 2 | 0.923 | 0.145 | 28.4 | JPEG artifacts... | [{"name":"swinir...",...}] | Motion blur... | [{"name":"xrestormer...",...}] |
| 1 | step1_idx1 | 0.622 | 1 | 0.812 | 0.234 | 24.1 | Haze detected | [{"name":"dehazeformer...",...}] | [ANSWER] | |

### C. Media Panel（保留，向后兼容）

**路径**: `Media → train/trajectories`

传统的Media视图，所有图像混在一起。

## 🔍 使用方式

### 场景1: 对比Step 1的所有样本

1. 在Charts搜索框输入 "train/step1"
2. 展开看到所有sample0, sample1, ...
3. 并排查看：
   - 图像质量
   - SSIM/LPIPS/PSNR指标
   - 对话内容
4. 快速对比哪个样本表现最好

### 场景2: 追踪样本进展

1. 搜索 "sample0"
2. 看到：
   - train/step1/sample0
   - train/step2/sample0
   - train/step3/sample0
3. 对比同一位置样本随训练的变化

### 场景3: 分析指标分布

1. 搜索 "train/step1/*/ssim"
2. 看到该step所有样本的SSIM分布
3. 或搜索 "train/*/sample0/psnr"
4. 看到sample0在所有step的PSNR变化

### 场景4: 查看完整对话

1. 点击 `train/step1/sample0/conversation`
2. Html面板显示格式化的对话
3. 每个turn单独显示，清晰易读

## 📊 关于PSNR/SSIM的说明

### 切换到有参考模式

**代码修改**: `verl/utils/reward_score/__init__.py` 第90行
```python
use_no_reference=False  # 使用有参考模式
```

### 需要真正的原图

**数据集要求**: `extra_info['original_image']` 必须是未退化的真实原图

**检查方法**:
```bash
grep "DEBUG GT.*Using original_image from extra_info" logs/*.log
```

**如果看到**:
```
✓ Using original_image from extra_info
```
说明使用了真正的原图。

**如果看到**:
```
⚠️  Fallback to origin_multi_modal_data
```
说明数据集没有提供原图，此时PSNR/SSIM是基于退化图计算的（不准确）。

### 指标含义

- **PSNR**: 峰值信噪比
  - 单位：dB
  - 范围：通常20-40
  - 越高越好：>30很好，>35excellent
  
- **SSIM**: 结构相似性
  - 范围：0-1
  - 越高越好：>0.9很好，>0.95excellent
  
- **LPIPS**: 感知损失
  - 范围：0-1
  - 越低越好：<0.2很好，<0.1excellent

## 🎯 查看示例

### Step 1的sample0

```
Charts → 搜索 "train/step1/sample0"

看到所有指标：
├─ image: [优化后的图像布局]
├─ quality: 0.856
├─ ssim: 0.923 ← 与GT的结构相似性
├─ lpips: 0.145 ← 感知损失
├─ psnr: 28.4 ← 峰值信噪比
├─ num_tools: 2
└─ conversation: 
    Turn 1: Think... Tools: swinir_jpeg...
    Turn 2: Think... [ANSWER]
```

### 对比同一step不同样本

```
搜索 "train/step1"

并排显示:
sample0: quality=0.856, ssim=0.923, lpips=0.145
sample1: quality=0.622, ssim=0.812, lpips=0.234
sample2: quality=0.301, ssim=0.567, lpips=0.567

快速看出sample0表现最好
```

## 🚀 运行命令

```bash
# 重新运行训练（应用所有优化）
bash examples/agent/IR.sh 2>&1 | tee logs/optimized_$(date +%Y%m%d_%H%M%S).log
```

## ✅ 验证

### 1. 检查有参考模式

```bash
grep "使用有参考模式\|使用有参考指标" logs/optimized_*.log | head -5

# 应该看到:
[DEBUG] 使用有参考模式...
ssim=0.923, lpips=0.145, psnr=28.4
```

### 2. 检查原图来源

```bash
grep "DEBUG GT.*Using original_image" logs/optimized_*.log | head -5

# 应该看到:
✓ Using original_image from extra_info
```

### 3. 在Wandb查看

**按step查看**:
- 搜索 "train/step1"
- 应该看到sample0, sample1, ...的分组
- 每个sample有image, quality, ssim, lpips, psnr, conversation

**Table查看**:
- 搜索 "conversation_details"
- 应该看到Quality_Score, SSIM, LPIPS, PSNR列
- 每个turn单独列

## 📝 优化总结

| 方面 | 之前 | 现在 |
|------|------|------|
| **图片排版** | 简单拼接 | 边框+彩色标签+间距 |
| **质量指标** | 无参考（NIQE等） | 有参考（PSNR/SSIM/LPIPS） |
| **参考图像** | 可能是退化图 | 真正的原图（extra_info） |
| **数据组织** | 所有step混在一起 | 按step/sample分层组织 |
| **对话展示** | 挤在一列 | 每个turn单独列+Html panel |
| **对比方式** | 难以对比 | 按step横向对比，按sample纵向追踪 |

## 🎉 最终效果

现在你在wandb中可以：

1. **看到优化后的图像** - 更清晰的布局和标签
2. **看到真实的PSNR/SSIM** - 基于原图计算
3. **按step对比样本** - 方便分析同一step的不同表现
4. **完整的对话** - 每个turn清晰可见，内容不截断

所有功能完全优化！🎨

