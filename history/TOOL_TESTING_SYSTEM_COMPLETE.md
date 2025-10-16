# ✅ 图像修复工具测试系统 - 完成报告

## 📦 已创建的文件

```
tests/test_tools/
├── test_restoration_tools.py    (24KB) - 主测试脚本
├── run_test.sh                  (5.7KB) - 快速运行脚本 ✓可执行
├── __init__.py                  (114B) - Python包初始化
├── README.md                    (7.4KB) - 完整功能文档
├── QUICK_START.md               (6.2KB) - 快速开始指南
└── TOOL_TEST_SUMMARY.md         (9.9KB) - 系统架构总结
```

**总大小**: ~64KB  
**创建时间**: 2025-10-14

---

## 🎯 系统功能

### ✅ 核心功能
1. **自动测试图像修复工具** - 支持8种退化类型、17个工具
2. **计算质量指标** - PSNR、SSIM、LPIPS（有参考指标）
3. **灵活配置** - 支持选择类型、级别、样本数量
4. **多格式报告** - JSON、CSV、Markdown三种格式
5. **工具对比** - 同一退化类型的多个工具效果对比
6. **基线对比** - 计算相对于退化图的改进百分比

### ✅ 支持的退化类型和工具

| 退化类型 | 工具数量 | 工具列表 |
|---------|---------|---------|
| **haze** | 1 | DehazeFormer |
| **noise** | 2 | SwinIR, MPRNet |
| **motion_blur** | 3 | Restormer, MPRNet, XRestormer |
| **defocus_blur** | 2 | Restormer, DRBNet |
| **rain** | 3 | Restormer, MPRNet, XRestormer |
| **jpeg** | 2 | SwinIR, FBCNN |
| **low_resolution** | 1 | SwinIR |
| **dark** | 3 | Constant Shift, Gamma Correction, Histogram Equalization |

**总计**: 8种退化类型，17个修复工具

---

## 🚀 快速使用

### 1. 准备数据集

确保数据集结构如下：
```
dataset/
├── original/              # 原图（ground truth）
│   ├── 000001.png
│   ├── 000002.png
│   └── ...
├── haze/                  # 雾霾退化
│   ├── low/
│   │   ├── 000001_level1.png
│   │   └── 000002_level1.png
│   ├── medium/
│   └── high/
├── noise/                 # 噪声退化
├── rain/                  # 雨滴退化
└── ...
```

### 2. 设置环境

```bash
# 设置工具服务IP（如果工具在远程机器上）
export TOOL_SERVICE_IP=10.21.9.34

# 进入测试目录
cd /app/xiaominl/DeepEyes_v2/tests/test_tools
```

### 3. 运行测试

```bash
# 方式1: 使用Shell脚本（推荐）
./run_test.sh --quick --types haze

# 方式2: 直接使用Python
python test_restoration_tools.py \
    --dataset /path/to/dataset \
    --types haze \
    --num-samples 10 \
    --output ./results
```

### 4. 查看结果

```bash
# 查看Markdown报告（最易读）
cat ./test_results_*/test_results.md

# 查看CSV（用于Excel分析）
xdg-open ./test_results_*/test_results.csv

# 查看JSON（完整数据）
cat ./test_results_*/test_results.json | jq '.'
```

---

## 📊 使用示例

### 示例1: 快速验证单个工具
```bash
# 测试去雾工具，每个级别3个样本
./run_test.sh --quick --types haze
```

### 示例2: 对比多个工具
```bash
# 对比不同的去噪工具
./run_test.sh --types noise --num-samples 10 --output ./noise_comparison
```

### 示例3: 完整性能评估
```bash
# 评估所有工具，使用所有样本
./run_test.sh --full --dataset /data/dataset --output ./full_eval
```

### 示例4: 排除某些类型
```bash
# 测试除了dark和low_resolution之外的所有类型
./run_test.sh --exclude dark,low_resolution --num-samples 10
```

---

## 📈 输出报告示例

### Markdown报告片段
```markdown
## haze

### 基线指标 (退化图 vs 原图)
| Level  | PSNR (dB) | SSIM   | LPIPS  |
|--------|-----------|--------|--------|
| low    | 18.45     | 0.7234 | 0.2891 |
| medium | 15.23     | 0.6521 | 0.3421 |
| high   | 12.67     | 0.5834 | 0.4123 |

### 工具修复效果
#### DehazeFormer
| Level  | PSNR  | SSIM   | LPIPS  | PSNR↑   | SSIM↑   | LPIPS↓  | 成功率  |
|--------|-------|--------|--------|---------|---------|---------|---------|
| low    | 31.23 | 0.9123 | 0.0987 | +69.3%  | +26.1%  | +65.9%  | 100.0%  |
| medium | 28.45 | 0.8921 | 0.1234 | +86.7%  | +36.8%  | +63.9%  | 100.0%  |
| high   | 25.89 | 0.8534 | 0.1567 | +104.3% | +46.3%  | +62.0%  | 100.0%  |
```

