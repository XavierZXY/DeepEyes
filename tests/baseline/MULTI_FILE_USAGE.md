# 多 Parquet 文件测试使用指南

## 概述

`run_baseline_test_multi.sh` 脚本支持处理多个 parquet 文件，有三种使用方式：

1. **指定多个文件**：逐个指定要测试的文件
2. **指定目录**：自动发现目录下所有 `.parquet` 文件
3. **混合模式**：组合使用上述两种方式

---

## 使用方法

### 方法 1：指定多个文件

使用多个 `--data-path` 参数：

```bash
cd /app/xiaominl/DeepEyes_v2/tests/baseline

# 测试 2 个文件，总共 20 个样本（每个文件 10 个）
./run_baseline_test_multi.sh \
    --data-path /path/to/file1.parquet \
    --data-path /path/to/file2.parquet \
    --num-samples 20

# 测试 3 个文件，每个文件 5 个样本
./run_baseline_test_multi.sh \
    --data-path file1.parquet \
    --data-path file2.parquet \
    --data-path file3.parquet \
    --num-samples-per-file 5
```

### 方法 2：指定目录（自动发现）

使用 `--data-dir` 参数，脚本会自动找到目录下所有 `.parquet` 文件：

```bash
# 测试目录下所有 parquet 文件，每个文件 10 个样本
./run_baseline_test_multi.sh \
    --data-dir /app/xiaominl/datasets/air_sp11np_up3_sample1_nosw/ \
    --num-samples-per-file 10

# 测试目录下所有文件，总共 50 个样本（平均分配）
./run_baseline_test_multi.sh \
    --data-dir /path/to/dataset/ \
    --num-samples 50
```

### 方法 3：指定策略和保存图像

```bash
# 只测试随机策略，保存图像
./run_baseline_test_multi.sh \
    --data-path file1.parquet \
    --data-path file2.parquet \
    --num-samples-per-file 5 \
    --strategy random \
    --save-images

# 测试两种策略
./run_baseline_test_multi.sh \
    --data-dir /path/to/dataset/ \
    --num-samples-per-file 10 \
    --strategy both
```

---

## 参数说明

### 基本参数

| 参数 | 说明 | 示例 |
|-----|------|------|
| `--data-path PATH` | 指定单个 parquet 文件（可多次使用） | `--data-path file1.parquet --data-path file2.parquet` |
| `--data-dir DIR` | 指定包含 parquet 文件的目录 | `--data-dir /path/to/dataset/` |
| `--num-samples N` | 总样本数（平均分配到各文件） | `--num-samples 100` |
| `--num-samples-per-file N` | 每个文件的样本数（覆盖 --num-samples） | `--num-samples-per-file 10` |
| `--strategy STRATEGY` | 修复策略：random、reverse 或 both | `--strategy both` |
| `--save-images` | 保存图像文件 | `--save-images` |
| `--tool-service-ip IP` | 工具服务 IP 地址 | `--tool-service-ip 10.21.9.6` |

### 样本数分配逻辑

1. **如果指定 `--num-samples-per-file`**：
   - 每个文件使用固定数量的样本
   - 总样本数 = 文件数 × 每文件样本数

2. **如果只指定 `--num-samples`**：
   - 总样本数平均分配到各个文件
   - 每文件样本数 = 总样本数 ÷ 文件数

---

## 使用示例

### 示例 1：测试数据集目录

假设你有一个目录包含多个 parquet 分片：

```bash
/app/xiaominl/datasets/my_dataset/
├── shard-test-000000.parquet
├── shard-test-000001.parquet
├── shard-test-000002.parquet
└── shard-test-000003.parquet
```

**测试所有分片，每个 10 个样本：**

```bash
./run_baseline_test_multi.sh \
    --data-dir /app/xiaominl/datasets/my_dataset/ \
    --num-samples-per-file 10 \
    --strategy both
```

**输出示例**：
```
========================================
Baseline Restoration Test Configuration
========================================
Number of Files:    4
Files:
  - /app/xiaominl/datasets/my_dataset/shard-test-000000.parquet
  - /app/xiaominl/datasets/my_dataset/shard-test-000001.parquet
  - /app/xiaominl/datasets/my_dataset/shard-test-000002.parquet
  - /app/xiaominl/datasets/my_dataset/shard-test-000003.parquet
Samples per File:   10
Total Samples:      40
Strategy:           both
========================================
```

### 示例 2：测试指定的文件

```bash
./run_baseline_test_multi.sh \
    --data-path /app/xiaominl/datasets/dataset1/shard-test-000000.parquet \
    --data-path /app/xiaominl/datasets/dataset2/shard-test-000000.parquet \
    --num-samples 20 \
    --save-images
```

这会：
- 测试 2 个文件
- 总共 20 个样本（每个文件 10 个）
- 保存图像文件

### 示例 3：只测试逆序策略

