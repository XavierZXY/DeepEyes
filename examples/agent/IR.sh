set -xmain_ppo



# CUDA_VISIBLE_DEVICES = 0,1,2,3 vllm serve /path/to/your/local/filedir \
#     --port 18901 \
#     --gpu-memory-utilization 0.8 \
#     --max-model-len 32768 \
#     --tensor-parallel-size 4 \ 
#     --served-model-name "judge" \
#     --trust-remote-code \
#     --disable-log-requests

PROJECT_NAME="IRagent"
# EXPERIMENT_NAME="debug_for_TIR_IR_air_refrew_bs128_n8_classreward_balanced_mi300"
# EXPERIMENT_NAME="debug_for_TIR_IR_air_refrew_bs32_n8_balanced_lr1e-7_mi300"
EXPERIMENT_NAME="debug_for_AIR_multideg_plan_ref_bs32_n8_spv12_lr5e-7_datarand_mi300"
# export CUDA_VISIBLE_DEVICES=4,5,6,7
export SAVE_CHECKPOINT_DIR=/app/model/verl_checkpoints
# export VLLM_ATTENTION_BACKEND=XFORMERS # vllm + qwen2-7b with flash_attn has some issues
export WORLD_SIZE=1
export NCCL_DEBUG=INFO
export ROCM_USE_GPU_COPY=1

export WANDB_API_KEY=ce0821ccdf886f2dbb5703772a0c41aa85611afb

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
export TOOL_SERVICE_IP=10.21.9.6
# ========================================================

# ========== Image Quality Reward Configuration ==========
# 控制图像质量奖励的计算方式
export IMAGE_QUALITY_USE_NO_REFERENCE=False  # True=无参考指标(NIQE/BRISQUE/CPBD/CLIP-IQA/Hyper-IQA), False=有参考指标(SSIM/LPIPS/PSNR)
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0    # 离散化等级: 0=连续奖励, 10=每10%一档, 20=每5%一档

# 推荐配置：
# - 训练阶段: use_no_reference=True, discretize_levels=0 (无参考+连续奖励，所有样本都能计算)
# - 早期训练: use_no_reference=True, discretize_levels=10 (离散化可减少波动)
# - 如果有GT: use_no_reference=False (有参考指标更准确，但只对执行工具的样本有效)
# ========================================================

# ========== Reward Weight Configuration ==========
# 控制各项奖励的权重系数
export FORMAT_REWARD_WEIGHT=0.3             # 格式奖励权重（默认0.3）
export QUALITY_REWARD_WEIGHT=0.7            # 图像质量奖励权重（默认0.7）
export ENABLE_DEGRADATION_TYPE_REWARD=False # 是否启用退化类型奖励（默认False）
export DEGRADATION_TYPE_REWARD_WEIGHT=1.0   # 退化类型奖励权重（默认1.0）
export USE_ENHANCED_FORMAT=True           # 是否使用增强格式检查（默认False）

# ========== Wandb Upload Configuration ==========
# 控制wandb上传行为
export WANDB_LOG_WRONG_PREDICTIONS=False     # 是否上传错误预测的验证样本到wandb（默认True）
# 说明：
# - True: 启用错误预测上传，验证时将预测错误的样本上传到wandb的 val_errors/wrong_predictions 表格
# - False: 禁用错误预测上传，跳过错误样本分析（节省存储和带宽）
# - 错误判定：模型预测的退化类型集合与GT不完全匹配
# - 表格包含：原图、退化图、复原图、GT退化类型、预测退化类型、漏检/误检类型、完整对话
# 使用场景：
# - 训练早期/调试阶段：建议启用（True），帮助发现模型问题
# - 训练后期/稳定阶段：可禁用（False），减少不必要的上传
# 详细文档：WANDB_WRONG_PREDICTIONS_CONFIG.md

