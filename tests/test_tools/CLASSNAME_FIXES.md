# 工具类名修复对照表

## 🐛 问题说明

在实现测试脚本时，发现多个工具的类名与预期不符（主要是拼写问题）。本文档记录所有修复的类名。

---

## ✅ 所有工具的正确类名

### 1. **SwinIR系列** (SwinIRToolbox.py)

| 工具名称 | ❌ 错误类名 | ✅ 正确类名 |
|---------|-----------|-----------|
| `swinir_denoising` | - | `SwinIRDenoisingToolbox` |
| `swinir_jpeg_artifact_removal` | `SwinIRJPEGToolbox` | `SwinIRJpegArtifactRemovalToolbox` |
| `swinir_super_resolution` | `SwinIRSuperResolutionToolbox` | `SwinIRSrToolbox` |

**注意**: 
- `Jpeg` 不是全大写的 `JPEG`
- 超分辨率工具是 `Sr` 不是 `SuperResolution`

---

### 2. **MPRNet系列** (MPRNetToolbox.py)

| 工具名称 | ❌ 错误类名 | ✅ 正确类名 |
|---------|-----------|-----------|
| `mprnet_denoising` | - | `MPRNetDenoisingToolbox` |
| `mprnet_motion_deblurring` | - | `MPRNetMotionDeblurringToolbox` |
| `mprnet_deraining` | `MPRNetDerainingToolbox` | `MPRNetDeraininingToolbox` |

**注意**: 
- 去雨工具是 `Derainining` (3个i)，不是 `Deraining` (2个i)

---

### 3. **Restormer系列** (RestormerToolbox.py)

| 工具名称 | ❌ 错误类名 | ✅ 正确类名 |
|---------|-----------|-----------|
| `restormer_motion_deblurring` | - | `RestormerMotionDeblurringToolbox` |
| `restormer_defocus_deblurring` | - | `RestormerDefocusDeblurringToolbox` |
| `restormer_deraining` | `RestormerDerainingToolbox` | `RestormerDerrainingToolbox` |

**注意**: 
- 去雨工具是 `Derraining` (2个r)，不是 `Deraining` (1个r)

---

### 4. **XRestormer系列** (XRestormerToolbox.py)

| 工具名称 | ❌ 错误类名 | ✅ 正确类名 |
|---------|-----------|-----------|
| `xrestormer_motion_deblurring` | - | `XRestormerMotionDeblurringToolbox` |
| `xrestormer_deraining` | `XRestormerDerainingToolbox` | `XRestormerDerainToolbox` |

**注意**: 
- 去雨工具是 `Derain` 不是 `Deraining`（没有ing后缀）

---

### 5. **FBCNN系列** (FBCNNToolbox.py)

| 工具名称 | ❌ 错误类名 | ✅ 正确类名 |
|---------|-----------|-----------|
| `fbcnn_jpeg_artifact_removal` | `FBCNNJPEGToolbox` | `FBCNNJpegArtifactRemovalToolbox` |
| `fbcnn_blind_quality_assessment` | - | `FBCNNBlindQualityAssessmentToolbox` |

**注意**: 
- `Jpeg` 不是全大写的 `JPEG`

---

### 6. **DeblurToolbox** (DeblurToolbox.py)

| 工具名称 | ❌ 错误类名 | ✅ 正确类名 |
|---------|-----------|-----------|
| `drbnet_defocus_deblurring` | `DRBNetDefocusDeblurringToolbox` | `DeblurToolbox` |

**注意**: 
- 只有一个通用的 `DeblurToolbox` 类，不是专门的 `DRBNetDefocusDeblurringToolbox`

---

### 7. **DehazeFormer** (DehazeFormerToolbox.py)

| 工具名称 | ✅ 正确类名 |
|---------|-----------|
| `dehazeformer_dehaze` | `DehazeFormerToolbox` |

**注意**: ✅ 类名正确，无需修改

---

### 8. **BrighteningToolbox** (BrighteningToolbox.py)

| 工具名称 | ✅ 正确类名 |
|---------|-----------|
| `constant_shift` | `BrighteningToolbox` |
| `gamma_correction` | `BrighteningToolbox` |
| `histogram_equalization` | `BrighteningToolbox` |

**注意**: ✅ 三个工具共用一个基类，类名正确

---

## 📝 修复的文件

以下文件已全部修复：

1. ✅ `tests/test_tools/test_restoration_tools.py` (主测试脚本)
   - Line 179-180: SwinIR JPEG工具
   - Line 182-183: SwinIR超分辨率工具
   - Line 191-192: MPRNet去雨工具
   - Line 200-201: Restormer去雨工具
   - Line 206-207: XRestormer去雨工具
   - Line 209-210: DRBNet工具
   - Line 212-213: FBCNN工具

