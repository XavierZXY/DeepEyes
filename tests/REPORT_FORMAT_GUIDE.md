# 📊 测试报告格式详解

## 生成的文件

运行测试后，会在输出目录生成以下文件：

```
output_dir/
├── detailed_results.csv      ← CSV表格（Excel可打开）
├── summary_report.txt        ← 文本报告（人类可读）
└── images/                   ← 图像文件夹
    ├── sample_0/
    │   ├── original.png      ← 原图（Ground Truth）
    │   ├── degraded.png      ← 退化图（输入）
    │   ├── swinir_denoising.png              ← 工具1修复结果
    │   ├── restormer_motion_deblurring.png   ← 工具2修复结果
    │   └── ... (所有14个工具的结果)
    ├── sample_1/
    └── ...
```

---

## 1️⃣ CSV详细报告 (detailed_results.csv)

### 格式
- **文件类型**: CSV（逗号分隔值）
- **可用软件**: Excel, LibreOffice Calc, Google Sheets, Python pandas
- **编码**: UTF-8

### 列说明

| 列名 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| **sample_id** | 文本 | 样本唯一标识 | `sample_0`, `sample_42` |
| **sample_index** | 整数 | 样本在文件中的索引 | `0`, `1`, `2` |
| **degradation_types** | 文本 | 退化类型（逗号分隔） | `"noise, blur"`, `"haze"` |
| **degradation_levels** | 文本 | 退化等级（逗号分隔） | `"high, medium"`, `"low"` |
| **tool_name** | 文本 | 工具名称 | `swinir_denoising` |
| **tool_description** | 文本 | 工具描述 | `SwinIR去噪` |
| **success** | 布尔 | 是否成功调用 | `True`, `False` |
| **baseline_psnr** | 浮点 | 退化图的PSNR (dB) | `22.45` |
| **baseline_ssim** | 浮点 | 退化图的SSIM | `0.6543` |
| **baseline_lpips** | 浮点 | 退化图的LPIPS | `0.3821` |
| **restored_psnr** | 浮点 | 修复图的PSNR (dB) | `28.32` |
| **restored_ssim** | 浮点 | 修复图的SSIM | `0.8123` |
| **restored_lpips** | 浮点 | 修复图的LPIPS | `0.2145` |
| **psnr_improvement** | 浮点 | PSNR改进量 (dB) | `+5.87` |
| **ssim_improvement** | 浮点 | SSIM改进量 | `+0.1580` |
| **lpips_improvement** | 浮点 | LPIPS改进量 | `+0.1676` |

### 数据示例

```csv
sample_id,degradation_types,tool_name,baseline_psnr,restored_psnr,psnr_improvement
sample_0,"noise, blur",swinir_denoising,22.45,28.32,+5.87
sample_0,"noise, blur",restormer_motion_deblurring,22.45,26.78,+4.33
sample_1,jpeg compression artifact,fbcnn_jpeg_artifact_removal,24.56,31.23,+6.67
```

### 数据量
- **每个样本** × **每个工具** = 1行数据
- 例如：10个样本 × 14个工具 = **140行**
- 例如：100个样本 × 14个工具 = **1,400行**

### 使用方法

**在Excel中打开**:
```bash
libreoffice detailed_results.csv
```

**用Python分析**:
```python
import pandas as pd

df = pd.read_csv('detailed_results.csv')

# 查看PSNR改进最大的前10个
top10 = df.nlargest(10, 'psnr_improvement')
print(top10[['sample_id', 'tool_name', 'psnr_improvement']])

# 按工具分组统计
by_tool = df.groupby('tool_name')['psnr_improvement'].mean()
print(by_tool.sort_values(ascending=False))

# 筛选特定退化类型
noise_samples = df[df['degradation_types'].str.contains('noise')]
```

---

## 2️⃣ 文本汇总报告 (summary_report.txt)

### 格式
- **文件类型**: 纯文本（TXT）
- **编码**: UTF-8
- **查看方式**: 任何文本编辑器

### 报告结构

