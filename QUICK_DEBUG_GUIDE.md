# 快速调试指南

## 🎯 运行训练后查看这些关键日志

### 1️⃣ 验证GT原图索引是否正确 ⭐ 最重要

```bash
grep "DEBUG GT SIZE" logs/*.log | head -20
```

**预期输出**（正确的情况）:
```
[DEBUG GT SIZE] Sample 0: GT原图尺寸 = (868, 1012)
[DEBUG GT SIZE] Sample 0: 复原图尺寸 = (434, 506)
# 比例: 2.0x ✅ 合理（SR×2后差2倍）

[DEBUG GT SIZE] Sample 1: GT原图尺寸 = (836, 836)
[DEBUG GT SIZE] Sample 1: 复原图尺寸 = (836, 836)
# 比例: 1.0x ✅ 完美（无low resolution）

[DEBUG GT SIZE] Sample 2: GT原图尺寸 = (816, 996)
[DEBUG GT SIZE] Sample 2: 复原图尺寸 = (408, 498)
# 比例: 2.0x ✅ 合理
```

**异常情况**（索引错位）:
```
[DEBUG GT SIZE] Sample 2: GT原图尺寸 = (796, 888)
[DEBUG GT SIZE] Sample 2: 复原图尺寸 = (512, 438)
# 比例: 1.55x, 2.03x ❌ 宽高不一致！索引可能错了
```

---

### 2️⃣ 检查工具是否改变尺寸

**Batch结束时自动显示**:

```bash
tail -100 logs/*.log | grep -A50 "所有工具都保持\|发现.*工具改变"
```

**正常输出**:
```
✅ 所有工具都保持尺寸或按整数倍缩放（SR工具）
```

**异常输出**:
```
⚠️  发现 N 个工具改变尺寸且不是整数倍关系的情况
工具: xxx (Y次异常)
  案例1: ...
```

---

### 3️⃣ 检查interleave逻辑

```bash
grep "needs_interleave" logs/*.log | head -5
```

**输出**:
```
[DEBUG GT] expected_size=32, saved_extra_info_list len=32, needs_interleave=False
[DEBUG GT] i=0, orig_idx=0, sampling_params.n=8
```

**关键**:
- `needs_interleave=False` → saved_list已经是正确长度，直接使用
- `needs_interleave=True` → 需要interleave映射

---

### 4️⃣ 检查fetch_image是否被移除

```bash
grep "after fetch_image" logs/*.log | wc -l
```

**应该输出**: `0` ← 没有fetch_image了 ✅

**同时检查**:
```bash
grep "保存原始PIL图像" logs/*.log | wc -l
```

**应该输出**: `>0` ← 保存了原始PIL ✅

---

### 5️⃣ 检查工具链统计

```bash
grep "DEBUG TOOL CNT.*✅" logs/*.log | wc -l
grep "DEBUG TOOL CNT.*❌" logs/*.log | wc -l
```

**比例**: ✅数量 应该 >> ❌数量

---

## 📊 一键诊断脚本

```bash
#!/bin/bash
LOG="logs/debug_for_AIR_multideg_plan_ref_bs32_n8_spv13_lr1e-6_datarand_mi300.log"

echo "1. GT索引验证（前6个样本）"
echo "================================"
grep "DEBUG GT SIZE" $LOG | head -12
echo ""

echo "2. Interleave逻辑"
echo "================================"
grep "needs_interleave" $LOG | head -3
echo ""

echo "3. 工具尺寸检测"
echo "================================"
tail -100 $LOG | grep -A20 "所有工具都保持\|发现.*工具改变" | head -25
echo ""

echo "4. 工具链统计"
echo "================================"
SUCCESS=$(grep "DEBUG TOOL CNT.*✅" $LOG | wc -l)
FAIL=$(grep "DEBUG TOOL CNT.*❌" $LOG | wc -l)
echo "  成功: $SUCCESS"
echo "  失败: $FAIL"
echo ""

echo "5. fetch_image检查"
echo "================================"
FETCH=$(grep "after fetch_image" $LOG | wc -l)
SAVE_PIL=$(grep "保存原始PIL" $LOG | wc -l)
echo "  fetch_image使用: $FETCH (应该=0)"
echo "  保存原始PIL: $SAVE_PIL (应该>0)"
```

保存为 `quick_check.sh` 并运行：
```bash
bash quick_check.sh
```

---

## ✅ 所有调试功能列表

| 功能 | 触发时机 | 位置 | 作用 |
|------|---------|------|------|
| 工具链执行追踪 | 每个工具 | 执行中 | 详细的执行日志 |
| 工具调用统计 | 每个turn | 执行后 | 统计成功/失败 |
| 尺寸异常检测 | Batch结束 | 汇总显示 | 找出异常工具 |
| **GT索引验证** | **Batch结束** | **新增** | **验证GT对应** ⭐ |
| Interleave检测 | Batch结束 | 新增 | 显示索引逻辑 |
| 图像保存确认 | 每个step | 执行中 | 确认保存PIL |
| Reward详情 | Reward计算 | 计算中 | 尺寸和质量 |

---

**重新运行训练，所有调试信息都会显示！** 🎉

