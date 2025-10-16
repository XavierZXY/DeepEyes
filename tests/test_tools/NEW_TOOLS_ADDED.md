# 新增工具说明 - SCUNet & Retinexformer

## 📦 新增工具总览

本次更新添加了**12个新工具**，分为两大类：

| 类别 | 用途 | 工具数量 | API端口 |
|-----|------|---------|---------|
| **SCUNet** | 去噪 (Noise) | 4 | 5008 |
| **Retinexformer** | 低光增强 (Dark) | 8 | 5009 |

**总计**: 从17个工具增加到**29个工具** ✨

---

## 🎯 SCUNet工具系列 (去噪)

### 概述
SCUNet是一个先进的图像去噪工具，支持真实世界噪声和合成噪声。

### 4个工具变体

| 工具名称 | 显示名称 | 用途 | 适用场景 |
|---------|---------|------|---------|
| `scunet_real_denoising_psnr` | SCUNet-Real-PSNR | 真实噪声去除（PSNR优化） | 真实拍摄的噪声图像 |
| `scunet_real_denoising_gan` | SCUNet-Real-GAN | 真实噪声去除（GAN优化） | 视觉效果优先的真实噪声 |
| `scunet_color_denoising` | SCUNet-Color | 彩色图像去噪 | 合成的彩色噪声（15/25/50级） |
| `scunet_gray_denoising` | SCUNet-Gray | 灰度图像去噪 | 合成的灰度噪声（15/25/50级） |

### 使用示例

```bash
# 测试SCUNet真实噪声去除（PSNR版本）
python diagnose_tool.py scunet_real_denoising_psnr /path/to/noisy_image.png

# 测试SCUNet彩色去噪
python diagnose_tool.py scunet_color_denoising /path/to/noisy_image.png

# 批量测试所有SCUNet工具
./run_test.sh --types noise --num-samples 5
```

### 工具调用格式

```json
// 真实噪声去除（无参数）
{
    "name": "scunet_real_denoising_psnr",
    "arguments": {}
}

// 彩色去噪（可指定噪声级别）
{
    "name": "scunet_color_denoising",
    "arguments": {
        "noise_level": 25  // 可选: 15, 25, 50
    }
}
```

### API配置
- **端口**: 5008
- **端点**: `/process`
- **完整URL**: `http://{TOOL_SERVICE_IP}:5008/process`

---

## 🌙 Retinexformer工具系列 (低光增强)

### 概述
Retinexformer是基于Retinex理论的低光图像增强工具，针对不同数据集训练了多个模型。

### 8个工具变体

| 工具名称 | 显示名称 | 训练数据集 | 适用场景 |
|---------|---------|-----------|---------|
| `retinexformer_enhance` | Retinexformer-General | LOL-v2-Real | **通用推荐** ⭐ |
| `retinexformer_lol_v1` | Retinexformer-LOLv1 | LOL-v1 | LOL-v1数据集 |
| `retinexformer_lol_v2_real` | Retinexformer-LOLv2-Real | LOL-v2-Real | 真实低光场景 |
| `retinexformer_lol_v2_synthetic` | Retinexformer-LOLv2-Syn | LOL-v2-Synthetic | 合成低光场景 |
| `retinexformer_sdsd_indoor` | Retinexformer-SDSD-Indoor | SDSD-Indoor | 室内静态场景 |
| `retinexformer_sdsd_outdoor` | Retinexformer-SDSD-Outdoor | SDSD-Outdoor | 室外静态场景 |
| `retinexformer_sid` | Retinexformer-SID | SID | See in the Dark |
| `retinexformer_smid` | Retinexformer-SMID | SMID | 静态多场景 |
| `retinexformer_fivek` | Retinexformer-FiveK | MIT Adobe FiveK | 专业摄影 |

### 使用示例

```bash
# 测试通用Retinexformer工具（推荐）
python diagnose_tool.py retinexformer_enhance /path/to/dark_image.png

# 测试LOL-v1模型
python diagnose_tool.py retinexformer_lol_v1 /path/to/dark_image.png

# 批量测试所有低光增强工具
./run_test.sh --types dark --num-samples 3
```

### 工具调用格式

```json
// 通用工具（可选择任务）
{
    "name": "retinexformer_enhance",
    "arguments": {
        "task": "LOL_v2_real"  // 可选任务名称
    }
}

// 特定任务工具（无参数）
{
    "name": "retinexformer_lol_v1",
    "arguments": {}
}
```

### 可用的任务列表
通用工具 `retinexformer_enhance` 支持以下任务：
- `LOL_v1` - LOL-v1数据集
- `LOL_v2_real` - LOL-v2真实场景（默认）
- `LOL_v2_synthetic` - LOL-v2合成场景
- `SDSD_indoor` - 室内静态
- `SDSD_outdoor` - 室外静态
- `SID` - See in the Dark
- `SMID` - 静态多场景
- `FiveK` - MIT Adobe FiveK

