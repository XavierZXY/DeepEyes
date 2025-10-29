# 所有新增的调试功能总结

## 🔍 调试信息概览

### 1. 工具链执行追踪

**位置**: `parallel_env.py` 执行过程中

```bash
[DEBUG T1-00] 🔧 开始执行工具链，共3个工具
[DEBUG T1-00] 📋 origin_multi_modal_data: True
[DEBUG T1-00] 📋 raw_prompt: True
[DEBUG T1-00] 📏 工具输入图像尺寸: (217, 253)
[DEBUG T1-00] 📋 工具列表: ['restormer_deraining', 'retinexformer_sdsd_indoor', 'scunet_real_denoising_gan']
[DEBUG T1-00] 📋 有效工具数: 3/3

[DEBUG T1-00] 🔍 处理工具1/3
[DEBUG T1-00] 📝 工具1类型: RestormerDerrainingToolbox, 名称: restormer_deraining
[DEBUG T1-00] 📝 工具1 tool_call: {'name': 'restormer_deraining', ...}
[DEBUG T1-00] 🔄 工具1/3: restormer_deraining (输入: 原图)
[DEBUG T1-00] ✅ 工具1 reset成功
[DEBUG T1-00] 🚀 开始执行工具1: restormer_deraining
[DEBUG T1-00] ✅ 工具1执行返回: type=<class 'dict'>, reward=0.000, done=False, info_status=success
[DEBUG T1-00] 📷 更新当前图像数据

... (工具2, 3类似)

[DEBUG T1-00] 🎉 工具链执行完成: restormer_deraining -> retinexformer_sdsd_indoor -> scunet_real_denoising_gan
[DEBUG T1-00] 💾 保存原始multi_modal_data用于reward计算
[DEBUG T1-00] 🔄 预处理multi_modal输入...
[DEBUG T1-00] ✅ 预处理完成，已保存原始图像用于reward
```

---

### 2. 工具调用统计

**位置**: `parallel_env.py` 每个turn后

```bash
[DEBUG TOOL CNT] ✅ 样本0 轮次1: 工具链成功执行 [restormer_deraining → retinexformer_sdsd_indoor → scunet_real_denoising_gan], 计数 = 1
[DEBUG TOOL CNT] ❌ 样本5 轮次1: 工具链执行失败，不计数
[DEBUG TOOL CNT] 样本3 轮次2: 给出answer，无工具调用
```

---

### 3. 尺寸异常检测（Batch结束时显示）

**位置**: `parallel_env.py` 第658-689行

```bash
================================================================================
⚠️  发现 15 个工具改变尺寸且不是整数倍关系的情况
================================================================================

工具: scunet_real_denoising_gan (8次异常)
--------------------------------------------------------------------------------
  案例1: T1-样本12
    输入尺寸: (1188, 1800)
    输出尺寸: (1176, 1792)
    比例: width=0.990x, height=0.996x
    差异: Δwidth=-12, Δheight=-8

  案例2: ...
  案例3: ...
  
  ... 还有 5 个类似案例

================================================================================
⚠️  这些工具可能需要检查API服务端的实现
================================================================================
```

**或者**:
```bash
✅ 所有工具都保持尺寸或按整数倍缩放（SR工具）
```

---

### 4. GT原图索引验证（新增！）⭐

**位置**: `parallel_env.py` 第856-878行

```bash
[DEBUG GT] expected_size=32, saved_extra_info_list len=32, needs_interleave=False
[DEBUG GT] i=0, orig_idx=0, sampling_params.n=8
[DEBUG GT] ✓ Using original_image from extra_info[0]

# 前3个样本的尺寸验证
[DEBUG GT SIZE] Sample 0: GT原图尺寸 = (868, 1012)
[DEBUG GT SIZE] Sample 0: 复原图尺寸 = (434, 506)
[DEBUG GT SIZE] Sample 1: GT原图尺寸 = (836, 980)
[DEBUG GT SIZE] Sample 1: 复原图尺寸 = (418, 490)
[DEBUG GT SIZE] Sample 2: GT原图尺寸 = (816, 996)
[DEBUG GT SIZE] Sample 2: 复原图尺寸 = (408, 498)
```

**关键信息**:
- `needs_interleave`: 是否需要interleave
- `orig_idx`: 实际使用的索引
- GT原图和复原图的尺寸对应

---

### 5. 图像历史保存

