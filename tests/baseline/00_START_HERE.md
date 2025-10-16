# 🎯 从这里开始！

## ✅ 状态确认

**Baseline测试框架已完全准备就绪！**

- ✅ 所有Python脚本已创建和验证
- ✅ 数据集格式验证通过
- ✅ 支持8种退化类型，14个修复工具
- ✅ 所有文档完整

## 🚀 3分钟快速开始

### Step 1: 进入目录

```bash
cd /app/xiaominl/DeepEyes_v2/tests/baseline
```

### Step 2: 快速测试（推荐）

```bash
./quick_test.sh
```

这将：
- 测试2个样本
- 使用两种策略（random和reverse）
- 验证环境配置
- 大约需要1-2分钟

### Step 3: 查看结果

```bash
# 查看最新的摘要文件
cat results/summary_*.txt | head -50
```

## 📖 推荐阅读顺序

如果您是第一次使用，请按以下顺序阅读文档：

1. **00_START_HERE.md** ← 您在这里 ✨
2. **READY_TO_USE.md** - 验证状态和详细说明
3. **USAGE_EXAMPLES.md** - 实际使用示例
4. **README.md** - 完整API文档

## 🎓 核心概念

### 两种修复策略

**Random（随机修复）:**
```
退化: [A, B, C]
   ↓ 随机打乱
修复: [C, A, B]  # 随机顺序
```

**Reverse（逆序修复）:**
```
退化: [A, B, C]
   ↓ 逆序
修复: [C, B, A]  # 撤销顺序
```

**问题：哪种策略更好？**  
→ 运行测试来找出答案！

### 三种评估指标

| 指标 | 含义 | 好的范围 | 越大越好？ |
|------|------|---------|----------|
| PSNR | 信噪比 | 25-35 dB | ✅ 是 |
| SSIM | 结构相似性 | 0.80-0.95 | ✅ 是 |
| LPIPS | 感知相似性 | 0.05-0.20 | ❌ 否（越小越好） |

## 💻 常用命令

```bash
# 快速测试（2个样本）
./quick_test.sh

# 完整测试（10个样本，两种策略）
./run_baseline_test.sh --num-samples 10 --strategy both

# 保存图像结果
./run_baseline_test.sh --num-samples 10 --save-images

# 只测试一种策略
./run_baseline_test.sh --num-samples 20 --strategy reverse

# 验证数据集
python3 verify_dataset.py

# 检查安装
./check_installation.sh
```

## 📊 结果解读

### 示例输出

```
REVERSE Strategy Results:
Average Degraded Metrics:
  PSNR: 23.45      ← 退化图与原图的差距
  SSIM: 0.72
  LPIPS: 0.28

Average Restored Metrics:
  PSNR: 27.12      ← 修复图与原图的差距
  SSIM: 0.83
  LPIPS: 0.17

Average Improvements:
  PSNR: +3.67      ← 改善程度（正值=变好）
  SSIM: +0.11
  LPIPS: +0.11     ← 注意：LPIPS是越小越好，所以正值=变好
```

**解读：**
- PSNR提升3.67 dB → 显著改善 ✅
- SSIM提升0.11 → 结构恢复良好 ✅  
- LPIPS降低0.11 → 感知质量提升 ✅

## 🎯 典型使用场景

### 场景1: 评估工具效果

```bash
# 测试50个样本
./run_baseline_test.sh --num-samples 50 --strategy reverse

# 查看平均改善
grep "Average Improvements" results/summary_*.txt
```

### 场景2: 比较策略

```bash
# 测试两种策略
./run_baseline_test.sh --num-samples 30 --strategy both

# 比较结果
python3 << 'EOF'
import json
with open(max(glob.glob('results/results_*.json'))) as f:
    results = json.load(f)
random_avg = np.mean([r['improvements']['psnr'] 
                      for r in results if r['strategy'] == 'random'])
reverse_avg = np.mean([r['improvements']['psnr'] 
                       for r in results if r['strategy'] == 'reverse'])
print(f"Random: +{random_avg:.2f} dB")
print(f"Reverse: +{reverse_avg:.2f} dB")
print(f"Winner: {'Reverse' if reverse_avg > random_avg else 'Random'}")
EOF
```

### 场景3: 可视化分析

```bash
# 保存图像进行人工检查
./run_baseline_test.sh --num-samples 10 --save-images

# 查看样本0的图像
ls results/sample_0_reverse/
# degraded.png  original.png  restored.png
```

## ⚙️ 配置

### 环境变量

```bash
# 设置工具服务IP（如果不是默认值）
export TOOL_SERVICE_IP="10.21.9.34"

# 运行测试
./run_baseline_test.sh --num-samples 10
```

### 自定义数据集

```bash
# 使用自定义数据集
./run_baseline_test.sh \
    --data-path /path/to/your/dataset.parquet \
    --num-samples 20
```

## 🔧 故障排查

### 问题：工具服务连接失败

**症状：**
```
ConnectionError: Failed to connect to ... API
```

**解决方案：**
1. 检查 TOOL_SERVICE_IP：`echo $TOOL_SERVICE_IP`
2. 测试连接：`curl http://10.21.9.34:5001/health`
3. 确保工具服务正在运行

### 问题：导入失败

**症状：**
```
ImportError: cannot import name ...
```

**解决方案：**
```bash
export PYTHONPATH=/app/xiaominl/DeepEyes_v2:$PYTHONPATH
python3 -c "from tests.baseline.test_baseline_restoration import *"
```

### 问题：CUDA不可用

**症状：**
```
[WARNING] LPIPS calculation failed
```

**解决方案：**
- LPIPS会自动使用CPU（较慢但可用）
- 确认：`python3 -c "import torch; print(torch.cuda.is_available())"`

## 📁 输出结果

测试完成后，结果保存在 `results/` 目录：

```
results/
├── results_20251015_123456.json     # 详细结果数据
├── summary_20251015_123456.txt      # 统计摘要
└── sample_<idx>_<strategy>/         # 图像文件（可选）
    ├── degraded.png                 # 退化图
    ├── original.png                 # 原图
    └── restored.png                 # 修复图
```

## 📚 深入学习

想了解更多？查看这些文档：

- **技术细节** → `PROJECT_SUMMARY.md`
- **使用示例** → `USAGE_EXAMPLES.md`
- **API参考** → `README.md`
- **安装说明** → `INSTALL_COMPLETE.md`

## ✨ 现在就开始！

```bash
cd /app/xiaominl/DeepEyes_v2/tests/baseline
./quick_test.sh
```

**祝测试顺利！** 🎉

---

*提示：遇到问题？运行 `./check_installation.sh` 进行诊断*

