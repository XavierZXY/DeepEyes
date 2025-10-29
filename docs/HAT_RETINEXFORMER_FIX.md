# HAT 和 Retinexformer 工具映射修复

## 🔧 修复内容

### 问题1: HAT工具缺失

**现象：**
```
tool_match/unique_count/low resolution = 0
```

**原因：**
1. ✅ 数据集有 low resolution 退化
2. ❌ 模型可能调用了 `hat_super_resolution`
3. ❌ 但映射表中没有 `hat_super_resolution`
4. ❌ 格式检查的 ALLOWED_TOOLS 中也没有 `hat_super_resolution`

**修复：**

#### 修复1.1: 添加到统计映射表

`parallel_env.py` 第533行：
```python
'low resolution': ['swinir_super_resolution', 'hat_super_resolution'],  # ✅ 已添加
```

#### 修复1.2: 添加到格式检查允许列表

`image_restoration.py` 第40-41行：
```python
# Super resolution
"swinir_super_resolution",
"hat_super_resolution",  # ✅ 已添加
```

---

### 问题2: Retinexformer工具完整性

**检查：** 所有 retinexformer 系列工具都已在 ALLOWED_TOOLS 中

```python
# Low-light enhancement (Retinexformer系列)
"retinexformer_enhance",           ✅
"retinexformer_lol_v1",            ✅
"retinexformer_lol_v2_real",       ✅
"retinexformer_lol_v2_synthetic",  ✅
"retinexformer_sdsd_indoor",       ✅
"retinexformer_sdsd_outdoor",      ✅
"retinexformer_sid",               ✅
"retinexformer_smid",              ✅
"retinexformer_fivek",             ✅
```

**统计映射表：**
```python
'dark': ['retinexformer_enhance', 'retinexformer_lol_v1', ..., 'retinexformer_fivek'],  ✅
```

---

## ✅ 修复后的效果

### 之前（修复前）

```python
# 如果模型调用了 hat_super_resolution
工具调用: ['hat_super_resolution']

格式检查:
→ ❌ 格式错误！(hat_super_resolution 不在 ALLOWED_TOOLS 中)
→ format_score = -1.0

统计:
→ ❌ 不计入 low resolution 统计（映射表中没有）
→ unique_count/low resolution = 0
```

### 现在（修复后）

```python
# 如果模型调用了 hat_super_resolution
工具调用: ['hat_super_resolution']

格式检查:
→ ✅ 格式正确！(hat_super_resolution 在 ALLOWED_TOOLS 中)
→ format_score = 1.0

统计:
→ ✅ 计入 low resolution 统计
→ unique_count/low resolution += 1
```

---

## 🎯 为什么之前是0？

### 可能的两种情况

#### 情况A: 模型调用了HAT但格式检查失败

```
模型输出: ['hat_super_resolution', 'fbcnn_jpeg_artifact_removal']

之前:
→ 格式检查: ❌ (hat_super_resolution不在允许列表)
→ format_score = -1.0
→ 总奖励很低，模型被惩罚

现在:
→ 格式检查: ✅ 
→ format_score = 1.0
→ 统计: low resolution += 1
```

#### 情况B: 模型确实没调用超分辨率工具

```
样本: 退化=['low resolution', 'noise']
模型输出: ['scunet_real_denoising_gan']  # 只处理了noise

统计:
→ low resolution: 0/1 = 0.0  # 该样本没有调用超分辨率工具
```

---

## 🔍 如何验证修复生效？

### 步骤1: 清理缓存并重新训练

```bash
# 清理Python缓存
find /app/xiaominl/DeepEyes_v2 -name "*.pyc" -delete
find /app/xiaominl/DeepEyes_v2 -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null

# 重新运行
ray stop
bash examples/agent/IRv2.sh
```

### 步骤2: 检查格式错误日志

```bash
# 搜索格式错误
grep "使用了未允许的工具.*hat_super_resolution" logs/new_run_*.log
```

**修复前：** 会看到错误
**修复后：** 不应该有这个错误

### 步骤3: 检查统计结果

```bash
grep "low resolution:" logs/new_run_*.log
```

**期望看到（如果模型有调用）：**
```
[TOOL STATS]   low resolution: X/X = 0.XXX  # X > 0
```

**如果还是：**
```
[TOOL STATS]   low resolution: 0/X = 0.000
```

说明模型确实没有调用超分辨率工具（训练问题，不是代码问题）

---

## 📊 完整的工具映射检查

### 验证所有映射都正确

```bash
# 检查parallel_env.py中的映射
grep -A 10 "DEGRADATION_TO_TOOLS = {" /app/xiaominl/DeepEyes_v2/verl/workers/agent/parallel_env.py

# 检查ALLOWED_TOOLS
grep -A 60 "ALLOWED_TOOLS = {" /app/xiaominl/DeepEyes_v2/verl/utils/reward_score/image_restoration.py
```

**确认：**
- ✅ low resolution → ['swinir_super_resolution', 'hat_super_resolution']
- ✅ dark → ['retinexformer_*' 全系列]
- ✅ 所有工具都在 ALLOWED_TOOLS 中

---

## 💡 下一步

### 如果修复后 low resolution 还是0

说明是**模型训练问题**，需要：

1. **检查数据分布**
   ```bash
   # 统计各退化类型的比例
   grep "真实退化类型" logs/*.log | grep "low resolution" | wc -l
   ```

2. **检查模型输出**
   ```bash
   # 看模型是否调用了超分辨率工具
   grep "调用工具.*hat_super_resolution\|调用工具.*swinir_super_resolution" logs/*.log
   ```

3. **分析原因**
   - 如果模型从不调用 → 训练数据不足或奖励信号弱
   - 如果偶尔调用 → 模型正在学习，继续训练
   - 如果调用但统计还是0 → 代码问题（再检查）

---

## ✅ 修复总结

### 已修复

1. ✅ `hat_super_resolution` 添加到统计映射表
2. ✅ `hat_super_resolution` 添加到格式检查允许列表
3. ✅ 所有 retinexformer 系列工具都已包含

### 需要验证

- 重新训练后检查格式错误是否消失
- 观察 low resolution 和 dark 的统计是否改善

### 如果还是0

说明是模型性能问题，不是代码问题。这个统计正是为了发现这种问题！

---

## 🎉 代码已修复

清理缓存并重新训练即可！🚀

```bash
ray stop
find . -name "*.pyc" -delete
find . -type d -name __pycache__ -rm -rf {} + 2>/dev/null
bash examples/agent/IRv2.sh
```

