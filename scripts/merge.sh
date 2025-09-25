MODEL_PATH=/data/models/qwen-iad-ground-3b-200
    # --hf_model_path ${MODEL_PATH}/global_step_192/actor/huggingface \
python3 -m verl.model_merger merge \
    --backend fsdp \
    --local_dir ${MODEL_PATH}/global_step_200/actor \
    --target_dir ${MODEL_PATH}/global_step_200/actor/huggingface
