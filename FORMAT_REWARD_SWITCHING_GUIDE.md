# 格式奖励模式切换指南 (Format Reward Switching Guide)

本指南说明如何在训练的不同阶段切换格式奖励模式，以适应模型的学习进度。

## 📋 三种格式奖励模式对比

| 模式 | 环境变量 | 奖励范围 | 适用阶段 | 优点 | 缺点 |
|------|---------|---------|---------|------|------|
| **阶梯式** (Progressive) | `USE_PROGRESSIVE_FORMAT=True` | 0.0 → 1.0 (6级) | 训练初期 | 温和引导，不会崩溃 | 收敛慢，格式要求松 |
| **增强检查** (Enhanced) | `USE_ENHANCED_FORMAT=True` | -1.0 或 1.0 (二元) | 训练稳定后 | 快速收敛，格式严格 | 初期过严，负反馈多 |
| **单轮检查** (Single Turn) | `USE_SINGLE_TURN_FORMAT=True` | -1.0 或 1.0 (二元) | 特定场景 | 简化单轮对话检查 | 仅适用于max_turns=1 |

---

## 🎯 阶梯式格式奖励 (Progressive) - 详解

### 适用场景
- 模型刚完成 SFT，但**格式遵循能力弱**
- 经常**不输出工具调用**（`<tool_call>` 缺失）
- 输出**不完整或格式混乱**

### 奖励等级（6级）

```
Level 0 (0.0)  ❌ 完全无格式或格式严重错误
Level 1 (0.2)  ⚠️  至少有 <think> 块（内容≥10字符）
Level 2 (0.4)  📝 有 <think> + <tool_call> 或 <answer>
Level 3 (0.6)  📋 有 <think> + 正确的 JSON 格式（可解析）
Level 4 (0.8)  🔧 有 <think> + 正确 JSON + 工具名称在允许列表中
Level 5 (1.0)  ✅ 完全符合所有格式规范
```

### 工作原理
- **不会直接惩罚**（最低0.0，不会给-1.0）
- **逐级奖励**：每达到一个里程碑就给予正向奖励
- **容错性高**：即使格式不完美，也能得到部分奖励

### 示例输出评分

#### 示例 1: 只有 `<think>` 块
```xml
<think>
我看到图像很暗，需要增强亮度。
</think>
```
**评分**: 0.2 (Level 1) - 至少有思考过程

---

#### 示例 2: 有 `<think>` + `<tool_call>` (但 JSON 错误)
```xml
<think>
我看到图像很暗，需要增强亮度。
</think>
<tool_call>
{name: "retinexformer_enhance"}  // ❌ 缺少引号，JSON 错误
</tool_call>
```
**评分**: 0.4 (Level 2) - 有工具调用意图，但格式错误

---

#### 示例 3: JSON 正确，但工具名称不存在
```xml
<think>
我看到图像很暗，需要增强亮度。
</think>
<tool_call>
[
    {"name": "brightness_enhancer", "arguments": {}}  // ❌ 工具名称不存在
]
</tool_call>
```
**评分**: 0.6 (Level 3) - JSON 格式正确，但工具名称错误

---

#### 示例 4: JSON 正确，工具名称合法，但缺少必要字段
```xml
<think>
我看到图像很暗，需要增强亮度。
</think>
<tool_call>
[
    {"name": "retinexformer_enhance", "arguments": {}}  // ❌ 缺少 degradation 字段
]
</tool_call>
```
**评分**: 0.8 (Level 4) - 工具名称正确，但格式不完整

---

#### 示例 5: 完全正确
```xml
<think>
## 1. Perception Analysis
Initial Observation: 图像明显偏暗...
Most Severe: darken

## 2. Planning & Action
Action Choice: 修复 darken 问题
Tool Rationale: 使用 retinexformer_enhance
</think>
<tool_call>
[
    {"name": "retinexformer_enhance", "degradation": "darken", "arguments": {}}
]
</tool_call>
```
**评分**: 1.0 (Level 5) - 完美格式 ✅

---

## ⚡ 增强检查模式 (Enhanced) - 详解

### 适用场景
- 模型**已经能稳定输出基本格式**
- 需要**强化格式规范**
- 追求**快速收敛**

### 奖励机制
- **1.0**: 完全符合所有规范 ✅
- **-1.0**: 任何格式违规（强惩罚）❌

### 严格检查项
1. ✅ 必须有 `<think>` 块（内容≥10字符）
2. ✅ 必须有 `<tool_call>` 或 `<answer>`（二选一）
3. ✅ `<answer>` 必须在最后一轮
4. ✅ 非 clean 样本：至少1个工具调用
5. ✅ JSON 格式必须正确
6. ✅ 工具名称必须在允许列表中
7. ✅ 单工具迭代模式：每轮恰好1个工具
8. ✅ 总工具数 ≤ 退化数量 + 1（可选）

---

## 🔄 推荐切换策略

### 阶段 1: 训练初期（前1-2个 epoch）
```bash
export USE_PROGRESSIVE_FORMAT=True   # ✅ 启用阶梯式
export USE_ENHANCED_FORMAT=False     # ❌ 关闭增强检查
export USE_SINGLE_TURN_FORMAT=False  # ❌ 关闭单轮检查
```

**目标**: 让模型学会基本格式结构
- 输出 `<think>` 块
- 输出 `<tool_call>` 或 `<answer>` 块
- 基本的 JSON 语法

**预期效果**:
- 格式奖励分数从 0.2 → 0.4 → 0.6 → 0.8 逐步提升
- 模型不会因为格式问题获得大量负奖励

---

### 阶段 2: 训练稳定后（后续 epoch）
```bash
export USE_PROGRESSIVE_FORMAT=False  # ❌ 关闭阶梯式
export USE_ENHANCED_FORMAT=True      # ✅ 启用增强检查
export USE_SINGLE_TURN_FORMAT=False  # ❌ 关闭单轮检查
```