2. ✅ `tests/test_tools/diagnose_tool.py` (诊断脚本)
   - 添加了所有工具的正确类名
   - 分类组织（DehazeFormer, SwinIR, MPRNet, Restormer, XRestormer, FBCNN, DeblurToolbox, Brightening）

---

## 🔍 完整的工具类名映射表

### 导入语句参考

```python
# DehazeFormer
from verl.workers.agent.envs.mm_process_engine.DehazeFormerToolbox import DehazeFormerToolbox

# SwinIR
from verl.workers.agent.envs.mm_process_engine.SwinIRToolbox import (
    SwinIRDenoisingToolbox,
    SwinIRJpegArtifactRemovalToolbox,  # 注意: Jpeg不是JPEG
    SwinIRSrToolbox                     # 注意: Sr不是SuperResolution
)

# MPRNet
from verl.workers.agent.envs.mm_process_engine.MPRNetToolbox import (
    MPRNetDenoisingToolbox,
    MPRNetMotionDeblurringToolbox,
    MPRNetDeraininingToolbox  # 注意: Derainining (3个i)
)

# Restormer
from verl.workers.agent.envs.mm_process_engine.RestormerToolbox import (
    RestormerMotionDeblurringToolbox,
    RestormerDefocusDeblurringToolbox,
    RestormerDerrainingToolbox  # 注意: Derraining (2个r)
)

# XRestormer
from verl.workers.agent.envs.mm_process_engine.XRestormerToolbox import (
    XRestormerMotionDeblurringToolbox,
    XRestormerDerainToolbox  # 注意: Derain (无ing后缀)
)

# FBCNN
from verl.workers.agent.envs.mm_process_engine.FBCNNToolbox import (
    FBCNNJpegArtifactRemovalToolbox,  # 注意: Jpeg不是JPEG
    FBCNNBlindQualityAssessmentToolbox
)

# DeblurToolbox (DRBNet)
from verl.workers.agent.envs.mm_process_engine.DeblurToolbox import DeblurToolbox

# Brightening
from verl.workers.agent.envs.mm_process_engine.BrighteningToolbox import BrighteningToolbox
```

---

## ⚠️ 拼写陷阱总结

### 陷阱1: Jpeg vs JPEG
- ❌ `JPEG` (全大写)
- ✅ `Jpeg` (首字母大写)
- 影响工具: SwinIR, FBCNN

### 陷阱2: Deraining的多种拼写
- ✅ `Derainining` (3个i) - MPRNet
- ✅ `Derraining` (2个r) - Restormer  
- ✅ `Derain` (无ing) - XRestormer
- ❌ `Deraining` (标准拼写，但这里不用)

### 陷阱3: 超分辨率
- ❌ `SuperResolution`
- ✅ `Sr` (缩写)

### 陷阱4: DRBNet
- ❌ `DRBNetDefocusDeblurringToolbox`
- ✅ `DeblurToolbox` (通用类名)

---

## ✅ 验证结果

所有工具类名已修复，现在可以正确加载：

```bash
# 验证所有工具都可以加载
cd /app/xiaominl/DeepEyes_v2/tests/test_tools

# 测试各个工具
python diagnose_tool.py mprnet_deraining /path/to/test.png
python diagnose_tool.py restormer_deraining /path/to/test.png
python diagnose_tool.py xrestormer_deraining /path/to/test.png
python diagnose_tool.py swinir_jpeg_artifact_removal /path/to/test.png
python diagnose_tool.py fbcnn_jpeg_artifact_removal /path/to/test.png
python diagnose_tool.py drbnet_defocus_deblurring /path/to/test.png
```

---

## 📊 修复统计

| 类别 | 错误数量 | 状态 |
|-----|---------|------|
| SwinIR | 2 | ✅ 已修复 |
| MPRNet | 1 | ✅ 已修复 |
| Restormer | 1 | ✅ 已修复 |
| XRestormer | 1 | ✅ 已修复 |
| FBCNN | 1 | ✅ 已修复 |
| DeblurToolbox | 1 | ✅ 已修复 |
| **总计** | **7** | **✅ 全部修复** |

---

## 🚀 现在可以正常使用了

```bash
cd /app/xiaominl/DeepEyes_v2/tests/test_tools

# 快速测试（验证修复）
./run_test.sh --quick --types rain

# 完整测试所有工具
./run_test.sh --full
```

---

**修复时间**: 2025-10-14  
**版本**: v1.2  
**状态**: ✅ 所有类名已验证并修复

