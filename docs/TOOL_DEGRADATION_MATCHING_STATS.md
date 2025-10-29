# 工具-退化匹配统计指标说明

## 📊 功能概述

新增的统计指标用于衡量**模型调用工具与图像退化类型的匹配程度**，帮助分析模型是否学会了正确识别退化类型并选择对应的处理工具。

---

## 🎯 统计内容

### 8种退化类型

每种退化类型都会生成独立的统计指标：

| 退化类型 | 对应工具示例 |
|---------|-------------|
| `rain` | mprnet_deraining, restormer_deraining, xrestormer_deraining |
| `haze` | dehazeformer_dehaze |
| `dark` | retinexformer_enhance, retinexformer_lol_v1, ... |
| `motion blur` | xrestormer_motion_deblurring, mprnet_motion_deblurring, ... |
| `defocus blur` | drbnet_defocus_deblurring, restormer_defocus_deblurring |
| `noise` | swinir_denoising, mprnet_denoising, scunet_*_denoising |
| `low resolution` | swinir_super_resolution |
| `jpeg compression artifact` | swinir_jpeg_artifact_removal, fbcnn_jpeg_artifact_removal |

**说明：** `clean` 类型不参与统计（因为不需要调用工具）

---

## 📈 两种统计方式

### 1️⃣ 重复统计（Repeat）- 工具调用次数级别

**定义：** 统计工具调用的总次数与退化类型出现总次数的比例

**计算方式：**
```
repeat_ratio = 对应工具被调用的总次数 / 该退化类型出现的总次数
```

**示例：**
```
批次有100个样本：
- 30个样本有 rain 退化
- 其中有些样本调用了多次去雨工具（mprnet_deraining, restormer_deraining）
- 去雨工具总共被调用了45次

rain_repeat_ratio = 45 / 30 = 1.5
```

**含义：**
- `= 1.0`：每个退化平均调用1次对应工具（完美匹配）
- `> 1.0`：有重复调用（可能是模型不确定或多轮尝试）
- `< 1.0`：有漏调用（模型没有识别或处理所有退化）

**WandB 指标：**
```
tool_match/rain_repeat_ratio        # 匹配率
tool_match/rain_repeat_count        # 调用次数
tool_match/rain_total_count         # 退化出现次数
```

---

### 2️⃣ 不重复统计（Unique）- 样本级别

**定义：** 统计至少调用过一次对应工具的样本占有该退化的样本的比例

**计算方式：**
```
unique_ratio = 调用过对应工具的样本数 / 有该退化的样本总数
```

**示例：**
```
批次有100个样本：
- 30个样本有 rain 退化
- 其中25个样本至少调用了1次去雨工具
- 不管某个样本调用了几次，都只算1个

rain_unique_ratio = 25 / 30 = 0.833
```

**含义：**
- `= 1.0`：所有有该退化的样本都调用了对应工具（完美识别）
- `< 1.0`：有部分样本没有调用对应工具（识别遗漏）

**WandB 指标：**
```
tool_match/rain_unique_ratio        # 匹配率
tool_match/rain_unique_matched      # 匹配样本数
tool_match/rain_unique_total        # 有该退化的样本总数
```

---

## 🔀 模式差异

### 单轮多工具模式（multi_tool_planning）

**统计策略：** 只看最后一轮的工具调用

```python
第1轮: [dehaze, deblur, denoise]
第2轮: [enhance]  # ← 只统计这一轮
第3轮: <answer>

# 统计时只看第2轮的 [enhance]
```

**原因：** 多工具模式可能在前面轮次尝试错误方案，最后一轮才是最终决策

**特殊情况：** 如果只有1轮，那就统计第1轮

---

### 多轮单工具模式（single_tool_iterative）

**统计策略：** 统计所有轮次的工具调用

```python
第1轮: [dehaze]
第2轮: [deblur]
第3轮: [denoise]
第4轮: <answer>

# 统计所有工具：[dehaze, deblur, denoise]
```

**原因：** 单工具模式每轮都是有意义的处理步骤，都应该统计

---

## 📊 WandB 展示

### Panel 组织

所有指标都在 `tool_match/` 命名空间下，wandb 会自动创建独立的 panel。

### 指标分组

**重复统计（Repeat）：**
```
tool_match/
  ├─ rain_repeat_ratio
  ├─ rain_repeat_count
  ├─ rain_total_count
  ├─ haze_repeat_ratio
  ├─ haze_repeat_count
  ├─ ...
```

**不重复统计（Unique）：**
```
tool_match/
  ├─ rain_unique_ratio
  ├─ rain_unique_matched
  ├─ rain_unique_total
  ├─ haze_unique_ratio
  ├─ haze_unique_matched
  ├─ ...
```

### 建议的可视化

1. **折线图：** 各退化类型的匹配率随训练步数的变化
   - X轴：training_step
   - Y轴：ratio (0-1)
   - 多条线：每种退化类型一条