### 指标解读
- **PSNR**: 从15.23dB → 28.45dB，提升**86.7%** ✅
- **SSIM**: 从0.6521 → 0.8921，提升**36.8%** ✅
- **LPIPS**: 从0.3421 → 0.1234，降低**63.9%** ✅（越低越好）
- **成功率**: 100%（10/10样本全部成功）✅

---

## 🔧 配置参数

### Shell脚本参数 (`run_test.sh`)
```bash
-d, --dataset PATH          # 数据集根目录
-o, --output PATH           # 输出目录
-n, --num-samples N         # 每个级别的样本数量
-t, --types TYPE1,TYPE2     # 要测试的退化类型（逗号分隔）
-e, --exclude TYPE1,TYPE2   # 要排除的退化类型
-l, --levels LEV1,LEV2      # 要测试的级别（逗号分隔）
-i, --ip IP                 # 工具服务IP地址
--quick                     # 快速测试（每级别3个样本）
--full                      # 完整测试（所有样本）
-h, --help                  # 显示帮助
```

### Python脚本参数 (`test_restoration_tools.py`)
```bash
--dataset PATH              # 数据集根目录（必需）
--output PATH               # 输出目录
--num-samples N             # 每个级别的样本数量
--types TYPE1 TYPE2         # 要测试的退化类型（空格分隔）
--exclude-types TYPE1       # 要排除的退化类型
--levels LEV1 LEV2          # 要测试的级别
--tool-service-ip IP        # 工具服务IP地址
```

---

## 📚 文档导航

### 新手用户
1. 先阅读: [QUICK_START.md](tests/test_tools/QUICK_START.md)
2. 然后参考: [README.md](tests/test_tools/README.md)

### 高级用户
1. 阅读: [README.md](tests/test_tools/README.md) - 完整参数说明
2. 参考: [TOOL_TEST_SUMMARY.md](tests/test_tools/TOOL_TEST_SUMMARY.md) - 系统架构

### 开发者
1. 查看: [TOOL_TEST_SUMMARY.md](tests/test_tools/TOOL_TEST_SUMMARY.md) - 设计文档
2. 阅读: 源代码 `test_restoration_tools.py`

---

## 🔍 技术细节

### 工具加载机制
```python
# 动态导入和缓存
def load_tool(self, tool_name: str):
    if tool_name in self.tool_instances:
        return self.tool_instances[tool_name]  # 使用缓存
    
    # 动态导入工具类
    if tool_name == "dehazeformer_dehaze":
        from verl.workers.agent.envs.mm_process_engine.DehazeFormerToolbox import DehazeFormerToolbox
        tool = DehazeFormerToolbox(tool_name, "", {})
    # ... 其他工具
    
    self.tool_instances[tool_name] = tool  # 缓存
    return tool
```

### 指标计算
```python
# 使用ImageQualityMetrics类（单例模式）
from verl.utils.reward_score.image_quality_metrics import ImageQualityMetrics

metrics_calculator = ImageQualityMetrics()
metrics = metrics_calculator.calculate_all_metrics(restored_img, original_img)

# 返回: {'psnr': float, 'ssim': float, 'lpips': float}
```

### 报告生成
```python
# 三种格式同时生成
def generate_report(all_results, output_dir):
    # 1. JSON - 完整数据
    json.dump(all_results, file)
    
    # 2. CSV - 表格分析
    df.to_csv(csv_path)
    
    # 3. Markdown - 可读报告
    with open(md_path, 'w') as f:
        f.write("# 报告...")
```

---

## ⚠️ 注意事项

### 1. 环境要求
- Python 3.8+
- PyTorch (用于LPIPS)
- scikit-image (用于PSNR、SSIM)
- PIL/Pillow (用于图像处理)
- pandas (用于CSV生成)

### 2. 工具服务
确保以下API服务已启动：
- DehazeFormer: `http://$TOOL_SERVICE_IP:5002`
- SwinIR: `http://$TOOL_SERVICE_IP:5001`
- MPRNet: `http://$TOOL_SERVICE_IP:5004`
- Restormer: `http://$TOOL_SERVICE_IP:5006`
- 等...

### 3. 资源使用
- **GPU**: LPIPS计算会使用GPU（如果可用）
- **内存**: 大量高分辨率图像会占用较多内存
- **网络**: 工具API调用需要网络连接

