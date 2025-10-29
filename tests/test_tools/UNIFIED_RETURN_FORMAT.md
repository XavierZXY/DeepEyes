# 工具统一返回格式说明

## 🎯 重要发现

**所有图像修复工具使用统一的返回格式！**

## 📊 统一返回格式

所有工具的 `execute()` 方法在成功执行后，都返回相同的 `observation` 结构：

```python
obs = {
    "prompt": "...",
    "multi_modal_data": {"image": [restored_image]}
}
```

### 确认的工具列表（全部 10 个工具类）

| 工具类 | 返回格式 | 代码位置 | 确认 |
|--------|---------|----------|------|
| **DehazeFormerToolbox** | `obs['multi_modal_data']['image']` | Line 136-139 | ✅ |
| **SwinIRToolbox** | `obs['multi_modal_data']['image']` | Line 178-187 | ✅ |
| **MPRNetToolbox** | `obs['multi_modal_data']['image']` | Line 160-164 | ✅ |
| **RestormerToolbox** | `obs['multi_modal_data']['image']` | Line 172-181 | ✅ |
| **XRestormerToolbox** | `obs['multi_modal_data']['image']` | Line 137-141 | ✅ |
| **FBCNNToolbox** | `obs['multi_modal_data']['image']` | Line 161-165 | ✅ |
| **DeblurToolbox** (DRBNet) | `obs['multi_modal_data']['image']` | Line 146-150 | ✅ |
| **SCUNetToolbox** | `obs['multi_modal_data']['image']` | Line 180-184 | ✅ |
| **RetinexformerToolbox** | `obs['multi_modal_data']['image']` | Line 177-181 | ✅ |
| **BrighteningToolbox** | `obs['multi_modal_data']['image']` | Line 92-95 | ✅ |

---

## 🔧 代码示例

### DehazeFormerToolbox (典型示例)

```python
# Line 136-139 in DehazeFormerToolbox.py
obs = {
    "prompt": "\n<|im_start|>user\n" + "<tool_response>" + "<image>" + 
              self.user_prompt.format(tool_name=self.name) + 
              "</tool_response>" + "<|im_end|>\n<|im_start|>assistant\n",
    "multi_modal_data": {"image": [current_image]}  # ⭐ 修复后的图像
}
return obs, reward, done, info
```

### RestormerToolbox (典型示例)

```python
# Line 172-181 in RestormerToolbox.py
obs = {
    "prompt": (
        "\n<|im_start|>user\n"
        "<tool_response><image>"
        + formatted_prompt
        + "</tool_response>"
        "<|im_end|>\n<|im_start|>assistant\n"
    ),
    "multi_modal_data": {"image": [restored_image]}  # ⭐ 修复后的图像
}
return obs, reward, done, info
```

### 所有其他工具

完全相同的模式！只是变量名可能不同：
- `current_image` (DehazeFormer)
- `restored_image` (Restormer, MPRNet, SwinIR, FBCNN, XRestormer)
- `denoised_image` (SCUNet)
- `deblurred_image` (DeblurToolbox)
- `enhanced_image` (Retinexformer)
- `processed_pil_img` (BrighteningToolbox)

但结构完全一致！

---

## ⚠️ 重要：工具不更新 `self.multi_modal_data`

所有工具的 `execute()` 方法**都不会更新** `self.multi_modal_data`：

```python
def execute(self, action_string):
    # 从 self.multi_modal_data 读取输入图像
    source_image = self.multi_modal_data['image'][0]
    
    # 处理图像...
    restored_image = process_image(source_image)
    
    # 只在 obs 中返回修复后的图像
    obs = {
        "multi_modal_data": {"image": [restored_image]}
    }
    
    # ❌ 不更新 self.multi_modal_data
    # self.multi_modal_data 仍然是输入的退化图
    
    return obs, reward, done, info
```

### 验证

搜索所有工具的 `execute()` 方法，确认：
- ❌ 没有任何工具在 `execute()` 中执行 `self.multi_modal_data = ...`
- ✅ 所有工具只在 `reset()` 方法中设置 `self.multi_modal_data`