2. **柱状图：** 对比不同退化类型的匹配率
   - X轴：退化类型
   - Y轴：ratio
   - 两组柱：repeat vs unique

3. **热力图：** 退化类型 × 训练步数的匹配率矩阵

---

## 🎯 使用建议

### 指标解读

#### 理想情况
```
rain_repeat_ratio ≈ 1.0     # 不多不少，刚好匹配
rain_unique_ratio ≈ 1.0     # 所有样本都识别到了
```

#### 问题诊断

**情况1：unique_ratio 低，repeat_ratio 正常**
```
rain_unique_ratio = 0.5     # 只有50%的样本调用了
rain_repeat_ratio = 1.0     # 但调用的样本都只调用了1次
```
**问题：** 模型识别能力不足，漏检了50%的rain退化
**建议：** 增加训练数据，或调整奖励函数强调识别准确性

**情况2：unique_ratio 高，repeat_ratio 高**
```
rain_unique_ratio = 1.0     # 所有样本都调用了
rain_repeat_ratio = 2.5     # 但平均每个调用了2.5次
```
**问题：** 模型重复调用工具（可能不确定或探索）
**建议：** 正常现象，尤其是单工具模式；如果是多工具模式可能需要优化

**情况3：unique_ratio 低，repeat_ratio 低**
```
rain_unique_ratio = 0.3     # 只有30%的样本调用了
rain_repeat_ratio = 0.4     # 总调用次数也很少
```
**问题：** 模型严重忽略该类型退化
**建议：** 检查训练数据分布，增加该类型样本比例

---

## 🔧 代码位置

### 数据收集
- **文件：** `verl/workers/agent/parallel_env.py`
- **位置：** 第457-465行（收集工具调用）
- **位置：** 第674-710行（提取真实退化类型并计算统计）

### 统计计算
- **函数：** `compute_tool_degradation_matching_stats`
- **位置：** 第286-414行

### 指标上传
- **文件：** `verl/trainer/ppo/metric_utils.py`
- **函数：** `compute_agent_metrics`
- **位置：** 第195-207行（提取tool_match指标）

---

## 📝 完整指标列表

### 每种退化类型有6个指标

以 `rain` 为例：

```python
# 重复统计
'tool_match/rain_repeat_ratio'       # 匹配率（可能>1）
'tool_match/rain_repeat_count'       # 工具调用总次数
'tool_match/rain_total_count'        # 退化出现总次数

# 不重复统计
'tool_match/rain_unique_ratio'       # 匹配率（0-1）
'tool_match/rain_unique_matched'     # 匹配的样本数
'tool_match/rain_unique_total'       # 有该退化的样本总数
```

### 总共指标数

8个退化类型 × 6个指标 = **48个指标**

---

## 🎨 可视化示例

### WandB 图表配置建议

#### 1. 匹配率趋势图（折线图）

```python
# 创建自定义图表
y_keys = [
    'tool_match/rain_unique_ratio',
    'tool_match/haze_unique_ratio',
    'tool_match/dark_unique_ratio',
    'tool_match/motion blur_unique_ratio',
    'tool_match/defocus blur_unique_ratio',
    'tool_match/noise_unique_ratio',
    'tool_match/low resolution_unique_ratio',
    'tool_match/jpeg compression artifact_unique_ratio',
]
```

#### 2. 重复 vs 不重复对比

```python
# 对于每种退化，对比两种统计方式
groups = {
    'rain': ['tool_match/rain_repeat_ratio', 'tool_match/rain_unique_ratio'],
    'haze': ['tool_match/haze_repeat_ratio', 'tool_match/haze_unique_ratio'],
    # ...
}
```

---

## 🧪 验证方法

### 检查日志输出

训练时应该看到：

```bash
[TOOL STATS] 开始提取真实退化类型...
[TOOL STATS] 样本0: 真实退化类型 ['rain', 'haze']
[TOOL STATS] 样本1: 真实退化类型 ['noise', 'dark']
...

[TOOL STATS] 样本0 轮次1: 调用工具 ['mprnet_deraining', 'dehazeformer_dehaze']
...

[TOOL STATS] 开始计算工具-退化匹配统计...

[TOOL STATS] === 工具-退化匹配统计 ===
[TOOL STATS] 重复统计（工具调用次数级别）:
[TOOL STATS]   rain: 28/30 = 0.933
[TOOL STATS]   haze: 15/20 = 0.750
...

[TOOL STATS] 不重复统计（样本级别）:
[TOOL STATS]   rain: 25/30 = 0.833
[TOOL STATS]   haze: 14/20 = 0.700
...

[METRICS] 收集了 48 个工具-退化匹配指标
```

### 检查 WandB 面板

1. 打开 WandB 项目页面
2. 查看 Charts
3. 搜索 `tool_match/`
4. 应该看到48个新指标
5. 创建自定义图表来可视化

---

## ⚙️ 配置说明

### 退化类型到工具的映射

在 `parallel_env.py` 第298-311行定义：

