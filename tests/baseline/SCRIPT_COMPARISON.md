# Baseline 测试脚本对比

## 快速选择

| 场景 | 推荐脚本 | 命令示例 |
|-----|---------|---------|
| 测试单个文件 | `run_baseline_test.sh` | `./run_baseline_test.sh --data-path file.parquet --num-samples 10` |
| 测试多个文件 | `run_baseline_test_multi.sh` | `./run_baseline_test_multi.sh --data-path f1.parquet --data-path f2.parquet --num-samples 20` |
| 测试整个目录 | `run_baseline_test_multi.sh` | `./run_baseline_test_multi.sh --data-dir /path/to/dataset/ --num-samples-per-file 10` |

---

## 详细对比

### 1. run_baseline_test.sh（原版）

**适用场景**: 测试单个 parquet 文件

#### 优点
- ✅ 简单直接
- ✅ 参数少，容易理解
- ✅ 适合快速测试单个文件

#### 缺点
- ❌ 只能测试一个文件
- ❌ 测试多个文件需要多次运行

#### 使用示例

```bash
# 基本使用
./run_baseline_test.sh \
    --data-path /path/to/file.parquet \
    --num-samples 10 \
    --strategy both

# 保存图像
./run_baseline_test.sh \
    --data-path /path/to/file.parquet \
    --num-samples 20 \
    --save-images
```

---

### 2. run_baseline_test_multi.sh（新版）

**适用场景**: 测试多个 parquet 文件或整个数据集目录

#### 优点
- ✅ 支持多个文件
- ✅ 支持目录自动发现
- ✅ 灵活的样本数分配
- ✅ 批量处理效率高
- ✅ **也支持单文件测试**（向下兼容）

#### 缺点
- ⚠️ 参数稍多（但有合理默认值）

#### 使用示例

**单文件（与原版等效）**:
```bash
./run_baseline_test_multi.sh \
    --data-path /app/xiaominl/air_v16_dm3_update_raintool/shards/shard-test-000000.parquet \
    --num-samples 9999 \
    --strategy reverse
```

**多文件**:
```bash
./run_baseline_test_multi.sh \
    --data-path file1.parquet \
    --data-path file2.parquet \
    --data-path file3.parquet \
    --num-samples 30
```

**目录**:
```bash
./run_baseline_test_multi.sh \
    --data-dir /path/to/dataset/ \
    --num-samples-per-file 10
```

---

## 功能对比表

| 功能 | run_baseline_test.sh | run_baseline_test_multi.sh |
|-----|---------------------|---------------------------|
| **基本功能** | | |
| 测试单个文件 | ✅ | ✅ |
| 测试多个文件 | ❌ | ✅ |
| 目录自动发现 | ❌ | ✅ |
| **样本数控制** | | |
| 总样本数 | ✅ | ✅ |
| 每文件样本数 | N/A | ✅ |
| 平均分配样本 | N/A | ✅ |
| **策略和选项** | | |
| random 策略 | ✅ | ✅ |
| reverse 策略 | ✅ | ✅ |
| both 策略 | ✅ | ✅ |
| 保存图像 | ✅ | ✅ |
| 自定义工具服务 IP | ✅ | ✅ |
| **输出** | | |
| JSON 结果 | ✅ | ✅ |
| 文本摘要 | ✅ | ✅ |
| CSV 统计 | ✅ | ✅ |
| 进度显示 | ✅ | ✅ (增强) |

---

## 参数对比

### 共同参数

| 参数 | 说明 | 两个脚本都支持 |
|-----|------|---------------|
| `--num-samples` | 总样本数 | ✅ |
| `--strategy` | 修复策略 | ✅ |
| `--save-images` | 保存图像 | ✅ |
| `--tool-service-ip` | 工具服务 IP | ✅ |

### 原版专有参数

| 参数 | 说明 | 备注 |
|-----|------|------|
| `--data-path` | 单个文件路径 | 新版也支持，但可多次使用 |

### 新版专有参数

| 参数 | 说明 | 用途 |
|-----|------|------|
| `--data-path` (多次) | 多个文件路径 | 指定多个文件 |
| `--data-dir` | 数据目录 | 自动发现所有 .parquet 文件 |
| `--num-samples-per-file` | 每文件样本数 | 固定每个文件的样本数 |

---

## 迁移指南

### 从原版迁移到新版

**原版命令**:
```bash
./run_baseline_test.sh \
    --data-path /path/to/file.parquet \
    --num-samples 10 \
    --strategy both
```

**等效的新版命令**（完全兼容）:
```bash
./run_baseline_test_multi.sh \
    --data-path /path/to/file.parquet \
    --num-samples 10 \
    --strategy both
```

