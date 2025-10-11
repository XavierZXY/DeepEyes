import numpy as np
import requests
import base64
import io
import json
import re
from typing import Dict, Any, Union
from PIL import Image

# Assuming ToolBase and PROMPT are correctly imported from your framework
from ...tool_envs import ToolBase
from .IRprompt import PROMPT

# ====================== 公共基类 ======================
class BaseRestormerToolbox(ToolBase):
    """
    Restormer工具箱基类，提供公共逻辑。
    这个基类本身不应该是一个可执行的工具。
    """
    # We give it a placeholder name to satisfy the ToolBase requirement,
    # but it won't be registered as a usable tool.
    name = "base_restormer_toolbox" 
    
    # These will be overridden by subclasses
    task_name: str = ""
    
    user_prompt = PROMPT.USER_PROMPT_V1
    api_url = "http://10.21.9.34:5006/process"

    def __init__(self, _name, _desc, _params, **kwargs):
        # The 'name' is now a class attribute, so we don't need to pass it here.
        super().__init__(name=self.name,**kwargs) 
        self.chatml_history = []
        self.multi_modal_data = None
        print(f"RestormerToolbox initialized. API endpoint: {self.api_url}")

    def _call_restormer_api(self, image: Image.Image, task_params: Dict[str, Any]) -> Image.Image:
        print(f"[RESTORMER API] 🚀 开始调用API: {self.api_url}", flush=True)
        print(f"[RESTORMER API] 任务参数: {task_params}", flush=True)
        
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        image_bytes = buf.getvalue()
        files = {'image': ('image.png', image_bytes, 'image/png')}
        
        try:
            print(f"[RESTORMER API] 发送POST请求...", flush=True)
            resp = requests.post(self.api_url, files=files, data=task_params, timeout=300)
            print(f"[RESTORMER API] 收到响应，状态码: {resp.status_code}", flush=True)
            
            resp.raise_for_status()
            result = resp.json()
            print(f"[RESTORMER API] JSON响应: success={result.get('success')}", flush=True)
            
            if result.get('success'):
                img_b64 = result['image']
                img_bytes = base64.b64decode(img_b64)
                restored_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                self.multi_modal_data['image'][0] = restored_image
                print(f"[RESTORMER API] ✅ API调用成功，图像处理完成", flush=True)
                return restored_image
            else:
                error_msg = result.get('error','Unknown API error')
                print(f"[RESTORMER API] ❌ API返回错误: {error_msg}", flush=True)
                raise RuntimeError(f"Restormer API error: {error_msg}")
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if "503" in error_msg and "SERVICE UNAVAILABLE" in error_msg:
                raise ConnectionError(f"Restormer service is temporarily unavailable (likely due to GPU memory shortage). Please try again later or contact administrator. Error: {e}")
            else:
                raise ConnectionError(f"Failed to connect to Restormer API at {self.api_url}. Error: {e}")
            
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
            print(f"[RESTORMER DEBUG] 开始处理图像，尺寸: {current_image.size}", flush=True)
            
            # 计算输入图像的统计信息
            import numpy as np
            input_array = np.array(current_image)
            input_mean = np.mean(input_array)
            input_std = np.std(input_array)
            print(f"[RESTORMER DEBUG] 输入图像统计: mean={input_mean:.2f}, std={input_std:.2f}, shape={input_array.shape}", flush=True)
            
            params = self.build_params(args)
            print(f"[RESTORMER DEBUG] API参数: {params}", flush=True)
            
            restored_image = self._call_restormer_api(current_image, params)
            print(f"[RESTORMER DEBUG] API调用完成，返回图像尺寸: {restored_image.size}", flush=True)
            
            # 计算输出图像的统计信息
            output_array = np.array(restored_image)
            output_mean = np.mean(output_array)
            output_std = np.std(output_array)
            print(f"[RESTORMER DEBUG] 输出图像统计: mean={output_mean:.2f}, std={output_std:.2f}, shape={output_array.shape}", flush=True)
            
            # 检查图像一致性
            size_changed = current_image.size != restored_image.size
            significant_change = abs(input_mean - output_mean) > 10 or abs(input_std - output_std) > 10
            print(f"[RESTORMER DEBUG] 图像变化检查: 尺寸变化={size_changed}, 显著统计变化={significant_change}", flush=True)

            # 使用 USER_PROMPT_V1 的正确格式化方式
            formatted_prompt = self.user_prompt.format(tool_name=self.name) 
            # + ' Note that you have already used the restoration tool and are not allowed to use it a second time.'
            
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


# ====================== 三个独立工具 ======================

class RestormerMotionDeblurringToolbox(BaseRestormerToolbox):
    name = "restormer_motion_deblurring"
    task_name = "motion_deblurring"

    def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        # Restormer 不需要额外参数，只需要指定任务类型
        print(f'[DEBUG] RestormerMotionDeblurringToolbox build_params: task={self.task_name}')
        return {"task": self.task_name}


