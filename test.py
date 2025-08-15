import torch
from vllm import LLM

llm = LLM(model="/app/models/Qwen2.5-VL-7B-Instruct", enable_sleep_mode=True)

def run_inference(prompt):
        outputs = llm.generate(prompt)
        for output in outputs:
                prompt = output.prompt
                generated_text = output.outputs[0].text
                print(f"Prompt: {prompt!r}, Generated text: {generated_text!r}")


print("CUDA Memory Usage (after inference):")
torch.cuda.empty_cache()
print(f"{torch.cuda.memory_allocated()=}")

run_inference("San Francisco is")
llm.sleep()

print("CUDA Memory Usage (after sleep):")
torch.cuda.empty_cache()
print(f"{torch.cuda.memory_allocated()=}")

llm.wake_up()

print("CUDA Memory Usage (after wakeup):")
torch.cuda.empty_cache()
print(f"{torch.cuda.memory_allocated()=}")

run_inference("Paris is")