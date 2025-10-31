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
from .tool_load_balancer import get_tool_service_ip


# ====================== 公共基类 ======================
class BaseSCUNetToolbox(ToolBase):
    """
    SCUNet 工具基类，处理公共逻辑。
    这个基类本身不应该是一个可执行的工具。
    """
    # Placeholder name to satisfy the ToolBase requirement
    name = "base_scunet_toolbox"
    
    # These will be overridden by subclasses
    task_name: str = ""
    
    user_prompt = PROMPT.USER_PROMPT_V1
    # 从环境变量读取IP地址，端口号5008
    
    @property
    def api_url(self):
        """动态获取API URL，支持负载均衡"""
        ip = get_tool_service_ip()
        return f"http://{ip}:5008/process"

    def __init__(self, _name, _desc, _params, **kwargs):
        # The 'name' is now a class attribute, so we don't need to pass it here.
        super().__init__(name=self.name, **kwargs)
        self.chatml_history = []
        self.multi_modal_data = None
        print(f"SCUNetToolbox initialized. API endpoint: {self.api_url}")

    def _call_scunet_api(self, image: Image.Image, task_params: Dict[str, Any]) -> Image.Image:
        """调用 SCUNet API 进行图像去噪"""
        print(f"[SCUNET API] 🚀 开始调用API: {self.api_url}", flush=True)
        print(f"[SCUNET API] 任务参数: {task_params}", flush=True)
        
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        image_bytes = buf.getvalue()
        files = {'image': ('image.png', image_bytes, 'image/png')}
        
        try:
            print(f"[SCUNET API] 发送POST请求...", flush=True)
            resp = requests.post(self.api_url, files=files, data=task_params, timeout=300)
            print(f"[SCUNET API] 收到响应，状态码: {resp.status_code}", flush=True)
            
            resp.raise_for_status()
            result = resp.json()
            print(f"[SCUNET API] JSON响应: success={result.get('success')}", flush=True)
            
            if result.get('success'):
                img_b64 = result['image']
                img_bytes = base64.b64decode(img_b64)
                denoised_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                self.multi_modal_data['image'][0] = denoised_image
                print(f"[SCUNET API] ✅ API调用成功，图像处理完成", flush=True)
                return denoised_image
            else:
                error_msg = result.get('error', 'Unknown API error')
                print(f"[SCUNET API] ❌ API返回错误: {error_msg}", flush=True)
                raise RuntimeError(f"SCUNet API error: {error_msg}")
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if "503" in error_msg and "SERVICE UNAVAILABLE" in error_msg:
                raise ConnectionError(f"SCUNet service is temporarily unavailable (likely due to GPU memory shortage). Please try again later or contact administrator. Error: {e}")
            elif "408" in error_msg or "timeout" in error_msg.lower():
                raise ConnectionError(f"SCUNet service timeout (GPU queue might be full). Please try again later. Error: {e}")
            else:
                raise ConnectionError(f"Failed to connect to SCUNet API at {self.api_url}. Error: {e}")
            
    def extract_answer(self, action_string: str) -> Union[str, None]:
        """从模型的输出中提取 <answer> 标签内的最终答案。"""
        answer_match = re.search(r'<answer>(.*?)</answer>', action_string, re.DOTALL)
        return answer_match.group(1) if answer_match else None

    def extract_action(self, action_string: str) -> Union[str, None]:
        """从模型的输出中提取 <tool_call> 标签内的工具调用指令。"""
        tool_call_match = re.search(r'<tool_call>(.*?)</tool_call>', action_string, re.DOTALL)
        return tool_call_match.group(1) if tool_call_match else None

    def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """构建 API 请求参数，子类需要实现"""
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
            print(f"[SCUNET DEBUG] 开始处理图像，尺寸: {current_image.size}", flush=True)
            
            # 计算输入图像的统计信息
            import numpy as np
            input_array = np.array(current_image)
            input_mean = np.mean(input_array)
            input_std = np.std(input_array)
            print(f"[SCUNET DEBUG] 输入图像统计: mean={input_mean:.2f}, std={input_std:.2f}, shape={input_array.shape}", flush=True)
            
            params = self.build_params(args)
            print(f"[SCUNET DEBUG] API参数: {params}", flush=True)
            
            denoised_image = self._call_scunet_api(current_image, params)
            print(f"[SCUNET DEBUG] API调用完成，返回图像尺寸: {denoised_image.size}", flush=True)
            
            # 计算输出图像的统计信息
            output_array = np.array(denoised_image)
            output_mean = np.mean(output_array)
            output_std = np.std(output_array)
            print(f"[SCUNET DEBUG] 输出图像统计: mean={output_mean:.2f}, std={output_std:.2f}, shape={output_array.shape}", flush=True)
            
            # 检查图像一致性
            size_changed = current_image.size != denoised_image.size
            significant_change = abs(input_mean - output_mean) > 10 or abs(input_std - output_std) > 10
            print(f"[SCUNET DEBUG] 图像变化检查: 尺寸变化={size_changed}, 显著统计变化={significant_change}", flush=True)

            # 使用 USER_PROMPT_V1 的正确格式化方式
            formatted_prompt = self.user_prompt.format(tool_name=self.name) + ' Note that you have already used the denoising tool and are not allowed to use it a second time.'
            
            obs = {
                "prompt": (
                    "\n<|im_start|>user\n"
                    "<tool_response><image>"
                    + formatted_prompt
                    + "</tool_response>"
                    "<|im_end|>\n<|im_start|>assistant\n"
                ),
                "multi_modal_data": {"image": [denoised_image]}
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
        """重置工具状态"""
        self.chatml_history = raw_prompt
        # 使用当前处理后的图片，如果没有则使用原始图片
        self.multi_modal_data = multi_modal_data if multi_modal_data else origin_multi_modal_data
        print(f"[RESET] {self.name} reset with new image and prompt.")


# ====================== SCUNet 工具类 ======================

class SCUNetRealDenoisingPSNRToolbox(BaseSCUNetToolbox):
    """真实图像去噪工具（PSNR优化版本）- 适用于真实世界的噪声图像"""
    name = "scunet_real_denoising_psnr"
    task_name = "real_denoising_psnr"

    def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建真实图像去噪参数
        这个模型专门针对真实世界的噪声进行优化，PSNR优化版本
        """
        print(f'[DEBUG] SCUNetRealDenoisingPSNRToolbox build_params')
        return {
            "task": self.task_name,
            "format": "base64"
        }


class SCUNetRealDenoisingGANToolbox(BaseSCUNetToolbox):
    """真实图像去噪工具（GAN版本）- 视觉效果更好，适用于真实世界的噪声图像"""
    name = "scunet_real_denoising_gan"
    task_name = "real_denoising_gan"

    def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建真实图像去噪参数
        这个模型专门针对真实世界的噪声进行优化，GAN版本视觉效果更好
        """
        print(f'[DEBUG] SCUNetRealDenoisingGANToolbox build_params')
        return {
            "task": self.task_name,
            "format": "base64"
        }


class SCUNetColorDenoisingToolbox(BaseSCUNetToolbox):
    """彩色图像去噪工具 - 支持不同噪声等级（15/25/50）"""
    name = "scunet_color_denoising"
    task_name = "color_denoising_25"  # 默认使用25级噪声

    def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建彩色图像去噪参数
        支持的噪声等级：15, 25, 50
        """
        # 从参数中获取噪声等级，默认为25
        noise_level = args.get("noise_level", 25)
        
        # 确保噪声等级在支持的范围内
        if noise_level not in [15, 25, 50]:
            print(f"[WARNING] Unsupported noise level {noise_level}, defaulting to 25")
            noise_level = 25
        
        task = f"color_denoising_{noise_level}"
        print(f'[DEBUG] SCUNetColorDenoisingToolbox build_params: noise_level={noise_level}, task={task}')
        
        return {
            "task": task,
            "format": "base64"
        }


class SCUNetGrayDenoisingToolbox(BaseSCUNetToolbox):
    """灰度图像去噪工具 - 支持不同噪声等级（15/25/50）"""
    name = "scunet_gray_denoising"
    task_name = "gray_denoising_25"  # 默认使用25级噪声

    def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建灰度图像去噪参数
        支持的噪声等级：15, 25, 50
        """
        # 从参数中获取噪声等级，默认为25
        noise_level = args.get("noise_level", 25)
        
        # 确保噪声等级在支持的范围内
        if noise_level not in [15, 25, 50]:
            print(f"[WARNING] Unsupported noise level {noise_level}, defaulting to 25")
            noise_level = 25
        
        task = f"gray_denoising_{noise_level}"
        print(f'[DEBUG] SCUNetGrayDenoisingToolbox build_params: noise_level={noise_level}, task={task}')
        
        return {
            "task": task,
            "format": "base64"
        }


# ====================== 示例：测试自动注册和工具执行 ======================
if __name__ == "__main__":
    # --- 准备工作 ---
    import numpy as np
    from PIL import Image

    # 1. 检查工具是否已自动注册
    print("\n--- Checking Tool Registry ---")
    # 因为 ToolBase 使用了 __init_subclass__，只要类被定义，它们就应该在注册表里
    registered_tools = ToolBase.registry.keys()
    print(f"Available tools in registry: {list(registered_tools)}")

    assert "scunet_real_denoising_psnr" in registered_tools
    assert "scunet_real_denoising_gan" in registered_tools
    assert "scunet_color_denoising" in registered_tools
    assert "scunet_gray_denoising" in registered_tools
    print("All SCUNet tools successfully auto-registered.")

    # 2. 构造一张测试图片和初始数据
    test_img_array = np.random.randint(0, 200, (128, 128, 3), dtype=np.uint8)
    test_image = Image.fromarray(test_img_array)

    initial_prompt = [{"role": "user", "content": "Please denoise this image."}]
    initial_data = {"image": [test_image]}
    
    print(f"\nCreated a test image with size: {test_image.size}")

    # --- 测试每个工具 ---

    # 1) 测试真实图像去噪工具（PSNR）
    print("\n--- [Test 1] Testing Real Denoising (PSNR) Tool ---")
    try:
        # 使用 ToolBase.create() 工厂方法创建工具实例
        real_psnr_tool = ToolBase.create("scunet_real_denoising_psnr")
        
        # 调用 reset 初始化工具状态
        real_psnr_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
        
        # 准备工具调用字符串
        action_string = """
<tool_call>
{"name": "scunet_real_denoising_psnr", "arguments": {}}
</tool_call>
"""
        
        # 调用 execute 执行工具
        obs, reward, done, info = real_psnr_tool.execute(action_string)
        
        if info.get("status") == "success":
            print("Real denoising (PSNR) tool executed successfully.")
            # 检查返回的图像
            processed_image = obs['multi_modal_data']['image'][0]
            print(f"Returned image size: {processed_image.size}")
        else:
            print(f"Real denoising (PSNR) tool failed with error: {info.get('error')}")

    except (ValueError, ConnectionError) as e:
        print(f"An error occurred: {e}")
        print("NOTE: This might be expected if the SCUNet API service is not running")

    # 2) 测试真实图像去噪工具（GAN）
    print("\n--- [Test 2] Testing Real Denoising (GAN) Tool ---")
    try:
        real_gan_tool = ToolBase.create("scunet_real_denoising_gan")
        real_gan_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
        
        action_string = """
<tool_call>
{"name": "scunet_real_denoising_gan", "arguments": {}}
</tool_call>
"""
        
        obs, reward, done, info = real_gan_tool.execute(action_string)

        if info.get("status") == "success":
            print("Real denoising (GAN) tool executed successfully.")
        else:
            print(f"Real denoising (GAN) tool failed with error: {info.get('error')}")
            
    except (ValueError, ConnectionError) as e:
        print(f"An error occurred: {e}")

    # 3) 测试彩色图像去噪工具
    print("\n--- [Test 3] Testing Color Denoising Tool ---")
    try:
        color_tool = ToolBase.create("scunet_color_denoising")
        color_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
        
        action_string = """
<tool_call>
{"name": "scunet_color_denoising", "arguments": {"noise_level": 25}}
</tool_call>
"""
        
        obs, reward, done, info = color_tool.execute(action_string)

        if info.get("status") == "success":
            print("Color denoising tool executed successfully.")
            processed_image = obs['multi_modal_data']['image'][0]
            print(f"Original size: {test_image.size} -> New size: {processed_image.size}")
        else:
            print(f"Color denoising tool failed with error: {info.get('error')}")

    except (ValueError, ConnectionError) as e:
        print(f"An error occurred: {e}")

    # 4) 测试灰度图像去噪工具
    print("\n--- [Test 4] Testing Gray Denoising Tool ---")
    try:
        gray_tool = ToolBase.create("scunet_gray_denoising")
        gray_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
        
        action_string = """
<tool_call>
{"name": "scunet_gray_denoising", "arguments": {"noise_level": 50}}
</tool_call>
"""
        
        obs, reward, done, info = gray_tool.execute(action_string)

        if info.get("status") == "success":
            print("Gray denoising tool executed successfully.")
        else:
            print(f"Gray denoising tool failed with error: {info.get('error')}")

    except (ValueError, ConnectionError) as e:
        print(f"An error occurred: {e}")

    # 5) 测试一个不存在的工具，确保它能正确报错
    print("\n--- [Test 5] Testing a non-existent tool ---")
    try:
        fake_tool = ToolBase.create("a_tool_that_does_not_exist")
    except ValueError as e:
        print(f"Correctly caught expected error: {e}")

