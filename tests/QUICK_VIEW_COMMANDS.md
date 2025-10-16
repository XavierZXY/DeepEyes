# 🔍 快速查看结果命令

测试完成后，使用这些命令快速查看结果。

---

## 📄 查看文本报告

### 汇总报告（退化图基线+工具对比）
```bash
cat output_dir/summary_report.txt
```

### 统计分析报告（工具针对性分析）
```bash
cat output_dir/statistical_analysis.txt
```

### 只看退化图基线
```bash
cat output_dir/summary_report.txt | head -20
```

### 只看工具性能汇总
```bash
cat output_dir/summary_report.txt | grep -A 5 "工具:"
```

### 只看工具针对性分析
```bash
cat output_dir/statistical_analysis.txt | grep -A 10 "工具针对性分析"
```

### 找出最佳工具
```bash
cat output_dir/summary_report.txt | grep -A 20 "推荐工具"
```

---

## 📊 查看CSV数据

### 预览前20行
```bash
head -20 output_dir/detailed_results.csv
```

### 在Excel中打开
```bash
libreoffice output_dir/detailed_results.csv
```

### 只看成功的测试
```bash
grep "True" output_dir/detailed_results.csv
```

### 只看失败的测试
```bash
grep "False" output_dir/detailed_results.csv
```

### 按PSNR改进排序
```bash
cat output_dir/detailed_results.csv | sort -t',' -k14 -nr | head -20
```

---

## 📈 查看可视化图表

### 查看所有图表（Linux）
```bash
eog output_dir/plots/*.png
```

### 查看所有图表（Mac）
```bash
open output_dir/plots/*.png
```

### 单独查看某个图表
```bash
# 工具PSNR改进对比
eog output_dir/plots/tool_psnr_improvement.png

# 退化类型热力图
eog output_dir/plots/degradation_heatmap.png

# 改进量分布
eog output_dir/plots/tool_improvement_distribution.png

# 散点图
eog output_dir/plots/baseline_vs_restored.png

# 成功率
eog output_dir/plots/success_rate_pie.png
```

### 复制图表到其他位置
```bash
# 复制到论文目录
cp output_dir/plots/*.png ~/paper/figures/

# 只复制热力图
cp output_dir/plots/degradation_heatmap.png ~/presentation/
```

---

## 🖼️ 查看图像对比

### 查看某个样本的所有图像
```bash
ls output_dir/images/sample_0/
```

### 查看原图、退化图、修复图
```bash
# Linux
eog output_dir/images/sample_0/*.png

# Mac
open output_dir/images/sample_0/*.png
```

### 对比特定工具的效果
```bash
eog output_dir/images/sample_0/original.png \
    output_dir/images/sample_0/degraded.png \
    output_dir/images/sample_0/mprnet_denoising.png
```

---

## 🔍 数据分析命令

### 统计成功率
```bash
python3 << 'EOF'
import pandas as pd
df = pd.read_csv('output_dir/detailed_results.csv')
success_rate = df.groupby('tool_name')['success'].mean() * 100
print(success_rate.sort_values(ascending=False))