---

## 🐛 常见问题

### Q1: 数据集结构不匹配
```
[WARNING] No levels found for haze
```
**解决**: 检查目录结构，确保有 `low/`, `medium/`, `high/` 等子目录

### Q2: 工具服务连接失败
```
[ERROR] Tool dehazeformer_dehaze execution failed
```
**解决**: 
1. 检查工具API是否运行: `curl http://$TOOL_SERVICE_IP:5002/dehaze`
2. 检查IP配置: `echo $TOOL_SERVICE_IP`
3. 检查防火墙设置

### Q3: 内存不足
```
CUDA out of memory
```
**解决**: 
- 减少样本数: `--num-samples 3`
- 只测试部分类型: `--types haze`
- 关闭其他GPU程序

---

## 🚀 扩展功能（待实现）

### 计划中的功能
- [ ] 保存修复后的图像到磁盘
- [ ] 生成可视化对比图（原图/退化图/修复图并排）
- [ ] 支持无参考质量指标（NIQE、BRISQUE）
- [ ] 多GPU并行测试
- [ ] 交互式HTML报告
- [ ] 自动化回归测试
- [ ] 支持视频质量评估

### 如何扩展

#### 添加新的退化类型
```python
# 在DEGRADATION_TO_TOOLS中添加
DEGRADATION_TO_TOOLS = {
    "your_new_type": [
        ("your_tool_name", "Tool Display Name")
    ]
}
```

#### 添加新的工具
```python
# 在load_tool()中添加
elif tool_name == "your_tool_name":
    from verl.workers.agent.envs.mm_process_engine.YourToolbox import YourToolbox
    tool = YourToolbox(tool_name, "", {})
```

#### 添加新的指标
```python
# 在calculate_metrics()中添加
def calculate_metrics(self, img1, img2):
    metrics = self.metrics_calculator.calculate_all_metrics(img1, img2)
    # 添加自定义指标
    metrics['your_metric'] = your_calculation(img1, img2)
    return metrics
```

---

## ✅ 验证清单

在使用前，请确认：

- [x] 数据集目录结构正确
  - [x] 有 `original/` 文件夹
  - [x] 有退化类型文件夹（如 `haze/`, `noise/` 等）
  - [x] 每个退化类型有级别子文件夹（如 `low/`, `medium/`, `high/`）
  - [x] 图像命名格式正确（`XXXXXX_levelN.png`）

- [x] 工具服务已启动
  - [ ] DehazeFormer服务（端口5002）
  - [ ] SwinIR服务（端口5001）
  - [ ] MPRNet服务（端口5004）
  - [ ] Restormer服务（端口5006）
  - [ ] 其他需要的服务...

- [x] 环境配置正确
  - [x] Python 3.8+已安装
  - [x] 必需的库已安装（torch, scikit-image, PIL, pandas）
  - [x] `TOOL_SERVICE_IP` 环境变量已设置

- [x] 脚本可执行
  - [x] `run_test.sh` 有执行权限
  - [x] 在正确的目录（`tests/test_tools/`）

---

## 📞 支持和反馈

### 获取帮助
```bash
# 查看Shell脚本帮助
./run_test.sh --help

# 查看Python脚本帮助
python test_restoration_tools.py --help
```

### 报告问题
1. 记录错误信息
2. 检查数据集结构
3. 验证工具服务状态
4. 查看日志文件

### 贡献代码
欢迎提交PR改进系统：
- 添加新工具支持
- 优化性能
- 修复Bug
- 完善文档

---

## 🎉 总结

### 已完成
- ✅ 完整的工具测试系统
- ✅ 支持8种退化类型、17个工具
- ✅ PSNR、SSIM、LPIPS三种指标
- ✅ JSON、CSV、Markdown三种报告
- ✅ 灵活的配置选项
- ✅ Shell脚本和Python脚本两种使用方式
- ✅ 完整的文档（README、快速指南、架构文档）

### 系统特点
- 🎯 **易用性**: Shell脚本一键运行
- 🔧 **灵活性**: 丰富的配置选项
- 📊 **完整性**: 多种报告格式
- ⚡ **高效性**: 工具缓存、GPU加速
- 📚 **文档化**: 完善的使用文档

### 快速开始
```bash
cd /app/xiaominl/DeepEyes_v2/tests/test_tools
./run_test.sh --quick --types haze
cat ./test_results_*/test_results.md
```

---

**创建完成时间**: 2025-10-14  
**版本**: v1.0  
**分支**: air_v6_degradation_tool_planning  
**维护团队**: DeepEyes Team

🎉 **工具测试系统已完成并可用！**

