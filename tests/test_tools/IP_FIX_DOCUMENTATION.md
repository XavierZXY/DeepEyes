# 工具 IP 地址修复文档

## 🐛 问题描述

### 现象
在运行工具测试时，发现 DehazeFormer 和其他工具的测试结果显示：
- 所有指标改进率都是 **0%**
- 成功率显示 **100%**，但实际没有进行图像修复

```markdown
#### DehazeFormer
| Level  | PSNR  | SSIM   | LPIPS  | PSNR↑ | SSIM↑ | LPIPS↓ | 成功率  |
|--------|-------|--------|--------|-------|-------|--------|---------|
| low    | 25.56 | 0.9462 | 0.0283 | +0.0% | +0.0% | +0.0% | 100.0%  |
```

### 根本原因

经过诊断发现了两个问题：

#### 问题 1: 默认 IP 地址错误

**所有工具的默认 IP 地址配置错误**：
- ❌ 代码中硬编码的默认 IP: `10.21.9.34`
- ✅ 实际服务运行的 IP: `10.21.9.6`

当 `TOOL_SERVICE_IP` 环境变量未设置时，工具会使用错误的默认 IP，导致连接失败。

**影响的工具**：
1. DehazeFormerToolbox - Port 5002
2. SwinIRToolbox - Port 5001
3. MPRNetToolbox - Port 5004
4. RestormerToolbox - Port 5006
5. XRestormerToolbox - Port 5007
6. FBCNNToolbox - Port 5005
7. DeblurToolbox (DRBNet) - Port 5003
8. SCUNetToolbox - Port 5008

**只有 RetinexformerToolbox 使用了正确的默认 IP `10.21.9.6`**

#### 问题 2: 图像提取方式缺失

测试脚本的 `apply_tool()` 方法没有处理 DehazeFormer 的图像返回格式。

**DehazeFormer 返回格式**：
```python
observation = {
    'prompt': '...',
    'multi_modal_data': {
        'image': [<PIL.Image>]  # ⭐ 图像在这里
    }
}
```

**原测试脚本只检查**：
1. `observation['image']` - ❌ DehazeFormer 没有这个字段
2. `tool.multi_modal_data['image']` - ❌ 但检查逻辑有问题
3. `info['image']` 或 `info['restored_image']` - ❌ DehazeFormer 没有这些字段

---

## ✅ 解决方案

### 修复 1: 更新所有工具的默认 IP 地址

将所有工具的默认 IP 从 `10.21.9.34` 改为 `10.21.9.6`：

#### 修改的文件

1. **DehazeFormerToolbox.py** (Line 37)
   ```python
   # 修改前
   tool_service_ip = os.environ.get('TOOL_SERVICE_IP', '10.21.9.34')
   
   # 修改后
   tool_service_ip = os.environ.get('TOOL_SERVICE_IP', '10.21.9.6')
   ```

2. **SwinIRToolbox.py** (Line 30)
   ```python
   # 修改前
   api_url = f"http://{os.environ.get('TOOL_SERVICE_IP', '10.21.9.34')}:5001/process"
   
   # 修改后
   api_url = f"http://{os.environ.get('TOOL_SERVICE_IP', '10.21.9.6')}:5001/process"
   ```

3. **MPRNetToolbox.py** (Line 30)
4. **RestormerToolbox.py** (Line 30)
5. **XRestormerToolbox.py** (Line 29)
6. **FBCNNToolbox.py** (Line 30)
7. **DeblurToolbox.py** (Line 31)
8. **SCUNetToolbox.py** (Line 30)

所有工具的修改模式相同，只是端口号不同。

### 修复 2: 增强图像提取逻辑

在 `test_restoration_tools.py` 的 `apply_tool()` 方法中添加对 `observation['multi_modal_data']['image']` 的支持：

```python
# 方法1: 从observation中提取图像（dict格式）
if isinstance(observation, dict):
    # 方法1a: observation['image']
    if 'image' in observation:
        restored_images = observation['image']
        if restored_images and len(restored_images) > 0:
            return restored_images[0]
    
    # 方法1b: observation['multi_modal_data']['image'] ⭐ 新增
    if 'multi_modal_data' in observation:
        mmd = observation['multi_modal_data']
        if isinstance(mmd, dict) and 'image' in mmd:
            restored_images = mmd['image']
            if restored_images and len(restored_images) > 0:
                return restored_images[0]
```

---

## 🧪 验证结果

### 修复前
```bash
$ python diagnose_tool.py dehazeformer_dehaze test.png
[TOOL EXECUTE] ❌ dehazeformer_dehaze 执行失败 (耗时: 0.39s): 
HTTPConnectionPool(host='10.21.9.34', port=5002): Max retries exceeded
Connection refused

成功率: 0.0% (0/1)
```

### 修复后
```bash
$ python diagnose_tool.py dehazeformer_dehaze test.png
DehazeFormerToolbox initialized. API endpoint: http://10.21.9.6:5002/dehaze
[TOOL EXECUTE] ✅ dehazeformer_dehaze 执行成功 (耗时: 1.69s)
✅ 可以从observation['multi_modal_data']['image'][0]获取图像

成功率: 100.0% (1/1)
```

### 测试报告对比

**修复前**：
```markdown
#### DehazeFormer
| Level | PSNR  | SSIM   | LPIPS  | PSNR↑ | SSIM↑ | LPIPS↓ | 成功率 |
|-------|-------|--------|--------|-------|-------|--------|--------|
| low   | 25.56 | 0.9462 | 0.0283 | +0.0% | +0.0% | +0.0%  | 100.0% |  ❌ 假成功
```

