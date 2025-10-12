# 工具服务IP地址统一控制方案

## 📋 修改总结

所有图像处理工具的IP地址现在统一通过 `IR.sh` 脚本中的环境变量 `TOOL_SERVICE_IP` 进行控制。

## ✅ 已修改的文件

### 1. DehazeFormerToolbox.py (去雾工具 - 端口5002)
- **修改内容**: 
  - 添加 `import os`
  - 修改 `__init__` 方法，从环境变量读取IP
  - `api_url = f'http://{os.environ.get("TOOL_SERVICE_IP", "10.21.9.34")}:5002/dehaze'`

### 2. DeblurToolbox.py (去模糊工具 - 端口5003)
- **修改内容**: 
  - 添加 `import os`
  - 将 `server_url` 改为 `@property` 动态属性
  - `return f"http://{os.environ.get('TOOL_SERVICE_IP', '10.21.9.34')}:5003/deblur"`

### 3. MPRNetToolbox.py (多用途修复网络 - 端口5004)
- **修改内容**: 
  - 添加 `import os`
  - 类属性直接使用环境变量
  - `api_url = f"http://{os.environ.get('TOOL_SERVICE_IP', '10.21.9.34')}:5004/process"`

### 4. FBCNNToolbox.py (JPEG伪影去除 - 端口5005)
- **修改内容**: 
  - 添加 `import os`
  - 类属性直接使用环境变量
  - `api_url = f"http://{os.environ.get('TOOL_SERVICE_IP', '10.21.9.34')}:5005/process"`

### 5. RestormerToolbox.py (图像修复工具 - 端口5006)
- **修改内容**: 
  - 添加 `import os`
  - 类属性直接使用环境变量
  - `api_url = f"http://{os.environ.get('TOOL_SERVICE_IP', '10.21.9.34')}:5006/process"`

### 已经使用环境变量的工具（无需修改）

- ✅ **SwinIRToolbox.py** (端口5001) - 已使用环境变量
- ✅ **XRestormerToolbox.py** (端口5007) - 已使用环境变量
- ✅ **BrighteningToolbox.py** - 本地处理工具，不需要网络服务

## 🎯 端口号映射（已固定）

| 工具名称 | 端口号 | 功能 |
|---------|--------|------|
| SwinIR | 5001 | 去噪/超分/JPEG伪影去除 |
| DehazeFormer | 5002 | 去雾 |
| DRBNet (DeblurToolbox) | 5003 | 散焦去模糊 |
| MPRNet | 5004 | 去噪/去雨/运动去模糊 |
| FBCNN | 5005 | JPEG伪影去除/质量评估 |
| Restormer | 5006 | 运动去模糊/散焦去模糊/去雨 |
| XRestormer | 5007 | 运动去模糊/去雨 |

## 🔧 使用方法

### 在 IR.sh 中控制IP地址

```bash
# IR.sh 脚本中已有的配置（第35行）
export TOOL_SERVICE_IP=10.21.9.34
```

### 修改IP地址

只需要在 `IR.sh` 中修改一处：

```bash
# 修改为新的服务器IP
export TOOL_SERVICE_IP=192.168.1.100
```

### 端口号保持不变

所有工具的端口号已固定，不需要单独配置：
- 端口号在各个工具类中硬编码
- 只有IP地址通过环境变量动态配置

## 📝 完整工具配置示例

```bash
# IR.sh 中的配置部分
export TOOL_SERVICE_IP=10.21.9.34

# 自动生成的完整URL列表：
# - http://10.21.9.34:5001/process      (SwinIR)
# - http://10.21.9.34:5002/dehaze       (DehazeFormer)
# - http://10.21.9.34:5003/deblur       (DRBNet)
# - http://10.21.9.34:5004/process      (MPRNet)
# - http://10.21.9.34:5005/process      (FBCNN)
# - http://10.21.9.34:5006/process      (Restormer)
# - http://10.21.9.34:5007/process      (XRestormer)
```

## ✅ 优势

1. **统一管理**: 所有工具的IP地址在一处配置
2. **灵活切换**: 切换服务器只需修改一个环境变量
3. **保持兼容**: 默认值为原IP (10.21.9.34)，不影响现有部署
4. **端口固定**: 端口号保持不变，便于服务部署和防火墙配置
5. **无语法错误**: 所有修改已通过linter检查

## 🚀 验证

运行训练时会看到工具初始化日志：

```
DehazeFormerToolbox initialized. API endpoint: http://10.21.9.34:5002/dehaze
SwinIRToolbox initialized. API endpoint: http://10.21.9.34:5001/process
MPRNetToolbox initialized. API endpoint: http://10.21.9.34:5004/process
...
```

## 📌 注意事项

1. **环境变量优先级**: 如果系统中已设置 `TOOL_SERVICE_IP`，会优先使用系统环境变量
2. **默认回退**: 如果未设置环境变量，自动使用默认IP `10.21.9.34`
3. **端口不可变**: 端口号已固定在代码中，确保服务部署的一致性
4. **运行时读取**: IP地址在工具初始化时读取，修改环境变量需要重启训练进程

## 🎉 完成状态

- ✅ 所有7个工具的IP配置已统一
- ✅ 端口号保持不变
- ✅ 通过linter检查
- ✅ 向后兼容（默认值不变）
- ✅ 集中在IR.sh控制

---
*修改完成时间: 2025-01-XX*
*修改内容: 统一工具服务IP地址配置*

