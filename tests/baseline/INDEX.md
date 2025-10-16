# Baseline测试文档索引

欢迎使用Baseline退化图像修复测试框架！

## 🚀 快速开始

**第一次使用？从这里开始：**

1. **查看就绪状态** → `READY_TO_USE.md` ⭐
2. **运行快速测试** → `./quick_test.sh`
3. **查看结果** → `results/summary_*.txt`

## 📚 文档导航

### 核心文档

| 文档 | 用途 | 推荐阅读顺序 |
|------|------|------------|
| **READY_TO_USE.md** ⭐ | 验证状态和快速开始 | 1️⃣ 首先阅读 |
| **README.md** | 完整功能说明和API参考 | 2️⃣ 深入了解 |
| **USAGE_EXAMPLES.md** | 详细使用示例和场景 | 3️⃣ 实际应用 |
| **PROJECT_SUMMARY.md** | 项目架构和设计决策 | 4️⃣ 技术细节 |
| **INSTALL_COMPLETE.md** | 详细的安装和配置说明 | 参考文档 |

### 使用流程

```
READY_TO_USE.md (验证准备就绪)
    ↓
运行 quick_test.sh (快速验证)
    ↓
查看 USAGE_EXAMPLES.md (学习使用)
    ↓
运行完整测试 (run_baseline_test.sh)
    ↓
分析结果 (results/)
    ↓
参考 PROJECT_SUMMARY.md (深入理解)
```

## 🛠️ 可执行文件

| 脚本 | 功能 | 用法 |
|------|------|------|
| `quick_test.sh` | 快速测试（2个样本） | `./quick_test.sh` |
| `run_baseline_test.sh` | 完整测试脚本 | `./run_baseline_test.sh --num-samples 10` |
| `verify_dataset.py` | 验证数据集格式 | `python3 verify_dataset.py` |
| `check_installation.sh` | 检查安装状态 | `./check_installation.sh` |
| `test_baseline_restoration.py` | 主测试程序 | 不直接运行，使用上述脚本 |

## 📋 常见任务

### 任务1: 验证环境配置

```bash
./check_installation.sh
```

### 任务2: 验证数据集

```bash
python3 verify_dataset.py --num-samples 5
```

### 任务3: 快速测试

```bash
./quick_test.sh
```

### 任务4: 比较策略效果

```bash
./run_baseline_test.sh --num-samples 20 --strategy both
cat results/summary_*.txt
```

### 任务5: 大规模评估

```bash
./run_baseline_test.sh --num-samples 100 --strategy reverse
```

## 💡 概念说明

### 修复策略

1. **Random（随机修复）**
   - 随机打乱退化类型顺序
   - 依次应用修复工具
   - 评估工具的鲁棒性

2. **Reverse（逆序修复）**
   - 按退化顺序的逆序修复
   - 模拟"撤销"退化的过程
   - 理论上应该效果更好

### 评估指标

- **PSNR**: 峰值信噪比，越高越好（20-40 dB为良好）
- **SSIM**: 结构相似性，越高越好（0-1，接近1最好）
- **LPIPS**: 感知相似性，越低越好（0-1，接近0最好）

### 数据结构

```
Parquet文件
├── images (numpy.ndarray)
│   └── [0] → {'bytes': <图像字节数据>}  # 退化图
├── extra_info (dict)
│   ├── original_image (bytes)  # 原图（ground truth）
│   ├── index (int)
│   ├── split (str)
│   └── degradation_combo (list)
└── reward_model (numpy.ndarray)
    └── [0..N] → {'degradation_type': str, 'degradation_level': str}
```

## 🎯 典型工作流

### 流程1: 首次使用

```bash
# 1. 检查安装
cd /app/xiaominl/DeepEyes_v2/tests/baseline
./check_installation.sh

# 2. 验证数据集
python3 verify_dataset.py

# 3. 快速测试
./quick_test.sh

# 4. 查看结果
cat results/summary_*.txt
```

### 流程2: 研究对比

```bash
# 测试两种策略
./run_baseline_test.sh --num-samples 50 --strategy both --save-images

# 分析结果
python3 << 'EOF'
import json
import numpy as np

with open('results/results_*.json') as f:
    results = json.load(f)

random_psnr = np.mean([r['improvements']['psnr'] 
                       for r in results if r['strategy'] == 'random'])
reverse_psnr = np.mean([r['improvements']['psnr'] 
                        for r in results if r['strategy'] == 'reverse'])

print(f"Random strategy: +{random_psnr:.2f} dB")
print(f"Reverse strategy: +{reverse_psnr:.2f} dB")
print(f"Difference: {reverse_psnr - random_psnr:.2f} dB")
EOF
```

### 流程3: 调优参数

1. 编辑 `test_baseline_restoration.py`
2. 修改 `DEGRADATION_TO_TOOLS` 中的默认参数
3. 重新运行测试
4. 比较结果

## 📞 支持

### 获取帮助

1. 查看对应的文档文件
2. 运行 `check_installation.sh` 诊断
3. 检查工具服务状态
4. 查看日志文件

### 报告问题

请提供：
- 完整的错误信息
- `check_installation.sh` 的输出
- 使用的命令和参数
- 数据集路径和样本数量

## 🎊 开始使用

**所有组件已验证，立即开始测试：**

```bash
cd /app/xiaominl/DeepEyes_v2/tests/baseline
./quick_test.sh
```

**期待看到您的测试结果！** 🚀

---

*最后更新：2024-10-15*  
*项目版本：1.0*  
*状态：✅ 已验证，可用于生产*