```
================================================================================
第1部分: 报告头部
================================================================================
- 生成时间
- 测试样本数
- 测试工具数
- 总测试次数

================================================================================
第2部分: 工具性能汇总
================================================================================
每个工具的：
- 成功率（百分比）
- 平均PSNR及改进量
- 平均SSIM及改进量
- 平均LPIPS及改进量

工具按PSNR改进量从高到低排序

================================================================================
第3部分: 按退化类型的工具性能
================================================================================
对每种退化类型：
- 列出前5名最佳工具
- 显示PSNR改进量

================================================================================
第4部分: 推荐工具
================================================================================
前10名工具：
- 排名
- PSNR/SSIM/LPIPS改进量
```

### 示例片段

```
工具: swinir_denoising
  成功率: 100.0%
  平均PSNR: 28.45 dB (改进: +6.23)
  平均SSIM: 0.8456 (改进: +0.1834)
  平均LPIPS: 0.1923 (改进: +0.1645)
```

```
退化类型: noise
----------------------------------------
  swinir_denoising: +7.89 dB
  mprnet_denoising: +6.78 dB
  restormer_motion_deblurring: +2.34 dB
```

### 查看方法

**Linux/Mac**:
```bash
cat summary_report.txt
less summary_report.txt
```

**Windows**:
```bash
type summary_report.txt
notepad summary_report.txt
```

---

## 3️⃣ 图像文件 (images/)

### 目录结构

```
images/
├── sample_0/              ← 第1个样本
│   ├── original.png       ← 原图（512×512 或实际尺寸）
│   ├── degraded.png       ← 退化图
│   ├── swinir_denoising.png
│   ├── swinir_jpeg_artifact_removal.png
│   ├── swinir_super_resolution.png
│   ├── restormer_motion_deblurring.png
│   ├── restormer_defocus_deblurring.png
│   ├── restormer_deraining.png
│   ├── xrestormer_motion_deblurring.png
│   ├── xrestormer_deraining.png
│   ├── mprnet_denoising.png
│   ├── mprnet_motion_deblurring.png
│   ├── mprnet_deraining.png
│   ├── fbcnn_jpeg_artifact_removal.png
│   ├── drbnet_defocus_deblurring.png
│   └── dehazeformer_dehaze.png
├── sample_1/              ← 第2个样本
│   └── ... (同上)
└── ...
```

### 文件特点
- **格式**: PNG（无损压缩）
- **颜色**: RGB（3通道）
- **尺寸**: 与原图一致
- **命名**: `{tool_name}.png`

### 图像类型说明

| 文件名 | 说明 | 来源 |
|--------|------|------|
| `original.png` | 原图（未退化） | parquet的`extra_info['original_image']` |
| `degraded.png` | 退化图（输入） | parquet的`data_dict` 或 `image`字段 |
| `{tool}.png` | 修复图（输出） | 工具API返回的处理结果 |

### 使用场景

**可视化对比**:
```bash
# 查看某个样本的所有结果
ls images/sample_0/
eog images/sample_0/*.png  # Linux
open images/sample_0/*.png # Mac
```

**制作对比图**:
```python
from PIL import Image
import matplotlib.pyplot as plt

# 读取图像
original = Image.open('images/sample_0/original.png')
degraded = Image.open('images/sample_0/degraded.png')
restored = Image.open('images/sample_0/swinir_denoising.png')

# 对比显示
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
axes[0].imshow(original); axes[0].set_title('Original')
axes[1].imshow(degraded); axes[1].set_title('Degraded')
axes[2].imshow(restored); axes[2].set_title('Restored')
plt.savefig('comparison.png')
```

---

## 📊 数据解读指南

### PSNR (峰值信噪比)
- **单位**: dB (分贝)
- **典型范围**: 15-45 dB
- **解读**:
  - < 20 dB: 质量很差
  - 20-25 dB: 质量较差
  - 25-30 dB: 质量中等
  - 30-35 dB: 质量良好
  - 35-40 dB: 质量优秀
  - \> 40 dB: 质量极佳
