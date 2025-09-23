#!/bin/bash
#SBATCH --job-name=deepeyes_train      # 任务名称
#SBATCH --partition=Silo_Customer_Engineering  # 分区名称
#SBATCH --nodelist=tw006               # 可用节点，可替换为其他可用节点
#SBATCH --ntasks=1                     # 任务数量
#SBATCH --cpus-per-task=16             # CPU核心数，根据需求调整
#SBATCH --mem=450G                     # 内存需求，略高于shm-size
#SBATCH --time=8:00:00                 # 任务超时时间，根据训练时长调整
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

# 清理任何可能存在的同名旧容器
docker stop $CONTAINER_NAME > /dev/null 2>&1 || true
docker rm $CONTAINER_NAME > /dev/null 2>&1 || true

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
if ! docker ps -f name=$CONTAINER_NAME --format '{{.Names}}' | grep -q $CONTAINER_NAME; then
    echo "错误：容器启动失败"
    docker logs $CONTAINER_NAME # 打印日志以帮助调试
    exit 1
fi

# 在容器内执行初始化操作
echo "在容器内执行初始化操作..."
docker exec $CONTAINER_NAME bash -c "
  set -e; # 如果任何命令失败，则立即退出

  echo '--- 步骤1: 更新软件包并安装系统依赖 (tmux, git) ---';
  apt-get update && apt-get install -y tmux git;

  echo '--- 步骤2: 解决 git 仓库所有权问题 ---';
  git config --global --add safe.directory $DATA_DIR/codes/DeepEyes;

  echo '--- 步骤3: 安装 Python 依赖 (verl) ---';
  cd $DATA_DIR/codes/verl && pip install -e .;
  
  echo '--- 步骤4: 安装其他 Python 依赖 ---';
  pip install duckduckgo_search gymnasium playwright 'transformers<4.53.0' qwen-vl-utils;
  
  echo '--- 步骤5: 检出 DeepEyes 的目标分支 ---';
  cd $DATA_DIR/codes/DeepEyes && git checkout train_iad_tools;
"

# 检查上一步初始化是否成功
if [ $? -ne 0 ]; then
    echo "错误：容器内初始化失败。请检查上方日志。"
    docker logs $CONTAINER_NAME
    docker stop $CONTAINER_NAME
    docker rm $CONTAINER_NAME
    exit 1
fi
echo "容器初始化成功！"

# 启动vllm会话并运行
echo "启动vllm会话..."
docker exec $CONTAINER_NAME bash -c "
  cd $DATA_DIR && \
  tmux new-session -d -s vllm && \
  tmux send-keys -t vllm 'huggingface-cli download Qwen/Qwen2.5-VL-72B-Instruct' C-m && \
  tmux send-keys -t vllm 'export ROCR_VISIBLE_DEVICES=7' C-m && \
  tmux send-keys -t vllm 'bash $DATA_DIR/codes/vllm_infra/run.sh' C-m
"

# 等待vllm启动完成
echo "等待vllm启动 (约5分钟)..."
sleep 300

# 启动verl训练会话
echo "启动verl训练会话..."
docker exec $CONTAINER_NAME bash -c "
  cd $DATA_DIR/codes/DeepEyes && \
  tmux new-session -d -s verl && \
  tmux send-keys -t verl 'export ROCR_VISIBLE_DEVICES=0,1,2,3,4,5,6' C-m && \
  tmux send-keys -t verl 'bash examples/agent/train_iad.sh' C-m
"

echo "所有会话已启动，任务在后台运行。"
echo "可通过以下命令进入容器查看进度："
echo "docker exec -it $CONTAINER_NAME /bin/bash"
echo "然后使用 'tmux attach -t vllm' 或 'tmux attach -t verl' 查看对应会话"

# 监控任务运行状态
echo "开始监控训练任务..."
while true; do
  # 检查两个tmux会话是否都在运行
  VLLM_RUNNING=\$(docker exec $CONTAINER_NAME bash -c "tmux has-session -t vllm 2>/dev/null && echo 1 || echo 0")
  VERL_RUNNING=\$(docker exec $CONTAINER_NAME bash -c "tmux has-session -t verl 2>/dev/null && echo 1 || echo 0")
  
  if [ \$VLLM_RUNNING -eq 0 ] && [ \$VERL_RUNNING -eq 0 ]; then
    echo "所有tmux会话已结束，训练任务完成。"
    break
  fi
  
  echo "任务仍在运行中...（\$(date)）"
  sleep 300  # 每5分钟检查一次
done

# 训练完成后停止并移除容器
echo "训练完成，正在停止并清理容器..."
docker stop $CONTAINER_NAME
docker rm $CONTAINER_NAME

echo "任务结束时间: $(date)"