### API配置
- **端口**: 5009
- **端点**: `/enhance`
- **完整URL**: `http://{TOOL_SERVICE_IP}:5009/enhance`

---

## 📊 工具统计对比

### 更新前（v1.0）
```
noise类型: 2个工具 (SwinIR, MPRNet)
dark类型: 3个工具 (Constant Shift, Gamma, Histogram)
总计: 17个工具
```

### 更新后（v1.1）
```
noise类型: 6个工具 ✨ (+4个SCUNet)
  - SwinIR, MPRNet
  - SCUNet-Real-PSNR, SCUNet-Real-GAN
  - SCUNet-Color, SCUNet-Gray

dark类型: 11个工具 ✨ (+8个Retinexformer)
  - Constant Shift, Gamma, Histogram
  - Retinexformer-General (推荐)
  - Retinexformer-LOLv1/v2, SDSD, SID, SMID, FiveK

总计: 29个工具 (+12个新工具)
```

---

## 🚀 测试新工具

### 快速测试SCUNet

```bash
cd /app/xiaominl/DeepEyes_v2/tests/test_tools

# 测试所有SCUNet工具（噪声）
./run_test.sh --types noise --num-samples 5 --output ./scunet_test
```

### 快速测试Retinexformer

```bash
# 测试所有Retinexformer工具（低光）
./run_test.sh --types dark --num-samples 5 --output ./retinexformer_test
```

### 对比不同工具

```bash
# 对比所有去噪工具（包括新的SCUNet）
./run_test.sh --types noise --num-samples 10 --output ./denoising_comparison

# 查看结果对比
cat ./denoising_comparison/test_results.md
```

---

## 📈 预期结果示例

### 噪声去除对比

```markdown
## noise

### 基线指标 (退化图 vs 原图)
| Level  | PSNR (dB) | SSIM   | LPIPS  |
|--------|-----------|--------|--------|
| low    | 25.34     | 0.7845 | 0.2123 |
| medium | 20.12     | 0.6534 | 0.3234 |
| high   | 15.67     | 0.5123 | 0.4567 |

### 工具修复效果

#### SwinIR
| Level  | PSNR  | SSIM   | LPIPS  | PSNR↑  | SSIM↑  | LPIPS↓ | 成功率 |
|--------|-------|--------|--------|--------|--------|--------|--------|
| low    | 32.45 | 0.9234 | 0.0987 | +28.0% | +17.7% | +53.5% | 100%   |

#### SCUNet-Real-PSNR ✨
| Level  | PSNR  | SSIM   | LPIPS  | PSNR↑  | SSIM↑  | LPIPS↓ | 成功率 |
|--------|-------|--------|--------|--------|--------|--------|--------|
| low    | 33.89 | 0.9456 | 0.0823 | +33.7% | +20.5% | +61.2% | 100%   |

#### SCUNet-Real-GAN ✨
| Level  | PSNR  | SSIM   | LPIPS  | PSNR↑  | SSIM↑  | LPIPS↓ | 成功率 |
|--------|-------|--------|--------|--------|--------|--------|--------|
| low    | 32.12 | 0.9567 | 0.0745 | +26.8% | +21.9% | +64.9% | 100%   |
```

### 低光增强对比

```markdown
## dark

### Retinexformer-General ✨ (推荐)
| Level  | PSNR  | SSIM   | LPIPS  | PSNR↑   | SSIM↑   | LPIPS↓  | 成功率 |
|--------|-------|--------|--------|---------|---------|---------|--------|
| low    | 28.45 | 0.8921 | 0.1234 | +125.3% | +78.4%  | +72.3%  | 100%   |
```

---

## 🔧 修改的文件

### 1. test_restoration_tools.py
**新增内容**:
- ✅ DEGRADATION_TO_TOOLS 字典中添加12个新工具
- ✅ load_tool() 方法中添加所有工具的导入逻辑

**修改行数**: 
- Line 33-81: 工具映射表
- Line 230-270: 工具加载逻辑

### 2. diagnose_tool.py
**新增内容**:
- ✅ 添加所有新工具的诊断支持
- ✅ 更新工具列表显示

**修改行数**:
- Line 93-133: 工具加载逻辑
- Line 136-149: 工具列表显示

---

## 🎯 完整工具清单（v1.1）

### 按退化类型分类

#### 1. 去雾 (Haze) - 1个工具
- DehazeFormer

