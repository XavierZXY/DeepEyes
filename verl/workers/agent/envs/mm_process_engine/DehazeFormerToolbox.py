import requests
import json
import re
import io
import os
from PIL import Image
from typing import Dict, Any, Tuple
from .IRprompt import PROMPT
from .tool_load_balancer import get_tool_service_ip
# This is a placeholder for the actual ToolBase class.
# In a real environment, you would import it:
# from verl.workers.agent.tool_envs import ToolBase
# class ToolBase:
#     def __init__(self, name):
#         self._name = name

#     @property
#     def name(self):
#         return self._name     
from verl.workers.agent.tool_envs import ToolBase
class DehazeFormerToolbox(ToolBase):
    """
    A toolbox that provides an image dehazing tool by calling a Flask API.
    """
    name = "dehazeformer_dehaze"
    user_prompt = PROMPT.USER_PROMPT_V1
    
    def __init__(self, _name, _desc, _params, api_url: str = None):
        """
        Initializes the toolbox.

        Args:
            api_url (str): The URL of the DehazeFormer Flask API endpoint.
        """
        super().__init__(name=self.name)
        # 从环境变量读取IP地址，保留端口号5002
        if api_url is None:
            ip = get_tool_service_ip()
            api_url = f'http://{ip}:5002/dehaze'
        self.api_url = api_url
        self.multi_modal_data = None
        print(f"DehazeFormerToolbox initialized. API endpoint: {self.api_url}")

    def extract_answer(self, action_string: str) -> str or None:
        """Extracts the final answer from the action string."""
        answer = re.findall(r'<answer>(.*?)</answer>', action_string, re.DOTALL)
        return answer[-1] if answer else None

    def extract_action(self, action_string: str) -> str or None:
        """Extracts the tool call from the action string."""
        tool_call_match = re.findall(r'<tool_call>(.*?)</tool_call>', action_string, re.DOTALL)
        return tool_call_match[-1] if tool_call_match else None

    def execute(self, action_string: str, **kwargs) -> Tuple[Dict[str, Any] or str, float, bool, Dict[str, Any]]:
        """
        Executes the tool functionality based on the action string.

        Args:
            action_string: The string containing the tool call.

        Returns:
            A tuple containing (observation, reward, done, info).
        """
        import time
        start_time = time.time()
        print(f"[TOOL EXECUTE] 🚀 开始执行 {self.name}")
        
        answer = self.extract_answer(action_string)
        if answer:
            # If a final answer is given, terminate the episode.
            return "", 0.0, True, {"status": "finished", "answer": answer}

        action = self.extract_action(action_string)
        if not action:
            # No valid action found, terminate.
            error_msg = "Invalid action format: No <tool_call> or <answer> tags found."
            obs = "\n<|im_start|>user\n" + f"Error: {error_msg}" + "<|im_end|>\n<|im_start|>assistant\n"
            return obs, 0.0, True, {"error": error_msg, "status": "failed"}

        try:
            
            tool_call = json.loads(action.strip())
            if isinstance(tool_call, list):
                tool_call = tool_call[0]
            tool_name = tool_call["name"]
            
            if tool_name != self.name:
                raise ValueError(f"Unknown tool name: '{tool_name}'. This toolbox only supports '{self.name}'.")

            # Get the current image from the state
            if not self.multi_modal_data or 'image' not in self.multi_modal_data or not self.multi_modal_data['image']:
                raise ValueError("No image found in the current state to process.")
            
            source_image = self.multi_modal_data['image'][0]
            
            # 添加输入图像调试信息
            import numpy as np
            input_array = np.array(source_image)
            input_mean = np.mean(input_array)
            input_std = np.std(input_array)
            print(f"[DEHAZE DEBUG] 输入图像: 尺寸={source_image.size}, mean={input_mean:.2f}, std={input_std:.2f}", flush=True)

            # Convert PIL Image to bytes to send to the API
            img_byte_arr = io.BytesIO()
            source_image.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)

            # Call the DehazeFormer API
            files = {'image': ('hazy_image.png', img_byte_arr, 'image/png')}
            data = {'queue': 'true'}  # 启用队列机制，避免并发时直接拒绝
            print(f"[DEHAZE DEBUG] 发送图像到去雾服务器", flush=True)
            response = requests.post(self.api_url, files=files, data=data, timeout=180)
            
            if response.status_code != 200:
                raise ConnectionError(f"API request failed with status code {response.status_code}: {response.text}")
            
            # Process the returned image
            dehazed_image_bytes = io.BytesIO(response.content)
            current_image = Image.open(dehazed_image_bytes)
            
            # 添加输出图像调试信息
            output_array = np.array(current_image)
            output_mean = np.mean(output_array)
            output_std = np.std(output_array)
            print(f"[DEHAZE DEBUG] 输出图像: 尺寸={current_image.size}, mean={output_mean:.2f}, std={output_std:.2f}", flush=True)
            
            # 检查图像一致性
            size_changed = source_image.size != current_image.size
            significant_change = abs(input_mean - output_mean) > 10 or abs(input_std - output_std) > 10
            print(f"[DEHAZE DEBUG] 图像变化: 尺寸变化={size_changed}, 显著统计变化={significant_change}", flush=True)
            
            # 检查像素差异
            if input_array.shape == output_array.shape:
                pixel_diff = np.mean(np.abs(input_array.astype(float) - output_array.astype(float)))
                print(f"[DEHAZE DEBUG] 像素差异: 平均绝对差={pixel_diff:.2f}", flush=True)

            # Prepare the observation for the next step
            obs = {
                "prompt": "\n<|im_start|>user\n" + "<tool_response>" + "<image>" + self.user_prompt.format(tool_name=self.name) + "</tool_response>" + "<|im_end|>\n<|im_start|>assistant\n",
                "multi_modal_data": {"image": [current_image]}
            }
            end_time = time.time()
            execution_time = end_time - start_time
            print(f"[TOOL EXECUTE] ✅ {self.name} 执行成功 (耗时: {execution_time:.2f}s)")
            
            reward = 0.  # Reward for a successful tool call
            done = False
            info = {"status": "success", "tool_used": tool_name, "execution_time": execution_time}
            return obs, reward, done, info

        except Exception as e:
            end_time = time.time()
            execution_time = end_time - start_time
            print(f"[TOOL EXECUTE] ❌ {self.name} 执行失败 (耗时: {execution_time:.2f}s): {str(e)}")
            
            # Handle JSON errors, tool errors, or API connection errors
            error_msg = f"Execution failed. Error: {e}"
            obs = "\n<|im_start|>user\n" + f"Error: {error_msg}" + "<|im_end|>\n<|im_start|>assistant\n"
            return obs, -0.1, False, {"error": str(e), "status": "failed", "execution_time": execution_time}
    # def execute(self, arguments: Dict[str, Any], **kwargs) -> Tuple[Dict[str, Any] or str, float, bool, Dict[str, Any]]:
    #     """
    #     根据 Agent 框架传入的参数执行工具功能。

    #     Args:
    #         arguments (Dict[str, Any]): Agent 从模型输出中解析出的参数字典。
    #                                    对于这个工具，此字典可能为空。

    #     Returns:
    #         一个包含 (observation, reward, done, info) 的元组。
    #     """
    #     try:
    #         # 1. 从状态中获取当前图像
    #         if not self.multi_modal_data or 'image' not in self.multi_modal_data or not self.multi_modal_data['image']:
    #             raise ValueError("在当前状态中未找到可处理的图像。")
            
    #         source_image = self.multi_modal_data['image'][0]

    #         # 2. 将 PIL 图像转换为字节流以便发送到 API
    #         img_byte_arr = io.BytesIO()
    #         source_image.save(img_byte_arr, format='PNG')
    #         img_byte_arr.seek(0)

    #         # 3. 调用 DehazeFormer API
    #         files = {'image': ('hazy_image.png', img_byte_arr, 'image/png')}
    #         response = requests.post(self.api_url, files=files, timeout=30)
            
    #         if response.status_code != 200:
    #             raise ConnectionError(f"API 请求失败，状态码 {response.status_code}: {response.text}")
            
    #         # 4. 处理返回的去雾后图像
    #         dehazed_image_bytes = io.BytesIO(response.content)
    #         current_image = Image.open(dehazed_image_bytes)

    #         # 5. 准备下一步的观察（observation）
    #         # Agent 会将这个字典处理成模型可读的 token 和多模态输入
    #         obs = {
    #             "prompt": "\n<|im_start|>user\n" + "<tool_response>" + "<image>" + self.user_prompt + "</tool_response>" + "<|im_end|>\n<|im_start|>assistant\n",
    #             "multi_modal_data": {"image": [current_image]}
    #         }
    #         reward = 0.1  # 成功调用工具的奖励
    #         done = False
    #         info = {"status": "success", "tool_used": self.name}
    #         return obs, reward, done, info

    #     except Exception as e:
    #         # 处理各类错误
    #         error_msg = f"工具执行失败。错误: {e}"
    #         # 返回一个错误信息作为观察，让模型知道调用失败了
    #         obs = {
    #             "prompt": "\n<|im_start|>user\n" + f"<tool_response>Error: {error_msg}</tool_response>" + "<|im_end|>\n<|im_start|>assistant\n"
    #         }
    #         return obs, -1.0, False, {"error": str(e), "status": "failed"}

    def reset(self, raw_prompt, multi_modal_data, origin_multi_modal_data=None, **kwargs):
        """Resets the state of the toolbox with a new image and prompt."""
        # 使用当前处理后的图片，如果没有则使用原始图片
        self.multi_modal_data = multi_modal_data if multi_modal_data else origin_multi_modal_data
        assert 'image' in self.multi_modal_data and self.multi_modal_data['image'], "Initial multi_modal_data must contain at least one image."
        print("Toolbox reset with a new image.")


