# Wandb文档索引

本文档提供DeepEyes_v2项目中所有Wandb相关文档的快速索引。

## 📚 文档列表

### 🎯 核心文档

#### 1. [WANDB_UPLOAD_COMPLETE_GUIDE.md](WANDB_UPLOAD_COMPLETE_GUIDE.md)
**Wandb图像上传完整修复指南**
- 所有修复内容总结
- 完整的数据流说明
- 可视化结构详解
- 验证步骤和故障排查

#### 2. [WANDB_FEATURES_SUMMARY.md](WANDB_FEATURES_SUMMARY.md)
**Wandb功能完整总结**
- 图像轨迹可视化
- 训练采样策略
- 验证全量上传
- 奖励组成部分统计
- 工具调用统计

#### 3. [WANDB_METRICS_GUIDE.md](WANDB_METRICS_GUIDE.md)
**Wandb指标完整说明**
- 核心奖励指标详解
- 图像质量指标说明
- Agent行为指标
- 训练性能指标
- 验证指标

### 🆕 最新更新

#### 4. [WANDB_WRONG_PREDICTIONS_CONFIG.md](WANDB_WRONG_PREDICTIONS_CONFIG.md) ⭐ **NEW**
**错误预测上传配置说明**
- 功能说明
- 配置方式（IR.sh环境变量）
- 错误判定标准
- 在Wandb中查看的方法
- 使用建议和常见问题

#### 5. [WANDB_CONTROL_SUMMARY.md](WANDB_CONTROL_SUMMARY.md) ⭐ **NEW**
**Wandb上传控制总结**
- 环境变量配置说明
- 启用/禁用方法
- 日志示例
- 使用场景推荐
- 技术细节

#### 6. [UPDATE_WANDB_CONTROL.md](UPDATE_WANDB_CONTROL.md) ⭐ **NEW**
**更新说明：Wandb错误预测上传控制**
- 修改内容总结
- 功能说明
- 测试验证结果
- 使用示例

### 📖 其他相关文档

#### 7. [README_WANDB_FEATURES.md](README_WANDB_FEATURES.md)
**Wandb图像和对话上传功能说明**
- 功能总览
- 在Wandb中的位置
- 优化的图片排版
- 所有指标说明

#### 8. [WANDB_README.md](WANDB_README.md)
**Wandb基础说明**
（如果存在）

### 🧪 测试工具

#### 9. [test_wandb_wrong_predictions_config.py](test_wandb_wrong_predictions_config.py) ⭐ **NEW**
**配置测试脚本**
```bash
python test_wandb_wrong_predictions_config.py
```
- 测试环境变量解析逻辑
- 检查当前配置
- 显示使用示例

---

## 🚀 快速开始

### 步骤1: 配置环境变量

编辑 `examples/agent/IR.sh`:
```bash
# 基础配置
export WANDB_API_KEY=your_api_key_here

# 错误预测上传控制（新增）
export WANDB_LOG_WRONG_PREDICTIONS=True  # 或 False
```

### 步骤2: 运行训练

```bash
bash examples/agent/IR.sh
```

### 步骤3: 查看Wandb

1. 打开 https://wandb.ai
2. 进入你的项目
3. 查看不同标签：
   - **Charts** - 标量指标（reward, loss等）
   - **Media** - 图像轨迹
   - **Tables** - 对话表格和错误预测表格

---

## 📊 Wandb中的数据位置

### 指标（Charts）

| 位置 | 内容 |
|------|------|
| `critic/score/*` | 总奖励分数 |
| `reward/format_*` | 格式奖励统计 |
| `reward/quality_*` | 图像质量奖励 |
| `reward/ssim_*`, `reward/lpips_*`, `reward/psnr_*` | 有参考指标 |
| `agent/tool_call_*` | 工具调用统计 |
| `actor/loss`, `critic/vf_loss` | 训练损失 |

### 图像（Media）

| 位置 | 内容 |
|------|------|
| `train/trajectories` | 训练轨迹图像（采样） |
| `val/trajectories` | 验证轨迹图像（全部） |

### 表格（Tables）

| 位置 | 内容 |
|------|------|
| `train_conversation_table` | 训练对话表格（累积） |
| `val_conversation_table` | 验证对话表格（累积） |
| `val_errors/wrong_predictions` | 错误预测表格（可选） ⭐ |

---

## 🔧 环境变量配置参考

### Wandb基础配置

```bash
# Wandb API密钥
export WANDB_API_KEY=your_api_key

# 项目和实验名称
PROJECT_NAME="IRagent"
EXPERIMENT_NAME="your_experiment_name"
```

### 奖励配置

