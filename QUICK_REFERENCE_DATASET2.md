# 数据集2快速参考卡片 🚀

## 一键启动
```bash
# 测试reward
python3 test_visual_toolbox_v2_reward.py

# 启动训练
bash examples/agent/visual_toolbox_v2.sh
```

---

## 核心差异 3秒理解

| 项目 | 数据集1 | 数据集2 |
|------|---------|---------|
| **任务** | 图像复原 | 缺陷检测 |
| **答案** | 图像质量(0-1) | Yes/No(0/1) |
| **工具** | 链式处理 | 独立处理 |
| **Reward** | format(1/-1) + quality(0-1) | format(-1/1) + acc(0/1) |
| **总分** | -0.3~2.0 | -1~2 |

---

## Reward公式

### 数据集1
```
total = 0.3×format + 0.7×quality
format: 1.0 或 -1.0
quality: 0.0 ~ 1.0 (SSIM/LPIPS/PSNR)
```

### 数据集2 ⭐
```
total = format_reward + acc_reward
format_reward: -1 或 1
acc_reward: 0 或 1
```

---

## 工具行为

### 数据集1（链式）
```
退化图 → SwinIR → Restormer → 最终图
        ↓         ↓            ↓
       处理1     基于处理1    基于处理2
```

### 数据集2（独立）⭐
```
原图 → zoom_in → 裁剪区域
       ↑ 都从原图处理
原图 → rotate → 旋转结果
```

---

## Wandb指标速查

### 必看指标（数据集2）
- `reward/format_correct_ratio` - 格式正确率（>0.95好）
- `reward/accuracy_ratio` - 准确率（>0.8好）✨
- `critic/score/max` - 最大分（应该=2.0）
- `agent/tool_call_mean` - 工具使用率

### Wandb位置
- **图像**: Media → train/trajectories
- **表格**: Charts → train/conversation_details
- **指标**: Charts → reward/*

---

## 修改文件（2个）

1. `verl/utils/reward_score/__init__.py`
   - 第122行：添加`vstar_visual_toolbox_v2`

2. `verl/workers/reward_manager/naive.py`
   - 第150行：添加visual_toolbox_v2统计
   - 第160行：提取format_reward和acc_reward

**其他文件都已支持，无需修改！**

---

## 新建文件（2个）

1. `examples/agent/visual_toolbox_v2.sh` - 训练脚本
2. `test_visual_toolbox_v2_reward.py` - 测试脚本

---

## 验证检查点

```bash
# ✓ Reward测试通过
python3 test_visual_toolbox_v2_reward.py
# 预期: 6个测试全部PASS

# ✓ 语法正确
python3 -m py_compile verl/utils/reward_score/__init__.py
python3 -m py_compile verl/workers/reward_manager/naive.py
# 预期: 无错误

# ✓ 数据集字段正确
python3 -c "import pandas as pd; df=pd.read_parquet('data/train/train_dataset.parquet'); print(df.iloc[0]['env_name'])"
# 预期: visual_toolbox_v2
```

---

## 预期训练曲线

```
Step 0:     format~0.5, acc~0.5, score~0.5
Step 100:   format~0.9, acc~0.6, score~1.2
Step 500:   format~0.95, acc~0.75, score~1.5
Step 1000+: format~0.98, acc~0.85, score~1.8
```

---

## 🎉 就绪！

所有修改已完成并测试通过。运行`bash examples/agent/visual_toolbox_v2.sh`即可开始训练！

**详细文档**:
- `MIGRATION_DATASET2_GUIDE.md` - 完整迁移指南
- `DATASET_COMPARISON.md` - 详细对比
- `DATASET2_MIGRATION_COMPLETE.md` - 完成报告

