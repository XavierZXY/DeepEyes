MODEL_PATH=/data/models/zxy/verl_checkpoints/agent_vlagent/debug_for_single_node
    # --hf_model_path ${MODEL_PATH}/global_step_192/actor/huggingface \
python3 -m verl.model_merger merge \
    --backend fsdp \
    --local_dir ${MODEL_PATH}/global_step_192/actor \
    --target_dir ${MODEL_PATH}/global_step_192/actor/huggingface