class RestormerDefocusDeblurringToolbox(BaseRestormerToolbox):
    name = "restormer_defocus_deblurring"
    task_name = "defocus_deblurring"

    def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        # Restormer 不需要额外参数，只需要指定任务类型
        print(f'[DEBUG] RestormerDefocusDeblurringToolbox build_params: task={self.task_name}')
        return {"task": self.task_name}


class RestormerDerrainingToolbox(BaseRestormerToolbox):
    name = "restormer_deraining"
    task_name = "deraining"

    def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        # Restormer 不需要额外参数，只需要指定任务类型
        print(f'[DEBUG] RestormerDerrainingToolbox build_params: task={self.task_name}')
        return {"task": self.task_name}


# ====================== 示例：测试自动注册和工具执行 ======================
if __name__ == "__main__":
    # --- 准备工作 ---
    import numpy as np
    from PIL import Image

    # 1. 检查工具是否已自动注册
    print("\n--- Checking Tool Registry ---")
    # 因为 ToolBase 使用了 __init_subclass__，只要类被定义，它们就应该在注册表里
    # 注意：这里我们直接访问 ToolBase.registry 字典来检查，这在测试中是合理的
    registered_tools = ToolBase.registry.keys()
    print(f"Available tools in registry: {list(registered_tools)}")

    assert "restormer_motion_deblurring" in registered_tools
    assert "restormer_defocus_deblurring" in registered_tools
    assert "restormer_deraining" in registered_tools
    print("All Restormer tools successfully auto-registered.")

    # 2. 构造一张测试图片和初始数据
    test_img_array = np.random.randint(0, 200, (128, 128, 3), dtype=np.uint8)
    test_image = Image.fromarray(test_img_array)

    initial_prompt = [{"role": "user", "content": "Please enhance this image."}]
    initial_data = {"image": [test_image]}
    
    print(f"\nCreated a test image with size: {test_image.size}")

    # --- 测试每个工具 ---

    # 1) 测试运动去模糊工具
    print("\n--- [Test 1] Testing Motion Deblurring Tool ---")
    try:
        # 使用 ToolBase.create() 工厂方法创建工具实例
        motion_deblur_tool = ToolBase.create("restormer_motion_deblurring")
        
        # 调用 reset 初始化工具状态
        motion_deblur_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
        
        # 准备参数字典
        motion_deblur_args = {}
        
        # 模拟完整的 action_string
        action_string = f'<tool_call>{{"name": "restormer_motion_deblurring", "arguments": {json.dumps(motion_deblur_args)}}}</tool_call>'
        
        # 调用 execute 执行工具
        obs, reward, done, info = motion_deblur_tool.execute(action_string)
        
        if info.get("status") == "success":
            print("Motion deblurring tool executed successfully.")
            # 检查返回的图像
            processed_image = obs['multi_modal_data']['image'][0]
            print(f"Returned image size: {processed_image.size}")
        else:
            print(f"Motion deblurring tool failed with error: {info.get('error')}")

    except (ValueError, ConnectionError) as e:
        print(f"An error occurred: {e}")
        print("NOTE: This might be expected if the Restormer API service is not running at http://172.18.148.193:5006")

    # 2) 测试散焦去模糊工具
    print("\n--- [Test 2] Testing Defocus Deblurring Tool ---")
    try:
        defocus_tool = ToolBase.create("restormer_defocus_deblurring")
        defocus_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
        
        defocus_args = {}
        action_string = f'<tool_call>{{"name": "restormer_defocus_deblurring", "arguments": {json.dumps(defocus_args)}}}</tool_call>'
        
        obs, reward, done, info = defocus_tool.execute(action_string)

        if info.get("status") == "success":
            print("Defocus deblurring tool executed successfully.")
        else:
            print(f"Defocus deblurring tool failed with error: {info.get('error')}")
            
    except (ValueError, ConnectionError) as e:
        print(f"An error occurred: {e}")

    # 3) 测试去雨工具
    print("\n--- [Test 3] Testing Deraining Tool ---")
    try:
        derain_tool = ToolBase.create("restormer_deraining")
        derain_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
        
        derain_args = {}
        action_string = f'<tool_call>{{"name": "restormer_deraining", "arguments": {json.dumps(derain_args)}}}</tool_call>'
        
        obs, reward, done, info = derain_tool.execute(action_string)

        if info.get("status") == "success":
            print("Deraining tool executed successfully.")
        else:
            print(f"Deraining tool failed with error: {info.get('error')}")

    except (ValueError, ConnectionError) as e:
        print(f"An error occurred: {e}")

    # 4) 测试一个不存在的工具，确保它能正确报错
    print("\n--- [Test 4] Testing a non-existent tool ---")
    try:
        fake_tool = ToolBase.create("a_tool_that_does_not_exist")
    except ValueError as e:
        print(f"Correctly caught expected error: {e}")

