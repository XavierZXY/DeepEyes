# 图像质量奖励配置指南

## 概述

从现在开始，您可以通过**环境变量**在训练脚本中直接控制图像质量奖励的计算方式，无需修改代码！

---

## 🎛️ 配置参数

### 1. `IMAGE_QUALITY_USE_NO_REFERENCE`

控制使用有参考还是无参考图像质量指标。

**可选值**：
- `True` (默认) - 使用**无参考指标**
- `False` - 使用**有参考指标**

**无参考指标** (use_no_reference=True)：
```python
reward = 0.20 × NIQE_norm       # 自然场景统计
       + 0.20 × BRISQUE_norm    # 空间域失真
       + 0.20 × CPBD_norm       # 模糊检测
       + 0.20 × CLIP-IQA_norm   # 语义质量
       + 0.20 × Hyper-IQA_norm  # 局部失真
```

**有参考指标** (use_no_reference=False)：
```python
reward = 0.35 × SSIM_norm           # 结构相似性
       + 0.50 × (1 - LPIPS_norm)    # 感知相似性
       + 0.15 × PSNR_norm            # 像素精度
```

### 2. `IMAGE_QUALITY_DISCRETIZE_LEVELS`

控制奖励信号的离散化程度。

**可选值**：
- `0` (默认) - 连续奖励，范围 [0.0, 1.0]
- `10` - 每10%一档，值为 {0.0, 0.1, 0.2, ..., 1.0}
- `20` - 每5%一档，值为 {0.0, 0.05, 0.10, ..., 1.0}
- 其他正整数 - 自定义档位数量

**效果**：
- **连续奖励** (0): 精细区分，但可能导致训练波动
- **离散化** (>0): 平滑奖励信号，提高训练稳定性

---

## 📝 使用方法

### 在训练脚本中配置

编辑您的训练脚本 (如 `examples/agent/IR.sh`)，在开头添加：

```bash
# ========== Image Quality Reward Configuration ==========
export IMAGE_QUALITY_USE_NO_REFERENCE=True  # 使用无参考指标
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0    # 连续奖励

# 或者使用有参考指标（需要数据集中有original_image）
# export IMAGE_QUALITY_USE_NO_REFERENCE=False
# export IMAGE_QUALITY_DISCRETIZE_LEVELS=10
# ========================================================
```

### 直接在命令行运行

```bash
# 使用无参考指标 + 连续奖励
IMAGE_QUALITY_USE_NO_REFERENCE=True \
IMAGE_QUALITY_DISCRETIZE_LEVELS=0 \
bash examples/agent/IR.sh

# 使用有参考指标 + 离散化
IMAGE_QUALITY_USE_NO_REFERENCE=False \
IMAGE_QUALITY_DISCRETIZE_LEVELS=10 \
bash examples/agent/IR.sh
```

---

## 🎯 推荐配置

### 场景1: 标准训练（推荐）
```bash
export IMAGE_QUALITY_USE_NO_REFERENCE=True
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0
```

**适用于**：
- ✅ 大部分训练场景
- ✅ 数据集没有ground truth原图
- ✅ 希望所有样本都能计算奖励

**优势**：
- 无需ground truth，适用性强
- 所有样本（包括未执行工具的）都能计算
- 避免batch长度不一致问题

---

### 场景2: 训练早期（稳定性优先）
```bash
export IMAGE_QUALITY_USE_NO_REFERENCE=True
export IMAGE_QUALITY_DISCRETIZE_LEVELS=10
```

**适用于**：
- ✅ 训练初期，策略不稳定
- ✅ 奖励信号波动较大
- ✅ 希望快速收敛

**优势**：
- 离散化减少奖励波动
- 提高训练稳定性
- 后期可切换回连续奖励

---

### 场景3: 有Ground Truth数据集
```bash
export IMAGE_QUALITY_USE_NO_REFERENCE=False
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0
```

**适用于**：
- ✅ 数据集包含original_image字段
- ✅ 希望更准确的质量评估
- ✅ 样本都会执行工具

**注意**：
- ⚠️ 需要数据集中有`original_image`
- ⚠️ 未执行工具的样本会返回0.0
- ⚠️ 可能导致batch长度不一致（部分样本无效）

---

### 场景4: 精细调优
```bash
export IMAGE_QUALITY_USE_NO_REFERENCE=False
export IMAGE_QUALITY_DISCRETIZE_LEVELS=20
```

**适用于**：
- ✅ 训练后期微调
- ✅ 有高质量GT数据
- ✅ 需要精确的质量区分

**优势**：
- 有参考指标更准确
- 20档位提供精细区分
- 适合对比不同策略效果

---

## 🔍 两种模式对比

| 特性 | 无参考模式 | 有参考模式 |
|------|-----------|-----------|
| **需要GT** | ❌ 不需要 | ✅ 需要original_image |
| **适用样本** | 所有样本 | 仅执行工具的样本 |
| **评估指标** | NIQE/BRISQUE/CPBD/CLIP-IQA/Hyper-IQA | SSIM/LPIPS/PSNR |
| **准确性** | 较好 (无参考标准) | 更准确 (与GT对比) |
| **训练稳定性** | ✅ 高 (batch一致) | ⚠️ 中 (部分样本无效) |
| **推荐场景** | 标准训练 | 有GT数据集 |