```bash
# 图像质量配置
export IMAGE_QUALITY_USE_NO_REFERENCE=False  # True=无参考, False=有参考
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0      # 0=连续奖励

# 奖励权重
export FORMAT_REWARD_WEIGHT=0.3               # 格式奖励权重
export QUALITY_REWARD_WEIGHT=0.7              # 图像质量奖励权重

# 退化类型奖励
export ENABLE_DEGRADATION_TYPE_REWARD=False   # 是否启用
export DEGRADATION_TYPE_REWARD_WEIGHT=1.0     # 权重
```

### Wandb上传控制（新增）⭐

```bash
# 错误预测上传控制
export WANDB_LOG_WRONG_PREDICTIONS=True  # True=启用, False=禁用
```

### 训练器配置（YAML）

```yaml
trainer:
  logger: ['console', 'wandb', 'rl_logging_board']
  log_images_to_wandb: true
  num_train_images_to_log: 5           # 训练随机采样数
  num_best_worst_images_to_log: 2      # 最好/最差采样数
  test_freq: 10                        # 验证频率
```

---

## 💡 使用建议

### 训练早期（前10-20个epoch）

✅ **推荐配置**:
```bash
export WANDB_LOG_WRONG_PREDICTIONS=True  # 启用错误预测上传
export IMAGE_QUALITY_USE_NO_REFERENCE=True  # 使用无参考指标
```

**原因**:
- 快速发现模型问题
- 了解错误模式
- 无参考指标适用于所有样本

### 训练中期（稳定训练）

✅ **推荐配置**:
```bash
export WANDB_LOG_WRONG_PREDICTIONS=True  # 继续监控错误
export IMAGE_QUALITY_USE_NO_REFERENCE=False  # 切换到有参考指标
```

**原因**:
- 继续追踪错误模式
- 有参考指标更准确

### 训练后期（模型收敛）

✅ **推荐配置**:
```bash
export WANDB_LOG_WRONG_PREDICTIONS=False  # 禁用错误预测上传
export IMAGE_QUALITY_USE_NO_REFERENCE=False  # 使用有参考指标
```

**原因**:
- 错误样本很少，上传价值低
- 节省存储和带宽
- 专注于质量指标

---

## 🔍 调试命令

### 查看日志

```bash
# 查看wandb相关日志
tail -f logs/*.log | grep "WANDB\|wandb"

# 查看错误预测相关日志
tail -f logs/*.log | grep "wrong predictions"

# 查看图像上传相关日志
tail -f logs/*.log | grep "DEBUG WANDB IMAGE"
```

### 测试配置

```bash
# 测试环境变量解析
python test_wandb_wrong_predictions_config.py

# 验证配置文件
grep "WANDB" examples/agent/IR.sh
```

---

## 📈 数据流总结

```
1. DataLoader加载数据
   ↓ origin_multi_modal_data (原图GT)
   ↓ multi_modal_data (退化图)

2. ParallelEnv交互
   ↓ 保存图像历史 [退化图, 工具1处理, 工具2处理, ...]

3. Reward计算
   ↓ 提取指标 {ssim, lpips, psnr, quality_score, ...}

4. Wandb上传
   ↓ 图像轨迹 → train/trajectories, val/trajectories
   ↓ 对话表格 → train_conversation_table, val_conversation_table
   ↓ 错误预测 → val_errors/wrong_predictions (可选)
   ↓ 标量指标 → Charts
```

---

## ❓ 常见问题

### Q: 如何禁用所有wandb上传？

A: 修改训练配置:
```yaml
trainer:
  logger: ['console']  # 移除'wandb'
```

### Q: 如何只禁用错误预测上传？

A: 设置环境变量:
```bash
export WANDB_LOG_WRONG_PREDICTIONS=False
```

### Q: 为什么看不到Media标签？

A: 可能原因:
- `log_images_to_wandb: false`
- 图像历史为空
- wandb初始化失败

### Q: 表格数据过多怎么办？

A: 
- 减少验证频率 `test_freq`
- 禁用错误预测上传
- 减少训练图像上传数量 `num_train_images_to_log`

---

## 📞 获取帮助

### 文档

1. 阅读相关文档（见上方列表）
2. 查看配置说明和示例
3. 运行测试脚本验证配置

### 调试

1. 检查日志输出
2. 验证环境变量设置
3. 确认wandb API密钥有效

### 联系

- 项目维护者：DeepEyes Team
- 更新日期：2025-10-14

---

## 📝 文档更新历史

| 日期 | 更新内容 |
|------|---------|
| 2025-10-14 | 添加错误预测上传控制功能和相关文档 |
| 之前 | 基础wandb集成和文档 |

---

**Happy Tracking! 🎉**

