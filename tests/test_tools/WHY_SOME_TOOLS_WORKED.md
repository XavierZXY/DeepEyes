# 为什么之前有些工具能成功测试？

## 🔍 问题回顾

用户提出了一个非常好的问题：

> "既然所有工具都使用统一的返回格式 `obs['multi_modal_data']['image']`，
> 而测试脚本在修复前没有处理这个格式，
> **那为什么之前有些工具能成功（改进率不为0），有些工具失败（改进率为0）？**"

## 💡 答案：两种不同的实现模式

经过仔细检查，发现工具实际上有**两种不同的实现模式**：

### 模式A：同时更新 `self.multi_modal_data` 和返回 `obs['multi_modal_data']`（8个工具）✅

这些工具在 API 调用成功后会**显式更新** `self.multi_modal_data['image'][0]`：

```python
def _call_api(self, image, params):
    # 调用API
    result = requests.post(self.api_url, ...).json()
    
    if result.get('success'):
        restored_image = Image.open(...)
        
        # ⭐ 关键：更新 self.multi_modal_data
        self.multi_modal_data['image'][0] = restored_image
        
        return restored_image
```

**采用此模式的工具（8个）**：

| 工具 | 代码位置 | 确认 |
|------|---------|------|
| **SwinIRToolbox** | Line 64 | ✅ `self.multi_modal_data['image'][0] = restored_image` |
| **MPRNetToolbox** | Line 61 | ✅ `self.multi_modal_data['image'][0] = restored_image` |
| **RestormerToolbox** | Line 61 | ✅ `self.multi_modal_data['image'][0] = restored_image` |
| **XRestormerToolbox** | Line 66 | ✅ `self.multi_modal_data['image'][0] = restored_image` |
| **FBCNNToolbox** | Line 62 | ✅ `self.multi_modal_data['image'][0] = restored_image` |
| **SCUNetToolbox** | Line 62 | ✅ `self.multi_modal_data['image'][0] = denoised_image` |
| **RetinexformerToolbox** | Line 59 | ✅ `self.multi_modal_data['image'][0] = enhanced_image` |
| **BrighteningToolbox** | Line 90 | ✅ `self.multi_modal_data['image'][0] = processed_pil_img` |

### 模式B：只返回 `obs['multi_modal_data']`，不更新 `self.multi_modal_data`（2个工具）❌

这些工具**不会更新** `self.multi_modal_data['image'][0]`，只在 `obs` 中返回修复后的图像：

```python
def _call_api(self, image, params):
    # 调用API
    result = requests.post(self.api_url, ...).json()
    
    if result.get('success'):
        restored_image = Image.open(...)
        
        # ❌ 没有更新 self.multi_modal_data
        # self.multi_modal_data['image'][0] 仍然是输入的退化图
        
        return restored_image
```

**采用此模式的工具（2个）**：

| 工具 | 原因 | 结果 |
|------|------|------|
| **DehazeFormerToolbox** | 只读取 `self.multi_modal_data['image'][0]`，不更新 | ❌ 测试失败（改进率0%） |
| **DeblurToolbox (DRBNet)** | 只读取 `self.multi_modal_data['image'][0]`，不更新 | ❌ 测试失败（改进率0%） |

---

## 📊 修复前的测试脚本逻辑

修复前，测试脚本的图像提取逻辑是：

```python
def apply_tool(self, tool_name, degraded_image):
    tool.multi_modal_data = {'image': [degraded_image]}
    observation, reward, done, info = tool.execute(action_string)
    
    # 方法1: 检查 observation['image']
    if isinstance(observation, dict) and 'image' in observation:
        return observation['image'][0]  # ❌ 所有工具都没有这个字段
    
    # 方法2: 检查 tool.multi_modal_data ⭐ 关键
    if hasattr(tool, 'multi_modal_data'):
        restored_img = tool.multi_modal_data['image'][0]
        # ... 检查图像是否改变 ...
        return restored_img  # 无论如何都返回
    
    # 方法3: 检查 info
    if 'image' in info:
        return info['image']  # ❌ 所有工具都没有这个字段
```