# 说明：
# 【默认奖励结构】
# total_reward = FORMAT_WEIGHT × format_score + QUALITY_WEIGHT × quality_score
#
# 【启用退化类型奖励后】
# total_reward = FORMAT_WEIGHT × format_score 
#              + QUALITY_WEIGHT × quality_score 
#              + DEGRADATION_TYPE_WEIGHT × degradation_type_score
#
# 【各项说明】
# - format_score: 1.0(完美格式) 或 -1.0(格式违规)
# - quality_score: 0.0~1.0 (图像质量分数，SSIM/LPIPS/PSNR或NIQE/BRISQUE/CPBD等)
# - degradation_type_score: 0.0~1.0 (退化类型识别准确性，不考虑顺序，只看集合匹配)
#
# 【增强格式检查说明】
# USE_ENHANCED_FORMAT=True 时，格式检查增加以下约束：
# - Answer必须在最后一轮对话中（如果存在）
# - Tool_call总数必须 >= 退化数量（对于非clean样本）
# - 继承所有原有格式检查规则
#
# 【推荐配置】
# - 默认训练: FORMAT=0.3, QUALITY=0.7, DEGRADATION_TYPE=关闭, ENHANCED_FORMAT=关闭
# - 强化类型识别: FORMAT=0.3, QUALITY=0.7, DEGRADATION_TYPE=开启(权重1.0), ENHANCED_FORMAT=关闭
# - 严格格式训练: FORMAT=0.3, QUALITY=0.7, ENHANCED_FORMAT=开启
# - 通常保持 FORMAT_WEIGHT + QUALITY_WEIGHT = 1.0，退化类型作为额外奖励
# ==================================================================

export MASTER_ADDR=127.0.0.1
export MASTER_PORT=29500
export NCCL_DEBUG=INFO
export NCCL_SOCKET_IFNAME=lo


# export NCCL_DEBUG=INFO
# export NCCL_IB_DISABLE=1
# export NCCL_SOCKET_IFNAME=bond0.2026
# export MASTER_ADDR=10.21.239.125   # head node IP
# export MASTER_PORT=29500            # 任意未被占用端口
export LLM_AS_A_JUDGE_BASE="http://172.18.148.193:18901/v1"
export VLLM_USE_TRITON_FLASH_ATTN=0
export HSA_FORCE_FINE_GRAIN_PCIE=1 
export RAY_TMPDIR=/app/models/ray_tmp
export MIOPEN_FIND_MODE=1
export MIOPEN_DEBUG_DISABLE_FIND_DB=1
export MIOPEN_USER_DB_PATH=/tmp/miopen-cache
export MIOPEN_CUSTOM_CACHE_DIR=/tmp/miopen-cache
export PYTORCH_ROCM_ARCH=gfx90a
# BASEDIR=/app/xiaominl/datasets/air_d1_sp9_up2_balanced
BASEDIR=/app/xiaominl/datasets/air_sp12_up3_samole1_rand
# VISUAL_DATASET_TRAIN_0_6_2=${BASEDIR}/shard-000000.parquet
# VISUAL_DATASET_TRAIN_0_1_2=${BASEDIR}/shard-000000.parquet
# VISUAL_DATASET_TRAIN_0_8=${BASEDIR}/shard-000000.parquet
# VISUAL_DATASET_TEST=${BASEDIR}/shard-000000.parquet
# EUREKA_DATASET_TRAIN=${BASEDIR}/shard-000000.parquet

VISUAL_DATASET_TRAIN_0=${BASEDIR}/shard-train-000000.parquet
VISUAL_DATASET_TRAIN_1=${BASEDIR}/shard-train-000001.parquet
VISUAL_DATASET_TRAIN_2=${BASEDIR}/shard-train-000002.parquet
VISUAL_DATASET_TRAIN_3=${BASEDIR}/shard-train-000003.parquet

