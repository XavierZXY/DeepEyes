# 工具执行失败问题诊断

## 🚨 发现的问题

从最新日志 `debug_for_AIR_multideg_plan_ref_bs64_n4_spv15_lr1e-6_datarand_newraintool_mi300.log` 中发现多个工具执行失败。

---

## 🐛 问题1: Restormer API 服务错误

### 错误信息

```
❌ restormer_defocus_deblurring 执行失败: 
   Failed to connect to Restormer API at http://10.21.9.6:5006/process
   Error: 500 Server Error: INTERNAL SERVER ERROR

❌ restormer_motion_deblurring 执行失败:
   500 Server Error: INTERNAL SERVER ERROR
```

### 影响范围

- `restormer_defocus_deblurring` - 散焦去模糊
- `restormer_motion_deblurring` - 运动去模糊
- `restormer_deraining` - 可能也受影响

### 根本原因

**Restormer API 服务（端口5006）出现内部错误**

可能原因：
1. GPU显存不足
2. 服务崩溃或重启中
3. 输入图像格式问题
4. 服务负载过高

### 解决方案

#### 方案1: 检查服务状态

```bash
# 检查服务是否在运行
curl http://10.21.9.6:5006/health 2>/dev/null || echo "服务无响应"

# 检查GPU状态
ssh 10.21.9.6 nvidia-smi
```

#### 方案2: 重启服务

```bash
# SSH到服务器
ssh 10.21.9.6

# 重启Restormer服务
# (具体命令取决于你的部署方式)
```

#### 方案3: 临时禁用Restormer工具

如果服务短期内无法修复，可以临时禁用：

```python
# 在 parallel_env.py 的映射表中移除
'motion blur': ['xrestormer_motion_deblurring', 'mprnet_motion_deblurring'],  # 移除restormer
'defocus blur': ['drbnet_defocus_deblurring'],  # 移除restormer
```

---

## 🐛 问题2: HAT 超分辨率图像过大

### 错误信息

```
❌ hat_super_resolution 执行失败 (耗时: 79.81s):
   Image size (185303040 pixels) exceeds limit of 178956970 pixels
   could be decompression bomb DOS attack
```

### 问题分析

```
图像大小: 185,303,040 像素
PIL限制: 178,956,970 像素
超出: 6,346,070 像素 (约3.5%)
```

这是PIL的安全限制，防止解压缩炸弹攻击。

### 根本原因

**图像太大**，可能是：
1. 输入图像本身很大
2. 超分辨率后图像更大（2x或4x放大）

### 解决方案

#### 方案1: 增加PIL限制（推荐）

在 `HATToolbox.py` 中添加：

```python
from PIL import Image

# 在类开头或 __init__ 中
Image.MAX_IMAGE_PIXELS = 200000000  # 提升到2亿像素
```

#### 方案2: 预处理大图像

在调用HAT前，检查并缩小过大的图像：

```python
def _resize_if_too_large(image, max_pixels=150000000):
    pixels = image.width * image.height
    if pixels > max_pixels:
        scale = (max_pixels / pixels) ** 0.5
        new_size = (int(image.width * scale), int(image.height * scale))
        return image.resize(new_size, Image.LANCZOS)
    return image
```

#### 方案3: 使用tile模式

HAT工具支持tile模式处理大图：

```python
# 确保使用tile参数
{
    "scale": 2,
    "tile": "true",  # 启用分块处理
    "tile_size": 512  # 减小tile大小
}
```

---

## 🐛 问题3: 代码错误 - 'str' object has no attribute 'get'

### 错误信息

```
[ERROR T1-样本X] 工具3执行异常: 'str' object has no attribute 'get'
```

### 根本原因

在 `parallel_env.py` 第1287行：

```python
# 之前的代码
print(f'结果: multi_modal_data={tool_result.get("multi_modal_data") is not None}')
```

当工具执行失败时，`tool_result` 可能是错误字符串而不是字典，调用 `.get()` 会报错。

### 解决方案 ✅

**已修复！** 改为：

```python
# 修复后的代码
has_multi_modal = isinstance(tool_result, dict) and tool_result.get("multi_modal_data") is not None
print(f'结果: multi_modal_data={has_multi_modal}')
```

---

## 📊 问题统计

### 从日志分析

```bash
工具失败频率:
- Restormer API: 频繁失败（500错误）
- HAT API: 偶尔失败（图像过大）
- 其他工具: 基本正常
```

### 影响

```
工具成功率估算:
- Restormer系列: ~70-80% (有500错误)
- HAT: ~95% (偶尔图像过大)
- 其他工具: ~99%
```

**这会影响训练效果！** 工具失败导致：
- 奖励为0或负数
- 模型学习受干扰
- 某些退化类型的统计偏低

---

## 🔧 立即行动建议

### 优先级1: 修复Restormer服务（紧急）

```bash
# 1. 检查服务
curl http://10.21.9.6:5006/health

# 2. 检查日志
ssh 10.21.9.6
tail -100 /path/to/restormer/service.log

# 3. 重启服务
systemctl restart restormer  # 或者你的启动命令
```

**影响：** 这会立即提升 motion blur 和 defocus blur 的处理成功率

---

### 优先级2: 增加PIL图像限制

修改 `HATToolbox.py`：

```python
from PIL import Image

class BaseHATToolbox(ToolBase):
    def __init__(self, _name=None, _desc=None, _params=None, **kwargs):
        # 增加PIL图像大小限制
        Image.MAX_IMAGE_PIXELS = 250000000  # 2.5亿像素
        super().__init__(name=self.name, **kwargs)
```

**影响：** 允许处理更大的图像

---

### 优先级3: 监控工具失败率

在WandB添加工具失败监控（未来功能）：

```python
# 统计每个工具的成功率
tool_success_rate = {
    'restormer_defocus_deblurring': 0.72,
    'hat_super_resolution': 0.95,
    # ...
}
```

---

## ✅ 已修复的问题

### 代码错误修复 ✅

```python
# parallel_env.py 第1287-1289行
# 修复了 tool_result.get() 在字符串上调用的错误
has_multi_modal = isinstance(tool_result, dict) and tool_result.get("multi_modal_data") is not None
```

---

## 📈 预期改进

### 修复Restormer服务后

```
之前:
- motion blur 成功率: ~70%
- defocus blur 成功率: ~70%

之后:
- motion blur 成功率: ~95%+
- defocus blur 成功率: ~95%+
```

### 增加PIL限制后

```
之前:
- HAT 成功率: ~95% (大图失败)

之后:
- HAT 成功率: ~99%
```

---

## 🎯 总结

### 发现的问题

1. ❌ **Restormer API 500错误** - 服务问题，需要运维修复
2. ❌ **HAT图像过大** - PIL限制，需要调整配置
3. ✅ **代码错误** - 已修复

### 优先级

1. **紧急：** 修复Restormer服务（影响大）
2. **重要：** 增加PIL限制（影响中等）
3. **已完成：** 代码错误修复

### 对训练的影响

工具失败会导致：
- ✅ nerd_deraining 的统计可能正常（如果nerd服务正常）
- ❌ restormer系列工具的统计偏低
- ❌ hat_super_resolution 偶尔失败

**建议先修复服务问题，再继续训练！** 🔧

