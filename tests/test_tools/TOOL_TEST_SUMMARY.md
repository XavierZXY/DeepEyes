# 图像修复工具测试系统 - 完整文档

## 📚 文档索引

| 文档 | 用途 | 适合人群 |
|-----|------|---------|
| [README.md](README.md) | 完整功能说明和参数文档 | 所有用户 |
| [QUICK_START.md](QUICK_START.md) | 快速上手指南 | 新手用户 |
| 本文档 | 系统架构和设计说明 | 开发者 |

---

## 🎯 系统概述

### 功能定位
一个完整的图像修复工具效果测试系统，用于：
1. ✅ 评估各种图像修复工具的性能
2. ✅ 对比不同工具在同一退化类型上的表现
3. ✅ 计算标准图像质量指标（PSNR、SSIM、LPIPS）
4. ✅ 生成详细的测试报告（JSON/CSV/Markdown）

### 核心特性
- 🔧 **灵活配置**: 支持选择测试类型、样本数量、退化级别
- 📊 **多种指标**: PSNR（峰值信噪比）、SSIM（结构相似性）、LPIPS（感知相似度）
- 🎨 **多种格式**: JSON（完整数据）、CSV（表格分析）、Markdown（可读报告）
- 🚀 **易于使用**: Shell脚本封装，一键运行
- ⚡ **高效计算**: GPU加速的质量指标计算

---

## 📁 文件结构

```
tests/test_tools/
├── test_restoration_tools.py   # 主测试脚本（Python）
├── run_test.sh                  # 快速运行脚本（Shell）
├── __init__.py                  # Python包初始化
├── README.md                    # 完整文档
├── QUICK_START.md              # 快速开始指南
└── TOOL_TEST_SUMMARY.md        # 本文档（系统总结）
```

---

## 🏗️ 系统架构

### 核心类: `ToolTester`

```python
class ToolTester:
    """工具测试类"""
    
    def __init__(dataset_root, tool_service_ip)
        # 初始化数据集路径和工具服务IP
    
    def get_degradation_types() -> List[str]
        # 扫描数据集，获取所有退化类型
    
    def parse_image_samples(deg_type, level, num_samples) -> List[Dict]
        # 解析图像样本，匹配原图和退化图
    
    def load_tool(tool_name)
        # 动态加载工具实例（支持缓存）
    
    def apply_tool(tool_name, degraded_image) -> Image
        # 应用工具处理图像
    
    def calculate_metrics(img1, img2) -> Dict
        # 计算PSNR、SSIM、LPIPS指标
    
    def test_degradation_type(deg_type, num_samples, levels) -> Dict
        # 测试某个退化类型的所有工具
    
    def generate_report(all_results, output_dir)
        # 生成JSON/CSV/Markdown报告
```

### 工作流程

```
1. 初始化
   ├── 设置数据集路径
   ├── 配置工具服务IP
   └── 初始化图像质量评估器

2. 扫描数据集
   ├── 获取所有退化类型
   ├── 获取每个类型的级别
   └── 解析图像样本（匹配原图和退化图）

3. 测试循环
   ├── 对每个退化类型:
   │   ├── 对每个级别:
   │   │   ├── 计算基线指标（退化图 vs 原图）
   │   │   ├── 对每个工具:
   │   │   │   ├── 加载工具实例
   │   │   │   ├── 应用工具处理退化图
   │   │   │   ├── 计算修复后指标（修复图 vs 原图）
   │   │   │   └── 计算改进百分比
   │   │   └── 汇总该级别的所有工具结果
   │   └── 汇总该类型的所有级别结果
   └── 汇总所有类型的结果

4. 生成报告
   ├── JSON格式（完整数据）
   ├── CSV格式（表格分析）
   └── Markdown格式（可读报告）
```

---

## 🔧 支持的工具

### 工具映射表

| 退化类型 | 工具名称 | 显示名称 | API端口 |
|---------|---------|---------|---------|
| **haze** | dehazeformer_dehaze | DehazeFormer | 5002 |
| **noise** | swinir_denoising | SwinIR | 5001 |
| **noise** | mprnet_denoising | MPRNet | 5004 |
| **motion_blur** | restormer_motion_deblurring | Restormer | 5006 |
| **motion_blur** | mprnet_motion_deblurring | MPRNet | 5004 |
| **motion_blur** | xrestormer_motion_deblurring | XRestormer | 5007 |
| **defocus_blur** | restormer_defocus_deblurring | Restormer | 5006 |
| **defocus_blur** | drbnet_defocus_deblurring | DRBNet | 5003 |
| **rain** | restormer_deraining | Restormer | 5006 |
| **rain** | mprnet_deraining | MPRNet | 5004 |
| **rain** | xrestormer_deraining | XRestormer | 5007 |
| **jpeg** | swinir_jpeg_artifact_removal | SwinIR | 5001 |
| **jpeg** | fbcnn_jpeg_artifact_removal | FBCNN | 5005 |
| **low_resolution** | swinir_super_resolution | SwinIR | 5001 |
| **dark** | constant_shift | Constant Shift | - |
| **dark** | gamma_correction | Gamma Correction | - |
| **dark** | histogram_equalization | Histogram Equalization | - |

### 添加新工具

在 `DEGRADATION_TO_TOOLS` 字典中添加：

```python
DEGRADATION_TO_TOOLS = {
    "your_degradation_type": [
        ("tool_internal_name", "Tool Display Name")
    ]
}
```

在 `load_tool()` 方法中添加导入逻辑：

```python
elif tool_name == "your_tool_name":
    from verl.workers.agent.envs.mm_process_engine.YourToolbox import YourToolbox
    tool = YourToolbox(tool_name, "", {})
```

