# DeepEyes AIR v9 Changelog

## 版本信息

**版本**: AIR v9  
**基于**: AIR v8-4  
**创建日期**: 2025-10-31  
**分支**: air_v9

## 继承的功能（来自v8-4）

### 1. 对话模式支持
- ✅ 多工具链式规划模式（`multi_tool_planning`）
- ✅ 单工具迭代模式（`single_tool_iterative`）

### 2. 格式检查系统
- ✅ 标准多轮格式检查（v2）
- ✅ 增强多轮格式检查（v3）
  - Answer必须在最后一轮
  - 单轮工具数限制（`MAX_TOOLS_PER_TURN`）
  - **总工具调用数上限检查**（v8-4新增）

### 3. 奖励系统
- ✅ 格式奖励（可配置权重）
- ✅ 图像质量奖励（无参考/有参考指标）
- ✅ 退化类型奖励（可选）
- ✅ 工具多样性奖励

### 4. 图像质量评估
- ✅ 无参考指标：NIQE, BRISQUE, CPBD, CLIP-IQA, Hyper-IQA
- ✅ 有参考指标：SSIM, LPIPS, PSNR
- ✅ 离散化奖励支持

### 5. 工具管理
- ✅ 13个图像修复工具集成
- ✅ 工具-退化类型映射
- ✅ 工具调用统计和监控

### 6. 训练监控
- ✅ Wandb集成
- ✅ RL Logging Board
- ✅ 退化类型准确率追踪
- ✅ 工具-退化匹配率统计

## v8-4的最新改进

### 总工具调用数上限约束（v8-4）
- **功能**: 防止模型过度调用工具
- **约束**: 总工具数 ≤ 退化数量 + 1
- **适用**: 单工具迭代模式
- **配置**: `ENABLE_TOTAL_TOOLS_UPPER_LIMIT=True`

**示例**：
- 双退化图像（noise + blur）
- 允许最大工具数：2 + 1 = 3
- 超过3个工具 → 格式违规（-1.0）

**效果**：
- 减少冗余工具调用
- 提高训练效率
- 保持适度探索空间

## v9 开发计划

### 优先级1：核心功能优化
- [ ] 修复工具计数BUG（parallel_env.py第840-854行）
  - 问题：计数阶段使用原始工具数，执行阶段才截取
  - 影响：单工具模式下计数虚高
- [ ] 优化格式奖励结构
- [ ] 改进图像质量指标计算

### 优先级2：训练效率提升
- [ ] 数据加载优化
- [ ] 内存使用优化
- [ ] 分布式训练改进

### 优先级3：新功能探索
- [ ] 自适应工具选择
- [ ] 分层退化处理策略
- [ ] 多阶段训练方案

### 优先级4：实验和评估
- [ ] 大规模数据集测试
- [ ] 泛化能力评估
- [ ] 与baseline对比

## 配置参考

### 单工具迭代模式（推荐配置）

```bash
# 对话模式
export AGENT_CONVERSATION_MODE="single_tool_iterative"

# 格式检查
export USE_ENHANCED_FORMAT=True
export MAX_TOOLS_PER_TURN=1
export ENABLE_TOTAL_TOOLS_UPPER_LIMIT=True

# 奖励权重
export FORMAT_REWARD_WEIGHT=0.3
export QUALITY_REWARD_WEIGHT=0.7
export ENABLE_DEGRADATION_TYPE_REWARD=False

# 图像质量配置
export IMAGE_QUALITY_USE_NO_REFERENCE=False
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0

# 训练参数
actor_rollout_ref.rollout.agent.max_turns=4
actor_rollout_ref.actor.optim.lr=1e-6
actor_rollout_ref.rollout.n=4
data.train_batch_size=32
```

## 技术栈

- **RL Framework**: VeRL
- **LLM**: Qwen-2.5-VL-7B-Instruct
- **Judge Model**: Qwen-2.5-72B-Instruct
- **Rollout**: vLLM
- **Training**: FSDP + PPO/GRPO

## 文档索引

- `TOTAL_TOOLS_UPPER_LIMIT_FEATURE.md` - 总工具数上限功能详解
- `CONVERSATION_MODE_GUIDE.md` - 对话模式切换指南
- `AGENT_MODE_QUICK_REFERENCE.md` - Agent模式快速参考

## 分支策略

- `air_v9` - 主开发分支
- `air_v9-{N}` - 子版本/实验分支
- 定期合并回主分支，保持代码同步

## 已知问题

### 工具计数BUG
- **位置**: `verl/workers/agent/parallel_env.py:840-854`
- **现象**: 单工具模式下，计数可能显示6个工具，但实际只执行4个
- **原因**: 计数阶段和执行阶段对工具数量的处理不一致
- **优先级**: 高
- **计划**: v9早期修复

## 版本历史

| 版本 | 主要特性 | 基于 |
|------|---------|------|
| v5 | 基础图像修复Agent | - |
| v6 | 退化类型工具规划 | v5 |
| v7 | 奖励系统重构 | v6 |
| v8 | 对话模式支持 | v7 |
| v8-2 | 格式检查优化 | v8 |
| v8-3 | 工具统计增强 | v8-2 |
| v8-4 | 总工具数上限约束 | v8-3 |
| **v9** | **继续优化和新功能** | **v8-4** |

---

**创建者**: AI Assistant  
**联系**: XavierZXY/DeepEyes  
**最后更新**: 2025-10-31