```python
DEGRADATION_TO_TOOLS = {
    'rain': ['mprnet_deraining', 'restormer_deraining', 'xrestormer_deraining'],
    'haze': ['dehazeformer_dehaze'],
    'dark': ['retinexformer_enhance', 'retinexformer_lol_v1', ...],
    'motion blur': ['xrestormer_motion_deblurring', 'mprnet_motion_deblurring', ...],
    'defocus blur': ['drbnet_defocus_deblurring', 'restormer_defocus_deblurring'],
    'noise': ['swinir_denoising', 'mprnet_denoising', 'scunet_*_denoising'],
    'low resolution': ['swinir_super_resolution'],
    'jpeg compression artifact': ['swinir_jpeg_artifact_removal', 'fbcnn_jpeg_artifact_removal'],
}
```

**如需修改：** 直接编辑这个字典，添加或删除工具

---

## 💡 实际应用示例

### 示例1：训练早期（模型还在探索）

```
WandB 显示：
tool_match/rain_unique_ratio = 0.45    # 只有45%的rain样本调用了去雨工具
tool_match/rain_repeat_ratio = 0.60    # 总调用次数也偏低

解读：模型还没学会识别rain退化，需要继续训练
```

### 示例2：训练中期（模型开始收敛）

```
WandB 显示：
tool_match/rain_unique_ratio = 0.85    # 85%的rain样本识别正确
tool_match/rain_repeat_ratio = 1.20   # 平均每个调用1.2次

解读：模型基本学会了，但还有15%的遗漏和一些重复调用
```

### 示例3：训练后期（模型收敛良好）

```
WandB 显示：
tool_match/rain_unique_ratio = 0.95    # 95%的样本识别正确
tool_match/rain_repeat_ratio = 1.05   # 几乎每个只调用1次

解读：模型表现优秀，可以考虑停止训练或降低学习率
```

---

## 🎯 与现有指标的关系

### 现有指标（奖励相关）
```
reward/format_correct_ratio          # 格式正确率
reward/quality_score_mean            # 图像质量
reward/degradation_type_score_mean   # 退化类型识别准确率（基于集合匹配）
```

### 新增指标（工具调用相关）
```
tool_match/*_unique_ratio            # 工具选择准确率（样本级别）
tool_match/*_repeat_ratio            # 工具调用覆盖率（次数级别）
```

### 互补性

- **退化类型识别准确率**：模型是否在answer中正确列出所有退化
- **工具调用匹配率**：模型是否实际调用了正确的工具

两者结合可以全面评估模型的理解和执行能力。

---

## 🔍 故障排查

### 问题1：所有指标都是0

**可能原因：**
- 数据集中都是clean样本
- reward_model或env_name字段缺失

**解决方法：**
- 检查日志中的 `[TOOL STATS] 样本X: 真实退化类型 []`
- 确认数据集包含退化样本

### 问题2：某个退化类型没有统计

**可能原因：**
- 该退化类型在 DEGRADATION_TO_TOOLS 中没有映射
- 或者数据集中没有该类型样本

**解决方法：**
- 查看警告：`[TOOL STATS WARNING] 退化类型 'XXX' 没有对应的工具映射`
- 添加映射关系到 DEGRADATION_TO_TOOLS

### 问题3：repeat_ratio 非常高（>3）

**可能原因：**
- 单工具模式下，模型反复调用同一工具
- 或者多工具模式下，模型在多轮中重复同样的工具

**解决方法：**
- 正常现象（尤其是单工具模式多轮迭代）
- 如果过高可能需要调整max_turns或奖励函数

---

## 📚 技术细节

### 数据流

```
1. agent_rollout_loop
   ├─ 收集工具调用: tool_calls_per_sample
   ├─ 提取真实退化: degradation_types_per_sample
   └─ 计算统计: compute_tool_degradation_matching_stats()

2. 添加到 DataProto.tensors
   └─ tool_match/* (48个指标)

3. metric_utils.compute_agent_metrics
   └─ 从 batch.batch 提取 tool_match/* 指标

4. ray_trainer
   └─ metrics.update(compute_agent_metrics(batch))

5. logger.log(metrics)
   └─ 上传到 WandB
```

### 性能影响

- **计算开销：** 极小（O(batch_size × num_degradations)）
- **内存开销：** 每个batch增加约 200KB（48个指标 × batch_size）
- **网络开销：** 每step上传48个float值，可忽略

---

## ✅ 总结

### 新增指标数量
- **8个退化类型** × **6个指标** = **48个新指标**

### 关键优势
- ✅ 细粒度评估每种退化的工具选择能力
- ✅ 区分重复和不重复统计，提供多角度分析
- ✅ 自动适配两种对话模式
- ✅ 独立panel，不影响现有指标

### 使用场景
- 诊断模型在哪些退化类型上表现较弱
- 对比不同训练策略的效果
- 监控模型训练过程中的能力演化

---

## 📞 反馈

如有问题或建议，欢迎反馈！