---

## 📊 指标计算

### PSNR (Peak Signal-to-Noise Ratio)
```python
# 使用scikit-image实现
from skimage.metrics import peak_signal_noise_ratio as psnr
psnr_value = psnr(img1_array, img2_array)

# 改进百分比
improvement = (restored_psnr - baseline_psnr) / baseline_psnr * 100
```

### SSIM (Structural Similarity Index)
```python
# 使用scikit-image实现
from skimage.metrics import structural_similarity as ssim
ssim_value = ssim(img1_array, img2_array, channel_axis=2)

# 改进百分比
improvement = (restored_ssim - baseline_ssim) / baseline_ssim * 100
```

### LPIPS (Learned Perceptual Image Patch Similarity)
```python
# 使用lpips库实现
import lpips
lpips_model = lpips.LPIPS(net='alex')
lpips_value = lpips_model(img1_tensor, img2_tensor).item()

# 改进百分比（注意：LPIPS越低越好，所以顺序相反）
improvement = (baseline_lpips - restored_lpips) / baseline_lpips * 100
```

---

## 📈 报告格式

### JSON格式（完整数据）
```json
{
  "degradation_type": {
    "baseline": {
      "level": {"psnr": float, "ssim": float, "lpips": float}
    },
    "tools": {
      "tool_name": {
        "display_name": str,
        "levels": {
          "level": {
            "metrics": {"psnr": float, "ssim": float, "lpips": float, "success_rate": float},
            "improvement": {"psnr": float, "ssim": float, "lpips": float},
            "num_samples": int,
            "success_count": int
          }
        }
      }
    }
  }
}
```

### CSV格式（表格分析）
| 列名 | 说明 |
|-----|------|
| Degradation_Type | 退化类型 |
| Level | 退化级别 |
| Tool | 工具显示名称 |
| Tool_Name | 工具内部名称 |
| Baseline_PSNR | 基线PSNR |
| Restored_PSNR | 修复后PSNR |
| Improve_PSNR% | PSNR改进百分比 |
| ... | 其他指标 |

### Markdown格式（可读报告）
- 分退化类型组织
- 每个类型包含基线表格和工具效果表格
- 清晰的改进百分比显示
- 成功率统计

---

## 🔍 使用场景

### 场景1: 工具开发验证
```bash
# 开发新的去雾工具后，快速验证效果
./run_test.sh --types haze --num-samples 10
# 对比Baseline和新工具的指标
```

### 场景2: 工具对比选型
```bash
# 对比不同的去噪工具
./run_test.sh --types noise --output ./noise_comparison
# 查看CSV报告，选择最优工具
```

### 场景3: 参数调优验证
```bash
# 调整工具参数后，验证改进
./run_test.sh --types motion_blur --num-samples 20
# 对比前后两次测试的结果
```

### 场景4: 完整性能评估
```bash
# 对所有工具进行完整评估
./run_test.sh --full --output ./full_evaluation
# 生成完整报告供论文/报告使用
```

---

## ⚙️ 配置选项

### 环境变量
```bash
TOOL_SERVICE_IP=10.21.9.34  # 工具API服务IP
```

### 命令行参数

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| --dataset | 必需 | - | 数据集根目录 |
| --output | 可选 | ./test_results | 输出目录 |
| --num-samples | 可选 | None | 每级别样本数 |
| --types | 可选 | 全部 | 测试的退化类型 |
| --exclude-types | 可选 | 无 | 排除的退化类型 |
| --levels | 可选 | 全部 | 测试的级别 |
| --tool-service-ip | 可选 | 环境变量 | 工具服务IP |

---

## 🐛 常见问题

### Q1: 工具加载失败
**A**: 检查工具箱导入路径是否正确，确保工具类已注册

### Q2: API调用超时
**A**: 检查网络连接，增加超时时间，或减少样本数量

### Q3: 内存不足
**A**: 使用`--num-samples`限制样本数量，或关闭其他占用GPU的程序

### Q4: 指标计算错误
**A**: 确保图像尺寸一致，检查图像格式（RGB/灰度）

---

## 🚀 性能优化

### 1. 工具实例缓存
```python
# 避免重复加载同一工具
self.tool_instances = {}  # 缓存已加载的工具
```

### 2. GPU加速
```python
# LPIPS模型使用GPU（如果可用）
if torch.cuda.is_available():
    self._lpips_model = self._lpips_model.cuda()
```

### 3. 批量处理
- 可扩展为批量处理多个样本
- 减少API调用开销

---

## 📝 TODO

- [ ] 支持保存修复后的图像到磁盘
- [ ] 添加可视化对比图（原图/退化图/修复图）
- [ ] 支持更多无参考质量指标（NIQE、BRISQUE）
- [ ] 支持多GPU并行测试
- [ ] 生成交互式HTML报告
- [ ] 支持视频质量评估
- [ ] 添加自动化回归测试

---

## 📚 相关资源

### 依赖库
- **scikit-image**: PSNR、SSIM计算
- **lpips**: 感知相似度计算
- **PIL/Pillow**: 图像处理
- **pandas**: 数据分析和CSV生成
- **tqdm**: 进度条显示

### 参考文档
- [SSIM论文](https://www.cns.nyu.edu/~lcv/ssim/)
- [LPIPS GitHub](https://github.com/richzhang/PerceptualSimilarity)
- [Image Quality Assessment](https://en.wikipedia.org/wiki/Image_quality)

---

**版本**: v1.0  
**创建时间**: 2025-10-14  
**最后更新**: 2025-10-14  
**维护团队**: DeepEyes v6  
**分支**: air_v6_degradation_tool_planning