**关键点**：方法2 会返回 `tool.multi_modal_data['image'][0]`

### 对于模式A的工具（成功）✅

```
1. 输入：degraded_image (退化图)
2. tool.multi_modal_data = {'image': [degraded_image]}
3. tool.execute() 调用 API
4. API 返回 restored_image
5. 工具内部：self.multi_modal_data['image'][0] = restored_image ⭐
6. 测试脚本方法2：return tool.multi_modal_data['image'][0]
7. 返回：restored_image（修复后的图像）✅
8. 结果：改进率 ≠ 0%，测试成功！
```

### 对于模式B的工具（失败）❌

```
1. 输入：degraded_image (退化图)
2. tool.multi_modal_data = {'image': [degraded_image]}
3. tool.execute() 调用 API
4. API 返回 restored_image
5. 工具内部：不更新 self.multi_modal_data ❌
6. 测试脚本方法2：return tool.multi_modal_data['image'][0]
7. 返回：degraded_image（仍然是输入的退化图）❌
8. 结果：改进率 = 0%，测试"失败"！
```

---

## 🎯 验证：查看之前的测试结果

### 成功的工具（采用模式A）

从 `test_results_20251015_105638/test_results.md`：

```markdown
#### Restormer (defocus_blur)
| Level  | PSNR  | SSIM   | LPIPS  | PSNR↑ | SSIM↑ | LPIPS↓ | 成功率 |
|--------|-------|--------|--------|-------|-------|--------|--------|
| high   | 26.00 | 0.7704 | 0.3151 | +7.5% | +22.4% | +43.4% | 100.0% | ✅

#### SwinIR (noise - low level)
| Level | PSNR  | SSIM   | LPIPS  | PSNR↑ | SSIM↑  | LPIPS↓ | 成功率 |
|-------|-------|--------|--------|-------|--------|--------|--------|
| low   | 32.90 | 0.9172 | 0.1907 | +3.8% | +13.8% | -37.6% | 100.0% | ✅

#### Restormer (rain)
| Level  | PSNR  | SSIM   | LPIPS  | PSNR↑  | SSIM↑ | LPIPS↓ | 成功率 |
|--------|-------|--------|--------|--------|-------|--------|--------|
| high   | 34.95 | 0.9554 | 0.1065 | +67.8% | +49.7% | +77.3% | 100.0% | ✅
```

✅ **这些工具有实际的改进效果**（改进率 ≠ 0%）

### 失败的工具（采用模式B）

```markdown
#### DehazeFormer (haze)
| Level  | PSNR  | SSIM   | LPIPS  | PSNR↑ | SSIM↑ | LPIPS↓ | 成功率 |
|--------|-------|--------|--------|-------|-------|--------|--------|
| low    | 25.56 | 0.9462 | 0.0283 | +0.0% | +0.0% | +0.0%  | 100.0% | ❌
| medium | 17.54 | 0.8701 | 0.0904 | +0.0% | +0.0% | +0.0%  | 100.0% | ❌
| high   | 12.19 | 0.7804 | 0.1793 | +0.0% | +0.0% | +0.0%  | 100.0% | ❌

#### DRBNet (defocus_blur)
| Level  | PSNR  | SSIM   | LPIPS  | PSNR↑ | SSIM↑ | LPIPS↓ | 成功率 |
|--------|-------|--------|--------|-------|-------|--------|--------|
| high   | 24.18 | 0.6296 | 0.5566 | +0.0% | +0.0% | +0.0%  | 100.0% | ❌
| low    | 25.66 | 0.7965 | 0.3551 | +0.0% | +0.0% | +0.0%  | 100.0% | ❌
| medium | 26.06 | 0.7187 | 0.4547 | +0.0% | +0.0% | +0.0%  | 100.0% | ❌
```

❌ **这些工具改进率全部为 0%**（指标与基线完全相同）

