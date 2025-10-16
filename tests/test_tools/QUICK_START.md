# 🚀 快速开始指南

## 1. 环境准备

### 检查数据集结构
```bash
# 确保数据集目录结构正确
ls /path/to/dataset/
# 应该看到: original/ haze/ noise/ rain/ 等文件夹

ls /path/to/dataset/original/
# 应该看到: 000001.png 000002.png ...

ls /path/to/dataset/haze/low/
# 应该看到: 000001_level1.png 000002_level1.png ...
```

### 启动工具服务
确保以下API服务正在运行：
- DehazeFormer (端口5002)
- SwinIR (端口5001)
- MPRNet (端口5004)
- Restormer (端口5006)
- 等...

### 设置环境变量
```bash
export TOOL_SERVICE_IP=10.21.9.34  # 工具服务所在IP
```

---

## 2. 快速测试

### 方式1: 使用Shell脚本（推荐）

```bash
cd /app/xiaominl/DeepEyes_v2/tests/test_tools

# 快速测试（每个级别3个样本）
./run_test.sh --quick --types haze

# 测试指定类型，每个级别10个样本
./run_test.sh -n 10 -t haze,noise,rain

# 完整测试所有类型
./run_test.sh --full -d /path/to/dataset
```

### 方式2: 直接使用Python

```bash
cd /app/xiaominl/DeepEyes_v2/tests/test_tools

# 快速测试
python test_restoration_tools.py \
    --dataset /path/to/dataset \
    --types haze \
    --num-samples 3 \
    --output ./quick_test

# 完整测试
python test_restoration_tools.py \
    --dataset /path/to/dataset \
    --output ./full_test
```

---

## 3. 常用命令示例

### 测试单个类型
```bash
# 只测试去雾
./run_test.sh --types haze -n 10

# 只测试去噪
./run_test.sh --types noise -n 10

# 只测试去模糊
./run_test.sh --types motion_blur,defocus_blur -n 10
```

### 排除某些类型
```bash
# 测试除了dark和low_resolution之外的所有类型
./run_test.sh --exclude dark,low_resolution -n 10
```

### 只测试特定级别
```bash
# 只测试low和medium级别
./run_test.sh --levels low,medium -n 10

# 只测试high级别
./run_test.sh --levels high -n 20
```

### 组合使用
```bash
# 测试haze和noise的low和medium级别，每个级别5个样本
./run_test.sh \
    --types haze,noise \
    --levels low,medium \
    --num-samples 5 \
    --output ./haze_noise_test
```

---

## 4. 查看结果

### 查看Markdown报告
```bash
cat ./test_results_*/test_results.md
# 或使用文本编辑器打开
```

### 查看CSV表格
```bash
# 用Excel/LibreOffice打开
xdg-open ./test_results_*/test_results.csv

# 或用命令行查看
column -t -s, ./test_results_*/test_results.csv | less -S
```

### 分析JSON数据
```bash
# 使用jq工具美化输出
cat ./test_results_*/test_results.json | jq '.'

# 提取特定工具的结果
cat ./test_results_*/test_results.json | jq '.haze.tools.dehazeformer_dehaze'
```

---

## 5. 结果解读

### 查看基线指标
基线 = 退化图 vs 原图的指标（工具处理前）
```
Baseline PSNR: 15.23 dB  (退化图质量)
Baseline SSIM: 0.6521    (退化图结构相似度)
Baseline LPIPS: 0.3421   (退化图感知距离)
```

### 查看修复效果
```
Restored PSNR: 28.45 dB  (修复后质量)
Restored SSIM: 0.8921    (修复后结构相似度)
Restored LPIPS: 0.1234   (修复后感知距离)

改进:
- PSNR: +86.7% (提升越多越好)
- SSIM: +36.8% (提升越多越好)
- LPIPS: +63.9% (降低越多越好，注意LPIPS是越低越好)
```

### 成功率
```
Success Rate: 100.0% (10/10)
- 表示10个样本中有10个成功修复
- 如果<100%，说明部分样本工具执行失败
```

---

## 6. 故障排查

### 问题1: 找不到数据集
```
[WARNING] No levels found for haze
```
**解决**: 
```bash
# 检查目录结构
ls -R /path/to/dataset/haze/
# 确保有 low/ medium/ high/ 等子目录
```

### 问题2: 工具调用失败
```
[ERROR] Tool dehazeformer_dehaze execution failed
```
**解决**:
```bash
# 检查工具服务是否运行
curl http://$TOOL_SERVICE_IP:5002/dehaze -X POST

# 检查环境变量
echo $TOOL_SERVICE_IP
```

### 问题3: 内存不足
```
CUDA out of memory
```
**解决**:
```bash
# 减少样本数量
./run_test.sh --num-samples 3

# 或只测试部分类型
./run_test.sh --types haze --num-samples 5
```

---

## 7. 高级用法

### 保存中间结果
```bash
# 重定向输出到日志文件
./run_test.sh --full -d /data/dataset 2>&1 | tee test.log
```

### 批量测试不同配置
```bash
# 创建批量测试脚本
cat > batch_test.sh << 'EOF'
#!/bin/bash
for type in haze noise rain; do
    ./run_test.sh --types $type -n 10 -o ./results_$type
done
EOF

chmod +x batch_test.sh
./batch_test.sh
```

### 对比两个工具服务器
```bash
# 测试服务器A
./run_test.sh --ip 10.21.9.34 -n 10 -o ./results_serverA

# 测试服务器B
./run_test.sh --ip 10.21.9.35 -n 10 -o ./results_serverB

# 对比结果
diff -u ./results_serverA/test_results.md ./results_serverB/test_results.md
```

---

## 8. 最佳实践

### 1. 渐进式测试
```bash
# Step 1: 快速验证（3个样本）
./run_test.sh --quick --types haze

# Step 2: 中等规模测试（10个样本）
./run_test.sh -n 10 --types haze,noise

# Step 3: 完整测试（所有样本）
./run_test.sh --full
```

### 2. 关注关键指标
- **PSNR**: 关注改进百分比，通常>50%表示效果好
- **SSIM**: 修复后应>0.8为佳
- **LPIPS**: 修复后应<0.2为佳
- **成功率**: 应>95%，否则需要检查工具稳定性

### 3. 记录测试配置
```bash
# 保存测试配置
cat > test_config.txt << EOF
测试时间: $(date)
数据集: /path/to/dataset
样本数: 10
类型: haze,noise,rain
工具IP: $TOOL_SERVICE_IP
EOF
```

---

## 9. 输出示例

### Markdown报告示例
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

---

**最后更新**: 2025-10-14  
**维护者**: DeepEyes Team