#### 2. 去噪 (Noise) - 6个工具 ✨ (+4)
- SwinIR
- MPRNet
- **SCUNet-Real-PSNR** ⭐ 新增
- **SCUNet-Real-GAN** ⭐ 新增  
- **SCUNet-Color** ⭐ 新增
- **SCUNet-Gray** ⭐ 新增

#### 3. 运动去模糊 (Motion Blur) - 3个工具
- Restormer
- MPRNet
- XRestormer

#### 4. 散焦去模糊 (Defocus Blur) - 2个工具
- Restormer
- DRBNet

#### 5. 去雨 (Rain) - 3个工具
- Restormer
- MPRNet
- XRestormer

#### 6. JPEG伪影去除 (JPEG) - 2个工具
- SwinIR
- FBCNN

#### 7. 超分辨率 (Low Resolution) - 1个工具
- SwinIR

#### 8. 低光增强 (Dark) - 11个工具 ✨ (+8)
- Constant Shift
- Gamma Correction
- Histogram Equalization
- **Retinexformer-General** ⭐ 新增（推荐）
- **Retinexformer-LOLv1** ⭐ 新增
- **Retinexformer-LOLv2-Real** ⭐ 新增
- **Retinexformer-LOLv2-Synthetic** ⭐ 新增
- **Retinexformer-SDSD-Indoor** ⭐ 新增
- **Retinexformer-SDSD-Outdoor** ⭐ 新增
- **Retinexformer-SID** ⭐ 新增
- **Retinexformer-SMID** ⭐ 新增
- **Retinexformer-FiveK** ⭐ 新增

---

## 📋 工具详细说明

### SCUNet系列

#### SCUNet-Real-PSNR
```python
tool_name: "scunet_real_denoising_psnr"
class: SCUNetRealDenoisingPSNRToolbox
用途: 真实世界噪声去除，PSNR优化版本
参数: 无需参数
端口: 5008
```

#### SCUNet-Real-GAN
```python
tool_name: "scunet_real_denoising_gan"
class: SCUNetRealDenoisingGANToolbox
用途: 真实世界噪声去除，GAN优化版本，视觉效果更好
参数: 无需参数
端口: 5008
```

#### SCUNet-Color
```python
tool_name: "scunet_color_denoising"
class: SCUNetColorDenoisingToolbox
用途: 彩色图像去噪，支持不同噪声等级
参数: 
  - noise_level: 15, 25, 50 (默认25)
端口: 5008
```

#### SCUNet-Gray
```python
tool_name: "scunet_gray_denoising"
class: SCUNetGrayDenoisingToolbox
用途: 灰度图像去噪，支持不同噪声等级
参数:
  - noise_level: 15, 25, 50 (默认25)
端口: 5008
```

### Retinexformer系列

#### Retinexformer-General（推荐）⭐
```python
tool_name: "retinexformer_enhance"
class: RetinexformerToolbox
用途: 通用低光图像增强，支持选择不同预训练模型
参数:
  - task: LOL_v1, LOL_v2_real, LOL_v2_synthetic, SDSD_indoor, 
          SDSD_outdoor, SID, SMID, FiveK (默认: LOL_v2_real)
端口: 5009
推荐: ✅ 通用场景首选
```

#### Retinexformer-LOLv1
```python
tool_name: "retinexformer_lol_v1"
class: RetinexformerLOLv1Toolbox
数据集: LOL-v1
适用: LOL-v1测试集
端口: 5009
```

#### Retinexformer-LOLv2-Real
```python
tool_name: "retinexformer_lol_v2_real"
class: RetinexformerLOLv2RealToolbox
数据集: LOL-v2 Real
适用: 真实低光拍摄场景
端口: 5009
```

#### Retinexformer-LOLv2-Synthetic
```python
tool_name: "retinexformer_lol_v2_synthetic"
class: RetinexformerLOLv2SyntheticToolbox
数据集: LOL-v2 Synthetic
适用: 合成低光场景
端口: 5009
```

#### Retinexformer-SDSD-Indoor
```python
tool_name: "retinexformer_sdsd_indoor"
class: RetinexformerSDSDIndoorToolbox
数据集: SDSD Indoor
适用: 室内静态低光场景
端口: 5009
```

#### Retinexformer-SDSD-Outdoor
```python
tool_name: "retinexformer_sdsd_outdoor"
class: RetinexformerSDSDOutdoorToolbox
数据集: SDSD Outdoor
适用: 室外静态低光场景
端口: 5009
```

#### Retinexformer-SID
```python
tool_name: "retinexformer_sid"
class: RetinexformerSIDToolbox
数据集: See in the Dark (SID)
适用: 极低光场景
端口: 5009
```

#### Retinexformer-SMID
```python
tool_name: "retinexformer_smid"
class: RetinexformerSMIDToolbox
数据集: SMID
适用: 静态多场景低光
端口: 5009
```

