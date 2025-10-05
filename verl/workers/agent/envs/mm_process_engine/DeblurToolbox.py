import numpy as np
import requests
import json
import re
from PIL import Image
from typing import Dict, Any, Union
import io

# 假设这些基类和 PROMPT 来自您的 deepeyes 环境
# from verl.workers.agent.tool_envs import ToolBase
# from verl.workers.agent.envs.mm_process_engine.prompt import PROMPT

# --- 为了独立测试而创建的虚拟类 ---
# class ToolBase:
#     def __init__(self, name, **kwargs):
#         self.name = name
from verl.workers.agent.tool_envs import ToolBase
from .IRprompt import PROMPT

class DeblurToolbox(ToolBase):
    """
    一个通过 API 调用 DRBNet 模型来去模糊图像的 DeepEyes 工具。
    """
    name = "drbnet_defocus_deblurring"
    user_prompt = PROMPT.USER_PROMPT_V1
    
    # 将此 URL 修改为您的 DRBNet 服务器的实际地址
    server_url = "http://172.18.148.193:5003/deblur"

    def __init__(self, _name="deblur_toolbox", _desc="A tool for deblurring images using a remote DRBNet API.", _params={}, **kwargs):
        super().__init__(
            name=self.name,
        )
        self.chatml_history = []
        self.multi_modal_data = None

    def extract_answer(self, action_string: str) -> Union[str, None]:
        """从模型的输出中提取 <answer> 标签内的最终答案。"""
        answer_match = re.search(r'<answer>(.*?)</answer>', action_string, re.DOTALL)
        return answer_match.group(1) if answer_match else None

    def extract_action(self, action_string: str) -> Union[str, None]:
        """从模型的输出中提取 <tool_call> 标签内的工具调用指令。"""
        tool_call_match = re.search(r'<tool_call>(.*?)</tool_call>', action_string, re.DOTALL)
        return tool_call_match.group(1) if tool_call_match else None

    def execute(self, action_string: str, **kwargs) -> tuple:
        """
        执行工具调用。

        Args:
            action_string: 包含 <tool_call> 或 <answer> 的模型输出字符串。

        Returns:
            一个元组 (observation, reward, done, info)。
        """
        import time
        start_time = time.time()
        print(f"[TOOL EXECUTE] 🚀 开始执行 {self.name}")
        
        answer = self.extract_answer(action_string)
        if answer:
            # 如果模型给出了最终答案，则任务结束
            return "", 0.0, True, {"status": "finished", "answer": answer}
        
        action = self.extract_action(action_string)
        if not action:
            # 如果没有找到工具调用或答案，视为无效操作
            error_msg = "No valid <tool_call> or <answer> tag found in the action string."
            obs = f"\n<|im_start|>user\nError: {error_msg}<|im_end|>\n<|im_start|>assistant\n"
            return obs, 0.0, False, {"error": error_msg, "status": "failed"}
        
        try:
            # 解析 JSON 格式的工具调用
            tool_call = json.loads(action.strip())
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON format in tool call: {action.strip()}. Error: {e}"
            obs = f"\n<|im_start|>user\nError: {error_msg}<|im_end|>\n<|im_start|>assistant\n"
            return obs, 0.0, False, {"error": str(e), "status": "failed"}

        try:
            if isinstance(tool_call, list):
                tool_call = tool_call[0]
            tool_name = tool_call.get("name")
            if tool_name != self.name:
                raise ValueError(f"Unknown tool name: '{tool_name}'. This toolbox only supports 'deblur_tool'.")

            # 从环境中获取当前图像
            if not self.multi_modal_data or 'image' not in self.multi_modal_data or not self.multi_modal_data['image']:
                 raise ValueError("No image found in the current environment state (multi_modal_data).")
            
            current_image = self.multi_modal_data['image'][0]
            
            # 添加输入图像调试信息
            import numpy as np
            input_array = np.array(current_image)
            input_mean = np.mean(input_array)
            input_std = np.std(input_array)
            print(f"[DEBLUR DEBUG] 输入图像: 尺寸={current_image.size}, mean={input_mean:.2f}, std={input_std:.2f}", flush=True)
            
            # 将 PIL Image 转换为二进制数据以便发送
            buffer = io.BytesIO()
            current_image.save(buffer, format='PNG')
            buffer.seek(0)
            
            # 准备发送到服务器的数据
            # 'image_c' 是服务器端要求的字段名
            files = {'image_c': ('image.png', buffer, 'image/png')}
            
            print(f"[DEBLUR DEBUG] 发送图像到去模糊服务器: {current_image.size}", flush=True)
            
            # 发送 POST 请求到 DRBNet 服务器
            response = requests.post(self.server_url, files=files, timeout=60)
            
            # 检查服务器响应是否成功
            if response.status_code != 200:
                try:
                    error_info = response.json()
                    raise ConnectionError(f"API Error ({response.status_code}): {error_info.get('error', 'Unknown server error')}")
                except json.JSONDecodeError:
                     raise ConnectionError(f"API Error ({response.status_code}): {response.text}")

            # 处理返回的去模糊图像
            deblurred_image = Image.open(io.BytesIO(response.content))
            
            # 添加输出图像调试信息
            output_array = np.array(deblurred_image)
            output_mean = np.mean(output_array)
            output_std = np.std(output_array)
            print(f"[DEBLUR DEBUG] 输出图像: 尺寸={deblurred_image.size}, mean={output_mean:.2f}, std={output_std:.2f}", flush=True)
            
            # 检查图像一致性
            size_changed = current_image.size != deblurred_image.size
            significant_change = abs(input_mean - output_mean) > 10 or abs(input_std - output_std) > 10
            print(f"[DEBLUR DEBUG] 图像变化: 尺寸变化={size_changed}, 显著统计变化={significant_change}", flush=True)
            
            # 检查图像是否完全相同
            if input_array.shape == output_array.shape:
                pixel_diff = np.mean(np.abs(input_array.astype(float) - output_array.astype(float)))
                print(f"[DEBLUR DEBUG] 像素差异: 平均绝对差={pixel_diff:.2f}", flush=True)

            # 构建并返回新的观测值 (observation)
            obs = {
                "prompt": f"\n<|im_start|>user\n<tool_response><image>{self.user_prompt.format(tool_name=self.name)}</tool_response><|im_end|>\n<|im_start|>assistant\n",
                "multi_modal_data": {"image": [deblurred_image]}
            }
            end_time = time.time()
            execution_time = end_time - start_time
            print(f"[TOOL EXECUTE] ✅ {self.name} 执行成功 (耗时: {execution_time:.2f}s)")
            
            reward = 0.  # 成功调用工具的奖励
            done = False
            info = {"status": "success", "tool_used": tool_name, "output_image_size": deblurred_image.size, "execution_time": execution_time}
            return obs, reward, done, info

        except (ValueError, ConnectionError, requests.exceptions.RequestException) as e:
            end_time = time.time()
            execution_time = end_time - start_time
            print(f"[TOOL EXECUTE] ❌ {self.name} 执行失败 (耗时: {execution_time:.2f}s): {str(e)}")
            
            obs = f"\n<|im_start|>user\nError: {str(e)}<|im_end|>\n<|im_start|>assistant\n"
            return obs, -0.1, False, {"error": str(e), "status": "failed", "execution_time": execution_time}

    def reset(self, raw_prompt, multi_modal_data, origin_multi_modal_data, **kwargs):
        """重置工具状态，在每个新任务开始时调用。"""
        self.chatml_history = raw_prompt
        # 使用当前处理后的图片，而不是原始图片
        self.multi_modal_data = multi_modal_data if multi_modal_data else origin_multi_modal_data