if __name__ == "__main__":
    # --- Example Usage (for testing) ---
    # This example requires the Flask server (app.py) to be running.
    
    print("--- DehazeFormerToolbox Test ---")
    
    # 1. Initialize the toolbox
    tool = DehazeFormerToolbox()
    
    # 2. Create a dummy hazy image for testing
    try:
        # Create a simple hazy-looking image (e.g., a gray square)
        hazy_img = Image.new('RGB', (200, 200), color = 'gray')
        print("Created a dummy gray image for testing.")
    except Exception as e:
        print(f"Could not create a dummy image. Make sure Pillow is installed. Error: {e}")
        hazy_img = None

    if hazy_img:
        # 3. Reset the tool's state with the image
        initial_data = {"image": [hazy_img]}
        tool.reset(raw_prompt="", multi_modal_data=initial_data)

        # 4. Define the tool call action
        dehaze_action = """
        <tool_call>
        {"name": "image_dehaze_tool", "arguments": {}}
        </tool_call>
        """
        
        print("\nExecuting 'image_dehaze_tool'...")
        # 5. Execute the action
        # This will send the dummy image to the running Flask API
        try:
            obs, reward, done, info = tool.execute(dehaze_action)
            
            print(f"\nExecution Result:")
            print(f"  - Reward: {reward}")
            print(f"  - Done: {done}")
            print(f"  - Info: {info}")

            if info.get("status") == "success":
                print("  - Observation contains a processed image.")
                processed_image = obs['multi_modal_data']['image'][0]
                print(f"  - Processed Image Size: {processed_image.size}")
                # In a real scenario, you could save or display this image
                # processed_image.save("test_dehazed_output.png")
                # print("  - Processed image saved to 'test_dehazed_output.png'")
            else:
                print(f"  - Observation contains an error message.")

        except requests.exceptions.ConnectionError:
            print("\n[ERROR] Connection failed. Please make sure the Flask server ('app.py') is running in a separate terminal before running this test.")
        except Exception as e:
            print(f"\n[ERROR] An unexpected error occurred during execution: {e}")
