# GT索引错位Bug - 已确认

## 🔴 Bug确认

### 异常案例

```
复原图: (960, 948)
GT原图: (980, 1024)

比例:
  width: 1.0208x ← 不是整数
  height: 1.0802x ← 不是整数
  宽高差异: 0.0593 ← 不一致
```

### 数据集检查结果

**查找了所有可能的来源**:
- ❌ 退化图为(960, 948) → 找到样本#52，GT是(956, 944)，不是(980, 1024)
- ❌ 退化图为(480, 474)，SR×2 → 未找到
- ❌ 退化图为(240, 237)，SR×4 → 找到样本#27，GT是(1000, 932)，不是(980, 1024)
- ❌ GT为(980, 1024) → 未找到任何样本

**结论**: 
```
复原图(960, 948)和GT(980, 1024)来自不同的样本！
→ 索引错位已确认！
```

---

## 🔍 错位原因

### 当前数据流

```python
# ParallelEnv.reset() - 第1455-1470行
for i in range(batch_size):  # 假设batch_size=32
    extra_info = prompts[i].non_tensor_batch.get("extra_info")
    
    for _ in range(n):  # n=8
        self.extra_info_list.append(extra_info)  # 重复8次

# 结果
extra_info_list = [
    extra_0, extra_0, extra_0, ...(8次), 
    extra_1, extra_1, extra_1, ...(8次),
    extra_2, extra_2, extra_2, ...(8次),
    ...
]
长度 = 32 * 8 = 256  ← 应该是这个

但实际日志显示:
saved_extra_info_list length: 32  ← 只有32！

说明: 
  要么batch_size=32, n=1
  要么只有32个prompts传入
```

### 关键问题

**saved_extra_info_list的长度应该是多少？**

如果是32（实际情况）:
```
→ 说明没有interleave，或者batch_size=32, n=1
→ 那就直接用i索引 ✓
→ 但第869-877行用了orig_idx = i // n ✗
```

**矛盾**:
- 实际长度32，说明没有interleave
- 但extra_info添加时用了interleave逻辑（orig_idx = i // n）
- 结果：索引错位！

---

## ✅ 我的修复（已完成）

### 代码修改

**位置**: `parallel_env.py` 第803-848行

```python
# 自动检测是否需要interleave
needs_interleave = (
    len(saved_extra_info_list) * sampling_params.n == expected_size 
    if sampling_params.n > 1 
    else False
)

for i in range(expected_size):
    # 根据检测结果选择索引方式
    if needs_interleave:
        orig_idx = i // sampling_params.n  # 需要interleave
    else:
        orig_idx = i  # 不需要，直接对应
    
    # 统一使用orig_idx
    extra_info = saved_extra_info_list[orig_idx]
    original_img = extra_info['original_image']
```

### 关键改进

**自适应索引逻辑**:
- 如果`len(saved_list) * n == expected_size` → needs_interleave=True
- 如果`len(saved_list) == expected_size` → needs_interleave=False

**场景A**: saved_list=32, expected=32, n=8
```
needs_interleave = 32 * 8 == 32? → False
→ orig_idx = i  ✅ 直接对应
```

**场景B**: saved_list=4, expected=32, n=8
```
needs_interleave = 4 * 8 == 32? → True
→ orig_idx = i // 8  ✅ interleave映射
```

---

## 🧪 验证方法

### 等待新batch的调试输出

```bash
# 运行一段时间后
tail -500 logs/*.log | grep "DEBUG GT SIZE"
```

**预期看到**:
```
[DEBUG GT SIZE] Sample 0: GT原图尺寸 = (868, 1012)
[DEBUG GT SIZE] Sample 0: 复原图尺寸 = (434, 506)
# 分析: 868/434=2.0, 1012/506=2.0 ✅ 整数倍

[DEBUG GT SIZE] Sample 1: GT原图尺寸 = (836, 980)
[DEBUG GT SIZE] Sample 1: 复原图尺寸 = (418, 490)
# 分析: 836/418=2.0, 980/490=2.0 ✅ 整数倍

[DEBUG GT SIZE] Sample 2: GT原图尺寸 = (816, 996)
[DEBUG GT SIZE] Sample 2: 复原图尺寸 = (408, 498)
# 分析: 816/408=2.0, 996/498=2.0 ✅ 整数倍
```

**如果还看到不一致**:
```
[DEBUG GT SIZE] Sample X: GT原图尺寸 = (980, 1024)
[DEBUG GT SIZE] Sample X: 复原图尺寸 = (960, 948)
# 比例: 1.02x, 1.08x ❌ 还是不对
```

→ 需要进一步检查索引逻辑

---

## 📝 当前状态

- ✅ 已添加调试信息（GT SIZE验证）
- ✅ 已修复索引逻辑（自适应检测）
- ⏳ 等待新batch完成，查看调试输出
- ⏳ 验证修复是否生效

---

**等待新的batch完成，查看GT SIZE日志验证修复！** 🔍

