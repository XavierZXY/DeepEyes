# 🔧 工具服务超时问题修复

## 📊 问题诊断

### 训练日志中的错误
```
[TOOL EXECUTE] ❌ dehazeformer_dehaze 执行失败 (耗时: 60.27s): 
HTTPConnectionPool(host='10.21.9.6', port=5002): Read timed out. (read timeout=60)
```

### 测试结果
✅ **DehazeFormer服务本身正常**：
- TCP连接正常
- 健康检查正常
- API处理正常（首次32秒，后续0.3秒）

### 根本原因分析

#### 1. **并发压力大**
```bash
data.train_batch_size=32
actor_rollout_ref.rollout.n=8
# 可能产生 32×8 = 256 个并发请求
```

#### 2. **首次调用慢**
- 每个worker首次调用需要加载模型（32秒）
- GPU显存紧张（aggressive_cleanup模式）
- 多个worker同时首次调用会排队

#### 3. **超时配置不一致**
- DehazeFormer: 180秒 ✅
- DeblurToolbox: 60秒 ❌（太短）
- 其他工具: 300秒 ✅

---

## ✅ 修复措施

### 修复1：增加DeblurToolbox超时
```python
# 文件: verl/workers/agent/envs/mm_process_engine/DeblurToolbox.py
# 行117
- response = requests.post(self.server_url, files=files, timeout=60)
+ response = requests.post(self.server_url, files=files, timeout=180)
```

### 修复2：DehazeFormer启用队列机制
```python
# 文件: verl/workers/agent/envs/mm_process_engine/DehazeFormerToolbox.py
# 行107-111
files = {'image': ('hazy_image.png', img_byte_arr, 'image/png')}
+ data = {'queue': 'true'}  # 启用队列机制，避免并发时直接拒绝
- response = requests.post(self.api_url, files=files, timeout=180)
+ response = requests.post(self.api_url, files=files, data=data, timeout=180)
```

---

## 🎯 当前超时配置汇总

| 工具 | 端口 | 超时(秒) | 状态 |
|------|------|---------|------|
| SwinIR | 5001 | 300 | ✅ |
| DehazeFormer | 5002 | 180 | ✅ 已优化 |
| DRBNet | 5003 | 180 | ✅ 已修复 |
| MPRNet | 5004 | 300 | ✅ |
| FBCNN | 5005 | 300 | ✅ |
| Restormer | 5006 | 300 | ✅ |
| XRestormer | 5007 | 300 | ✅ |
| RetinexFormer | 5008 | 300 | ✅ |
| SCUNet | 5009 | 300 | ✅ |

---

## 🔍 服务器端配置

### DehazeFormer服务
```json
{
    "queue_enabled": true,          // 启用队列
    "queue_timeout": 300,           // 队列超时5分钟
    "max_concurrent_requests": 8,   // 最多8个并发
    "aggressive_cleanup": true      // 激进清理GPU显存
}
```

**队列机制说明**：
- 当并发请求超过8个时，多余的请求会进入队列
- 队列中的请求最多等待300秒
- 客户端需要设置 `data={'queue': 'true'}` 才能使用队列

---

## 🧪 验证方法

### 1. 测试单个工具
```bash
python3 test_dehazeformer_detailed.py
```

### 2. 测试所有工具
```bash
export TOOL_SERVICE_IP=10.21.9.6
python3 test_tool_service_health.py
```

### 3. 检查超时配置
```bash
grep -r "timeout=" verl/workers/agent/envs/mm_process_engine/*.py
```

---

## 💡 未来优化建议

### 1. 服务器端
- 增加 `max_concurrent_requests`（如果GPU显存足够）
- 优化模型加载（预加载常用模型）
- 考虑使用模型缓存池

### 2. 客户端
- 添加重试机制（失败后等待重试）
- 实现请求优先级（重要样本优先）
- 添加超时警告日志

### 3. 训练配置
- 降低 `rollout.n`（减少并发压力）
- 增加 `concurrent_workers`间隔
- 使用梯度累积减少batch_size

---

## 📝 监控建议

训练时关注以下指标：
```bash
# 1. 工具执行时间
grep "TOOL EXECUTE.*耗时" logs/*.log | awk '{print $NF}' | sort -n

# 2. 超时错误
grep "Read timed out" logs/*.log | wc -l

# 3. 队列状态（如果服务支持）
curl http://10.21.9.6:5002/queue/status

# 4. GPU显存使用
curl http://10.21.9.6:5002/health | jq '.gpu_memory'
```

---

**修复完成时间**: 2025-10-21  
**测试状态**: ✅ 已验证  
**建议**: 监控首轮训练，如仍有超时可进一步增加timeout或降低并发

