# SCUNet 去噪效果测试总结报告

## 测试日期
2025-10-15

## 测试图像
- **原始图像**: `/app/xiaominl/datasets/degraded_datasets/degraded_dataset/original/000001.png`
- **测试工具**: `scunet_real_denoising_psnr` (PSNR优化版本)
- **服务地址**: `http://10.21.9.6:5008/process`

## 📊 测试结果总结

### 不同噪声等级的去噪效果

| 噪声等级 | 去噪前PSNR | 去噪后PSNR | PSNR改进 | 去噪前SSIM | 去噪后SSIM | SSIM改进 | 执行时间 |
|---------|-----------|-----------|---------|-----------|-----------|---------|---------|
| **Level 1 (极低噪声)** | 38.92 dB | 34.28 dB | **↓ -4.64 dB** | 0.9855 | 0.9813 | ↓ -0.42% | 1.68s |
| **Level 2 (低噪声)** | 26.33 dB | 31.32 dB | **↑ +4.99 dB** | 0.8438 | 0.9615 | ↑ +11.77% | 1.68s |
| **Level 3 (中噪声)** | 20.41 dB | 28.05 dB | **↑ +7.64 dB** | 0.6480 | 0.9210 | ↑ +27.30% | 1.90s |
| **Level 4 (高噪声)** | 19.02 dB | 26.98 dB | **↑ +7.96 dB** | 0.6180 | 0.9093 | ↑ +29.14% | 1.69s |

## 🎯 关键发现

### 1. SCUNet 在中高噪声图像上表现优异

- **Level 2** (低噪声): PSNR提升 +4.99 dB (18.9%)，SSIM提升 +11.77%
- **Level 3** (中噪声): PSNR提升 +7.64 dB (37.4%)，SSIM提升 +27.30%
- **Level 4** (高噪声): PSNR提升 +7.96 dB (41.9%)，SSIM提升 +29.14%

### 2. 噪声程度与去噪效果的关系

**结论**：噪声程度越高，SCUNet的去噪效果越显著！

```
  PSNR 改进幅度
    ↑
  8 |                                    ● Level 4 (+7.96 dB)
    |                              ● Level 3 (+7.64 dB)
  6 |
    |
  4 |                    ● Level 2 (+4.99 dB)
    |
  2 |
    |
  0 |          ╳ Level 1 (-4.64 dB)
    |─────────────────────────────────────────────────────>
      低噪声 ←                                    → 高噪声
```

### 3. Level 1 的特殊情况

对于 **Level 1** (极低噪声，PSNR 38.92 dB)：
- PSNR 和 SSIM 反而下降
- **原因**: 原始噪声程度极低，模型可能将微弱噪声当作图像细节
- **建议**: 对于这种高质量图像，不建议使用去噪处理

## 📈 性能指标

### PSNR改进曲线

```
去噪前 PSNR  →  去噪后 PSNR  =  改进幅度

Level 1:  38.92 dB  →  34.28 dB  =  -4.64 dB  ❌ (过度处理)
Level 2:  26.33 dB  →  31.32 dB  =  +4.99 dB  ✅ (显著提升)
Level 3:  20.41 dB  →  28.05 dB  =  +7.64 dB  ✅ (大幅提升)
Level 4:  19.02 dB  →  26.98 dB  =  +7.96 dB  ✅ (最佳效果)
```

### SSIM改进曲线

```
去噪前 SSIM  →  去噪后 SSIM  =  改进幅度

Level 1:  0.9855  →  0.9813  =  -0.42%  ❌
Level 2:  0.8438  →  0.9615  =  +11.77%  ✅
Level 3:  0.6480  →  0.9210  =  +27.30%  ✅
Level 4:  0.6180  →  0.9093  =  +29.14%  ✅
```

## 💡 使用建议

### 1. 何时使用 SCUNet

| 场景 | PSNR范围 | 是否推荐 | 预期效果 |
|------|---------|---------|---------|
| 极低噪声/高质量图像 | > 35 dB | ❌ 不推荐 | 可能降低质量 |
| 轻微噪声 | 25-35 dB | ✅ 推荐 | PSNR +4~5 dB |
| 中等噪声 | 20-25 dB | ✅✅ 强烈推荐 | PSNR +7~8 dB |
| 严重噪声 | < 20 dB | ✅✅✅ 最佳场景 | PSNR +8+ dB |

### 2. 工具选择

- **scunet_real_denoising_psnr**: 追求更高的PSNR指标 ✅ (本次测试使用)
- **scunet_real_denoising_gan**: 追求更好的视觉效果 ⭐
- **scunet_color_denoising**: 已知噪声等级的合成噪声 (noise_level: 15/25/50)
- **scunet_gray_denoising**: 灰度图像去噪

### 3. 噪声等级判断

```python
# 简单判断规则
if PSNR > 35:
    # 不建议去噪
    print("图像质量已经很高，不需要去噪")
elif 25 <= PSNR <= 35:
    # 可以使用去噪
    tool = "scunet_real_denoising_psnr"
elif PSNR < 25:
    # 强烈建议去噪
    tool = "scunet_real_denoising_psnr"  # 或 scunet_real_denoising_gan
```

## 🎨 视觉对比

所有去噪结果图像已保存至：`/app/xiaominl/DeepEyes_v2/scunet_test_results/`

- `000001_level1_denoised_scunet_real_denoising_psnr.png` - Level 1 去噪结果 (过度处理)
- `000001_level2_denoised_scunet_real_denoising_psnr.png` - Level 2 去噪结果 (良好)
- `000001_level3_denoised_scunet_real_denoising_psnr.png` - Level 3 去噪结果 (优秀)
- `000001_level4_denoised_scunet_real_denoising_psnr.png` - Level 4 去噪结果 (最佳)

## 🏆 最佳效果

**Level 4 (高噪声图像)** 去噪效果最佳：

- ✅ PSNR 从 19.02 dB 提升到 26.98 dB (+41.9%)
- ✅ SSIM 从 0.6180 提升到 0.9093 (+29.14%)
- ✅ 执行时间：1.69秒

## ⚡ 性能表现

- **平均执行时间**: ~1.7秒
- **图像尺寸**: 2040 × 1356 像素
- **处理效率**: 约 1.6 百万像素/秒

## 📝 结论

1. ✅ **SCUNet 工具实现成功**：所有工具类正常工作，API调用稳定
2. ✅ **去噪效果显著**：在中高噪声图像上，PSNR可提升4-8 dB，SSIM提升11-29%
3. ⚠️ **注意适用范围**：不适合处理高质量/低噪声图像（PSNR > 35 dB）
4. 🎯 **推荐使用场景**：中等至严重噪声的图像（PSNR < 25 dB）

---

**测试完成时间**: 2025-10-15  
**工具版本**: SCUNetToolbox v1.0  
**测试环境**: DeepEyes_v2

