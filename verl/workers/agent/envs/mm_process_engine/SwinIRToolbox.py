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

# ====================== 公共基类 (已修改) ======================
class BaseSwinIRToolbox(ToolBase):
    """
    把公共逻辑抽到基类。
    这个基类本身不应该是一个可执行的工具。
    """
    # We give it a placeholder name to satisfy the ToolBase requirement,
    # but it won't be registered as a usable tool.
    name = "base_swinir_toolbox" 
    
    # These will be overridden by subclasses
    task_name: str = ""
    
    user_prompt = PROMPT.USER_PROMPT_V1
    # 从环境变量读取IP地址，保留端口号5001
    api_url = f"http://{os.environ.get('TOOL_SERVICE_IP', '10.21.9.34')}:5001/process"

    def __init__(self, _name, _desc, _params, **kwargs):
        # The 'name' is now a class attribute, so we don't need to pass it here.
        super().__init__(name=self.name,**kwargs) 
        self.chatml_history = []
        self.multi_modal_data = None
        print(f"SwinIRToolbox initialized. API endpoint: {self.api_url}")

    # ... (the rest of your BaseSwinIRToolbox methods like _call_swinir_api, build_params, etc., remain the same) ...
    # ... Make sure the `execute` method uses self.name when referring to the tool's name ...

    def _call_swinir_api(self, image: Image.Image, task_params: Dict[str, Any]) -> Image.Image:
        print(f"[SWINIR API] 🚀 开始调用API: {self.api_url}", flush=True)
        print(f"[SWINIR API] 任务参数: {task_params}", flush=True)
        
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        image_bytes = buf.getvalue()
        files = {'image': ('image.png', image_bytes, 'image/png')}
        
        try:
            print(f"[SWINIR API] 发送POST请求...", flush=True)
            resp = requests.post(self.api_url, files=files, data=task_params, timeout=300)
            print(f"[SWINIR API] 收到响应，状态码: {resp.status_code}", flush=True)
            
            resp.raise_for_status()
            result = resp.json()
            print(f"[SWINIR API] JSON响应: success={result.get('success')}", flush=True)
            
            if result.get('success'):
                img_b64 = result['image']
                img_bytes = base64.b64decode(img_b64)
                restored_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                self.multi_modal_data['image'][0] = restored_image
                print(f"[SWINIR API] ✅ API调用成功，图像处理完成", flush=True)
                return restored_image
            else:
                error_msg = result.get('error','Unknown API error')
                print(f"[SWINIR API] ❌ API返回错误: {error_msg}", flush=True)
                raise RuntimeError(f"SwinIR API error: {error_msg}")
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if "503" in error_msg and "SERVICE UNAVAILABLE" in error_msg:
                raise ConnectionError(f"SwinIR service is temporarily unavailable (likely due to GPU memory shortage). Please try again later or contact administrator. Error: {e}")
            else:
                raise ConnectionError(f"Failed to connect to SwinIR API at {self.api_url}. Error: {e}")
            
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
            # print(f"[SWINIR EXECUTE] 🎯 开始处理工具调用", flush=True)
            # print(f"[SWINIR EXECUTE] tool_call类型: {type(tool_call)}, 内容: {tool_call}", flush=True)
            sys.stdout.flush()
            
            if isinstance(tool_call, list):
                tool_call = tool_call[0]
             
                
            tool_name = tool_call.get("name")
            args = tool_call.get("arguments", {})
            # print(f"[SWINIR EXECUTE] 解析结果 - 工具名: {tool_name}, 参数: {args}", flush=True)

            # 验证工具名称
            if tool_name != self.name:
                raise ValueError(f"Unknown tool name: '{tool_name}'. This toolbox only supports '{self.name}'.")

            # 检查是否有图像数据
            if not self.multi_modal_data or 'image' not in self.multi_modal_data or not self.multi_modal_data['image']:
                raise ValueError("No image found in the current environment state (multi_modal_data).")

            current_image = self.multi_modal_data['image'][0]
            print(f"[SWINIR DEBUG] 开始处理图像，尺寸: {current_image.size}", flush=True)
            
            # 计算输入图像的统计信息
            import numpy as np
            input_array = np.array(current_image)
            input_mean = np.mean(input_array)
            input_std = np.std(input_array)
            print(f"[SWINIR DEBUG] 输入图像统计: mean={input_mean:.2f}, std={input_std:.2f}, shape={input_array.shape}", flush=True)
            
            params = self.build_params(args)
            print(f"[SWINIR DEBUG] API参数: {params}", flush=True)
            
            restored_image = self._call_swinir_api(current_image, params)
            print(f"[SWINIR DEBUG] API调用完成，返回图像尺寸: {restored_image.size}", flush=True)
            
            # 计算输出图像的统计信息
            output_array = np.array(restored_image)
            output_mean = np.mean(output_array)
            output_std = np.std(output_array)
            print(f"[SWINIR DEBUG] 输出图像统计: mean={output_mean:.2f}, std={output_std:.2f}, shape={output_array.shape}", flush=True)
            
            # 检查图像一致性
            size_changed = current_image.size != restored_image.size
            significant_change = abs(input_mean - output_mean) > 10 or abs(input_std - output_std) > 10
            print(f"[SWINIR DEBUG] 图像变化检查: 尺寸变化={size_changed}, 显著统计变化={significant_change}", flush=True)

            # 使用 USER_PROMPT_V1 的正确格式化方式
            formatted_prompt = self.user_prompt.format(tool_name=self.name) + ' Note that you have already used the super-resolution tool and are not allowed to use it a second time.'
            
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