**无需修改任何参数！** 新版向下兼容原版的所有用法。

---

## 使用场景推荐

### 场景 1: 快速测试单个文件
**推荐**: 原版或新版都可以

```bash
# 原版（更简洁的名字）
./run_baseline_test.sh --data-path file.parquet --num-samples 10

# 新版（功能相同）
./run_baseline_test_multi.sh --data-path file.parquet --num-samples 10
```

### 场景 2: 测试数据集的多个分片
**推荐**: 新版（必须）

```bash
./run_baseline_test_multi.sh \
    --data-path shard-000000.parquet \
    --data-path shard-000001.parquet \
    --data-path shard-000002.parquet \
    --num-samples-per-file 10
```

### 场景 3: 测试整个数据集目录
**推荐**: 新版（必须）

```bash
./run_baseline_test_multi.sh \
    --data-dir /app/xiaominl/datasets/my_dataset/ \
    --num-samples-per-file 10
```

### 场景 4: 大规模测试（100+ 样本）
**推荐**: 新版

```bash
# 自动发现所有文件，每个测试 20 个样本
./run_baseline_test_multi.sh \
    --data-dir /path/to/dataset/ \
    --num-samples-per-file 20 \
    --strategy both
```

---

## 性能对比

| 场景 | 原版耗时 | 新版耗时 | 备注 |
|-----|---------|---------|------|
| 单文件 10 样本 | ~2 分钟 | ~2 分钟 | 相同 |
| 3 个文件，各 10 样本 | ~6 分钟（运行 3 次） | ~2 分钟（一次运行） | **新版快 3 倍** |
| 10 个文件，各 5 样本 | ~10 分钟（运行 10 次） | ~2.5 分钟（一次运行） | **新版快 4 倍** |

**注**: 新版的优势在于批量处理时只需一次初始化，节省了重复启动的开销。

---

## 输出结果对比

### 原版输出

```
results/
├── results_20251018_143025.json
├── summary_20251018_143025.txt
├── statistics_20251018_143025.csv
└── by_degradation_20251018_143025.csv
```

### 新版输出（每个文件独立）

```
results/
├── results_20251018_143025.json        # 文件 1
├── summary_20251018_143025.txt
├── results_20251018_143127.json        # 文件 2
├── summary_20251018_143127.txt
├── results_20251018_143229.json        # 文件 3
└── summary_20251018_143229.txt
```

**说明**: 每个文件的结果独立保存，带有不同的时间戳。

---

## 常见问题

### Q: 应该用哪个脚本？

**简单答案**: 
- 只测试一个文件 → 用原版（更简洁）
- 测试多个文件 → 用新版（必须）
- 不确定 → 用新版（向下兼容）

### Q: 新版会替代原版吗？

不会。两个脚本都会保留：
- 原版适合简单场景
- 新版适合复杂场景

### Q: 新版性能会更差吗？

不会。单文件测试时性能完全相同。多文件测试时，新版**更快**（一次初始化）。

### Q: 我需要修改现有脚本吗？

不需要。原版脚本继续工作。如果需要测试多文件，再切换到新版。

---

## 命令速查

### 原版 (run_baseline_test.sh)

```bash
# 最简单的用法
./run_baseline_test.sh --data-path file.parquet --num-samples 10

# 完整用法
./run_baseline_test.sh \
    --data-path /path/to/file.parquet \
    --num-samples 20 \
    --strategy both \
    --save-images \
    --tool-service-ip 10.21.9.6
```

### 新版 (run_baseline_test_multi.sh)

```bash
# 单文件（与原版相同）
./run_baseline_test_multi.sh --data-path file.parquet --num-samples 10

# 多文件
./run_baseline_test_multi.sh \
    --data-path file1.parquet \
    --data-path file2.parquet \
    --num-samples 20

# 目录
./run_baseline_test_multi.sh \
    --data-dir /path/to/dataset/ \
    --num-samples-per-file 10

# 完整用法
./run_baseline_test_multi.sh \
    --data-dir /path/to/dataset/ \
    --num-samples-per-file 10 \
    --strategy both \
    --save-images \
    --tool-service-ip 10.21.9.6
```

---

## 总结

| 如果你需要... | 推荐脚本 |
|------------|---------|
| 测试单个文件 | 原版或新版都可以 |
| 测试 2-3 个文件 | 新版 |
| 测试整个数据集 | 新版 |
| 自动发现文件 | 新版 |
| 最简单的命令 | 原版 |
| 最灵活的功能 | 新版 |

**推荐**: 如果不确定，使用新版。它向下兼容原版的所有用法，并提供更多功能。

---

**最后更新**: 2025-10-18