#### Retinexformer-FiveK
```python
tool_name: "retinexformer_fivek"
class: RetinexformerFiveKToolbox
数据集: MIT Adobe FiveK
适用: 专业摄影后期
端口: 5009
```

---

## 🎨 测试场景示例

### 场景1: 对比所有去噪工具

```bash
# 测试噪声数据集，对比6个去噪工具的效果
./run_test.sh --types noise --num-samples 20 --output ./noise_full_comparison

# 查看结果
cat ./noise_full_comparison/test_results.md

# 预期看到6个工具的对比：
# - SwinIR
# - MPRNet  
# - SCUNet-Real-PSNR ⭐
# - SCUNet-Real-GAN ⭐
# - SCUNet-Color ⭐
# - SCUNet-Gray ⭐
```

### 场景2: 对比所有低光增强工具

```bash
# 测试暗图数据集，对比11个工具的效果
./run_test.sh --types dark --num-samples 10 --output ./lowlight_full_comparison

# 预期看到11个工具的对比：
# 传统方法：
# - Constant Shift
# - Gamma Correction
# - Histogram Equalization
# 
# Retinexformer系列（深度学习）⭐:
# - Retinexformer-General
# - Retinexformer-LOLv1/v2
# - ... 等8个变体
```

### 场景3: 选择最优工具

```bash
# 针对真实世界噪声，对比PSNR和GAN版本
./run_test.sh --types noise --levels high --num-samples 10

# 查看CSV，对比：
# - SCUNet-Real-PSNR (PSNR更高)
# - SCUNet-Real-GAN (视觉效果更好，LPIPS更低)
```

---

## ⚙️ 环境配置

### 启动新工具的API服务

```bash
# 启动SCUNet服务（端口5008）
# [需要根据实际情况配置]

# 启动Retinexformer服务（端口5009）
# [需要根据实际情况配置]

# 设置工具服务IP
export TOOL_SERVICE_IP=10.21.9.6
```

### 验证服务状态

```bash
# 检查SCUNet服务
curl http://10.21.9.6:5008/process -X POST

# 检查Retinexformer服务
curl http://10.21.9.6:5009/enhance -X POST

# 批量检查所有服务
for port in 5001 5002 5003 5004 5005 5006 5007 5008 5009; do
    echo "检查端口 $port..."
    nc -zv 10.21.9.6 $port
done
```

---

## 📝 类名对照表

### SCUNet类名
```python
# 导入示例
from verl.workers.agent.envs.mm_process_engine.SCUNetToolbox import (
    SCUNetRealDenoisingPSNRToolbox,
    SCUNetRealDenoisingGANToolbox,
    SCUNetColorDenoisingToolbox,
    SCUNetGrayDenoisingToolbox
)
```

### Retinexformer类名
```python
# 导入示例
from verl.workers.agent.envs.mm_process_engine.RetinexformerToolbox import (
    RetinexformerToolbox,              # 通用工具
    RetinexformerLOLv1Toolbox,
    RetinexformerLOLv2RealToolbox,
    RetinexformerLOLv2SyntheticToolbox,
    RetinexformerSDSDIndoorToolbox,
    RetinexformerSDSDOutdoorToolbox,
    RetinexformerSIDToolbox,
    RetinexformerSMIDToolbox,
    RetinexformerFiveKToolbox
)
```

---

## ✅ 完成检查清单

- [x] 添加SCUNet工具映射（4个）
- [x] 添加Retinexformer工具映射（8个）
- [x] 在test_restoration_tools.py中添加加载逻辑
- [x] 在diagnose_tool.py中添加加载逻辑
- [x] 更新工具列表显示
- [x] 创建说明文档
- [ ] 测试SCUNet工具（需要API服务运行）
- [ ] 测试Retinexformer工具（需要API服务运行）

---

## 🎉 总结

**新增工具**: 12个（SCUNet×4 + Retinexformer×8）  
**总工具数**: 29个  
**支持退化类型**: 8种  
**测试脚本**: 已完全支持  

### 使用建议

1. **去噪任务**:
   - 真实噪声首选: `scunet_real_denoising_psnr` 或 `scunet_real_denoising_gan`
   - 合成噪声: `scunet_color_denoising` 或 `scunet_gray_denoising`
   - 通用: `swinir_denoising` 或 `mprnet_denoising`

2. **低光增强任务**:
   - 通用场景首选: `retinexformer_enhance` ⭐
   - 特定数据集: 选择对应训练数据集的模型
   - 简单调整: `gamma_correction` 或 `histogram_equalization`

---

**更新时间**: 2025-10-14  
**版本**: v1.1  
**分支**: air_v6_degradation_tool_planning  
**状态**: ✅ 完成

