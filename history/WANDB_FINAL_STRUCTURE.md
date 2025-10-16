# Wandb最终结构说明

## 📊 完整的Wandb结构

### Training Rollout

**图像**:
```
Media → train/trajectories
- 每个step采样9张图（2 best + 2 worst + 5 random）
- Wandb自动提供slider浏览
- Caption显示所有指标
```

**对话**:
```
Charts → train/conversation_details
- 累积表格，每个step添加新行
- 每个turn单独列
- 完整内容不截断
```

### Validation Rollout

**图像**:
```
Media → val/stepN/trajectories
- 每个step的所有validation样本
- Wandb自动提供slider浏览（←可以拖动查看不同样本）
- Caption显示该样本的指标
```

**汇总统计**:
```
Charts → val/
- quality_mean, quality_max, quality_min (所有step在同一图表，横坐标为step)
- ssim_mean, ssim_max (所有step在同一图表)
- lpips_mean, lpips_min (所有step在同一图表)
- psnr_mean, psnr_max (所有step在同一图表)
```

**对话**:
```
Charts → val/conversation_details
- 累积表格
- 完整对话内容
```

## 🎯 查看方式

### 查看Training图像

1. **Media** → `train/trajectories`
2. 点击任一step展开
3. 使用**slider**浏览该step的9张图
4. 点击图像查看大图和caption

### 查看Validation图像

1. **Media** → `val/step5/trajectories`
2. 使用**slider**浏览所有100张图
3. Caption显示该样本的quality, ssim, lpips等
4. 点击查看大图和对话

### 查看汇总指标

1. **Charts** → 搜索 "val/quality"
2. 看到所有step的质量指标曲线：
   - val/quality_mean: 显示所有step的平均质量（横坐标是step）
   - val/quality_min: 显示所有step的最小质量
   - val/quality_max: 显示所有step的最大质量
3. 同样可查看 val/ssim_mean, val/lpips_mean, val/psnr_mean 等
4. 所有指标在同一图表中，方便对比不同step的训练进展

### 查看详细对话

1. **Charts** → 搜索 "conversation_details"
2. Table中查看所有样本的完整对话
3. 按Quality排序，找最好/最差样本
4. 查看Turn列，分析工具使用

## 📈 优化效果

### 之前的问题
```
❌ val/step0/sample0/quality
❌ val/step0/sample0/num_tools
❌ val/step0/sample0/ssim_with_gt
❌ val/step0/sample0/lpips_with_gt
...
→ 每个指标都是单独图表，太多了！
```

### 现在的结构
```
✓ val/step5/trajectories: 所有图像（用slider浏览）
✓ val/quality_mean: 所有step的汇总统计（同一图表）
✓ val/ssim_mean: 所有step的汇总统计（同一图表）
✓ val/psnr_mean: 所有step的汇总统计（同一图表）
✓ val/conversation_details: 完整table

→ 简洁清晰，所有step的指标在同一图表，方便对比训练进展！
```

## 🎨 可视化布局

### Media Panel中的slider

```
Media → val/step5/trajectories

┌────────────────────────────────────────┐
│ ◀ 1 / 100 ▶  [===============○====]  │  ← slider
├────────────────────────────────────────┤
│ [GT] [Degraded] [Step1] [Restored]    │
│ Sample 0                               │
│ Quality: 0.856 | SSIM: 0.923 | ...    │
└────────────────────────────────────────┘

拖动slider → 切换到sample1, sample2, ...
```

### Charts中的统计指标

```
val/step5/
  ├─ quality_mean: 0.623  📈 (折线图)
  ├─ quality_max: 0.891
  ├─ quality_min: 0.301
  ├─ ssim_mean: 0.845  📈
  ├─ lpips_mean: 0.234  📈
  └─ psnr_mean: 26.7  📈

跨step对比：
step1: quality_mean=0.534
step5: quality_mean=0.623 
step10: quality_mean=0.712
→ 看出训练进展
```

## ✅ 最终功能清单

### 图像展示
- ✅ Training: Media/train/trajectories（采样，slider）
- ✅ Validation: Media/val/stepN/trajectories（全部，slider）
- ✅ 优化排版：边框、彩色标签
- ✅ Caption：完整指标

### 对话展示
- ✅ 图像上方：完整文本
- ✅ conversation_details表格：累积，每turn单独列
- ✅ 内容完整不截断

### 指标展示
- ✅ Caption：每个样本的指标
- ✅ 汇总统计：mean/max/min（按step）
- ✅ 不记录单个sample的指标图表

### 数据完整性
- ✅ GT：真正的原图（extra_info['original_image']）
- ✅ 有参考指标：PSNR/SSIM/LPIPS（基于GT）
- ✅ 无参考指标：NIQE/BRISQUE等
- ✅ 图像尺寸对齐：fetch_image处理

## 🚀 使用体验

**简洁高效**:
- 只有必要的图表
- 汇总指标追踪进展
- Slider浏览单个样本
- Table查看详细对话

**不再有**:
- ❌ 每个sample单独图表（太多）
- ❌ 大量image_pad打印（干扰日志）
- ❌ GT和退化图看起来差不多（已修复）

所有优化完成！运行训练应该看到简洁清晰的wandb界面！🎉