```bash
./run_baseline_test_multi.sh \
    --data-path file1.parquet \
    --data-path file2.parquet \
    --data-path file3.parquet \
    --num-samples-per-file 5 \
    --strategy reverse
```

这会：
- 测试 3 个文件
- 每个文件 5 个样本（共 15 个）
- 只使用逆序修复策略

---

## 环境变量

也可以使用环境变量：

```bash
# 设置工具服务 IP
export TOOL_SERVICE_IP=10.21.9.35

# 运行测试
./run_baseline_test_multi.sh --data-dir /path/to/dataset/ --num-samples-per-file 10
```

---

## 输出结果

### 结果文件位置

所有结果保存在：`/app/xiaominl/DeepEyes_v2/tests/baseline/results/`

### 结果文件类型

对于每次运行，会生成以下文件：

```
results/
├── results_20251018_143025.json        # 详细结果（JSON）
├── summary_20251018_143025.txt         # 文本摘要
├── statistics_20251018_143025.csv      # CSV 统计
├── by_degradation_20251018_143025.csv  # 按退化类型分组统计
└── sample_0_random/                    # 图像（如果使用 --save-images）
    ├── degraded.png
    ├── original.png
    └── restored.png
```

### 结果合并

每个文件的结果会独立保存，带有时间戳。如果需要合并所有文件的统计数据，可以使用相同的输出目录。

---

## 与原版脚本对比

| 功能 | `run_baseline_test.sh` | `run_baseline_test_multi.sh` |
|-----|----------------------|----------------------------|
| 单文件测试 | ✅ | ✅ |
| 多文件测试 | ❌ | ✅ |
| 目录自动发现 | ❌ | ✅ |
| 每文件样本数控制 | ❌ | ✅ |
| 总样本数控制 | ✅ | ✅ |

---

## 常见问题

### Q1: 如何测试所有分片，但跳过某些文件？

**方法 1**: 使用 `--data-path` 逐个指定文件：
```bash
./run_baseline_test_multi.sh \
    --data-path file1.parquet \
    --data-path file3.parquet \
    --num-samples-per-file 10
```

**方法 2**: 先移动不需要的文件到其他目录，然后使用 `--data-dir`

### Q2: 如何确保每个文件测试相同数量的样本？

使用 `--num-samples-per-file` 而不是 `--num-samples`：

```bash
./run_baseline_test_multi.sh \
    --data-dir /path/to/dataset/ \
    --num-samples-per-file 10
```

### Q3: 能否混合使用 --data-path 和 --data-dir？

不能。脚本只支持其中一种方式。建议：
- 如果大部分文件在同一目录 → 使用 `--data-dir`
- 如果文件分散在不同位置 → 使用多个 `--data-path`

### Q4: 测试结果会覆盖吗？

不会。每次运行都会生成带时间戳的新文件。

### Q5: 如何查看某个文件测试失败？

脚本会在失败时停止并显示错误信息。检查输出中的：
```
✗ File N failed
```

---

## 性能建议

### 1. 合理分配样本数

- **小数据集（< 100 样本/文件）**: 可以全部测试
- **中等数据集（100-1000 样本/文件）**: 建议每文件 10-50 个样本
- **大数据集（> 1000 样本/文件）**: 建议每文件 5-20 个样本

### 2. 批量处理

如果有很多文件，可以分批处理：

```bash
# 批次 1: 前 5 个文件
./run_baseline_test_multi.sh \
    --data-path file1.parquet --data-path file2.parquet \
    --data-path file3.parquet --data-path file4.parquet \
    --data-path file5.parquet \
    --num-samples-per-file 10

# 批次 2: 后 5 个文件
./run_baseline_test_multi.sh \
    --data-path file6.parquet --data-path file7.parquet \
    --data-path file8.parquet --data-path file9.parquet \
    --data-path file10.parquet \
    --num-samples-per-file 10
```

### 3. 使用 --save-images 的注意事项

保存图像会消耗大量磁盘空间。如果测试大量样本，考虑：
- 只在小规模测试时使用 `--save-images`
- 或者定期清理 `results/` 目录

---

## 快速参考

### 最常用的命令

```bash
# 1. 测试目录下所有文件（推荐）
./run_baseline_test_multi.sh --data-dir /path/to/dataset/ --num-samples-per-file 10

# 2. 测试多个指定文件
./run_baseline_test_multi.sh \
    --data-path file1.parquet \
    --data-path file2.parquet \
    --num-samples 20

# 3. 完整测试（两种策略 + 保存图像）
./run_baseline_test_multi.sh \
    --data-dir /path/to/dataset/ \
    --num-samples-per-file 5 \
    --strategy both \
    --save-images
```

---

## 获取帮助

查看完整帮助信息：

```bash
./run_baseline_test_multi.sh --help
```

---

**最后更新**: 2025-10-18