VISUAL_DATASET_TEST_0=${BASEDIR}/shard-test-000000.parquet
# VISUAL_DATASET_TEST_1=${BASEDIR}/shard-test-000001.parquet
# VISUAL_DATASET_TEST_2=${BASEDIR}/shard-test-000002.parquet
# VISUAL_DATASET_TEST_3=${BASEDIR}/shard-test-000003.parquet
# VISUAL_DATASET_TRAIN_4=${BASEDIR}/shard-000004.parquet
# VISUAL_DATASET_TRAIN_5=${BASEDIR}/shard-000005.parquet
# VISUAL_DATASET_TRAIN_6=${BASEDIR}/shard-000006.parquet
REF_MODEL_PATH=/app/xiaominl/models/Qwen2.5-VL-7B-Instruct
# RAY_ADDRESS='http://172.18.148.35:8265' ray job submit --address="http://172.18.148.35:8265" \
#     --runtime-env /app/xiaominl/DeepEyes/verl/trainer/runtime_env.yaml \
#     --no-wait \
#     -- \
PYTHONUNBUFFERED=1 python3 -m verl.trainer.main_ppo \
    +debug=False \
    +vs_debug=False \
    data.train_files=[${VISUAL_DATASET_TRAIN_0},${VISUAL_DATASET_TRAIN_1},${VISUAL_DATASET_TRAIN_2},${VISUAL_DATASET_TRAIN_3}] \
    data.val_files=[${VISUAL_DATASET_TEST_0}] \
    data.train_batch_size=32 \
    data.max_prompt_length=8192 \
    data.max_response_length=20480 \
    data.return_raw_chat=True \
    data.filter_overlong_prompts=True \
    algorithm.adv_estimator=grpo \
    algorithm.kl_ctrl.kl_coef=0.0 \
    actor_rollout_ref.model.path=${REF_MODEL_PATH} \
    actor_rollout_ref.model.use_remove_padding=True \
    actor_rollout_ref.actor.optim.lr=5e-7 \
    actor_rollout_ref.actor.ppo_mini_batch_size=32 \
    actor_rollout_ref.actor.ppo_micro_batch_size_per_gpu=8 \
    actor_rollout_ref.actor.use_kl_loss=False \
    actor_rollout_ref.actor.kl_loss_coef=0.0 \
    actor_rollout_ref.actor.kl_loss_type=low_var_kl \
    actor_rollout_ref.actor.entropy_coeff=0.0 \
    actor_rollout_ref.actor.checkpoint.contents=['model','hf_model','optimizer','extra'] \
    actor_rollout_ref.actor.ulysses_sequence_parallel_size=1 \
    actor_rollout_ref.rollout.log_prob_micro_batch_size_per_gpu=8 \
    actor_rollout_ref.rollout.tensor_model_parallel_size=1 \
    actor_rollout_ref.rollout.name=vllm \
    actor_rollout_ref.rollout.n=8 \
    actor_rollout_ref.rollout.max_num_batched_tokens=32768 \
    actor_rollout_ref.rollout.gpu_memory_utilization=0.25 \
    actor_rollout_ref.rollout.enforce_eager=False \
    actor_rollout_ref.rollout.free_cache_engine=False \
    actor_rollout_ref.rollout.enable_chunked_prefill=False \
    actor_rollout_ref.actor.fsdp_config.param_offload=True \
    actor_rollout_ref.actor.fsdp_config.optimizer_offload=True \
    actor_rollout_ref.ref.log_prob_micro_batch_size_per_gpu=8 \
    actor_rollout_ref.ref.fsdp_config.param_offload=True \
    actor_rollout_ref.rollout.agent.activate_agent=True \
    actor_rollout_ref.rollout.agent.tool_name_key=env_name \
    actor_rollout_ref.rollout.agent.single_response_max_tokens=10240 \
    actor_rollout_ref.rollout.agent.max_turns=4 \
    actor_rollout_ref.rollout.agent.concurrent_workers=2 \
    actor_rollout_ref.rollout.agent.show_tqdm=True \
    trainer.critic_warmup=0 \
    trainer.logger=['console','wandb','rl_logging_board'] \
    trainer.val_before_train=False \
    trainer.n_gpus_per_node=8 \
    trainer.nnodes=${WORLD_SIZE} \
    trainer.save_freq=25 \
    trainer.test_freq=25 \
    trainer.project_name=${PROJECT_NAME} \
    trainer.experiment_name=${EXPERIMENT_NAME} \
    trainer.default_local_dir=${SAVE_CHECKPOINT_DIR}/${PROJECT_NAME}/${EXPERIMENT_NAME} \
    +trainer.tensorboard_dir=${SAVE_CHECKPOINT_DIR}/logs/tensorboard \
    +trainer.rl_logging_board_dir=${SAVE_CHECKPOINT_DIR}/logs/rl_logging_board \
    trainer.total_epochs=32 2>&1 | tee ./logs/${EXPERIMENT_NAME}.log