---

## 🛠️ 测试脚本的图像提取逻辑

### 修复前的逻辑（❌ 不完整）

```python
def apply_tool(self, tool_name, degraded_image):
    tool.multi_modal_data = {'image': [degraded_image]}
    observation, reward, done, info = tool.execute(action_string)
    
    # 方法1: 检查 observation['image']
    if isinstance(observation, dict) and 'image' in observation:
        return observation['image'][0]  # ❌ 所有工具都没有这个字段
    
    # 方法2: 检查 tool.multi_modal_data
    if hasattr(tool, 'multi_modal_data'):
        return tool.multi_modal_data['image'][0]  # ❌ 这还是输入的退化图！
    
    # 方法3: 检查 info
    if 'image' in info:
        return info['image']  # ❌ 所有工具都没有这个字段
```

**问题**：所有方法都失败，导致：
- 方法1 失败：`observation['image']` 不存在
- 方法2 返回错误：`tool.multi_modal_data['image'][0]` 是原始退化图
- 方法3 失败：`info['image']` 不存在

**结果**：测试脚本会提取到原始退化图，计算出来的改进率为 **0%**

### 修复后的逻辑（✅ 正确）

```python
def apply_tool(self, tool_name, degraded_image):
    tool.multi_modal_data = {'image': [degraded_image]}
    observation, reward, done, info = tool.execute(action_string)
    
    # 方法1: 从observation中提取图像（dict格式）
    if isinstance(observation, dict):
        # 方法1a: observation['image']
        if 'image' in observation:
            return observation['image'][0]  # ❌ 仍然没有
        
        # 方法1b: observation['multi_modal_data']['image'] ⭐ 新增
        if 'multi_modal_data' in observation:
            mmd = observation['multi_modal_data']
            if isinstance(mmd, dict) and 'image' in mmd:
                return mmd['image'][0]  # ✅ 成功！
    
    # 方法2 和方法3 作为备用...
```

**结果**：正确提取修复后的图像！

---

## 📈 测试结果对比

### 修复前（错误的图像提取）

```markdown
#### DehazeFormer
| Level | PSNR  | SSIM   | LPIPS  | PSNR↑ | SSIM↑ | LPIPS↓ | 成功率 |
|-------|-------|--------|--------|-------|-------|--------|--------|
| low   | 25.56 | 0.9462 | 0.0283 | +0.0% | +0.0% | +0.0%  | 100.0% |
```

**分析**：
- PSNR = 基线 PSNR（完全相同）
- 改进率 = 0%（因为提取的是原始退化图）
- 成功率 = 100%（工具执行成功，但提取错了图像）

### 修复后（正确的图像提取）

```markdown
#### DehazeFormer
| Level | PSNR  | SSIM   | LPIPS  | PSNR↑  | SSIM↑ | LPIPS↓  | 成功率 |
|-------|-------|--------|--------|--------|-------|---------|--------|
| low   | 20.54 | 0.8939 | 0.0438 | -28.8% | -8.2% | -252.7% | 100.0% |
```

**分析**：
- PSNR ≠ 基线 PSNR（确实不同）
- 改进率 ≠ 0%（真实的修复效果）
- 虽然这个例子中效果不好（负改进），但说明工具在真实运行

---

## 🎯 为什么需要这个修复

### 问题根源

1. **统一的返回格式**：所有工具都使用 `obs['multi_modal_data']['image']`
2. **测试脚本遗漏**：测试脚本没有检查这个路径
3. **误导性的成功率**：工具执行成功，但提取到错误的图像

### 影响范围

**所有 29 个工具都受影响**：
- 如果服务连接失败：成功率 0%（正确反映问题）
- 如果服务连接成功但图像提取错误：成功率 100% 但改进率 0%（误导性）

### 修复方法

在测试脚本的 `apply_tool()` 方法中添加：

