# WandB 指标完整说明文档

本文档详细解释上传到 WandB 的所有训练和验证指标。

---

## 📊 指标分类索引

### 🎯 核心奖励指标
- [critic/score](#criticScore) - 总奖励分数
- [reward/format_score_mean](#rewardFormatScore) - 格式奖励平均值
- [reward/quality_score_mean](#rewardQualityScore) - 图像质量奖励平均值
- [reward/degradation_type_score_mean](#rewardDegradationTypeScore) - 退化类型识别准确度

### 🖼️ 图像质量指标
- [reward/ssim_mean](#rewardSSIM) - 结构相似度（有参考）
- [reward/lpips_mean](#rewardLPIPS) - 感知相似度（有参考）
- [reward/psnr_mean](#rewardPSNR) - 峰值信噪比（有参考）

### 🤖 Agent 行为指标
- [agent/tool_call_mean](#agentToolCall) - 工具调用次数
- [response_length/mean](#responseLength) - 响应长度

### ⚙️ 训练性能指标
- [actor/loss](#actorLoss) - Actor 损失
- [critic/vf_explained_var](#criticVfExplainedVar) - Value Function 解释方差
- [perf/throughput](#perfThroughput) - 训练吞吐量

---

## 🎯 核心奖励指标

### <a name="criticScore"></a>`critic/score/mean` | `critic/score/max` | `critic/score/min`

**含义**: 总奖励分数（所有奖励组成部分的加权和）

**计算公式**:
```python
total_reward = FORMAT_WEIGHT × format_score 
             + QUALITY_WEIGHT × quality_score 
             + [DEGRADATION_TYPE_WEIGHT × degradation_type_score]  # 可选
```

**默认权重** (在 `IR.sh` 中配置):
- `FORMAT_REWARD_WEIGHT=0.3` (格式奖励权重)
- `QUALITY_REWARD_WEIGHT=0.7` (图像质量奖励权重)
- `DEGRADATION_TYPE_REWARD_WEIGHT=1.0` (退化类型奖励权重，默认关闭)

**取值范围**:
- 理想值: `0.6 - 1.0` (格式正确 + 高质量修复)
- 格式违规: `-0.3` (FORMAT_WEIGHT × -1.0)
- 工具未执行: `0.3` (仅有格式奖励)

**监控建议**:
- ✅ `score/max` 持续上升: 模型在学习更好的修复策略
- ⚠️ `score/max` 停滞在 0.3: 模型不敢使用工具（过于保守）
- ❌ `score/mean` 为负: 大量格式违规

**数据来源**: `verl/trainer/ppo/metric_utils.py` → `compute_data_metrics()`

---

### <a name="rewardFormatScore"></a>`reward/format_score_mean` | `reward/format_correct_ratio` | `reward/format_violation_ratio`

**含义**: 格式奖励统计，衡量模型输出是否符合要求的格式规范

**格式要求** (必须全部满足):
1. 每轮必须有 `<think>` 块，内容 ≥10 字符
2. `<tool_call>` 和 `<answer>` 不能同时出现
3. JSON 格式必须有效
4. 工具名称必须在允许列表中
5. `<answer>` 必须包含 `restoration_log` 字段（且仅此字段）

**取值**:
- `format_score_mean`: 平均格式分数
  - `1.0`: 完美格式 ✅
  - `-1.0`: 格式违规 ❌
- `format_correct_ratio`: 格式正确的样本比例 (0.0 - 1.0)
- `format_violation_ratio`: 格式违规的样本比例 (0.0 - 1.0)

**示例**:
```python
# ✅ 正确格式
<think>图像有运动模糊，需要使用去模糊工具</think>
<tool_call>[{"name": "restormer_motion_deblurring", "arguments": {}}]</tool_call>

# ❌ 格式违规：同时有 tool_call 和 answer
<think>...</think>
<tool_call>[...]</tool_call>
<answer>{...}</answer>

# ❌ 格式违规：think 内容太短
<think>ok</think>
<tool_call>[...]</tool_call>
```

**监控建议**:
- ✅ `format_correct_ratio > 0.95`: 格式学习良好
- ⚠️ `format_correct_ratio < 0.8`: 需要检查 system prompt 或增加格式奖励权重
- 🔧 `format_violation_ratio > 0.2`: 考虑使用 strict format checking

**数据来源**: `verl/utils/reward_score/image_restoration.py` → `check_multiturn_format_v2()`

**相关配置**:
```bash
# IR.sh 第52行
export FORMAT_REWARD_WEIGHT=0.3
```

---

### <a name="rewardQualityScore"></a>`reward/quality_score_mean` | `reward/quality_score_max` | `reward/quality_score_min` | `reward/quality_score_std`

**含义**: 图像质量奖励统计，衡量模型修复图像的质量

**计算模式** (通过环境变量配置):

#### 1️⃣ **无参考模式** (默认，`IMAGE_QUALITY_USE_NO_REFERENCE=True`)
```python
quality_score = 0.20 × NIQE_norm 
              + 0.20 × BRISQUE_norm 
              + 0.20 × CPBD_norm
              + 0.20 × CLIP_IQA_norm
              + 0.20 × Hyper_IQA_norm
```

**优点**: 不需要 Ground Truth，所有样本都能计算  
**适用**: 训练阶段（数据集可能没有完美的 GT）

#### 2️⃣ **有参考模式** (`IMAGE_QUALITY_USE_NO_REFERENCE=False`)
```python
quality_score = 0.35 × SSIM_norm 
              + 0.50 × (1 - LPIPS_norm) 
              + 0.15 × PSNR_norm
```

**优点**: 更准确，基于与 GT 的对比  
**限制**: 只对使用工具修复的样本有效（未使用工具的样本分数为 0）

**取值范围**: `0.0 - 1.0` (越高越好)
- `> 0.8`: 优秀的修复质量
- `0.5 - 0.8`: 中等修复质量
- `< 0.5`: 修复质量较差
- `= 0.0`: 工具未执行或计算失败

**离散化选项** (可选):
```bash
# IR.sh 第42行
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0  # 0=连续, 10=每10%, 20=每5%
```

**监控建议**:
- ✅ `quality_score_mean` 持续上升: 修复质量在改进
- ⚠️ `quality_score_std` 过大: 样本间质量差异大，可能需要更多训练
- 🔧 `quality_score_max` 很高但 `mean` 很低: 模型不稳定，需要调整学习率或奖励权重

**数据来源**: `verl/utils/reward_score/image_restoration.py` → `compute_image_quality_reward_v2()`

**相关配置**:
```bash
# IR.sh 第41-42行
export IMAGE_QUALITY_USE_NO_REFERENCE=False
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0

# IR.sh 第53行
export QUALITY_REWARD_WEIGHT=0.7
```

---

### <a name="rewardDegradationTypeScore"></a>`reward/degradation_type_score_mean` | `reward/degradation_type_score_mean_all` | `reward/degradation_type_valid_samples`

**含义**: 退化类型识别准确度（不考虑顺序，只看集合匹配）

#### 🔑 两个指标的关键区别

**`reward/degradation_type_score_mean`** (过滤版本):
- 只统计**分数 > 0.0** 的样本
- 排除了 clean 样本（分数=0.0）
- 排除了未启用退化类型奖励的样本（分数=0.0）
- **反映的是**: 在实际计算了退化类型奖励的样本中，准确度如何

**`reward/degradation_type_score_mean_all`** (完整版本):
- 统计**所有样本**，包括分数为 0.0 的
- 包含了 clean 样本、格式错误样本等
- **反映的是**: 在整个 batch 中，退化类型识别的总体情况

#### ⚠️ 为什么 `degradation_type_score_mean` 一直是 1.0？

这是**正常现象**，原因如下：

**情况1: 退化类型奖励未启用**（最常见）
```bash
# IR.sh 第54行
export ENABLE_DEGRADATION_TYPE_REWARD=False  # ← 默认关闭
```
- 当关闭时，所有样本的 `degradation_type_score = 0.0`
- `reward/degradation_type_score_mean` **不会显示**（因为没有 > 0 的样本）
- `reward/degradation_type_score_mean_all = 0.0`

**情况2: 退化类型奖励已启用，但模型表现完美**
```python
# 只有当模型预测完全匹配时，分数才 > 0
# 例如：
GT: ["noise", "motion blur"]
预测: ["noise", "motion blur"]  → score = 1.0 ✅

GT: ["noise", "motion blur"]  
预测: ["noise"]  → score = 0.0 ❌ (因为 predicted_set 不是 expected_set 的完全匹配)
```

**关键代码逻辑**:
```python
# verl/utils/reward_score/image_restoration.py 第1166-1177行
if predicted_set == expected_set:
    score = 1.0  # 完全匹配
elif len(predicted_set) > 0:
    score = len(predicted_set) / len(expected_set)  # 部分匹配
else:
    score = 0.0  # 无匹配
```

**实际效果**:
- 如果模型预测不完全匹配，分数会是部分分数（如 0.33, 0.67）或 0
- 但由于 `degradation_type_score_mean` 只统计 > 0 的样本
- 如果恰好所有非零样本都是完全匹配（1.0），均值就是 1.0

#### 📊 示例数据

假设一个 batch 有 100 个样本：

| 样本类型 | 数量 | degradation_type_score |
|---------|-----|----------------------|
| Clean 样本 | 30 | 0.0 (跳过) |
| 格式错误 | 10 | 0.0 (跳过) |
| 完全匹配 | 40 | 1.0 ✅ |
| 部分匹配 | 15 | 0.67, 0.33 等 |
| 完全错误 | 5 | 0.0 |

**计算结果**:
```python
# degradation_type_score_mean (只统计 > 0 的样本)
有效样本 = [1.0, 1.0, ..., 0.67, 0.33, ...]  # 55个样本
mean = (40×1.0 + 15×0.5) / 55 = 0.864

# degradation_type_score_mean_all (统计所有样本)
所有样本 = [0.0×30, 0.0×10, 1.0×40, 部分分×15, 0.0×5]
mean_all = (40×1.0 + 15×0.5) / 100 = 0.475
```

**如果你看到 `degradation_type_score_mean = 1.0`**:
- 可能所有非零样本都完全匹配（模型非常准确！）
- 或者样本数量太少，只有少数完全匹配的样本

**计算方式**:
```python
# 从模型的 <tool_call> 中提取预测的退化类型
# 与 Ground Truth 的退化类型集合比较

score = len(predicted_set ∩ expected_set) / len(expected_set)
```

**评分示例**:

| Ground Truth | 模型预测 | 分数 | 说明 |
|-------------|---------|------|------|
| `["noise", "motion blur", "haze"]` | `["noise", "motion blur", "haze"]` | 1.0 | ✅ 完全匹配 |
| `["noise", "motion blur", "haze"]` | `["noise", "motion blur"]` | 0.67 | ⚠️ 预测了 2/3 |
| `["noise", "motion blur", "haze"]` | `["noise"]` | 0.33 | ⚠️ 预测了 1/3 |
| `["noise", "motion blur"]` | `["noise", "rain"]` | 0.0 | ❌ 预测了无效类型 |
| `["noise"]` | `["clean"]` | 0.0 | ❌ clean 会被过滤 |

**特殊处理**:
1. **自动过滤 "clean"**: 因为 GT 中没有这个标签
2. **合并连续重复**: `["noise", "noise", "blur"]` → `["noise", "blur"]`
3. **不考虑顺序**: 只要集合匹配即可

**配置开关**:
```bash
# IR.sh 第54-55行
export ENABLE_DEGRADATION_TYPE_REWARD=False  # 是否启用
export DEGRADATION_TYPE_REWARD_WEIGHT=1.0    # 权重系数
```

**启用时的总奖励**:
```python
total_reward = FORMAT_WEIGHT × format_score 
             + QUALITY_WEIGHT × quality_score 
             + DEGRADATION_TYPE_WEIGHT × degradation_type_score
```

#### 🎯 监控建议

**重点关注 `degradation_type_score_mean_all`**:
- ✅ `mean_all > 0.5`: 整体识别能力良好
- ⚠️ `mean_all < 0.3`: 整体识别能力较弱
- 📊 `degradation_type_valid_samples`: 有多少样本实际计算了此分数

**如果 `degradation_type_score_mean = 1.0`**:
1. 检查 `degradation_type_valid_samples` 是否很小（< 10）
2. 对比 `degradation_type_score_mean_all`，看整体情况
3. 查看 WandB 表格中的 `Prediction_Match` 列，确认是否真的全部匹配

**调试步骤**:
```bash
# 1. 检查是否启用
grep "ENABLE_DEGRADATION_TYPE_REWARD" examples/agent/IR.sh

# 2. 查看日志中的调试信息
grep "degradation_type_match" logs/*.log

# 3. 在 WandB 中对比两个指标
# - reward/degradation_type_score_mean (可能是1.0)
# - reward/degradation_type_score_mean_all (反映真实情况)
```

**注意**: 当前默认**关闭**，因为图像质量奖励已经足够指导训练。如果需要显式鼓励模型识别退化类型，可以启用。

**数据来源**: `verl/utils/reward_score/image_restoration.py` → `check_degradation_type_match_v2()`

---

## 🖼️ 图像质量指标（有参考）

### <a name="rewardSSIM"></a>`reward/ssim_mean` | `reward/ssim_max` | `reward/ssim_min` | `reward/ssim_std` | `reward/ssim_valid_samples`

**含义**: 结构相似度 (Structural Similarity Index Measure)

**计算方式**: 比较复原图与 Ground Truth 的结构相似性

**取值范围**: `0.0 - 1.0` (越高越好)
- `> 0.9`: 非常相似，结构几乎完全保留
- `0.7 - 0.9`: 较好的结构保留
- `0.5 - 0.7`: 中等结构保留
- `< 0.5`: 结构损失较大

**优势**: 对亮度、对比度、结构变化敏感

**数据来源**: `verl/utils/reward_score/image_quality_metrics.py` → `ImageQualityMetrics.calculate_ssim()`

**相关指标**:
- 验证阶段: `val/reward/ssim_mean`
- 训练阶段图像上传: `train/ssim_mean`

---

### <a name="rewardLPIPS"></a>`reward/lpips_mean` | `reward/lpips_max` | `reward/lpips_min` | `reward/lpips_std` | `reward/lpips_valid_samples`

**含义**: 感知相似度 (Learned Perceptual Image Patch Similarity)

**计算方式**: 基于深度学习特征（VGG网络）比较复原图与 Ground Truth

**取值范围**: `0.0 - 1.0` (越低越好 ⚠️ 注意方向相反)
- `< 0.1`: 感知上非常相似
- `0.1 - 0.3`: 较好的感知相似度
- `0.3 - 0.5`: 中等感知相似度
- `> 0.5`: 感知差异较大

**优势**: 
- 最接近人类视觉感知
- 对细节恢复最敏感
- 在质量奖励中权重最高 (0.50)

**数据来源**: `verl/utils/reward_score/image_quality_metrics.py` → `ImageQualityMetrics.calculate_lpips()`

**注意**: LPIPS 在奖励计算中会被转换为 `1 - LPIPS`，使其方向与 SSIM 一致（越高越好）

---

### <a name="rewardPSNR"></a>`reward/psnr_mean` | `reward/psnr_max` | `reward/psnr_min` | `reward/psnr_std` | `reward/psnr_valid_samples`

**含义**: 峰值信噪比 (Peak Signal-to-Noise Ratio)

**计算方式**: 基于像素级均方误差（MSE）计算

**取值范围**: 通常 `10 - 50 dB` (越高越好)
- `> 35 dB`: 优秀的像素级精度
- `25 - 35 dB`: 良好的像素级精度
- `20 - 25 dB`: 中等像素级精度
- `< 20 dB`: 像素级误差较大

**优势**: 计算简单，像素级精度高

**局限**: 不一定与人类感知一致（两张 PSNR 相同的图，感知质量可能差异很大）

**数据来源**: `verl/utils/reward_score/image_quality_metrics.py` → `ImageQualityMetrics.calculate_psnr()`

---

### 有参考指标说明

**共同特点**:
1. **只对工具执行的样本有效**: 如果模型没有调用工具，这些指标为 0.0
2. **需要 Ground Truth**: 数据集必须提供 `original_image` 字段
3. **不参与奖励计算**: 仅用于 WandB 可视化和分析
4. **单独计算**: 在 logging 时额外计算，不影响训练速度

**valid_samples 字段**: 表示有多少样本成功计算了该指标（排除了工具未执行的样本）

**配置**:
```bash
# 如果数据集有 GT，可以额外记录这些指标（不影响训练）
export IMAGE_QUALITY_USE_NO_REFERENCE=True  # 训练仍用无参考指标
# WandB 会自动额外记录有参考指标用于分析
```

---

## 🤖 Agent 行为指标

### <a name="agentToolCall"></a>`agent/tool_call_mean` | `agent/tool_call_max` | `agent/tool_call_min`

**含义**: Agent 调用工具的次数统计

**取值范围**: `0 - max_turns` (配置的最大轮数)
- 当前配置: `max_turns=1` (单轮对话)

**解释**:
- `0`: 模型没有调用工具（直接给出 answer）
- `1`: 模型调用了 1 次工具
- `> 1`: 模型进行了多轮工具调用（仅在 max_turns > 1 时可能）

**监控建议**:
- ✅ `tool_call_mean ~ 0.7`: 平衡状态（70%样本使用工具，30%识别为clean）
- ⚠️ `tool_call_mean < 0.3`: 模型过于保守，不敢使用工具
- ⚠️ `tool_call_mean > 0.95`: 模型可能在所有样本上都使用工具（包括 clean 样本）

**数据来源**: `verl/trainer/ppo/metric_utils.py` → `compute_agent_metrics()`

**相关配置**:
```yaml
# IR.sh 第158行
actor_rollout_ref.rollout.agent.max_turns=1
```

---

### <a name="responseLength"></a>`response_length/mean` | `response_length/max` | `response_length/min` | `response_length/clip_ratio`

**含义**: 模型生成响应的长度统计

**取值范围**: `0 - max_response_length`
- 当前配置: `max_response_length=20480`

**子指标**:
- `mean`: 平均响应长度（token数）
- `max`: 最长响应
- `min`: 最短响应
- `clip_ratio`: 达到最大长度限制的样本比例

**监控建议**:
- ⚠️ `clip_ratio > 0.1`: 超过10%的样本被截断，考虑增加 `max_response_length`
- ✅ `mean` 稳定: 模型生成长度稳定
- 🔧 `max - min` 差异过大: 不同样本的响应长度差异大（正常现象）

**数据来源**: `verl/trainer/ppo/metric_utils.py` → `compute_data_metrics()`

**相关指标**:
- `prompt_length/mean`: 输入提示的平均长度
- `obs_length/mean`: 观察信息的平均长度（工具返回的内容）

---

## ⚙️ 训练性能指标

### <a name="actorLoss"></a>`actor/loss` | `actor/pg_loss` | `actor/entropy` | `actor/kl`

**含义**: Actor 网络的训练损失

**子指标**:
- `actor/loss`: 总损失
- `actor/pg_loss`: Policy Gradient 损失（PPO clip 损失）
- `actor/entropy`: 策略熵（鼓励探索）
- `actor/kl`: 与参考策略的 KL 散度

**监控建议**:
- ✅ `pg_loss` 逐渐下降: 策略在优化
- ⚠️ `entropy` 快速下降到 0: 策略过早收敛，缺乏探索
- 🔧 `kl` 过大: 策略更新步长过大，考虑降低学习率

**数据来源**: `verl/trainer/ppo/ray_trainer.py` → Actor 更新后收集

---

### <a name="criticVfExplainedVar"></a>`critic/vf_explained_var` | `critic/values/mean` | `critic/returns/mean` | `critic/advantages/mean`

**含义**: Critic (Value Function) 相关指标

**子指标**:
- `vf_explained_var`: Value Function 解释方差（衡量 Critic 预测准确度）
  - `> 0.8`: Critic 预测很准
  - `0.5 - 0.8`: Critic 预测较准
  - `< 0.5`: Critic 预测不准，需要更多训练
- `values/mean`: 预测的状态价值平均值
- `returns/mean`: 实际回报平均值
- `advantages/mean`: 优势函数平均值（应该接近 0）

**监控建议**:
- ✅ `vf_explained_var > 0.7`: Critic 学习良好
- ⚠️ `advantages/mean` 偏离 0 太多: 可能需要调整 GAE lambda
- 🔧 `values` 和 `returns` 差异过大: Critic 预测不准

**数据来源**: `verl/trainer/ppo/metric_utils.py` → `compute_data_metrics()`

---

### <a name="perfThroughput"></a>`perf/throughput` | `perf/total_num_tokens` | `perf/time_per_step`

**含义**: 训练性能统计

**子指标**:
- `throughput`: 吞吐量（tokens/秒/GPU）
- `total_num_tokens`: 每个 step 处理的总 token 数
- `time_per_step`: 每个 step 的时间（秒）

**监控建议**:
- 📊 `throughput`: 根据硬件和配置会有不同，主要看是否稳定
- ⚠️ `time_per_step` 持续增长: 可能有内存泄漏
- 🔧 对比不同配置的 `throughput` 来优化性能

**数据来源**: `verl/trainer/ppo/metric_utils.py` → `compute_throughout_metrics()`

---

## 🧪 验证指标（Validation）

所有训练指标都有对应的验证版本，前缀为 `val/reward/`：

### 验证奖励指标
- `val/reward/quality_score_mean` - 验证集图像质量平均分
- `val/reward/ssim_mean` - 验证集 SSIM 平均值
- `val/reward/lpips_mean` - 验证集 LPIPS 平均值
- `val/reward/psnr_mean` - 验证集 PSNR 平均值
- `val/reward/format_correct_ratio` - 验证集格式正确率
- `val/reward/degradation_type_score_mean` - 验证集退化类型识别准确度

### 验证采样指标
- `val/quality_mean` - 验证图像质量均值
- `val/quality_max` - 验证图像质量最大值
- `val/quality_min` - 验证图像质量最小值
- `val/ssim_mean` - 验证 SSIM 均值
- `val/lpips_mean` - 验证 LPIPS 均值
- `val/psnr_mean` - 验证 PSNR 均值

**验证频率**: 
```yaml
# IR.sh 第167行
trainer.test_freq=10  # 每10个epoch验证一次
```

---

## 📈 可视化内容（Media）

### 训练轨迹图像 (`train/trajectories`)
自动上传采样的训练样本可视化：
- **采样策略**: 2 best + 2 worst + 5 random（共9张）
- **图像内容**: Ground Truth → 退化图 → 中间步骤 → 复原结果
- **Caption**: 包含质量分数、SSIM、LPIPS、PSNR 等

### 验证轨迹图像 (`val/step{X}/trajectories`)
上传所有验证样本：
- **组织方式**: 按 step 分组
- **完整样本**: 所有验证集样本的完整可视化

### 对话表格 (`train/conversation_details`, `val/conversation_details`)
结构化表格，包含：
- 35+ 列数据
- 退化类型、预测匹配、工具状态
- 每轮的 Think 和 Tools 内容
- 质量指标和改善百分比

详见: `WANDB_TABLE_DEGRADATION_DETAILS.md`

---

## 🛠️ 配置指南

### 环境变量配置（IR.sh）

```bash
# ===== 奖励权重配置 =====
export FORMAT_REWARD_WEIGHT=0.3             # 格式奖励权重
export QUALITY_REWARD_WEIGHT=0.7            # 图像质量奖励权重
export ENABLE_DEGRADATION_TYPE_REWARD=False # 退化类型奖励开关
export DEGRADATION_TYPE_REWARD_WEIGHT=1.0   # 退化类型奖励权重

# ===== 图像质量配置 =====
export IMAGE_QUALITY_USE_NO_REFERENCE=False # True=无参考, False=有参考
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0    # 离散化等级(0=连续)
```

### YAML 配置（ppo_trainer.yaml）

```yaml
trainer:
  test_freq: 10                    # 验证频率
  val_before_train: True           # 训练前先验证
  log_images_to_wandb: true        # 上传图像到 WandB

actor_rollout_ref:
  rollout:
    agent:
      max_turns: 1                 # 最大对话轮数
      show_tqdm: True              # 显示进度条
```

---

## 📚 相关文档

- **数据流分析**: `WANDB_DATA_FLOW_ANALYSIS.md`
- **表格列详解**: `WANDB_TABLE_DEGRADATION_DETAILS.md`
- **奖励系统**: `REWARD_CONFIG_FINAL_SUMMARY.md`
- **快速开始**: `QUICK_START.md`
- **验证清单**: `COMPLETE_VERIFICATION_CHECKLIST.md`

---

## 🔍 常见问题

### Q1: 为什么 `reward/ssim_mean` 显示为 0？
**A**: 有参考指标只对使用工具的样本有效。如果：
- 训练用无参考模式（`IMAGE_QUALITY_USE_NO_REFERENCE=True`）
- 或大部分样本没有调用工具
- 或数据集缺少 `original_image` 字段

则这些指标会为 0。检查 `reward/ssim_valid_samples` 来确认有多少样本计算了此指标。

### Q2: `reward/degradation_type_score_mean` 一直是 1.0 是正常的吗？
**A**: 这是**正常现象**！原因：
1. **过滤效果**: 该指标只统计分数 > 0 的样本
2. **完全匹配才有分**: 部分匹配（如预测 1/3 正确）也会被记为 0.0
3. **实际情况**: 查看 `degradation_type_score_mean_all` 才能看到真实的平均分数

**正确监控姿势**:
- ✅ 关注 `reward/degradation_type_score_mean_all` (包含所有样本)
- ✅ 关注 `reward/degradation_type_valid_samples` (有效样本数量)
- ⚠️ 如果 `valid_samples` 很小但 `mean=1.0`，说明大部分样本都被过滤了

**示例**:
```
degradation_type_score_mean = 1.0  (只有10个完全匹配的样本)
degradation_type_score_mean_all = 0.12  (100个样本的真实均值)
degradation_type_valid_samples = 10  (只有10个>0的样本)
```
这说明100个样本中，只有10个完全匹配（1.0分），其余90个都是0分。

### Q3: `critic/score/max` 一直停在 0.3？
**A**: 这表示模型只获得了格式奖励（0.3），没有图像质量奖励（0.7），说明：
- 模型没有调用工具（过于保守）
- 或工具调用失败
- 检查 `agent/tool_call_mean` 是否过低
- 可能需要降低 `FORMAT_REWARD_WEIGHT`，提高 `QUALITY_REWARD_WEIGHT`

### Q4: 如何区分训练用的指标和仅供分析的指标？
**A**:
- **训练用** (影响梯度): `critic/score/mean` (总奖励)
- **分解监控** (不直接影响梯度): `reward/format_score_mean`, `reward/quality_score_mean`
- **仅供分析** (不影响训练): `reward/ssim_mean`, `reward/lpips_mean`, `reward/psnr_mean`

### Q5: WandB 表格中的 `Prediction_Match` 是什么？
**A**: 表示模型预测的退化类型与 Ground Truth 的匹配程度：
- ✅ 完全正确
- ⚠️ 部分正确
- ❌ 完全错误
- ❓ 未知（无法判断）

详见 `WANDB_TABLE_DEGRADATION_DETAILS.md`

---

## 📊 推荐监控组合

### 🎯 基础监控（必看）
1. `critic/score/max` - 最高奖励（看模型天花板）
2. `critic/score/mean` - 平均奖励（看整体表现）
3. `reward/format_correct_ratio` - 格式正确率（看格式学习）
4. `agent/tool_call_mean` - 工具调用率（看探索程度）

### 🖼️ 质量监控（进阶）
1. `reward/quality_score_mean` - 总体质量
2. `reward/ssim_mean` - 结构保留（如果用有参考模式）
3. `reward/lpips_mean` - 感知质量（如果用有参考模式）
4. `val/reward/quality_score_mean` - 验证集质量（看泛化）

### 🤖 行为监控（调试）
1. `reward/degradation_type_score_mean` - 识别准确度（如果启用）
2. `response_length/clip_ratio` - 截断比例（看是否需要增加长度限制）
3. `critic/vf_explained_var` - Critic准确度（看值函数学习）

### ⚙️ 性能监控（优化）
1. `perf/throughput` - 吞吐量
2. `perf/time_per_step` - 每步时间
3. `timing_s/gen` - 生成时间
4. `timing_s/update_actor` - Actor更新时间

---

**最后更新**: 2025-01-XX  
**维护者**: DeepEyes Team

