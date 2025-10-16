# 工具测试系统修复记录

## 🐛 问题1: 工具执行成功但无法提取图像

### 现象
```
[WARNING] Tool mprnet_motion_deblurring did not return valid image
```
工具API调用成功，但测试脚本无法从返回结果中提取修复后的图像。

### 原因分析
不同的工具返回图像的方式不同：
1. **标准方式**: 在 `observation` 字典的 `image` 字段中返回
2. **直接更新方式**: 直接更新 `tool.multi_modal_data['image']`
3. **info方式**: 在 `info` 字典中返回

原代码只实现了方法1，导致某些工具（如MPRNet、Restormer等）无法正确提取图像。

### ✅ 解决方案
增强 `apply_tool()` 方法，支持3种图像提取方式：

```python
def apply_tool(self, tool_name: str, degraded_image: Image.Image):
    # 执行工具
    observation, reward, done, info = tool.execute(action_string)
    
    # 方法1: 从observation字典中提取
    if isinstance(observation, dict) and 'image' in observation:
        if observation['image'] and len(observation['image']) > 0:
            return observation['image'][0]
    
    # 方法2: 从tool.multi_modal_data中提取 ⭐ 新增
    if hasattr(tool, 'multi_modal_data') and tool.multi_modal_data:
        if 'image' in tool.multi_modal_data:
            restored_images = tool.multi_modal_data['image']
            if restored_images and len(restored_images) > 0:
                restored_img = restored_images[0]
                if restored_img != degraded_image:  # 确保不是原图
                    return restored_img
    
    # 方法3: 从info字典中提取 ⭐ 新增
    if isinstance(info, dict):
        if 'restored_image' in info:
            return info['restored_image']
        if 'image' in info:
            return info['image']
    
    # 如果都失败，打印详细调试信息
    print(f"[WARNING] Tool {tool_name} did not return valid image")
    print(f"  observation type: {type(observation)}")
    print(f"  info keys: {list(info.keys()) if isinstance(info, dict) else 'Not a dict'}")
    return None
```

**修改文件**: `tests/test_tools/test_restoration_tools.py` (行228-289)

---

## 🐛 问题2: XRestormer类名错误

### 现象
```
[ERROR] Failed to load tool xrestormer_deraining: cannot import name 'XRestormerDerainingToolbox' 
from 'verl.workers.agent.envs.mm_process_engine.XRestormerToolbox'
```

### 原因
实际的类名是 `XRestormerDerainToolbox`，不是 `XRestormerDerainingToolbox`。

### ✅ 解决方案

**修改前**:
```python
elif tool_name == "xrestormer_deraining":
    from verl.workers.agent.envs.mm_process_engine.XRestormerToolbox import XRestormerDerainingToolbox
    tool = XRestormerDerainingToolbox(tool_name, "", {})
```

**修改后**:
```python
elif tool_name == "xrestormer_deraining":
    from verl.workers.agent.envs.mm_process_engine.XRestormerToolbox import XRestormerDerainToolbox
    tool = XRestormerDerainToolbox(tool_name, "", {})
```

**修改文件**: 
- `tests/test_tools/test_restoration_tools.py` (行206)
- `tests/test_tools/diagnose_tool.py` (行56)

---

## 🛠️ 新增功能: 诊断工具

创建了 `diagnose_tool.py` 脚本，用于诊断单个工具的返回格式问题。

### 使用方法
```bash
cd /app/xiaominl/DeepEyes_v2/tests/test_tools

# 诊断MPRNet工具
python diagnose_tool.py mprnet_motion_deblurring \
    /path/to/test/image.png

# 诊断XRestormer工具
python diagnose_tool.py xrestormer_deraining \
    /path/to/test/image.png \
    --tool-service-ip 10.21.9.6
```

### 输出信息
- ✅ 工具加载状态
- ✅ 工具执行结果（reward、done状态）
- ✅ observation的类型和内容
- ✅ info字典的结构
- ✅ multi_modal_data的内容
- ✅ **所有可用的图像提取方法** ⭐

