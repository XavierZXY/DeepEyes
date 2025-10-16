# 📋 退化类型与工具映射完整列表

**数据集**: air_d1_sp9_up2_balanced  
**样本数**: 128  
**退化类型**: 8种

---

## 🎯 数据集中的退化类型分布

| 退化类型 | 样本数 | 描述 |
|---------|--------|------|
| dark | 21 | 暗光/欠曝光 |
| motion blur | 20 | 运动模糊 |
| rain | 18 | 雨滴/雨痕 |
| haze | 17 | 雾霾/去雾 |
| jpeg compression artifact | 16 | JPEG压缩伪影 |
| low resolution | 13 | 低分辨率 |
| defocus blur | 13 | 散焦模糊 |
| noise | 10 | 噪声 |

**总计**: 128 个样本

---

## 🔧 工具与退化类型的对应关系

### 1. Noise（噪声）- 10个样本
**对应工具**:
- ✅ `swinir_denoising` - SwinIR去噪
- ✅ `mprnet_denoising` - MPRNet去噪

### 2. Motion Blur（运动模糊）- 20个样本
**对应工具**:
- ✅ `restormer_motion_deblurring` - Restormer运动去模糊
- ✅ `xrestormer_motion_deblurring` - XRestormer运动去模糊
- ✅ `mprnet_motion_deblurring` - MPRNet运动去模糊

### 3. Defocus Blur（散焦模糊）- 13个样本
**对应工具**:
- ✅ `restormer_defocus_deblurring` - Restormer散焦去模糊
- ✅ `drbnet_defocus_deblurring` - DRBNet散焦去模糊

### 4. Rain（雨滴）- 18个样本
**对应工具**:
- ✅ `restormer_deraining` - Restormer去雨
- ✅ `xrestormer_deraining` - XRestormer去雨
- ✅ `mprnet_deraining` - MPRNet去雨

### 5. JPEG Compression Artifact（JPEG压缩伪影）- 16个样本
**对应工具**:
- ✅ `swinir_jpeg_artifact_removal` - SwinIR JPEG伪影去除
- ✅ `fbcnn_jpeg_artifact_removal` - FBCNN JPEG伪影去除

### 6. Low Resolution（低分辨率）- 13个样本
**对应工具**:
- ✅ `swinir_super_resolution` - SwinIR超分辨率（2倍）

### 7. Haze（雾霾）- 17个样本
**对应工具**:
- ✅ `dehazeformer_dehaze` - DehazeFormer去雾

### 8. Dark（暗光）- 21个样本
**对应工具**:
- ⚠️ 目前测试脚本中**没有包含**亮度调整工具
- 训练中可用: `constant_shift`, `gamma_correction`, `histogram_equalization`
- 建议: 添加BrighteningToolbox工具

---

## ⚠️ 缺失的工具

### BrighteningToolbox（亮度调整）
**文件**: `verl/workers/agent/envs/mm_process_engine/BrighteningToolbox.py`

**支持的工具**:
- `constant_shift` - 常数偏移
- `gamma_correction` - Gamma校正
- `histogram_equalization` - 直方图均衡化

**针对退化**: dark（暗光，21个样本）

**建议**: 将这些工具添加到测试脚本中

---

## 📊 工具覆盖率分析

### 有对应工具的退化（7种）
- ✅ noise - 2个工具
- ✅ motion blur - 3个工具
- ✅ defocus blur - 2个工具
- ✅ rain - 3个工具
- ✅ jpeg compression artifact - 2个工具
- ✅ low resolution - 1个工具
- ✅ haze - 1个工具

### 缺少对应工具的退化（1种）
- ⚠️ dark - 0个工具（BrighteningToolbox未包含）

---

## 🔧 工具API端点汇总

| 工具 | API端点 | 参数 |
|------|---------|------|
| SwinIR系列 | `10.21.9.6:5001/process` | task + 参数 |
| Restormer系列 | `10.21.9.6:5006/process` | task |
| XRestormer系列 | `10.21.9.6:5007/process` | task |
| MPRNet系列 | `10.21.9.6:5004/process` | task |
| FBCNN | `10.21.9.6:5005/process` | task + jpeg |
| DRBNet | `10.21.9.6:5003/deblur` | (无)，文件字段image_c |
| DehazeFormer | `10.21.9.6:5002/process` | task |
| BrighteningToolbox | ❓ 未知 | ❓ |

---

## 💡 建议

### 1. 添加亮度调整工具
为21个dark样本添加对应的处理工具。

### 2. 测试覆盖率
当前可测试：
- 107个样本（有对应工具）
- 21个dark样本（无对应工具）

### 3. 工具数量分布
- 1个工具: haze, low resolution
- 2个工具: noise, defocus blur, jpeg compression artifact
- 3个工具: motion blur, rain
- 0个工具: dark ⚠️

---

**更新时间**: 2025-10-13  
**数据集**: air_d1_sp9_up2_balanced  
**完整度**: 7/8 退化类型有对应工具