# ====================== 三个独立工具 (已修改) ======================

class SwinIRDenoisingToolbox(BaseSwinIRToolbox):
    name = "swinir_denoising"
    task_name = "denoising"

    def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        # 支持多种参数名称以保持兼容性
        # noise = int(args.get("strength", args.get("noise", 25)))
        noise = 25
        print(f'[DEBUG] SwinIRDenoisingToolbox build_params: {noise}')
        return {"task": self.task_name, "noise": noise}


class SwinIRJpegArtifactRemovalToolbox(BaseSwinIRToolbox):
    name = "swinir_jpeg_artifact_removal"
    task_name = "jpeg_compression_artifact_removal"

    def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        # 支持多种参数名称以保持兼容性
        # jpeg_q = int(args.get("strength", args.get("jpeg", 30)))
        jpeg_q = 30
        print(f'[DEBUG] SwinIRJpegArtifactRemovalToolbox build_params: {jpeg_q}')
        return {"task": self.task_name, "jpeg": jpeg_q}


class SwinIRSrToolbox(BaseSwinIRToolbox):
    name = "swinir_super_resolution"
    task_name = "super_resolution"

    def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        # scale = int(args.get("scale", 4))
        scale = 2
        print(f'[DEBUG] SwinIRSrToolbox build_params: {scale}')
        return {"task": self.task_name, "scale": scale}

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

    assert "swinir_denoising" in registered_tools
    assert "swinir_jpeg_artifact_removal" in registered_tools
    assert "swinir_super_resolution" in registered_tools
    print("All SwinIR tools successfully auto-registered.")

    # 2. 构造一张测试图片和初始数据
    test_img_array = np.random.randint(0, 200, (128, 128, 3), dtype=np.uint8)
    test_image = Image.fromarray(test_img_array)

    initial_prompt = [{"role": "user", "content": "Please enhance this image."}]
    initial_data = {"image": [test_image]}
    
    print(f"\nCreated a test image with size: {test_image.size}")

    # --- 测试每个工具 ---

    # 1) 测试去噪工具
    print("\n--- [Test 1] Testing Denoising Tool ---")
    try:
        # 使用 ToolBase.create() 工厂方法创建工具实例
        denoise_tool = ToolBase.create("swinir_denoising")
        
        # 调用 reset 初始化工具状态
        denoise_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
        
        # 准备参数字典，就像 parallel_env.py 做的那样
        denoising_args = {"noise": 30}
        
        # 调用 execute 执行工具
        obs, reward, done, info = denoise_tool.execute(denoising_args)
        
        if info.get("status") == "success":
            print("Denoising tool executed successfully.")
            # 检查返回的图像
            processed_image = obs['multi_modal_data']['image'][0]
            print(f"Returned image size: {processed_image.size}")
        else:
            print(f"Denoising tool failed with error: {info.get('error')}")

    except (ValueError, ConnectionError) as e:
        print(f"An error occurred: {e}")
        print("NOTE: This might be expected if the SwinIR API service is not running at http://127.0.0.1:5000")

    # 2) 测试 JPEG 伪影去除工具
    print("\n--- [Test 2] Testing JPEG Artifact Removal Tool ---")
    try:
        jpeg_tool = ToolBase.create("swinir_jpeg_artifact_removal")
        jpeg_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
        jpeg_args = {"jpeg": 40}
        obs, reward, done, info = jpeg_tool.execute(jpeg_args)

        if info.get("status") == "success":
            print("JPEG artifact removal tool executed successfully.")
        else:
            print(f"JPEG tool failed with error: {info.get('error')}")
            
    except (ValueError, ConnectionError) as e:
        print(f"An error occurred: {e}")

    # 3) 测试超分工具
    print("\n--- [Test 3] Testing Super Resolution Tool ---")
    try:
        sr_tool = ToolBase.create("swinir_super_resolution")
        sr_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
        sr_args = {"scale": 4}
        obs, reward, done, info = sr_tool.execute(sr_args)

        if info.get("status") == "success":
            print("Super resolution tool executed successfully.")
            processed_image = obs['multi_modal_data']['image'][0]
            print(f"Original size: {test_image.size} -> New size: {processed_image.size}")
            assert processed_image.size == (test_image.width * 4, test_image.height * 4)
        else:
            print(f"SR tool failed with error: {info.get('error')}")

    except (ValueError, ConnectionError) as e:
        print(f"An error occurred: {e}")

    # 4) 测试一个不存在的工具，确保它能正确报错
    print("\n--- [Test 4] Testing a non-existent tool ---")
    try:
        fake_tool = ToolBase.create("a_tool_that_does_not_exist")
    except ValueError as e:
        print(f"Correctly caught expected error: {e}")