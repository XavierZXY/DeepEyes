# 工具服务负载均衡功能使用指南

## 📖 功能概述

为了加速图像复原工具的处理速度，DeepEyes v2 引入了**多IP负载均衡**功能。当您有多台服务器部署了相同的图像处理工具时，系统可以自动将请求分配到不同的服务器，实现并行处理，大幅提升吞吐量。

## 🎯 适用场景

### 适合使用负载均衡的情况
- ✅ 有多台服务器可用
- ✅ 图像处理速度成为训练瓶颈
- ✅ 处理大尺寸图像（需要较长处理时间）
- ✅ 高并发训练场景（多个worker并行处理）

### 不需要负载均衡的情况
- ⛔ 只有一台服务器
- ⛔ 工具处理速度已经很快
- ⛔ 网络带宽受限
- ⛔ 训练batch size很小

## 🚀 配置方法

### 方式1: 多IP负载均衡模式（推荐）

在 `IRv2.sh` 中配置：

```bash
# 配置多个工具服务器IP（逗号分隔）
export TOOL_SERVICE_IPS="10.21.9.6,10.21.9.7"

# 或使用分号分隔
export TOOL_SERVICE_IPS="192.168.1.100;192.168.1.101;192.168.1.102"

# 选择负载均衡策略（可选）
export TOOL_LOAD_BALANCE_STRATEGY=round_robin  # 或 random
```

### 方式2: 单IP模式（传统方式）

```bash
# 只配置一个IP
export TOOL_SERVICE_IP=10.21.9.6
```

**注意**: 如果同时配置了 `TOOL_SERVICE_IPS` 和 `TOOL_SERVICE_IP`，系统优先使用 `TOOL_SERVICE_IPS`。

## ⚙️ 负载均衡策略

### 1. 轮询模式（round_robin）- 默认推荐

**特点**:
- 依次分配请求到各个服务器
- 保证每个服务器获得均匀的负载
- 线程安全，支持并发

**适用场景**:
- 所有服务器性能相同
- 希望负载完全均衡

**示例**:
```
请求1 → 10.21.9.6
请求2 → 10.21.9.7
请求3 → 10.21.9.6
请求4 → 10.21.9.7
...
```

### 2. 随机模式（random）

**特点**:
- 随机选择服务器
- 实现简单，无需维护状态
- 长期来看负载也是均衡的

**适用场景**:
- 服务器性能差异不大
- 对负载均衡要求不严格

**配置**:
```bash
export TOOL_LOAD_BALANCE_STRATEGY=random
```

## 📊 性能提升预期

| 服务器数量 | 理论吞吐量提升 | 实际提升（参考） |
|-----------|--------------|-----------------|
| 1台       | 基准         | 基准            |
| 2台       | 2倍          | 1.8-2.0倍       |
| 3台       | 3倍          | 2.7-3.0倍       |
| 4台       | 4倍          | 3.5-4.0倍       |

**影响因素**:
- 网络带宽
- 单台服务器GPU性能
- 图像大小和复杂度
- 并发请求数量

## 🔧 部署要求

### 服务器要求

1. **相同的工具部署**
   - 所有服务器必须部署完全相同的工具
   - 使用相同的端口号

2. **端口映射**
   ```
   所有服务器必须使用统一的端口：
   - SwinIR: 5001
   - DehazeFormer: 5002
   - DRBNet (DeblurToolbox): 5003
   - MPRNet: 5004
   - FBCNN: 5005
   - Restormer: 5006
   - XRestormer: 5007
   - SCUNet: 5008
   - Retinexformer: 5009
   - HAT: 5010
   - NeRD: 5011
   - NAFNet: 5012
   ```

3. **网络连通性**
   - 训练节点能够访问所有工具服务器
   - 防火墙开放对应端口
   - 建议使用内网连接

### 验证部署

使用以下命令检查各服务器是否正常：

```bash
# 检查服务器1
curl http://10.21.9.6:5001/health

# 检查服务器2
curl http://10.21.9.7:5001/health
```

## 💡 使用示例

### 示例1: 2台服务器负载均衡

```bash
# IRv2.sh 配置
export TOOL_SERVICE_IPS="10.21.9.6,10.21.9.7"
export TOOL_LOAD_BALANCE_STRATEGY=round_robin

# 运行训练
bash examples/agent/IRv2.sh
```

**预期效果**:
- 训练启动时会显示: `[LoadBalancer] 初始化成功: 已配置 2 个IP地址`
- 每个工具请求会轮流发送到两台服务器
- 处理速度提升约2倍

### 示例2: 3台服务器随机负载均衡

```bash
# IRv2.sh 配置
export TOOL_SERVICE_IPS="192.168.1.100,192.168.1.101,192.168.1.102"
export TOOL_LOAD_BALANCE_STRATEGY=random

# 运行训练
bash examples/agent/IRv2.sh
```

### 示例3: 单服务器模式（向后兼容）

```bash
# IRv2.sh 配置
export TOOL_SERVICE_IP=10.21.9.6

# 运行训练
bash examples/agent/IRv2.sh
```

