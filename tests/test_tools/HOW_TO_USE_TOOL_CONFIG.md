# 工具池配置使用指南

## 📁 配置文件

**文件**: `tool_config.py`  
**用途**: 集中管理所有29个测试工具，通过注释来选择要测试的工具

---

## ✨ 核心功能

### 按退化类型分组管理
所有工具按8种退化类型分组，清晰明了

### 通过注释控制测试
在不需要测试的工具前添加 `#` 即可跳过该工具

---

## 🔧 使用方法

### 编辑 `tool_config.py`

打开文件，找到要修改的退化类型，注释掉不需要的工具：

```python
"noise": [
    ("swinir_denoising", "SwinIR"),                      # 保留，会测试
    # ("mprnet_denoising", "MPRNet"),                    # 注释掉，不测试
    ("scunet_real_denoising_psnr", "SCUNet-Real-PSNR"), # 保留
    ("scunet_real_denoising_gan", "SCUNet-Real-GAN"),   # 保留
    # ("scunet_color_denoising", "SCUNet-Color"),        # 注释掉
    # ("scunet_gray_denoising", "SCUNet-Gray"),          # 注释掉
],
```

**结果**: 只会测试 SwinIR、SCUNet-Real-PSNR、SCUNet-Real-GAN 三个工具

---

## 📋 常用配置示例

### 示例1: 只测试SCUNet工具

```python
"noise": [
    # 注释掉传统工具
    # ("swinir_denoising", "SwinIR"),
    # ("mprnet_denoising", "MPRNet"),
    
    # 只保留SCUNet系列
    ("scunet_real_denoising_psnr", "SCUNet-Real-PSNR"),
    ("scunet_real_denoising_gan", "SCUNet-Real-GAN"),
    ("scunet_color_denoising", "SCUNet-Color"),
    ("scunet_gray_denoising", "SCUNet-Gray"),
],
```

### 示例2: 只测试Retinexformer通用工具

```python
"dark": [
    # 注释掉传统方法
    # ("constant_shift", "Constant Shift"),
    # ("gamma_correction", "Gamma Correction"),
    # ("histogram_equalization", "Histogram Equalization"),
    
    # 只保留通用Retinexformer
    ("retinexformer_enhance", "Retinexformer-General"),
    
    # 注释掉所有专用模型
    # ("retinexformer_lol_v1", "Retinexformer-LOLv1"),
    # ("retinexformer_lol_v2_real", "Retinexformer-LOLv2-Real"),
    # ... 其他全部注释掉
],
```

### 示例3: 每种类型只测试最佳工具

```python
"noise": [
    ("scunet_real_denoising_psnr", "SCUNet-Real-PSNR"),  # 只保留这个
],

"dark": [
    ("retinexformer_enhance", "Retinexformer-General"),  # 只保留这个
],
```

---

## 🔍 查看当前配置

运行配置文件查看当前激活的工具：

```bash
cd /app/xiaominl/DeepEyes_v2/tests/test_tools
python tool_config.py

# 输出示例:
# ================================================================================
# 当前激活的工具配置
# ================================================================================
# 
# 【haze】 - 1 个工具
#   ✓ DehazeFormer                       (dehazeformer_dehaze)
# 
# 【noise】 - 6 个工具
#   ✓ SwinIR                            (swinir_denoising)
#   ✓ MPRNet                            (mprnet_denoising)
#   ✓ SCUNet-Real-PSNR                  (scunet_real_denoising_psnr)
#   ...
# 
# ================================================================================
# 总计: 29 个工具
# ================================================================================
```

---

## 📊 预设配置方案

`tool_config.py` 提供了3种预设方案，可在文件底部切换：

### 方案1: PRESET_QUICK（快速测试）
```python
ACTIVE_TOOL_CONFIG = PRESET_QUICK  # 每种类型1-2个工具，约10个
```

### 方案2: PRESET_STANDARD（标准测试）
```python
ACTIVE_TOOL_CONFIG = PRESET_STANDARD  # 主要工具，约18个
```

### 方案3: TOOL_POOL（完整测试，默认）
```python
ACTIVE_TOOL_CONFIG = TOOL_POOL  # 所有29个工具（可自定义注释）
```

---

## ⚠️ 关于工具参数

### 当前实现
- **所有工具都使用默认参数**（空的 `arguments: {}`）
- `scunet_color_denoising` → 固定使用 `noise_level=25`
- `scunet_gray_denoising` → 固定使用 `noise_level=25`
- `retinexformer_enhance` → 固定使用默认任务 `LOL_v2_real`

### 如果需要测试不同参数
您可以：
1. **修改工具默认值**（在对应的Toolbox文件中）
2. **手动创建不同配置的工具变体**（在tool_config.py中）
3. **让我实现自动参数选择功能**（我刚才删除的那个）

---

## 📝 文件清单

当前 `tests/test_tools/` 目录下的文件：

| 文件 | 用途 | 状态 |
|-----|------|------|
| `tool_config.py` | 工具池配置 | ✅ 保留 |
| `test_restoration_tools.py` | 主测试脚本 | ✅ 保留 |
| `run_test.sh` | 运行脚本 | ✅ 保留 |
| `diagnose_tool.py` | 诊断工具 | ✅ 保留 |
| `README.md` | 完整文档 | ✅ 保留 |
| `QUICK_START.md` | 快速指南 | ✅ 保留 |
| ~~`tool_params_config.py`~~ | ~~参数配置~~ | ❌ 已删除 |
| ~~`TOOL_CONFIG_GUIDE.md`~~ | ~~参数指南~~ | ❌ 已删除 |

---

**总结**: 
- ✅ 工具池配置 `tool_config.py` 保留
- ✅ 所有工具使用默认参数
- ✅ `scunet_color_denoising` 固定使用 `noise_level=25`（默认值）
