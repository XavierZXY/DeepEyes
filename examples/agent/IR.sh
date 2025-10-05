set -xmain_ppo



# CUDA_VISIBLE_DEVICES = 0,1,2,3 vllm serve /path/to/your/local/filedir \
#     --port 18901 \
#     --gpu-memory-utilization 0.8 \
#     --max-model-len 32768 \
#     --tensor-parallel-size 4 \ 
#     --served-model-name "judge" \
#     --trust-remote-code \
#     --disable-log-requests

PROJECT_NAME="agent_vlagent"
EXPERIMENT_NAME="debug_for_TIR_IR_bs32_quality_0.3format_0.7accuracy_addclean0.2_systemPromptv8"
# export CUDA_VISIBLE_DEVICES=4,5,6,7
export SAVE_CHECKPOINT_DIR=/app/models/verl_checkpoints
# export VLLM_ATTENTION_BACKEND=XFORMERS # vllm + qwen2-7b with flash_attn has some issues
export WORLD_SIZE=2
export NCCL_DEBUG=INFO
export ROCM_USE_GPU_COPY=1

export WANDB_API_KEY=ce0821ccdf886f2dbb5703772a0c41aa85611afb



# export NCCL_DEBUG=INFO
# export NCCL_IB_DISABLE=1
export NCCL_SOCKET_IFNAME=bond0.2026
export MASTER_ADDR=172.18.148.35   # head node IP
export MASTER_PORT=29500            # 任意未被占用端口
export LLM_AS_A_JUDGE_BASE="http://172.18.148.193:18901/v1"
export VLLM_USE_TRITON_FLASH_ATTN=0
export HSA_FORCE_FINE_GRAIN_PCIE=1 
export RAY_TMPDIR=/app/models/ray_tmp
BASEDIR=/app/datasets/IRdatasetv5
VISUAL_DATASET_TRAIN_0_6_2=${BASEDIR}/shard-000000.parquet
VISUAL_DATASET_TRAIN_0_1_2=${BASEDIR}/shard-000000.parquet
VISUAL_DATASET_TRAIN_0_8=${BASEDIR}/shard-000000.parquet
VISUAL_DATASET_TEST=${BASEDIR}/shard-000000.parquet
EUREKA_DATASET_TRAIN=${BASEDIR}/shard-000000.parquet

VISUAL_DATASET_TRAIN_0=${BASEDIR}/shard-train-000000.parquet
VISUAL_DATASET_TRAIN_1=${BASEDIR}/shard-train-000001.parquet
VISUAL_DATASET_TRAIN_2=${BASEDIR}/shard-train-000002.parquet
VISUAL_DATASET_TRAIN_3=${BASEDIR}/shard-train-000003.parquet
# VISUAL_DATASET_TEST_0=${BASEDIR}/shard-test-000000.parquet
# VISUAL_DATASET_TRAIN_4=${BASEDIR}/shard-000004.parquet
# VISUAL_DATASET_TRAIN_5=${BASEDIR}/shard-000005.parquet
# VISUAL_DATASET_TRAIN_6=${BASEDIR}/shard-000006.parquet
REF_MODEL_PATH=/app/models/Qwen2.5-VL-7B-Instruct
RAY_ADDRESS='http://172.18.148.35:8265' ray job submit --address="http://172.18.148.35:8265" \
    --runtime-env /app/xiaominl/DeepEyes/verl/trainer/runtime_env.yaml \
    --no-wait \
    -- \
PYTHONUNBUFFERED=1 python3 -m verl.trainer.main_ppo \
    +debug=False \
    +vs_debug=False \
    data.train_files=[${VISUAL_DATASET_TRAIN_0},${VISUAL_DATASET_TRAIN_1},${VISUAL_DATASET_TRAIN_2}] \
    data.val_files=[${VISUAL_DATASET_TRAIN_3}] \
    data.train_batch_size=32 \
    data.max_prompt_length=8192 \
    data.max_response_length=20480 \
    data.return_raw_chat=True \
    data.filter_overlong_prompts=True \
    algorithm.adv_estimator=grpo \
    algorithm.kl_ctrl.kl_coef=0.0 \
    actor_rollout_ref.model.path=${REF_MODEL_PATH} \
    actor_rollout_ref.model.use_remove_padding=True \
    actor_rollout_ref.actor.optim.lr=1e-7 \
    actor_rollout_ref.actor.ppo_mini_batch_size=32 \
    actor_rollout_ref.actor.ppo_micro_batch_size_per_gpu=2 \
    actor_rollout_ref.actor.use_kl_loss=False \
    actor_rollout_ref.actor.kl_loss_coef=0.0 \
    actor_rollout_ref.actor.kl_loss_type=low_var_kl \
    actor_rollout_ref.actor.entropy_coeff=0.0 \
    actor_rollout_ref.actor.checkpoint.contents=['model','hf_model','optimizer','extra'] \
    actor_rollout_ref.actor.ulysses_sequence_parallel_size=1 \
    actor_rollout_ref.rollout.log_prob_micro_batch_size_per_gpu=8 \
    actor_rollout_ref.rollout.tensor_model_parallel_size=2 \
    actor_rollout_ref.rollout.name=vllm \
    actor_rollout_ref.rollout.n=16 \
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
    actor_rollout_ref.rollout.agent.max_turns=5 \
    actor_rollout_ref.rollout.agent.concurrent_workers=1 \
    actor_rollout_ref.rollout.agent.show_tqdm=True \
    trainer.critic_warmup=0 \
    trainer.logger=['console','wandb','rl_logging_board'] \
    trainer.val_before_train=False \
    trainer.n_gpus_per_node=8 \
    trainer.nnodes=${WORLD_SIZE} \
    trainer.save_freq=10 \
    trainer.test_freq=5 \
    trainer.project_name=${PROJECT_NAME} \
    trainer.experiment_name=${EXPERIMENT_NAME} \
    trainer.default_local_dir=${SAVE_CHECKPOINT_DIR}/${PROJECT_NAME}/${EXPERIMENT_NAME} \
    +trainer.tensorboard_dir=${SAVE_CHECKPOINT_DIR}/logs/tensorboard \
    +trainer.rl_logging_board_dir=${SAVE_CHECKPOINT_DIR}/logs/rl_logging_board \
    trainer.total_epochs=32 2>&1 | tee ./logs/${EXPERIMENT_NAME}.log