---

## 🔧 修复方案

### 问题根源

测试脚本依赖于工具更新 `self.multi_modal_data['image'][0]`，但并非所有工具都这样做。

### 解决方案

在测试脚本中添加对 `observation['multi_modal_data']['image']` 的支持：

```python
# 方法1: 从observation中提取图像
if isinstance(observation, dict):
    # 方法1a: observation['image']（已有）
    if 'image' in observation:
        return observation['image'][0]
    
    # 方法1b: observation['multi_modal_data']['image'] ⭐ 新增
    if 'multi_modal_data' in observation:
        mmd = observation['multi_modal_data']
        if isinstance(mmd, dict) and 'image' in mmd:
            return mmd['image'][0]  # ✅ 直接从返回值中获取
```

**优点**：
- ✅ 不依赖工具是否更新 `self.multi_modal_data`
- ✅ 适用于所有工具（模式A和模式B）
- ✅ 更符合工具的统一返回格式

---

## 📈 修复后的效果对比

### DehazeFormer（修复前 vs 修复后）

**修复前**（改进率0%，假成功）：
```markdown
| Level | PSNR  | SSIM   | LPIPS  | PSNR↑ | SSIM↑ | LPIPS↓ | 成功率 |
|-------|-------|--------|--------|-------|-------|--------|--------|
| low   | 25.56 | 0.9462 | 0.0283 | +0.0% | +0.0% | +0.0%  | 100.0% | ❌
```

**修复后**（真实效果）：
```markdown
| Level | PSNR  | SSIM   | LPIPS  | PSNR↑  | SSIM↑ | LPIPS↓  | 成功率 |
|-------|-------|--------|--------|--------|-------|---------|--------|
| low   | 20.54 | 0.8939 | 0.0438 | -28.8% | -8.2% | -252.7% | 100.0% | ✅
```

虽然这个案例中效果不好（负改进），但至少反映了真实情况！

---

## 🎓 经验教训

### 1. 工具实现不一致

虽然所有工具都使用统一的返回格式 `obs['multi_modal_data']['image']`，
但在内部实现上存在差异：
- 有些工具会更新 `self.multi_modal_data`（模式A）
- 有些工具不会更新（模式B）

### 2. 测试脚本的假设

原测试脚本假设所有工具都会更新 `self.multi_modal_data`，
这个假设对 80% 的工具有效（8/10），但对 20% 的工具失效（2/10）。

### 3. 误导性的成功率

- 成功率 100% 不代表工具正常工作
- 改进率 0% 才是真正的问题指标
- 需要综合多个指标判断测试是否真正成功

### 4. 正确的做法

测试脚本应该：
- ✅ **优先从返回值中提取图像**（`obs['multi_modal_data']['image']`）
- ❌ **不要依赖内部状态**（`self.multi_modal_data`）
- ✅ **使用工具的公开接口**（返回值）而非内部属性

---

## 📋 总结

| 问题 | 答案 |
|------|------|
| 为什么之前有些工具能成功？ | 因为它们会更新 `self.multi_modal_data['image'][0]`（模式A） |
| 为什么有些工具失败？ | 因为它们不更新 `self.multi_modal_data`（模式B） |
| 修复前测试脚本依赖什么？ | 依赖 `tool.multi_modal_data['image'][0]`（方法2） |
| 修复后测试脚本依赖什么？ | 依赖 `obs['multi_modal_data']['image'][0]`（方法1b） |
| 哪种方式更可靠？ | 修复后的方式（从返回值获取），不依赖内部状态 |

---

## 🔗 相关文档

- [UNIFIED_RETURN_FORMAT.md](./UNIFIED_RETURN_FORMAT.md) - 工具统一返回格式说明
- [IP_FIX_DOCUMENTATION.md](./IP_FIX_DOCUMENTATION.md) - IP 地址修复文档

---

**文档创建时间**: 2025-10-20  
**版本**: v1.0  
**作者**: AI Assistant & User