- **改进量**: +3 dB以上为显著改进

### SSIM (结构相似性)
- **范围**: 0-1
- **解读**:
  - < 0.5: 结构差异很大
  - 0.5-0.7: 结构有明显差异
  - 0.7-0.85: 结构较为相似
  - 0.85-0.95: 结构很相似
  - \> 0.95: 结构几乎一致
- **改进量**: +0.1以上为显著改进

### LPIPS (感知损失)
- **范围**: 0-1
- **方向**: 越低越好（与PSNR/SSIM相反）
- **解读**:
  - < 0.1: 感知上几乎一致
  - 0.1-0.2: 感知差异很小
  - 0.2-0.3: 感知差异中等
  - 0.3-0.5: 感知差异较大
  - \> 0.5: 感知差异很大
- **改进量**: -0.1以上为显著改进（注意负号）

### 成功率
- **100%**: 所有样本都成功处理
- **95-99%**: 偶尔失败（可能是网络或GPU内存问题）
- **< 95%**: 工具可能不稳定或不适合该数据集

---

## 🎯 实际应用示例

### 示例1: 找出最佳去噪工具

1. 打开 `detailed_results.csv`
2. 筛选 `degradation_types` 包含 "noise" 的行
3. 按 `psnr_improvement` 降序排序
4. 查看排名前3的工具

**预期结果**:
```
1. swinir_denoising: +7.89 dB
2. mprnet_denoising: +6.78 dB
3. restormer_motion_deblurring: +2.34 dB
```

### 示例2: 对比两个工具

查看 `summary_report.txt` 中的工具性能汇总：

```
工具: swinir_denoising
  成功率: 100.0%
  平均PSNR: 28.45 dB (改进: +6.23)

工具: mprnet_denoising
  成功率: 99.8%
  平均PSNR: 27.89 dB (改进: +5.67)
```

**结论**: SwinIR 略优于 MPRNet（+0.56 dB）

### 示例3: 查看失败案例

在 `detailed_results.csv` 中筛选 `success=False` 的行，查看：
- 哪些工具容易失败
- 哪些样本导致失败
- 失败的退化类型

---

## 💡 小技巧

### 快速查看最佳工具
```bash
# 查看报告的推荐工具部分
cat summary_report.txt | grep -A 50 "推荐工具"
```

### 导出Excel公式计算
在 Excel 中打开 `detailed_results.csv` 后：
```excel
# 计算平均改进
=AVERAGE(N2:N100)

# 找出最大改进
=MAX(N2:N100)

# 条件统计
=AVERAGEIF(E:E, "swinir_denoising", N:N)
```

### 批量查看图像
```bash
# 创建HTML对比页面
python3 -c "
import os
from pathlib import Path

html = '<html><body>'
for sample_dir in sorted(Path('images').iterdir()):
    html += f'<h2>{sample_dir.name}</h2>'
    html += '<table><tr>'
    for img in sorted(sample_dir.glob('*.png')):
        html += f'<td><img src=\"{img}\" width=200><br>{img.name}</td>'
    html += '</tr></table>'
html += '</body></html>'

with open('results.html', 'w') as f:
    f.write(html)
"

# 用浏览器打开
firefox results.html
```

---

## 📋 检查清单

运行测试后，确认以下文件存在：

- [ ] `detailed_results.csv` - CSV表格
- [ ] `summary_report.txt` - 文本报告
- [ ] `images/` - 图像目录
- [ ] `images/sample_0/original.png` - 原图
- [ ] `images/sample_0/degraded.png` - 退化图
- [ ] `images/sample_0/{tool_name}.png` - 修复图

检查数据完整性：

- [ ] CSV行数 = 样本数 × 工具数
- [ ] 每个样本目录有 2 + 工具数 张图片
- [ ] 报告中有"工具性能汇总"部分
- [ ] 报告中有"按退化类型"分析

---

**生成时间**: 自动记录  
**格式版本**: v1.0  
**兼容性**: CSV可用Excel/Python，TXT可用任何编辑器，PNG可用任何图片查看器