---

## 📊 监控指标

### 训练日志输出

成功配置后，您会在训练日志中看到：

```
[INFO] Image Quality Reward Config: use_no_reference=True, discretize_levels=0
```

或

```
[INFO] Image Quality Reward Config: use_no_reference=False, discretize_levels=10
```

### Wandb指标

无论使用哪种模式训练，Wandb都会展示：

**训练指标**（基于训练时使用的模式）：
```
reward/quality_score_mean     # 平均质量分数
reward/quality_score_max      # 最高质量
reward/quality_score_min      # 最低质量
reward/quality_score_std      # 标准差
```

**验证展示**（按需计算有参考指标）：
```
val/ssim_mean                 # SSIM均值
val/lpips_mean                # LPIPS均值  
val/psnr_mean                 # PSNR均值
```

**图像Caption**：
```
Sample 42 | Quality: 0.856 | SSIM: 0.678 | LPIPS: 0.156 | PSNR: 24.5
```

---

## 🛠️ 调试和验证

### 验证配置是否生效

```bash
# 运行训练，检查日志
bash examples/agent/IR.sh 2>&1 | grep "Image Quality Reward Config"

# 应该看到类似输出：
# [INFO] Image Quality Reward Config: use_no_reference=True, discretize_levels=0
```

### 查看详细奖励计算

训练过程中会输出详细的奖励计算日志：

**无参考模式**：
```
[DEBUG no_ref_image_quality] niqe=4.23(norm=0.79), brisque=18.46(norm=0.82), cpbd=0.62(norm=0.62)
[DEBUG no_ref_image_quality] clip_iqa=0.71(norm=0.71), hyper_iqa=0.68(norm=0.68)
[DEBUG no_ref_image_quality] reward=0.7248
```

**有参考模式**：
```
[DEBUG image_quality] ssim=0.86(norm=0.93), lpips=0.12(norm=0.12), psnr=28.45(norm=0.78)
[DEBUG image_quality] reward=0.8392
```

---

## ⚙️ 高级配置

### 动态切换模式

您可以在训练过程中切换模式（需要重启训练）：

```bash
# 前期使用无参考+离散化（稳定）
export IMAGE_QUALITY_USE_NO_REFERENCE=True
export IMAGE_QUALITY_DISCRETIZE_LEVELS=10
# ... 训练10 epochs

# 后期切换到无参考+连续（精细）
export IMAGE_QUALITY_USE_NO_REFERENCE=True
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0
# ... 继续训练
```

### 自定义离散化档位

```bash
# 5档位 (0.0, 0.25, 0.5, 0.75, 1.0)
export IMAGE_QUALITY_DISCRETIZE_LEVELS=5

# 50档位 (0.00, 0.02, 0.04, ..., 1.00)
export IMAGE_QUALITY_DISCRETIZE_LEVELS=50
```

---

## ❓ 常见问题

### Q1: 使用有参考模式时报错 "No original image found"？

**原因**：数据集中缺少`original_image`字段。

**解决方案**：
1. 确保parquet文件包含`original_image`列
2. 或者切换到无参考模式：`export IMAGE_QUALITY_USE_NO_REFERENCE=True`

---

### Q2: 离散化会影响训练效果吗？

**答案**：取决于训练阶段。

- **训练早期**：离散化有助于稳定策略，推荐使用
- **训练后期**：连续奖励提供更精细信号，建议切换回连续

---

### Q3: Wandb展示的SSIM/LPIPS/PSNR来自哪里？

**答案**：无论训练用哪种模式，Wandb都会**按需计算**有参考指标用于可视化。

- 训练奖励：使用您配置的模式（无参考或有参考）
- Wandb展示：自动计算有参考指标（SSIM/LPIPS/PSNR）
- 两者独立，互不影响

---

### Q4: 如何选择最佳配置？

**快速决策树**：

```
有GT原图吗？
├─ 是 → 用有参考 (IMAGE_QUALITY_USE_NO_REFERENCE=False)
│      训练稳定吗？
│      ├─ 是 → 连续奖励 (DISCRETIZE_LEVELS=0)
│      └─ 否 → 离散化 (DISCRETIZE_LEVELS=10)
│
└─ 否 → 用无参考 (IMAGE_QUALITY_USE_NO_REFERENCE=True)
       训练稳定吗？
       ├─ 是 → 连续奖励 (DISCRETIZE_LEVELS=0)
       └─ 否 → 离散化 (DISCRETIZE_LEVELS=10)
```

---

## 📚 相关文档

- [图像质量奖励详细说明](./IMAGE_QUALITY_METRICS_DETAIL.md)
- [Wandb奖励指标文档](./WANDB_REWARD_METRICS.md)
- [图像轨迹可视化](./TRAJECTORY_VISUALIZATION_LAYOUT.md)

---

## 🎉 总结

通过环境变量配置，您现在可以：

✅ **灵活切换** 有参考/无参考模式  
✅ **动态调整** 离散化等级  
✅ **无需修改代码** 直接在脚本中配置  
✅ **实时查看** 配置是否生效  

**默认推荐配置**（适用于大部分场景）：
```bash
export IMAGE_QUALITY_USE_NO_REFERENCE=True
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0
```

祝训练顺利！🚀

