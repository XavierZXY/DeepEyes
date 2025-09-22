#!/bin/bash
#SBATCH --job-name=deepeyes_train      # 任务名称
#SBATCH --partition=Silo_Customer_Engineering  # 分区名称
#SBATCH --nodelist=tw006               # 可用节点，可替换为其他可用节点
#SBATCH --ntasks=1                     # 任务数量
#SBATCH --cpus-per-task=16             # CPU核心数，根据需求调整
#SBATCH --mem=450G                     # 内存需求，略高于shm-size
#SBATCH --time=8:00:00                # 任务超时时间，根据训练时长调整
#SBATCH --output=deepeyes_%j.out       # 输出日志文件
#SBATCH --error=deepeyes_%j.err        # 错误日志文件

# 打印任务信息
echo "开始DeepEyes训练任务"
echo "任务ID: $SLURM_JOB_ID"
echo "执行节点: $(hostname)"
echo "开始时间: $(date)"

# 定义变量
CONTAINER_NAME="deepeyes_${SLURM_JOB_ID}"  # 为避免冲突，使用任务ID作为容器名后缀
DATA_DIR="/home/takisobe@amd.com/zxy"
DOCKER_IMAGE="388530baa949"

# 检查数据目录是否存在
if [ ! -d "$DATA_DIR" ]; then
    echo "错误：数据目录 $DATA_DIR 不存在！"
    exit 1
fi

# 检查Docker是否可用
if ! command -v docker &> /dev/null; then
    echo "错误: 未找到docker命令"
    exit 1
fi

# 启动Docker容器
echo "启动Docker容器: $CONTAINER_NAME"
docker run -d --name=$CONTAINER_NAME \
  --volume $DATA_DIR:$DATA_DIR \
  --device /dev/dri:/dev/dri \
  --device /dev/kfd:/dev/kfd \
  --shm-size=400g \
  --cap-add SYS_PTRACE \
  --privileged \
  --security-opt seccomp=unconfined \
  --group-add video \
  -w $DATA_DIR \
  -p 9091:9091 \
  -p 9092:9092 \
  -t $DOCKER_IMAGE

# 等待容器启动
sleep 10

# 检查容器是否正常运行
if ! docker inspect $CONTAINER_NAME &> /dev/null; then
    echo "错误：容器启动失败"
    exit 1
fi

# 在容器内执行命令
echo "在容器内执行初始化操作"

# 安装依赖包
docker exec $CONTAINER_NAME bash -c "
  cd $DATA_DIR/codes/verl && pip install -e . && \
  pip install duckduckgo_search gymnasium playwright && \
  pip install 'transformers<4.53.0' qwen-vl-utils && \
  cd $DATA_DIR/codes/DeepEyes && \
  git checkout train_iad_tools && \
  apt update && apt install -y tmux
"

# 启动vllm会话并运行
echo "启动vllm会话"
docker exec $CONTAINER_NAME bash -c "
  cd $DATA_DIR && \
  tmux new-session -d -s vllm && \
  tmux send-keys -t vllm 'huggingface-cli download Qwen/Qwen2.5-VL-72B-Instruct' C-m && \
  tmux send-keys -t vllm 'export ROCR_VISIBLE_DEVICES=7' C-m && \
  tmux send-keys -t vllm 'bash $DATA_DIR/codes/vllm_infra/run.sh' C-m
"

# 等待vllm启动完成（根据实际情况调整等待时间）
sleep 300

# 启动verl训练会话
echo "启动verl训练会话"
docker exec $CONTAINER_NAME bash -c "
  cd $DATA_DIR/codes/DeepEyes && \
  tmux new-session -d -s verl && \
  tmux send-keys -t verl 'export ROCR_VISIBLE_DEVICES=0,1,2,3,4,5,6' C-m && \
  tmux send-keys -t verl 'bash examples/agent/train_iad.sh' C-m
"

echo "所有会话已启动，任务在后台运行"
echo "可通过以下命令进入容器查看进度："
echo "docker exec -it $CONTAINER_NAME /bin/bash"
echo "然后使用 tmux at -t vllm 或 tmux at -t verl 查看对应会话"

# 监控任务运行状态（可选）
# 注意：如果训练需要长时间运行，可能需要移除或调整此部分
echo "开始监控训练任务..."
while true; do
  # 检查两个tmux会话是否都在运行
  VLLM_RUNNING=$(docker exec $CONTAINER_NAME bash -c "tmux has-session -t vllm 2>/dev/null && echo 1 || echo 0")
  VERL_RUNNING=$(docker exec $CONTAINER_NAME bash -c "tmux has-session -t verl 2>/dev/null && echo 1 || echo 0")
  
  if [ $VLLM_RUNNING -eq 0 ] && [ $VERL_RUNNING -eq 0 ]; then
    echo "所有训练任务已完成"
    break
  fi
  
  echo "任务仍在运行中...（$(date)）"
  sleep 300  # 每5分钟检查一次
done

# 训练完成后停止容器（可选，根据需求决定是否保留容器）
# docker stop $CONTAINER_NAME

echo "任务结束时间: $(date)"
