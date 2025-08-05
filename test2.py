import torch
from vllm import LLM
if __name__ == '__main__': 
    # 初始化模型
    llm = LLM(
        model="/app/models/Qwen2.5-VL-3B-Instruct",
        # enable_sleep_mode=True,
        enforce_eager=False,  # 启用 eager 模式以提高稳定性
        dtype="bfloat16",     # 使用 BF16 精度
        gpu_memory_utilization=0.5,  # 控制显存使用率
        device = 'auto'
    )

    # 定义推理函数
    def run_inference(prompt):
        outputs = llm.generate(prompt)
        for output in outputs:
            print(f"Prompt: {output.prompt}, Generated text: {output.outputs[0].text}")

    # 打印初始显存使用情况
    print("Initial CUDA Memory Usage:")
    torch.cuda.empty_cache()
    print(f"Memory Allocated: {torch.cuda.memory_allocated()} bytes")

    # 运行一次推理
    run_inference("The capital of France is")

    # 打印推理后的显存使用情况
    print("\nCUDA Memory Usage After Inference:")
    torch.cuda.empty_cache()
    print(f"Memory Allocated: {torch.cuda.memory_allocated()} bytes")

    # 进入睡眠模式
    llm.sleep()

    # 打印睡眠后的显存使用情况
    print("\nCUDA Memory Usage After Sleep:")
    torch.cuda.empty_cache()
    print(f"Memory Allocated: {torch.cuda.memory_allocated()} bytes")

    # 唤醒模型
    llm.wake_up()

    # 打印唤醒后的显存使用情况
    print("\nCUDA Memory Usage After Wake Up:")
    torch.cuda.empty_cache()
    print(f"Memory Allocated: {torch.cuda.memory_allocated()} bytes")

    # 再次运行推理
    run_inference("The capital of Japan is")