**预期效果**:
- 训练启动时会显示: `[LoadBalancer] 初始化成功: 使用单IP模式 - 10.21.9.6`
- 所有请求发送到同一台服务器
- 与之前的行为完全一致

## 🐛 故障排查

### 问题1: 负载均衡器未初始化

**症状**: 日志中没有看到 `[LoadBalancer]` 相关信息

**可能原因**:
- 没有配置 `TOOL_SERVICE_IPS` 或 `TOOL_SERVICE_IP`
- 环境变量未正确导出

**解决方案**:
```bash
# 确认环境变量
echo $TOOL_SERVICE_IPS

# 手动导出
export TOOL_SERVICE_IPS="10.21.9.6,10.21.9.7"
```

### 问题2: 某台服务器无法访问

**症状**: 请求超时或连接失败

**可能原因**:
- 服务器未启动
- 防火墙阻止
- IP地址配置错误

**解决方案**:
```bash
# 1. 检查服务器连通性
ping 10.21.9.7

# 2. 检查端口是否开放
telnet 10.21.9.7 5001

# 3. 检查服务是否运行
curl http://10.21.9.7:5001/health

# 4. 如果某台服务器有问题，临时从配置中移除
export TOOL_SERVICE_IPS="10.21.9.6"  # 只使用正常的服务器
```

### 问题3: 负载不均衡

**症状**: 某台服务器负载明显高于其他服务器

**可能原因**:
- 使用了 `random` 策略（短期内可能不均衡）
- 某台服务器性能较差（处理慢导致请求堆积）

**解决方案**:
```bash
# 切换到轮询策略
export TOOL_LOAD_BALANCE_STRATEGY=round_robin

# 或检查服务器性能，移除性能差的服务器
```

### 问题4: 性能提升不明显

**可能原因**:
- 网络带宽成为瓶颈
- 单个请求处理时间太短（负载均衡开销占比大）
- 并发请求数量不足

**解决方案**:
- 检查网络带宽使用情况
- 增大batch size或并发worker数量
- 使用本地工具服务器减少网络延迟

## 🔍 日志输出

### 初始化日志

**多IP模式**:
```
[LoadBalancer] 初始化成功: 已配置 2 个IP地址
[LoadBalancer]   IP1: 10.21.9.6
[LoadBalancer]   IP2: 10.21.9.7
[LoadBalancer] 负载均衡策略: round_robin
```

**单IP模式**:
```
[LoadBalancer] 初始化成功: 使用单IP模式 - 10.21.9.6
[LoadBalancer] 负载均衡策略: round_robin
```

### 工具初始化日志

每个工具初始化时会显示：
```
SwinIRToolbox initialized. API endpoint: http://10.21.9.6:5001/process
NAFNetToolbox initialized. API endpoint: http://10.21.9.7:5012/process
```

**注意**: 由于负载均衡的动态特性，每次调用的IP可能不同。

## 📝 实现细节

### 代码结构

```
verl/workers/agent/envs/mm_process_engine/
├── tool_load_balancer.py      # 负载均衡器核心实现
├── SwinIRToolbox.py            # 使用负载均衡的工具
├── NAFNetToolbox.py            # 使用负载均衡的工具
├── HATToolbox.py               # 使用负载均衡的工具
└── ...                         # 其他工具
```

### 关键API

```python
from tool_load_balancer import get_tool_service_ip

# 获取一个IP（自动负载均衡）
ip = get_tool_service_ip()
api_url = f"http://{ip}:5001/process"

# 获取所有配置的IP
all_ips = get_all_tool_service_ips()

# 获取IP数量
count = get_tool_service_ip_count()
```

### 线程安全

负载均衡器使用 `threading.Lock` 确保多线程环境下的安全性，可以在以下场景使用：
- Ray多worker并行
- 多线程数据加载
- 异步工具调用

## 🎓 最佳实践

### 1. 生产环境配置

```bash
# 使用多个高性能服务器
export TOOL_SERVICE_IPS="10.21.9.6,10.21.9.7,10.21.9.8"

# 使用轮询策略保证均衡
export TOOL_LOAD_BALANCE_STRATEGY=round_robin
```

### 2. 开发测试配置

```bash
# 使用单服务器简化调试
export TOOL_SERVICE_IP=localhost
```

### 3. 性能调优

- **批量大小**: 增大 `data.train_batch_size` 以充分利用多服务器
- **并发数**: 调整 `actor_rollout_ref.rollout.agent.concurrent_workers`
- **服务器数量**: 根据GPU资源和训练吞吐量需求配置

### 4. 监控建议

- 监控各服务器的GPU使用率
- 监控网络带宽使用情况
- 记录平均处理时间

## 📚 相关文档

- `IRv2.sh`: 训练脚本配置
- `verl/workers/agent/envs/mm_process_engine/tool_load_balancer.py`: 负载均衡器实现
- `AIR_V9_CHANGELOG.md`: 版本更新说明

## 🔄 版本历史

- **v9.0**: 引入多IP负载均衡功能
- **v8.4**: 使用单IP配置

---

**最后更新**: 2025-10-31  
**作者**: DeepEyes Team