if __name__ == '__main__':
    # --- 这是一个用于本地测试工具逻辑的示例 ---
    
    # 1. 实例化工具
    deblur_tool = DeblurToolboxV2()

    # 2. 创建一个符合模型要求的虚拟图片 (大尺寸)
    try:
        test_image = Image.new('RGB', (1280, 720), color = 'purple')
        print("Created a 1280x720 dummy image for testing.")
    except Exception as e:
        print(f"Failed to create dummy image: {e}")
        exit()

    # 3. 模拟 DeepEyes 环境的 reset 过程
    # multi_modal_data 包含一个名为 'image' 的 key，其 value 是一个 Image 对象列表
    initial_multi_modal_data = {"image": [test_image]}
    deblur_tool.reset(
        raw_prompt="Initial prompt",
        multi_modal_data=initial_multi_modal_data,
        origin_multi_modal_data=initial_multi_modal_data
    )
    print("Tool has been reset with the initial image.")

    # 4. 构造一个模拟的模型输出，其中包含工具调用指令
    action_to_execute = """
    <tool_call>
    {
        "name": "deblur_tool",
        "arguments": {}
    }
    </tool_call>
    """
    
    print("\nExecuting deblur_tool...")
    
    # 5. 执行工具调用
    # 假设您的 drbnet_server.py 正在 http://127.0.0.1:5001 上运行
    obs, reward, done, info = deblur_tool.execute(action_to_execute)

    # 6. 打印和分析结果
    print("\n--- Execution Result ---")
    print(f"Reward: {reward}")
    print(f"Done: {done}")
    print(f"Info: {info}")

    if info.get("status") == "success":
        print("✅ Tool execution was successful.")
        # 可以在本地显示返回的图片以供检查
        returned_image = obs['multi_modal_data']['image'][0]
        print(f"Returned image size: {returned_image.size}")
        # returned_image.show() 
    else:
        print(f"❌ Tool execution failed. Error: {info.get('error')}")