**位置**: `parallel_env.py` step执行中

```bash
[DEBUG step 1-00] 💾 保存原始PIL图像到历史
[DEBUG step 1-05] ⚠️  使用fetch后的图像（fallback）  ← 不应该出现
```

---

### 6. Reward计算详情

**位置**: `image_restoration.py` reward计算时

```bash
[DEBUG] 复原图尺寸（直接使用PIL）: (434, 506)
[DEBUG] 原图尺寸（直接使用PIL）: (868, 1012)
[DEBUG] 尺寸不匹配: restored=(434, 506) vs original=(868, 1012)
[DEBUG] 复原图已resize到: (868, 1012)
[DEBUG image_quality] ssim=0.8234, lpips=0.1567, psnr=28.45
```

---

## 🎯 如何使用这些调试信息

### 验证GT索引是否正确

**运行训练后查看**:

```bash
# 1. 查看needs_interleave的值
grep "needs_interleave" logs/*.log | head -10

# 2. 查看前3个样本的GT和复原图尺寸
grep "DEBUG GT SIZE" logs/*.log | head -20

# 3. 检查尺寸关系是否合理
```

**预期看到**:
```bash
[DEBUG GT SIZE] Sample 0: GT原图尺寸 = (868, 1012)
[DEBUG GT SIZE] Sample 0: 复原图尺寸 = (434, 506)  
# 比例: 2.0x, 2.0x ← 合理（SR×2后还差2倍）

[DEBUG GT SIZE] Sample 1: GT原图尺寸 = (836, 836)
[DEBUG GT SIZE] Sample 1: 复原图尺寸 = (836, 836)
# 比例: 1.0x ← 完美匹配（无low resolution）
```

**如果看到不合理的**:
```bash
[DEBUG GT SIZE] Sample 2: GT原图尺寸 = (800, 900)
[DEBUG GT SIZE] Sample 2: 复原图尺寸 = (512, 438)
# 比例: 1.56x, 2.05x ← 不一致！可能索引还是错的
```

---

### 验证工具是否改变尺寸

**Batch结束时会自动显示**:

```bash
✅ 所有工具都保持尺寸或按整数倍缩放（SR工具）
# 或
⚠️  发现 N 个工具改变尺寸...
```

---

### 验证索引逻辑

```bash
# 查看索引计算
grep "i=0, orig_idx=" logs/*.log

# 应该看到
[DEBUG GT] i=0, orig_idx=0, sampling_params.n=8
```

**关键**:
- 如果`needs_interleave=True`且`n=8`，则`orig_idx`应该是`i//8`
- 如果`needs_interleave=False`，则`orig_idx`应该是`i`

---

## 📊 完整的调试流程

```
Batch开始
  ↓
工具链执行（每个样本）
  ├─ 📏 显示工具输入尺寸
  ├─ 🔍 显示每个工具的处理
  ├─ ✅ 显示工具执行结果
  ├─ 📷 显示图像数据更新
  └─ 🎉 显示工具链完成
  ↓
Batch结束
  ├─ 🔍 尺寸异常统计（如果有）
  ├─ 📊 GT索引验证（前3个样本）
  └─ ✅ 所有工具保持尺寸（如果正常）
  ↓
Reward计算（每个样本）
  ├─ 💾 显示原始PIL保存
  ├─ 📏 显示复原图/GT尺寸
  ├─ ⚙️ 显示resize对齐
  └─ 📈 显示质量分数
```

---

## 🚀 下一步

**重新运行训练**，查看新的调试输出：

```bash
# 运行
bash examples/agent/IRv2.sh

# 等待一个batch完成，查看
tail -500 logs/*.log | grep "DEBUG GT SIZE"
```

**预期看到**:
```
[DEBUG GT SIZE] Sample 0: GT原图尺寸 = (868, 1012)
[DEBUG GT SIZE] Sample 0: 复原图尺寸 = (434, 506)
# 分析：868/434=2.0, 1012/506=2.0 ✅ 合理

[DEBUG GT SIZE] Sample 1: GT原图尺寸 = (836, 980)
[DEBUG GT SIZE] Sample 1: 复原图尺寸 = (418, 490)
# 分析：836/418=2.0, 980/490=2.0 ✅ 合理
```

**如果还不合理**，说明索引逻辑还需要调整。

---

**所有调试功能已就位！重新运行可以看到详细信息！** 🔍

