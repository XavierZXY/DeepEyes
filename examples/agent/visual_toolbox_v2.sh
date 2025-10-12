set -x

# Visual Toolbox V2 - Industrial Defect Detection Training Script
# 数据集2: 工业缺陷检测任务

PROJECT_NAME="visual_toolbox_v2"
EXPERIMENT_NAME="defect_detection_train"

# 基础配置
export SAVE_CHECKPOINT_DIR=/app/xiaominl/models/verl_checkpoints
export WORLD_SIZE=1
export NCCL_DEBUG=INFO
export ROCM_USE_GPU_COPY=1
export WANDB_API_KEY=ce0821ccdf886f2dbb5703772a0c41aa85611afb

# ========== 数据集2特定配置：Visual Toolbox V2 ==========
# 数据集2使用visual_toolbox_v2工具
# 奖励计算：format_reward (-1或1) + acc_reward (0或1)
# 工具行为：始终处理原始输入图，不使用上一个工具处理后的图

# Reward配置 - 数据集2不需要图像质量指标，只需要format和accuracy
# 这些环境变量对visual_toolbox_v2不生效，仅保留以避免其他代码警告
export IMAGE_QUALITY_USE_NO_REFERENCE=True  
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0
export FORMAT_REWARD_WEIGHT=1.0  # 数据集2中format是-1或1
export QUALITY_REWARD_WEIGHT=1.0  # 数据集2中是acc_reward (0或1)
export ENABLE_DEGRADATION_TYPE_REWARD=False  # 数据集2不使用退化类型奖励
# ========================================================

# 集群配置（单节点）
export MASTER_ADDR=127.0.0.1
export MASTER_PORT=29500
export NCCL_SOCKET_IFNAME=lo

# LLM Judge配置（数据集2可以不使用LLM judge，直接匹配yes/no）
# 如果不需要LLM judge，可以注释掉这一行
# export LLM_AS_A_JUDGE_BASE="http://172.18.148.193:18901/v1"

# ROCm配置
export VLLM_USE_TRITON_FLASH_ATTN=0
export HSA_FORCE_FINE_GRAIN_PCIE=1 
export RAY_TMPDIR=/app/models/ray_tmp
export MIOPEN_FIND_MODE=3
export MIOPEN_DEBUG_DISABLE_FIND_DB=0
export PYTORCH_ROCM_ARCH=gfx90a

# 数据集路径 - 数据集2
BASEDIR=/home/takisobe@amd.com/zxy/codes/DeepEyes/data
TRAIN_DATASET=${BASEDIR}/train/train_dataset.parquet
VAL_DATASET=${BASEDIR}/val/val_dataset.parquet  # 如果有验证集

# 模型路径
REF_MODEL_PATH=/app/xiaominl/models/Qwen2.5-VL-7B-Instruct

# 启动训练
PYTHONUNBUFFERED=1 python3 -m verl.trainer.main_ppo \
    +debug=False \
    +vs_debug=False \
    data.train_files=[${TRAIN_DATASET}] \
    data.val_files=[${VAL_DATASET}] \
    data.train_batch_size=16 \
    data.max_prompt_length=8192 \
    data.max_response_length=20480 \
    data.return_raw_chat=True \
    data.filter_overlong_prompts=True \
    algorithm.adv_estimator=grpo \
    algorithm.kl_ctrl.kl_coef=0.0 \
    actor_rollout_ref.model.path=${REF_MODEL_PATH} \
    actor_rollout_ref.model.use_remove_padding=True \
    actor_rollout_ref.actor.optim.lr=1e-6 \
    actor_rollout_ref.actor.ppo_mini_batch_size=16 \
    actor_rollout_ref.actor.ppo_micro_batch_size_per_gpu=4 \
    actor_rollout_ref.actor.use_kl_loss=False \
    actor_rollout_ref.actor.kl_loss_coef=0.0 \
    actor_rollout_ref.actor.kl_loss_type=low_var_kl \
    actor_rollout_ref.actor.entropy_coeff=0.0 \
    actor_rollout_ref.actor.checkpoint.contents=['model','hf_model','optimizer','extra'] \
    actor_rollout_ref.actor.ulysses_sequence_parallel_size=1 \
    actor_rollout_ref.rollout.log_prob_micro_batch_size_per_gpu=4 \
    actor_rollout_ref.rollout.tensor_model_parallel_size=1 \
    actor_rollout_ref.rollout.name=vllm \
    actor_rollout_ref.rollout.n=4 \
    actor_rollout_ref.rollout.max_num_batched_tokens=32768 \
    actor_rollout_ref.rollout.gpu_memory_utilization=0.25 \
    actor_rollout_ref.rollout.enforce_eager=False \
    actor_rollout_ref.rollout.free_cache_engine=False \
    actor_rollout_ref.rollout.enable_chunked_prefill=False \
    actor_rollout_ref.actor.fsdp_config.param_offload=True \
    actor_rollout_ref.actor.fsdp_config.optimizer_offload=True \
    actor_rollout_ref.ref.log_prob_micro_batch_size_per_gpu=4 \
    actor_rollout_ref.ref.fsdp_config.param_offload=True \
    actor_rollout_ref.rollout.agent.activate_agent=True \
    actor_rollout_ref.rollout.agent.tool_name_key=env_name \
    actor_rollout_ref.rollout.agent.single_response_max_tokens=10240 \
    actor_rollout_ref.rollout.agent.max_turns=5 \
    actor_rollout_ref.rollout.agent.concurrent_workers=1 \
    actor_rollout_ref.rollout.agent.show_tqdm=True \
    trainer.critic_warmup=0 \
    trainer.logger=['console','wandb','rl_logging_board'] \
    trainer.val_before_train=True \
    trainer.n_gpus_per_node=8 \
    trainer.nnodes=${WORLD_SIZE} \
    trainer.save_freq=20 \
    trainer.test_freq=10 \
    trainer.project_name=${PROJECT_NAME} \
    trainer.experiment_name=${EXPERIMENT_NAME} \
    trainer.default_local_dir=${SAVE_CHECKPOINT_DIR}/${PROJECT_NAME}/${EXPERIMENT_NAME} \
    +trainer.tensorboard_dir=${SAVE_CHECKPOINT_DIR}/logs/tensorboard \
    +trainer.rl_logging_board_dir=${SAVE_CHECKPOINT_DIR}/logs/rl_logging_board \
    +trainer.log_images_to_wandb=True \
    +trainer.num_train_images_to_log=5 \
    +trainer.num_best_worst_images_to_log=2 \
    trainer.total_epochs=32 2>&1 | tee ./logs/${EXPERIMENT_NAME}.log

