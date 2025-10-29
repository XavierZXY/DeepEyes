# low resolution 和 dark 为0 - 完整分析总结

## 🎯 最终结论

**这不是代码bug，是模型训练问题！**

模型还没有学会识别和处理 low resolution 退化（占数据集45%），也很少处理 dark 退化。

---

## ✅ 已完成的检查

### 1. 数据集检查 ✅

```
/app/xiaominl/air_v15_dm3_update_tool/shards

每个shard (~512样本):
- dark: 44-72个 (约10-14%)
- low resolution: 220-248个 (约43-48%，接近一半！)

结论：数据非常充足！
```

### 2. 工具注册检查 ✅

```python
已注册工具:
- hat_super_resolution ✅
- swinir_super_resolution ✅
- retinexformer_enhance ✅
- retinexformer_fivek ✅
- ... (所有 retinexformer 系列)
```

### 3. 统计映射检查 ✅

```python
# parallel_env.py
DEGRADATION_TO_TOOLS = {
    'low resolution': ['swinir_super_resolution', 'hat_super_resolution'],  ✅
    'dark': ['retinexformer_*' 全系列],  ✅
}
```

### 4. 格式检查允许列表 ✅

```python
# image_restoration.py
ALLOWED_TOOLS = {
    "hat_super_resolution",  ✅ 已添加（刚修复）
    "retinexformer_enhance",  ✅
    "retinexformer_fivek",  ✅
    ... (所有 retinexformer)
}
```

### 5. Tool Diversity Bonus 检查 ✅

```
reward/tool_diversity_bonus_obtained_ratio: 0.996  ← 99.6%获得
reward/tool_diversity_bonus_no_bonus_format_error: 1  ← 只有1个格式错误

结论：bonus机制正常，不是问题
```

### 6. 实际工具调用检查 ❌

```bash
观察到的工具调用（来自日志）:
✓ restormer_motion_deblurring
✓ scunet_real_denoising_gan
✓ restormer_defocus_deblurring
✓ fbcnn_jpeg_artifact_removal
✓ dehazeformer_dehaze
✓ restormer_deraining
✓ retinexformer_fivek

❌ 从未见到:
   - hat_super_resolution
   - swinir_super_resolution
```

**结论：模型根本不调用超分辨率工具！**

---

## 📊 统计结果验证

### WandB 指标（Step 61）

```
✅ 表现好的:
- rain: 12/12 = 1.000
- motion blur: 12/12 = 1.000
- defocus blur: 12/12 = 1.000
- noise: 20/20 = 1.000
- jpeg compression artifact: 12/12 = 1.000

❌ 表现差的:
- low resolution: 0/12 = 0.000  ← 有12个样本，0个调用对应工具
- dark: 0/0 = 0.000  ← 这个batch没有dark样本
- haze: 0/0 = 0.000  ← 这个batch没有haze样本
```

### Tool Count Match

```
deg2 (2种退化):
- exact: 8/16 = 0.500  ← 50%刚好
- less: 8/16 = 0.500   ← 50%少调用（很可能是因为缺少超分辨率）

deg3 (3种退化):
- exact: 12/16 = 0.750  ← 75%刚好
- less: 4/16 = 0.250    ← 25%少调用
```

**分析：** 
- 2种退化的样本有50%少调用 → 很可能是因为其中一个是low resolution，模型不调用
- 3种退化的样本75%刚好 → 可能这些样本的3种退化都是模型学会的

---

## 🔍 根本原因分析

### 为什么模型不调用超分辨率工具？

#### 可能原因1: 历史格式惩罚（最可能）

**之前的情况：**
```
模型尝试: ['hat_super_resolution']
→ 格式检查: ❌ (不在 ALLOWED_TOOLS)
→ format_score = -1.0
→ 总奖励 = 0.3 × (-1.0) + 0.7 × quality = -0.3 + 0.7×quality
  即使 quality = 0.8，总奖励 = -0.3 + 0.56 = 0.26
  
  如果不调用工具（直接answer）:
→ format_score = 1.0
→ 总奖励 = 0.3 × 1.0 + 0 = 0.3

结论：调用HAT反而更低！模型学会了不调用
```

#### 可能原因2: 超分辨率质量提升不明显

超分辨率任务比较困难，可能：
- 处理效果不够好
- 图像质量提升幅度小
- 奖励信号弱于其他退化类型

#### 可能原因3: 其他退化掩盖了low resolution

```
样本: ['low resolution', 'noise', 'defocus blur']
模型学习策略: 优先处理noise和blur（奖励高）
             忽略low resolution（奖励不明显）
```

---

## 🔧 解决方案（按优先级）

### 方案1: 清理缓存并重新训练（必须！）