```python
# 方法1b: observation['multi_modal_data']['image']
if 'multi_modal_data' in observation:
    mmd = observation['multi_modal_data']
    if isinstance(mmd, dict) and 'image' in mmd:
        restored_images = mmd['image']
        if restored_images and len(restored_images) > 0:
            return restored_images[0]
```

**位置**：`tests/test_tools/test_restoration_tools.py` Line 197-203

---

## 📝 最佳实践建议

### 1. 对于工具开发者

如果你要新增一个图像修复工具，**必须遵循统一的返回格式**：

```python
def execute(self, action_string):
    # 1. 从 self.multi_modal_data 获取输入图像
    source_image = self.multi_modal_data['image'][0]
    
    # 2. 处理图像
    restored_image = your_process_function(source_image)
    
    # 3. 构造标准返回格式 ⭐ 重要
    obs = {
        "prompt": "...",  # 提示文本
        "multi_modal_data": {"image": [restored_image]}  # 修复后的图像
    }
    
    # 4. 返回
    return obs, reward, done, info
```

### 2. 对于测试脚本开发者

提取图像时必须检查 `observation['multi_modal_data']['image']`：

```python
# ✅ 正确
if 'multi_modal_data' in observation:
    mmd = observation['multi_modal_data']
    if isinstance(mmd, dict) and 'image' in mmd:
        return mmd['image'][0]

# ❌ 错误（已废弃）
return tool.multi_modal_data['image'][0]  # 这是输入图像，不是输出！
```

### 3. 对于调试

如果发现测试结果异常（改进率为 0%），检查：

1. **服务是否可达**：
   ```bash
   curl http://$TOOL_SERVICE_IP:PORT/endpoint -X POST
   ```

2. **图像提取路径**：
   ```python
   print(f"observation keys: {observation.keys()}")
   if 'multi_modal_data' in observation:
       print(f"multi_modal_data: {observation['multi_modal_data'].keys()}")
   ```

3. **使用诊断工具**：
   ```bash
   cd tests/test_tools
   python diagnose_tool.py <tool_name> <test_image>
   ```

---

## 🔍 相关文件

### 工具实现文件
- `verl/workers/agent/envs/mm_process_engine/DehazeFormerToolbox.py`
- `verl/workers/agent/envs/mm_process_engine/SwinIRToolbox.py`
- `verl/workers/agent/envs/mm_process_engine/MPRNetToolbox.py`
- `verl/workers/agent/envs/mm_process_engine/RestormerToolbox.py`
- `verl/workers/agent/envs/mm_process_engine/XRestormerToolbox.py`
- `verl/workers/agent/envs/mm_process_engine/FBCNNToolbox.py`
- `verl/workers/agent/envs/mm_process_engine/DeblurToolbox.py`
- `verl/workers/agent/envs/mm_process_engine/SCUNetToolbox.py`
- `verl/workers/agent/envs/mm_process_engine/RetinexformerToolbox.py`
- `verl/workers/agent/envs/mm_process_engine/BrighteningToolbox.py`

### 测试脚本
- `tests/test_tools/test_restoration_tools.py` - 主测试脚本
- `tests/test_tools/diagnose_tool.py` - 诊断工具

### 文档
- `tests/test_tools/IP_FIX_DOCUMENTATION.md` - IP 地址修复文档
- `tests/test_tools/UNIFIED_RETURN_FORMAT.md` - 本文档

---

## ✅ 验证清单

在添加新工具或修改现有工具后，使用此清单验证：

- [ ] 工具返回格式使用 `obs['multi_modal_data']['image']`
- [ ] 工具**不**在 `execute()` 中修改 `self.multi_modal_data`
- [ ] 测试脚本能正确提取修复后的图像
- [ ] 使用诊断工具验证工具正常工作
- [ ] 改进率不为 0%（除非真的没有改进）
- [ ] 成功率符合预期

---

**文档创建时间**: 2025-10-20  
**版本**: v1.0  
**状态**: ✅ 已验证  
**维护者**: DeepEyes Team