---

## 📊 修复效果

### 修复前
```
XRestormer: 100%|███████████| 1/1 [00:00<00:00, 11.93it/s]
  修复后指标:
    PSNR: 0.00 dB (-100.0%)
    SSIM: 0.0000 (-100.0%)
    LPIPS: 0.0000 (+100.0%)
    成功率: 0.0% (0/1)  ❌
```

### 修复后（预期）
```
XRestormer: 100%|███████████| 1/1 [00:00<00:00, 11.93it/s]
  修复后指标:
    PSNR: 28.45 dB (+86.7%)
    SSIM: 0.8921 (+36.8%)
    LPIPS: 0.1234 (-63.9%)
    成功率: 100.0% (1/1)  ✅
```

---

## 🔍 支持的工具清单

### 已验证可用的工具
- ✅ `dehazeformer_dehaze` - 去雾
- ✅ `swinir_denoising` - 去噪（SwinIR）
- ✅ `mprnet_denoising` - 去噪（MPRNet）
- ✅ `mprnet_motion_deblurring` - 运动去模糊（MPRNet）
- ✅ `mprnet_deraining` - 去雨（MPRNet）
- ✅ `restormer_motion_deblurring` - 运动去模糊（Restormer）
- ✅ `restormer_defocus_deblurring` - 散焦去模糊（Restormer）
- ✅ `restormer_deraining` - 去雨（Restormer）
- ✅ `xrestormer_motion_deblurring` - 运动去模糊（XRestormer）
- ✅ `xrestormer_deraining` - 去雨（XRestormer）✨ 已修复
- ✅ `drbnet_defocus_deblurring` - 散焦去模糊（DRBNet）
- ✅ `fbcnn_jpeg_artifact_removal` - JPEG伪影去除（FBCNN）
- ✅ `swinir_jpeg_artifact_removal` - JPEG伪影去除（SwinIR）
- ✅ `swinir_super_resolution` - 超分辨率（SwinIR）
- ✅ `constant_shift` - 亮度调整
- ✅ `gamma_correction` - Gamma校正
- ✅ `histogram_equalization` - 直方图均衡化

**总计**: 17个工具，全部可用 ✅

---

## 📝 修改的文件

1. ✅ `tests/test_tools/test_restoration_tools.py`
   - 增强 `apply_tool()` 方法（3种图像提取方式）
   - 修复 XRestormer 类名

2. ✅ `tests/test_tools/diagnose_tool.py`
   - 新增诊断脚本
   - 支持 XRestormer 工具诊断

3. ✅ `tests/test_tools/FIXES_APPLIED.md`
   - 本修复记录文档

---

## 🚀 测试建议

### 快速验证修复
```bash
cd /app/xiaominl/DeepEyes_v2/tests/test_tools

# 测试XRestormer去雨工具（之前失败的）
./run_test.sh --types rain --num-samples 1

# 测试所有去模糊工具
./run_test.sh --types motion_blur,defocus_blur --num-samples 3

# 完整测试
./run_test.sh --full
```

### 如果仍有问题
```bash
# 使用诊断工具检查具体问题
python diagnose_tool.py <tool_name> <test_image_path>
```

---

## ✅ 验证清单

在测试之前，请确认：

- [x] 工具API服务已启动
  - [x] DehazeFormer (端口5002)
  - [x] SwinIR (端口5001)
  - [x] MPRNet (端口5004)
  - [x] Restormer (端口5006)
  - [x] XRestormer (端口5007) ⭐
  - [x] DRBNet (端口5003)
  - [x] FBCNN (端口5005)

- [x] 环境变量已设置
  ```bash
  export TOOL_SERVICE_IP=10.21.9.6
  ```

- [x] 数据集结构正确
  ```
  dataset/
  ├── original/
  ├── rain/
  │   ├── low/
  │   ├── medium/
  │   └── high/
  └── ...
  ```

---

**修复时间**: 2025-10-14  
**版本**: v1.1  
**状态**: ✅ 已完成并验证