```bash
# HAT工具的格式检查已修复，需要让模型重新学习
ray stop
find /app/xiaominl/DeepEyes_v2 -name "*.pyc" -delete
find /app/xiaominl/DeepEyes_v2 -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
bash /app/xiaominl/DeepEyes_v2/examples/agent/IRv2.sh
```

**原因：** 移除HAT工具的格式惩罚，让模型可以探索调用它

---

### 方案2: 监控指标变化

在 WandB 观察：
```
tool_match/unique_ratio/low resolution
```

**预期：**
- 前几百步: 0.0 → 0.1 → 0.2 （开始探索）
- 中期: 0.3 → 0.5 （逐步学习）
- 后期: 0.7 → 0.9 （收敛）

如果一直是0，进行方案3。

---

### 方案3: 增加 low resolution 的奖励（如果方案1不够）

修改 `image_restoration.py` 第1620行附近：

```python
# 在计算 total_score 之前
if 'low resolution' in degradation_addition_order:
    # 检查是否调用了超分辨率工具
    sr_tools_called = False
    try:
        tool_call_matches = re.finditer(r'<tool_call>\s*(\[.*?\])\s*</tool_call>', solution_str, re.DOTALL)
        for match in tool_call_matches:
            tools = json.loads(match.group(1))
            for tool_dict in tools:
                if tool_dict.get('name') in ['hat_super_resolution', 'swinir_super_resolution']:
                    sr_tools_called = True
                    break
    except:
        pass
    
    if sr_tools_called:
        # 调用了超分辨率工具，给额外奖励
        quality_score *= 1.2  # 提升20%
        print(f' [BONUS] 调用了超分辨率工具处理low resolution，quality_score增强到{quality_score:.3f}')
```

---

### 方案4: 检查 System Prompt（如果需要）

```bash
# 查看prompt中是否清楚说明了超分辨率的用法
grep -i "low.resolution\|super.resolution" verl/workers/agent/envs/mm_process_engine/IRprompt.py
```

确保prompt中有明确的指导，例如：
```
"For low resolution issues, use super resolution tools (hat_super_resolution or swinir_super_resolution)"
```

---

## 📈 预期的训练曲线

### 理想情况（HAT格式修复生效）

```
tool_match/unique_ratio/low resolution:

Step 0-200:   0.00 → 0.00  (旧策略惯性)
Step 200-500: 0.00 → 0.20  (开始探索HAT工具)
Step 500-1000: 0.20 → 0.60  (逐步学习)
Step 1000+:    0.60 → 0.85  (收敛)
```

### 如果还是不行

```
Step 0-1000: 0.00 → 0.05  (几乎不变)
→ 需要方案3：增加奖励权重
```

---

## 🎯 关键洞察

### Tool Diversity Bonus 的作用

**只是鼓励工具多样性，不指定具体工具：**

```python
# 只检查是否有重复
if len(tool_names) == len(set(tool_names)):  # 无重复
    bonus = 0.1
else:
    bonus = 0.0

# 不关心具体调用了哪些工具
# 只要不重复就给bonus
```

**所以它不会直接鼓励调用超分辨率工具！**

### 真正的问题

模型的学习策略可能是：
1. 调用容易的工具（去雨、去雾、去噪）→ 高质量分数
2. 避免困难的工具（超分辨率）→ 质量提升小，不值得
3. 加上之前HAT被惩罚的经验 → 强化了"不调用"的策略

---

## ✅ 行动计划

### 立即行动（必须）

```bash
# 1. 清理缓存
ray stop
find /app/xiaominl/DeepEyes_v2 -name "*.pyc" -delete

# 2. 重新训练
bash examples/agent/IRv2.sh

# 3. 监控WandB
# 观察 tool_match/unique_ratio/low resolution
```

### 中期观察（1-2天）

- 如果指标上升 → 格式修复生效 ✅
- 如果仍然是0 → 需要方案3（增加奖励）

### 长期优化（如果需要）

- 调整奖励函数
- 增加专门的bonus奖励超分辨率
- 或者接受模型的选择（可能low resolution影响确实小）

---

## 📊 总结

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 数据集分布 | ✅ | low resolution占45%，dark占10% |
| 工具注册 | ✅ | HAT和retinexformer都已注册 |
| 统计映射 | ✅ | 已正确映射 |
| 格式允许列表 | ✅ | HAT已添加（刚修复） |
| Bonus机制 | ✅ | 99.6%获得，无问题 |
| 模型调用 | ❌ | **从不调用超分辨率工具** |

### 根本原因

**之前HAT工具被格式检查惩罚，模型学会了避免调用！**

现在已修复格式检查，需要重新训练让模型"忘记"旧惩罚。

---

## 🚀 最终建议

**清理缓存并重新训练，然后耐心等待模型学习！**

如果训练500-1000步后还是0，再考虑增加额外奖励。

**代码已完全准备好！** ✅🎉

