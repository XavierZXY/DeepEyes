# 🎯 Wandb图像和对话上传 - 最终实现总结

## ✅ 已完成的所有功能

### 1. 图像可视化

#### Training (train/trajectories)
- **方式**: 传统Media panel（不用step panel，节省空间）
- **采样**: 2 best + 2 worst + 5 random
- **布局**: 优化排版（边框、彩色标签、间距）
- **内容**: GT + 退化图 + 处理步骤 + 复原结果
- **指标**: Caption显示所有指标

#### Validation (val/stepN/sampleM/)
- **方式**: 按step组织的独立panel（方便对比）
- **采样**: 所有验证样本
- **布局**: 同training（优化排版）
- **内容**: 完整序列
- **指标**: 每个sample独立展示

### 2. 对话历史

#### 图像上方文本
- User input
- Agent每轮的Think和Tools
- 完整展示

#### conversation_details表格
- 每个turn单独列
- Turn1_Think, Turn1_Tools, Turn2_Think, Turn2_Tools, ...
- 内容完整不截断
- 按step累积保存

### 3. 双重指标系统

#### 奖励计算（无参考）
- **用途**: 计算训练奖励
- **计算**: 只计算一次
- **指标**: NIQE, BRISQUE, CPBD, CLIP-IQA, Hyper-IQA
- **结果**: quality score

#### 额外展示（有参考）
- **用途**: Wandb展示和分析
- **计算**: 额外计算一次（只在有GT时）
- **指标**: PSNR, SSIM, LPIPS
- **结果**: ssim_score_ref, lpips_score_ref, psnr_score_ref

## 📊 计算流程

```python
# __init__.py 中的逻辑

# 1. 计算无参考奖励（训练用）
res = compute_score_v2(
    solution_str, ground_truth, extra_info,
    use_no_reference=True  # 无参考模式
)
# → 返回 {'score': 0.856, 'niqe_score': 5.71, 'brisque_score': 43.31, ...}

# 2. 额外计算有参考指标（展示用，只计算一次）
if extra_info and extra_info.get('original_image') is not None:
    ref_result = compute_image_quality_reward_v2(
        solution_str, extra_info,
        use_no_reference=False  # 有参考模式
    )
    # → 返回 {'ssim_score': 0.923, 'lpips_score': 0.145, 'psnr_score': 28.4}
    
    # 添加到res中
    res['ssim_score_ref'] = ref_result['ssim_score']
    res['lpips_score_ref'] = ref_result['lpips_score']
    res['psnr_score_ref'] = ref_result['psnr_score']

# 最终res包含所有指标（无参考+有参考）
```

**注意**: 
- ✅ 无参考只计算一次（在奖励计算时）
- ✅ 有参考额外计算一次（仅用于展示）
- ✅ 如果没有GT，跳过有参考计算

## 📍 Wandb中的位置

### Training

**Media**:
- `train/trajectories` - 所有训练图像（Media panel）

**Table**:
- `train/conversation_details` - 对话记录表格（按step累积）

**指标**:
- Caption中显示主要指标

### Validation

**Panel**（新增）:
- `val/step1/sample0/` - 图像+所有指标+对话
- `val/step1/sample1/` - ...
- `val/step5/sample0/` - ...

**Table**:
- `val/conversation_details` - 对话记录表格

## 🎨 可视化效果

### Training图像（优化排版）
```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│Ground Truth ┃ │  │Degraded Input│  │  Restored  ┃ │
│(浅蓝背景)    │  │(浅黄背景)    │  │(浅绿背景)    │
├──────────────┤  ├──────────────┤  ├──────────────┤
│┏━━━━━━━━┓  │  │┏━━━━━━━━┓  │  │┏━━━━━━━━┓  │
│┃  原图    ┃  │  │┃  退化    ┃  │  │┃  复原    ┃  │
│┗━━━━━━━━┛  │  │┗━━━━━━━━┛  │  │┗━━━━━━━━┛  │
└──────────────┘  └──────────────┘  └──────────────┘
```

**Caption**: 
```
Sample 42 [BEST] | Quality: 0.856 | SSIM: 0.923 | LPIPS: 0.145 | PSNR: 28.4 | NIQE: 5.71
```