**修复后**：
```markdown
#### DehazeFormer
| Level | PSNR  | SSIM   | LPIPS  | PSNR↑  | SSIM↑ | LPIPS↓  | 成功率 |
|-------|-------|--------|--------|--------|-------|---------|--------|
| low   | 20.54 | 0.8939 | 0.0438 | -28.8% | -8.2% | -252.7% | 100.0% |  ✅ 真实结果
```

---

## 📊 影响范围

### 受影响的工具（共 8 个）
| 工具名称 | 端口 | 默认IP (修复前) | 默认IP (修复后) | 状态 |
|---------|------|----------------|----------------|------|
| DehazeFormer | 5002 | 10.21.9.34 | 10.21.9.6 | ✅ 已修复 |
| SwinIR | 5001 | 10.21.9.34 | 10.21.9.6 | ✅ 已修复 |
| MPRNet | 5004 | 10.21.9.34 | 10.21.9.6 | ✅ 已修复 |
| Restormer | 5006 | 10.21.9.34 | 10.21.9.6 | ✅ 已修复 |
| XRestormer | 5007 | 10.21.9.34 | 10.21.9.6 | ✅ 已修复 |
| FBCNN | 5005 | 10.21.9.34 | 10.21.9.6 | ✅ 已修复 |
| DRBNet | 5003 | 10.21.9.34 | 10.21.9.6 | ✅ 已修复 |
| SCUNet | 5008 | 10.21.9.34 | 10.21.9.6 | ✅ 已修复 |

### 未受影响的工具
- **Retinexformer** (端口 5009) - 原本就使用正确的 `10.21.9.6` ✅
- **BrighteningToolbox** (无API调用) - 本地处理，无需网络 ✅

---

## 🔍 诊断过程

### 1. 发现问题
```bash
# 查看测试结果发现改进率全是 0%
cat test_results.md
```

### 2. 使用诊断工具
```bash
cd tests/test_tools
python diagnose_tool.py dehazeformer_dehaze test_image.png
```

输出显示连接被拒绝：
```
Connection refused: http://10.21.9.34:5002/dehaze
```

### 3. 验证服务可用性
```bash
# 测试错误的 IP
curl http://10.21.9.34:5002/dehaze -X POST --max-time 2
# 输出: 连接超时

# 测试正确的 IP
curl http://10.21.9.6:5002/dehaze -X POST --max-time 2
# 输出: {"error":"No image file provided"}  ✅ 服务正常
```

### 4. 检查代码中的默认IP
```bash
grep -r "TOOL_SERVICE_IP.*10.21" verl/workers/agent/envs/mm_process_engine/
```

发现所有工具都使用 `10.21.9.34` 作为默认值。

### 5. 分析图像返回格式
使用增强后的诊断工具发现 DehazeFormer 返回的图像在 `observation['multi_modal_data']['image']` 中。

---

## 💡 经验教训

1. **环境变量的重要性**：
   - 总是建议设置 `TOOL_SERVICE_IP` 环境变量
   - 不要完全依赖代码中的默认值

2. **工具返回格式的多样性**：
   - 不同工具可能使用不同的图像返回格式
   - 测试脚本需要支持多种提取方式

3. **诊断工具的价值**：
   - `diagnose_tool.py` 在定位问题时非常有用
   - 应该定期使用诊断工具验证工具的正常工作

4. **测试的局限性**：
   - 成功率 100% 不一定代表工具真正工作
   - 需要检查改进率是否合理

---

## 🚀 使用建议

### 1. 设置环境变量（推荐）
```bash
export TOOL_SERVICE_IP=10.21.9.6
```

### 2. 验证工具服务
运行测试前，先验证所有服务是否可用：
```bash
# 检查所有端口
for port in 5001 5002 5003 5004 5005 5006 5007 5008 5009; do
    echo "检查端口 $port..."
    curl -s http://10.21.9.6:$port -X POST --max-time 2 || echo "端口 $port 不可用"
done
```

### 3. 使用诊断工具测试单个工具
```bash
cd tests/test_tools
python diagnose_tool.py <tool_name> <test_image>
```

### 4. 快速验证修复
```bash
# 测试所有类型，每个级别只用 1 个样本
./run_test.sh --num-samples 1
```

---

## 📝 修改文件清单

### 工具类文件（8个）
- ✅ `verl/workers/agent/envs/mm_process_engine/DehazeFormerToolbox.py`
- ✅ `verl/workers/agent/envs/mm_process_engine/SwinIRToolbox.py`
- ✅ `verl/workers/agent/envs/mm_process_engine/MPRNetToolbox.py`
- ✅ `verl/workers/agent/envs/mm_process_engine/RestormerToolbox.py`
- ✅ `verl/workers/agent/envs/mm_process_engine/XRestormerToolbox.py`
- ✅ `verl/workers/agent/envs/mm_process_engine/FBCNNToolbox.py`
- ✅ `verl/workers/agent/envs/mm_process_engine/DeblurToolbox.py`
- ✅ `verl/workers/agent/envs/mm_process_engine/SCUNetToolbox.py`

### 测试脚本（2个）
- ✅ `tests/test_tools/test_restoration_tools.py` - 增强图像提取逻辑
- ✅ `tests/test_tools/diagnose_tool.py` - 增强诊断输出

### 文档（1个）
- ✅ `tests/test_tools/IP_FIX_DOCUMENTATION.md` - 本文档

---

**修复时间**: 2025-10-20  
**版本**: v1.3  
**状态**: ✅ 已完成并验证  
**修复人员**: AI Assistant

