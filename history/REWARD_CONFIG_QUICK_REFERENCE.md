# 奖励配置快速参考卡

## 🎯 奖励结构

```
总奖励 = 格式奖励 + 图像质量奖励 + (可选)退化类型奖励
```

---

## ⚙️ 环境变量配置

### 在 `examples/agent/IR.sh` 中配置

```bash
# 图像质量配置
export IMAGE_QUALITY_USE_NO_REFERENCE=True   # True=无参考, False=有参考
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0     # 0=连续, 10/20=离散化

# 奖励权重配置
export FORMAT_REWARD_WEIGHT=0.3              # 格式奖励权重
export QUALITY_REWARD_WEIGHT=0.7             # 图像质量奖励权重
export ENABLE_DEGRADATION_TYPE_REWARD=False  # 是否启用退化类型奖励
export DEGRADATION_TYPE_REWARD_WEIGHT=1.0    # 退化类型奖励权重
```

---

## 📊 奖励公式

### 默认配置
```python
total = 0.3 × format_score + 0.7 × quality_score
范围: [-0.3, 1.0]
```

### 启用退化类型奖励
```python
total = 0.3 × format_score + 0.7 × quality_score + 1.0 × degradation_type_score
范围: [-0.3, 2.0]
```

---

## 🔢 分数范围

| 组件 | 范围 | 说明 |
|-----|------|------|
| `format_score` | 1.0 或 -1.0 | 格式完美或违规 |
| `quality_score` | 0.0 ~ 1.0 | 图像质量（连续） |
| `degradation_type_score` | 0.0 ~ 1.0 | 退化类型匹配度 |

---

## 🎨 推荐配置

### 默认训练
```bash
FORMAT_REWARD_WEIGHT=0.3
QUALITY_REWARD_WEIGHT=0.7
ENABLE_DEGRADATION_TYPE_REWARD=False
```

### 强化类型识别
```bash
FORMAT_REWARD_WEIGHT=0.3
QUALITY_REWARD_WEIGHT=0.7
ENABLE_DEGRADATION_TYPE_REWARD=True  # 启用
DEGRADATION_TYPE_REWARD_WEIGHT=1.0
```

---

## 📍 WandB查看位置

```
WandB Run页面 → Overview → Config → reward_config
```

包含所有6个配置参数。

---

## ✅ 快速测试

```bash
python test_wandb_config.py
```

---

## 📚 详细文档

- `REWARD_STRUCTURE_EXPLAINED.md` - **完整奖励结构说明**
- `COMPLETE_REWARD_CONFIG_GUIDE.md` - 配置指南
- `IMAGE_QUALITY_AND_FORMAT_REWARD_REPORT.md` - 图像质量详解

---

**快速参考完成** 🚀

