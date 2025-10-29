import numpy as np
import requests
import base64
import io
import json
import re
import os
from typing import Dict, Any, Union
from PIL import Image

# Assuming ToolBase and PROMPT are correctly imported from your framework
from ...tool_envs import ToolBase
from .IRprompt import PROMPT

# ====================== 公共基类 ======================
class BaseNAFNetToolbox(ToolBase):
    """
    NAFNet (Nonlinear Activation Free Network) 图像复原工具基类
    """
    # Placeholder name for base class
    name = "base_nafnet_toolbox" 
    
    # These will be overridden by subclasses
    task_name: str = ""
    
    user_prompt = PROMPT.USER_PROMPT_V1
    # 从环境变量读取IP地址，端口号5012
    api_url = f"http://{os.environ.get('TOOL_SERVICE_IP', '10.21.9.6')}:5012/process"

    def __init__(self, _name=None, _desc=None, _params=None, **kwargs):
        # The 'name' is now a class attribute, so we don't need to pass it here.
        super().__init__(name=self.name, **kwargs) 
        self.chatml_history = []
        self.multi_modal_data = None
        print(f"NAFNetToolbox initialized. API endpoint: {self.api_url}")

    def _call_nafnet_api(self, image: Image.Image, task_params: Dict[str, Any]) -> Image.Image:
        """调用 NAFNet API 进行图像复原处理"""
        print(f"[NAFNet API] 🚀 开始调用API: {self.api_url}", flush=True)
        print(f"[NAFNet API] 任务参数: {task_params}", flush=True)
        
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        image_bytes = buf.getvalue()
        files = {'image': ('image.png', image_bytes, 'image/png')}
        
        try:
            print(f"[NAFNet API] 发送POST请求...", flush=True)
            resp = requests.post(self.api_url, files=files, data=task_params, timeout=300)
            print(f"[NAFNet API] 收到响应，状态码: {resp.status_code}", flush=True)
            
            resp.raise_for_status()
            result = resp.json()
            print(f"[NAFNet API] JSON响应: success={result.get('success')}", flush=True)
            
            if result.get('success'):
                img_b64 = result['image']
                img_bytes = base64.b64decode(img_b64)
                restored_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                self.multi_modal_data['image'][0] = restored_image
                print(f"[NAFNet API] ✅ API调用成功，图像处理完成", flush=True)
                return restored_image
            else:
                error_msg = result.get('error','Unknown API error')
                print(f"[NAFNet API] ❌ API返回错误: {error_msg}", flush=True)
                raise RuntimeError(f"NAFNet API error: {error_msg}")
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if "503" in error_msg and "SERVICE UNAVAILABLE" in error_msg:
                raise ConnectionError(f"NAFNet service is temporarily unavailable (likely due to GPU memory shortage). Please try again later or contact administrator. Error: {e}")
            else:
                raise ConnectionError(f"Failed to connect to NAFNet API at {self.api_url}. Error: {e}")
            
    def extract_answer(self, action_string: str) -> Union[str, None]:
        """从模型的输出中提取 <answer> 标签内的最终答案。"""
        answer_match = re.search(r'<answer>(.*?)</answer>', action_string, re.DOTALL)
        return answer_match.group(1) if answer_match else None

    def extract_action(self, action_string: str) -> Union[str, None]:
        """从模型的输出中提取 <tool_call> 标签内的工具调用指令。"""
        tool_call_match = re.search(r'<tool_call>(.*?)</tool_call>', action_string, re.DOTALL)
        return tool_call_match.group(1) if tool_call_match else None

    def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

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
        
        # 检查是否有最终答案
        answer = self.extract_answer(action_string)
        if answer:
            return "", 0.0, True, {}

        # 提取工具调用
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
            import sys
            sys.stdout.flush()
            
            if isinstance(tool_call, list):
                tool_call = tool_call[0]
             
                
            tool_name = tool_call.get("name")
            args = tool_call.get("arguments", {})

            # 验证工具名称
            if tool_name != self.name:
                raise ValueError(f"Unknown tool name: '{tool_name}'. This toolbox only supports '{self.name}'.")

            # 检查是否有图像数据
            if not self.multi_modal_data or 'image' not in self.multi_modal_data or not self.multi_modal_data['image']:
                raise ValueError("No image found in the current environment state (multi_modal_data).")

            current_image = self.multi_modal_data['image'][0]
            print(f"[NAFNet DEBUG] 开始处理图像，尺寸: {current_image.size}", flush=True)
            
            # 计算输入图像的统计信息
            import numpy as np
            input_array = np.array(current_image)
            input_mean = np.mean(input_array)
            input_std = np.std(input_array)
            print(f"[NAFNet DEBUG] 输入图像统计: mean={input_mean:.2f}, std={input_std:.2f}, shape={input_array.shape}", flush=True)
            
            params = self.build_params(args)
            print(f"[NAFNet DEBUG] API参数: {params}", flush=True)
            
            restored_image = self._call_nafnet_api(current_image, params)
            print(f"[NAFNet DEBUG] API调用完成，返回图像尺寸: {restored_image.size}", flush=True)
            
            # 计算输出图像的统计信息
            output_array = np.array(restored_image)
            output_mean = np.mean(output_array)
            output_std = np.std(output_array)
            print(f"[NAFNet DEBUG] 输出图像统计: mean={output_mean:.2f}, std={output_std:.2f}, shape={output_array.shape}", flush=True)
            
            # 检查图像一致性
            size_changed = current_image.size != restored_image.size
            significant_change = abs(input_mean - output_mean) > 10 or abs(input_std - output_std) > 10
            print(f"[NAFNet DEBUG] 图像变化检查: 尺寸变化={size_changed}, 显著统计变化={significant_change}", flush=True)

            # 使用 USER_PROMPT_V1 的正确格式化方式
            formatted_prompt = self.user_prompt.format(tool_name=self.name) + ' Note that you have already used the deblurring tool and are not allowed to use it a second time.'
            
            obs = {
                "prompt": (
                    "\n<|im_start|>user\n"
                    "<tool_response><image>"
                    + formatted_prompt
                    + "</tool_response>"
                    "<|im_end|>\n<|im_start|>assistant\n"
                ),
                "multi_modal_data": {"image": [restored_image]}
            }
            end_time = time.time()
            execution_time = end_time - start_time
            print(f"[TOOL EXECUTE] ✅ {self.name} 执行成功 (耗时: {execution_time:.2f}s)")
            
            reward = 0.
            done = False
            info = {"status": "success", "tool_used": self.name, "execution_time": execution_time}
            return obs, reward, done, info

        except Exception as e:
            end_time = time.time()
            execution_time = end_time - start_time
            print(f"[TOOL EXECUTE] ❌ {self.name} 执行失败 (耗时: {execution_time:.2f}s): {str(e)}")
            
            error_obs = f"\n<|im_start|>user\nError executing {self.name}: {str(e)}<|im_end|>\n<|im_start|>assistant\n"
            reward = -0.1
            done = False
            info = {"error": str(e), "status": "failed", "execution_time": execution_time}
            return error_obs, reward, done, info
            
    def reset(self, raw_prompt, multi_modal_data, origin_multi_modal_data=None, **kwargs):
        self.chatml_history = raw_prompt
        # 使用当前处理后的图片，如果没有则使用原始图片
        self.multi_modal_data = multi_modal_data if multi_modal_data else origin_multi_modal_data
        print(f"[RESET] {self.name} reset with new image and prompt.")


