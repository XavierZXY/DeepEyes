# 🎯 图像质量奖励配置 - 快速上手

## 一分钟配置

### 📝 编辑训练脚本

打开 `examples/agent/IR.sh`，找到这两行：

```bash
export IMAGE_QUALITY_USE_NO_REFERENCE=True  # True=无参考, False=有参考
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0    # 0=连续, 10=每10%一档
```

### 🎨 常用配置

| 场景 | USE_NO_REFERENCE | DISCRETIZE_LEVELS | 说明 |
|------|------------------|-------------------|------|
| **标准训练** | `True` | `0` | ✅ 推荐！无参考+连续 |
| **训练早期** | `True` | `10` | 稳定性优先 |
| **有GT数据** | `False` | `0` | 更准确评估 |
| **精细调优** | `False` | `20` | 最精细区分 |

### ⚡ 快速测试

```bash
# 测试配置是否生效
python test_reward_config.py

# 测试不同配置
IMAGE_QUALITY_USE_NO_REFERENCE=False \
IMAGE_QUALITY_DISCRETIZE_LEVELS=10 \
python test_reward_config.py
```

### 📊 两种模式对比

**无参考模式** (True) - 推荐
- ✅ 不需要GT原图
- ✅ 所有样本都能计算
- ✅ 指标: NIQE, BRISQUE, CPBD, CLIP-IQA, Hyper-IQA

**有参考模式** (False)
- ⚠️ 需要数据集中有 `original_image`
- ✅ 评估更准确
- ✅ 指标: SSIM (35%), LPIPS (50%), PSNR (15%)

### 🔍 查看生效

训练日志会显示：
```
[INFO] Image Quality Reward Config: use_no_reference=True, discretize_levels=0
```

---

## 详细文档

📖 完整配置指南: [docs/IMAGE_QUALITY_REWARD_CONFIG.md](docs/IMAGE_QUALITY_REWARD_CONFIG.md)

🎓 图像质量奖励原理: 见之前的详细介绍

---

**默认配置（无需修改）**：
```bash
export IMAGE_QUALITY_USE_NO_REFERENCE=True
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0
```

祝训练顺利！🚀