**目标**: 强化格式规范，消除所有格式违规
- 严格遵守所有格式约束
- 工具调用数量符合限制
- JSON 格式完全正确

**预期效果**:
- 格式奖励分数快速收敛到 1.0
- 少量违规样本获得 -1.0 惩罚，快速纠正

---

## 🛠️ 快速切换脚本

### 方式 1: 直接修改 `IRv2.sh`

编辑 `/app/xiaominl/DeepEyes_v2/examples/agent/IRv2.sh`：

```bash
# 训练初期（阶梯式）
export USE_PROGRESSIVE_FORMAT=True
export USE_ENHANCED_FORMAT=False

# 训练稳定后（增强检查）
# export USE_PROGRESSIVE_FORMAT=False
# export USE_ENHANCED_FORMAT=True
```

### 方式 2: 运行时覆盖环境变量

```bash
# 训练初期
USE_PROGRESSIVE_FORMAT=True USE_ENHANCED_FORMAT=False bash examples/agent/IRv2.sh

# 训练稳定后
USE_PROGRESSIVE_FORMAT=False USE_ENHANCED_FORMAT=True bash examples/agent/IRv2.sh
```

---

## 📊 监控指标（WandB）

### 关键指标
1. **`reward/format_score`**: 格式奖励分数
   - **阶梯式**: 观察分数逐步从 0.2 → 1.0 提升
   - **增强检查**: 观察违规率（-1.0 的比例）下降

2. **`reward/format_violation_rate`**: 格式违规率
   - **目标**: 从 80% → 50% → 20% → 5% 逐步下降

3. **`rollout/output_analysis/has_tool_call`**: 工具调用输出率
   - **训练初期**: 可能只有 20-30%
   - **训练后期**: 应该 >90%

---

## ⚠️ 常见问题

### Q1: 什么时候切换到增强检查模式？
**A**: 观察 WandB 指标：
- `reward/format_score` 平均值 **≥ 0.8**
- `rollout/output_analysis/has_tool_call` **≥ 80%**
- 格式违规率 **< 30%**

### Q2: 切换后奖励分数突然下降怎么办？
**A**: 这是正常现象！
- **增强模式**的 -1.0 惩罚会导致平均分暂时下降
- 通常训练 **100-200 步**后会快速恢复
- 如果持续下降 >500 步，可能需要回退到阶梯式模式

### Q3: 可以同时启用多个模式吗？
**A**: 不建议！
- 系统会按优先级选择：`USE_PROGRESSIVE_FORMAT` > `USE_ENHANCED_FORMAT` > `USE_SINGLE_TURN_FORMAT`
- 建议只启用一个模式，避免混淆

### Q4: 阶梯式模式是否适合长期训练？
**A**: 不建议！
- 阶梯式模式对格式要求**太松**，可能导致模型学会"钻空子"
- 建议训练 **1-2 个 epoch** 后切换到增强检查模式

---

## 📝 日志示例

### 阶梯式模式日志
```
[FORMAT REWARD] 使用阶梯式格式奖励 (progressive), score=0.20
  [Level 1] 已有 <think> 块 (内容长度: 25 字符)
  [Level 2] 未通过：缺少 <tool_call> 或 <answer> 块

[FORMAT REWARD] 使用阶梯式格式奖励 (progressive), score=0.60
  [Level 1] 已有 <think> 块
  [Level 2] 已有 <tool_call> 或 <answer>
  [Level 3] JSON 格式正确
  [Level 4] 未通过：工具名称 'brightness_tool' 不在允许列表中

[FORMAT REWARD] 使用阶梯式格式奖励 (progressive), score=1.00
  [Level 5] 完全符合所有格式规范 ✅
```

### 增强检查模式日志
```
[ENHANCED FORMAT] ✅ 格式检查通过 (score=1.0)
  - 第1轮：1个工具调用 [retinexformer_enhance]
  - 第2轮：1个工具调用 [restormer_deraining]
  - 第3轮：提供 <answer> 块
  - 总工具数：2（符合退化数量：2）

[ENHANCED FORMAT] 单工具迭代模式下，第1轮必须恰好1个工具，但检测到3个工具（严格限制）
  → score=-1.0 ❌
```

---

## 🎓 训练建议

### 最佳实践
1. **从宽松到严格**: 阶梯式 → 增强检查
2. **监控指标**: 密切关注 WandB 的格式相关指标
3. **及时切换**: 不要在阶梯式模式停留太久（≤2 epoch）
4. **保存检查点**: 切换模式前保存 checkpoint，方便回退

### 典型训练流程
```
Epoch 1:
  - USE_PROGRESSIVE_FORMAT=True
  - FORMAT_REWARD_WEIGHT=0.3
  - 目标：学会基本格式

Epoch 2:
  - USE_PROGRESSIVE_FORMAT=True（继续）
  - FORMAT_REWARD_WEIGHT=0.4（提高权重）
  - 目标：提高格式稳定性

Epoch 3-N:
  - USE_ENHANCED_FORMAT=True（切换！）
  - FORMAT_REWARD_WEIGHT=0.3（恢复正常）
  - 目标：完全规范化
```

---

## 📞 支持

如有问题，请查看：
- 代码实现: `verl/utils/reward_score/image_restoration.py`
  - `check_multiturn_format_progressive()` (阶梯式)
  - `check_multiturn_format_v3_enhanced()` (增强检查)
- 配置文件: `examples/agent/IRv2.sh`
- 日志输出: 查找 `[FORMAT REWARD]` 或 `[ENHANCED FORMAT]` 标记

---

**最后更新**: 2025-11-01