# ====================== NAFNet 去模糊工具 ======================

class NAFNetDeblurToolbox(BaseNAFNetToolbox):
    """NAFNet 去模糊工具 - 运动模糊去除"""
    name = "nafnet_deblur"
    task_name = "deblur"

    def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建 NAFNet API 参数
        
        Args:
            args: 工具调用参数，可能包含:
                - format: 返回格式，默认为 base64
        
        Returns:
            NAFNet API 所需的参数字典
        """
        # 返回格式
        return_format = args.get("format", "base64")
        
        params = {
            "task": self.task_name,  # 固定为 deblur
            "format": return_format
        }
        
        print(f'[DEBUG] NAFNetDeblurToolbox build_params: {params}')
        return params


# ====================== 示例：测试自动注册和工具执行 ======================
if __name__ == "__main__":
    # --- 准备工作 ---
    import numpy as np
    from PIL import Image

    # 1. 检查工具是否已自动注册
    print("\n--- Checking Tool Registry ---")
    registered_tools = ToolBase.registry.keys()
    print(f"Available tools in registry: {list(registered_tools)}")

    assert "nafnet_deblur" in registered_tools
    print("NAFNet deblur tool successfully auto-registered.")

    # 2. 构造一张测试图片和初始数据
    test_img_array = np.random.randint(0, 200, (128, 128, 3), dtype=np.uint8)
    test_image = Image.fromarray(test_img_array)

    initial_prompt = [{"role": "user", "content": "Please deblur this image."}]
    initial_data = {"image": [test_image]}
    
    print(f"\nCreated a test image with size: {test_image.size}")

    # --- 测试 NAFNet 工具 ---

    # 1) 测试去模糊
    print("\n--- [Test 1] Testing NAFNet Deblur ---")
    try:
        nafnet_tool = ToolBase.create("nafnet_deblur")
        nafnet_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
        
        # 构造工具调用字符串
        tool_call_str = '''<tool_call>
{
    "name": "nafnet_deblur",
    "arguments": {}
}
</tool_call>'''
        
        obs, reward, done, info = nafnet_tool.execute(tool_call_str)
        
        if info.get("status") == "success":
            print("NAFNet deblur executed successfully.")
            processed_image = obs['multi_modal_data']['image'][0]
            print(f"Original size: {test_image.size} -> New size: {processed_image.size}")
        else:
            print(f"NAFNet tool failed with error: {info.get('error')}")

    except (ValueError, ConnectionError) as e:
        print(f"An error occurred: {e}")
        print(f"NOTE: This might be expected if the NAFNet API service is not running at {nafnet_tool.api_url}")

    # 2) 测试使用默认参数
    print("\n--- [Test 2] Testing NAFNet with default parameters ---")
    try:
        nafnet_tool = ToolBase.create("nafnet_deblur")
        nafnet_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
        
        # 不指定任何参数，应该使用默认值
        tool_call_str = '''<tool_call>
{
    "name": "nafnet_deblur",
    "arguments": {}
}
</tool_call>'''
        
        obs, reward, done, info = nafnet_tool.execute(tool_call_str)
        
        if info.get("status") == "success":
            print("NAFNet with default parameters executed successfully.")
            processed_image = obs['multi_modal_data']['image'][0]
            print(f"Original size: {test_image.size} -> New size: {processed_image.size}")
        else:
            print(f"NAFNet tool failed with error: {info.get('error')}")

    except (ValueError, ConnectionError) as e:
        print(f"An error occurred: {e}")

    print("\n--- All tests completed ---")