### Validation Panel
```
val/step5/sample0/
  image: [同样优化的排版]
  quality: 0.812
  ssim_with_gt: 0.891
  lpips_with_gt: 0.178
  psnr_with_gt: 27.3
  niqe: 6.24
  brisque: 38.5
  cpbd: 0.79
  num_tools: 2
  conversation: [完整Html对话]
```

### 对话表格
```
| Step | Sample_ID | Quality | Num_Tools | User_Input | Turn1_Think | Turn1_Tools | Turn2_Think | Turn2_Tools |
|------|-----------|---------|-----------|------------|-------------|-------------|-------------|-------------|
| 1 | step1_idx0 | 0.856 | 2 | 完整输入... | 完整思考... | 完整JSON... | 完整思考... | [ANSWER] |
| 2 | step2_idx0 | 0.822 | 3 | ... | ... | ... | ... | ... |
```

## 🔧 计算资源优化

### 只计算必要的指标

**奖励计算时**:
- ✅ 计算无参考指标一次
- ✅ 返回niqe, brisque, cpbd等详细值

**额外展示时**:
- ✅ 只额外计算有参考指标（如果有GT）
- ✅ 不重复计算无参考

**总计算量**:
- 无参考指标: 计算1次
- 有参考指标: 计算1次（仅有GT时）
- **无重复计算**

## 📊 展示的所有指标

### 奖励相关（无参考）
- quality: 总质量分数（训练奖励）
- niqe_score: 自然度
- brisque_score: 盲质量
- cpbd_score: 锐度
- clip_iqa_score: CLIP质量
- hyper_iqa_score: 深度质量

### 评估相关（有参考，基于真实GT）
- ssim_score_ref: 结构相似性
- lpips_score_ref: 感知损失
- psnr_score_ref: 峰值信噪比

### 其他
- num_tools: 执行工具数量
- conversation: 完整对话历史

## 🎯 查看方式

### Training Rollout

**快速浏览**:
```
Media → train/trajectories
```

**详细分析**:
```
1. conversation_details表格 - 查看所有样本
2. 按Quality排序 - 找最好/最差
3. 查看Turn列 - 分析工具使用
```

### Validation Rollout

**按step对比**:
```
搜索 "val/step5"
→ 看到所有sample0, sample1, ...
→ 并排对比质量和指标
```

**追踪特定位置**:
```
搜索 "sample0"
→ 看到step1/sample0, step5/sample0, ...
→ 追踪进展
```

**查看所有指标**:
```
点击 val/step5/sample0
→ 看到完整的panel
→ 所有指标（有参考+无参考）
→ 对话内容
```

## ✅ 最终配置

### 默认配置
```yaml
trainer:
  log_images_to_wandb: true  # 启用wandb上传
  num_train_images_to_log: 5  # 训练随机样本数
  num_best_worst_images_to_log: 2  # 最好/最差各2个
  # save_conversation_markdown: false  # 不保存本地markdown（默认）
```

### 可选配置
```yaml
trainer:
  save_conversation_markdown: true  # 保存本地markdown文件
  num_train_images_to_log: 10  # 更多样本
```

## 📋 完整功能清单

- ✅ 训练图像: Media/train/trajectories（优化排版）
- ✅ 验证图像: val/stepN/sampleM/（按step组织）
- ✅ 对话历史: 图像上方+Table+Html panel
- ✅ 有参考指标: PSNR/SSIM/LPIPS（基于真实GT）
- ✅ 无参考指标: NIQE/BRISQUE/CPBD等（计算一次）
- ✅ Table累积: 按step增长，不覆盖
- ✅ 完整对话: 不截断，每turn单独列
- ✅ 资源优化: 无重复计算

## 🚀 立即运行

```bash
bash examples/agent/IR.sh 2>&1 | tee logs/final_optimized_$(date +%Y%m%d_%H%M%S).log
```

所有功能已完整实现并优化！🎉

**主要改进**:
1. ✅ Training保持传统方式（高效）
2. ✅ Validation按step组织（易对比）
3. ✅ 双重指标（无重复计算）
4. ✅ 完整对话展示
5. ✅ 优化图片排版

