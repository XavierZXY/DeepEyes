# 🚀 工具测试快速参考

## 一键测试命令

```bash
# 1. 设置环境变量
export TOOL_SERVICE_IP=10.21.9.6

# 2. 快速测试（5个样本）
python3 tests/test_all_tools_metrics.py \
    --parquet /app/xiaominl/datasets/air_d1_sp9_up2_balanced/shard-test-000000.parquet \
    --output_dir ./quick_test \
    --max_samples 5

# 3. 查看结果
cat ./quick_test/summary_report.txt
```

---

## 常用命令

### 完整测试
```bash
python3 tests/test_all_tools_metrics.py \
    --parquet /app/xiaominl/datasets/air_d1_sp9_up2_bs128_n8_balanced/shard-test-000000.parquet \
    --output_dir ./full_test
```

### 测试特定工具
```bash
python3 tests/test_all_tools_metrics.py \
    --parquet /path/to/data.parquet \
    --output_dir ./results \
    --tools swinir_denoising restormer_motion_deblurring
```

### 限制样本数
```bash
python3 tests/test_all_tools_metrics.py \
    --parquet /path/to/data.parquet \
    --output_dir ./results \
    --max_samples 50
```

### 不保存图像
```bash
python3 tests/test_all_tools_metrics.py \
    --parquet /path/to/data.parquet \
    --output_dir ./results \
    --no_save_images
```

---

## 可用工具列表

1. `swinir_denoising` - 去噪
2. `swinir_jpeg_artifact_removal` - JPEG伪影去除
3. `swinir_super_resolution` - 超分辨率
4. `restormer_motion_deblurring` - 运动去模糊
5. `restormer_defocus_deblurring` - 散焦去模糊
6. `restormer_deraining` - 去雨
7. `xrestormer_motion_deblurring` - 运动去模糊
8. `xrestormer_deraining` - 去雨
9. `mprnet_denoising` - 去噪
10. `mprnet_motion_deblurring` - 运动去模糊
11. `mprnet_deraining` - 去雨
12. `fbcnn_jpeg_artifact_removal` - JPEG伪影去除
13. `drbnet_defocus_deblurring` - 散焦去模糊
14. `dehazeformer_dehaze` - 去雾

---

## 输出文件

```
output_dir/
├── detailed_results.csv     # 详细数据（Excel可打开）
├── summary_report.txt       # 汇总报告（文本）
└── images/                  # 图像文件
    └── sample_X/
        ├── original.png     # 原图
        ├── degraded.png     # 退化图
        └── tool_name.png    # 修复图
```

---

## 指标说明

| 指标 | 范围 | 方向 | 说明 |
|------|------|------|------|
| PSNR | 0-100+ dB | ↑ 越高越好 | 峰值信噪比 |
| SSIM | 0-1 | ↑ 越高越好 | 结构相似性 |
| LPIPS | 0-1 | ↓ 越低越好 | 感知损失 |

---

## 故障排除

### 连接错误
```bash
# 检查工具服务
curl http://$TOOL_SERVICE_IP:5001/health

# 检查环境变量
echo $TOOL_SERVICE_IP
```

### GPU问题
```bash
# 检查GPU
nvidia-smi  # 或 rocm-smi

# 查看GPU使用情况
python3 tests/validate_test_script.py
```

---

## 帮助命令

```bash
# 查看完整帮助
python3 tests/test_all_tools_metrics.py --help

# 查看使用示例
bash tests/example_test_usage.sh

# 验证功能
python3 tests/validate_test_script.py

# 查看详细文档
cat tests/README_TOOL_TESTING.md
```

