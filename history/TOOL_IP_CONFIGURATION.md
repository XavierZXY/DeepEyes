# 工具服务IP地址统一配置

## 📋 修改说明

已将所有图像处理工具的IP地址配置统一到训练脚本 `IR.sh` 中，通过环境变量 `TOOL_SERVICE_IP` 控制。

## ✅ 修改内容

### 1. 训练脚本配置 (`examples/agent/IR.sh`)

新增环境变量：
```bash
# ========== Tool Service IP Configuration ==========
# 统一配置所有图像处理工具的服务IP地址（端口号由各工具内部保留）
# 工具及对应端口：
# - SwinIR: 5001 (去噪/超分/JPEG伪影去除)
# - DehazeFormer: 5002 (去雾)
# - DRBNet (DeblurToolbox): 5003 (散焦去模糊)
# - MPRNet: 5004 (去噪/去雨/运动去模糊)
# - FBCNN: 5005 (JPEG伪影去除/质量评估)
# - Restormer: 5006 (运动去模糊/散焦去模糊/去雨)
# - XRestormer: 5007 (运动去模糊/去雨)
export TOOL_SERVICE_IP=10.21.9.34
# ========================================================
```

### 2. 修改的工具文件

所有工具文件都已更新，从环境变量读取IP地址，但保留各自的端口号：

| 工具文件 | 端口号 | 工具功能 |
|---------|--------|---------|
| `SwinIRToolbox.py` | 5001 | 去噪/超分辨率/JPEG伪影去除 |
| `DehazeFormerToolbox.py` | 5002 | 去雾 |
| `DeblurToolbox.py` | 5003 | 散焦去模糊 (DRBNet) |
| `MPRNetToolbox.py` | 5004 | 去噪/去雨/运动去模糊 |
| `FBCNNToolbox.py` | 5005 | JPEG伪影去除/质量评估 |
| `RestormerToolbox.py` | 5006 | 运动去模糊/散焦去模糊/去雨 |
| `XRestormerToolbox.py` | 5007 | 运动去模糊/去雨 |

### 3. 修改细节

**添加 `import os`**:
所有工具文件都添加了 `import os` 导入。

**API URL 配置**:
- 从硬编码：`api_url = "http://10.21.9.34:5001/process"`
- 改为动态：`api_url = f"http://{os.environ.get('TOOL_SERVICE_IP', '10.21.9.34')}:5001/process"`

**默认值保护**:
如果环境变量未设置，会回退到默认IP地址 `10.21.9.34`。

## 🚀 使用方法

### 修改IP地址

只需在 `IR.sh` 中修改一个环境变量即可：

```bash
# 修改这一行
export TOOL_SERVICE_IP=your.new.ip.address
```

### 端口号

端口号无需修改，已在各工具内部固定：
- 每个工具有独立的端口号
- 如需修改端口，需要编辑对应的工具文件

### 运行训练

```bash
bash examples/agent/IR.sh
```

工具会自动使用配置的IP地址。

## 📝 示例

### 使用不同的IP地址

```bash
# 在 IR.sh 中设置
export TOOL_SERVICE_IP=192.168.1.100

# 运行后，SwinIR 会连接到: http://192.168.1.100:5001/process
# MPRNet 会连接到: http://192.168.1.100:5004/process
# 以此类推...
```

## ✨ 优点

1. **集中管理**: 所有工具的IP地址在一个地方配置
2. **易于修改**: 只需改一行代码即可切换服务器
3. **保持端口**: 各工具保留各自的端口号，避免冲突
4. **向后兼容**: 如果忘记设置环境变量，会使用默认值
5. **灵活部署**: 可以轻松切换开发/测试/生产环境

## 🔍 验证

运行训练时，工具初始化日志会显示实际使用的API端点：

```
SwinIRToolbox initialized. API endpoint: http://10.21.9.34:5001/process
MPRNetToolbox initialized. API endpoint: http://10.21.9.34:5004/process
...
```

可以通过日志确认IP地址是否正确应用。

## 📌 注意事项

1. **环境变量优先级**: 环境变量 > 默认值
2. **端口号固定**: 端口号在代码中固定，不从环境变量读取
3. **所有工具同IP**: 所有工具必须使用相同的IP地址（但端口不同）
4. **服务需同机**: 确保所有工具服务运行在同一台机器上

## 🎯 完成状态

- ✅ IR.sh 添加环境变量
- ✅ SwinIRToolbox.py (端口 5001)
- ✅ DehazeFormerToolbox.py (端口 5002)
- ✅ DeblurToolbox.py (端口 5003)
- ✅ MPRNetToolbox.py (端口 5004)
- ✅ FBCNNToolbox.py (端口 5005)
- ✅ RestormerToolbox.py (端口 5006)
- ✅ XRestormerToolbox.py (端口 5007)
- ✅ 无语法错误

全部修改已完成！


