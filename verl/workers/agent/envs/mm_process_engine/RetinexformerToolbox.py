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

# ====================== 基础类 ======================
class BaseRetinexformerToolbox(ToolBase):
    """
    Retinexformer低光图像增强工具基类
    支持多个预训练模型用于不同场景的低光增强
    """
    name = "base_retinexformer_toolbox"
    
    # 任务名称 - 子类会覆盖
    task_name: str = ""
    
    user_prompt = PROMPT.USER_PROMPT_V1
    # 从环境变量读取IP地址，端口号5009
    
    @property
    def api_url(self):
        """动态获取API URL，支持负载均衡"""
        ip = get_tool_service_ip()
        return f"http://{ip}:5009/process"

    def __init__(self, _name, _desc, _params, **kwargs):
        super().__init__(name=self.name, **kwargs) 
        self.chatml_history = []
        self.multi_modal_data = None
        print(f"RetinexformerToolbox initialized. API endpoint: {self.api_url}")

    def _call_retinexformer_api(self, image: Image.Image, task_params: Dict[str, Any]) -> Image.Image:
        """调用Retinexformer API进行低光图像增强"""
        print(f"[RETINEXFORMER API] 🚀 开始调用API: {self.api_url}", flush=True)
        print(f"[RETINEXFORMER API] 任务参数: {task_params}", flush=True)
        
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        image_bytes = buf.getvalue()
        files = {'image': ('image.png', image_bytes, 'image/png')}
        
        try:
            print(f"[RETINEXFORMER API] 发送POST请求...", flush=True)
            resp = requests.post(self.api_url, files=files, data=task_params, timeout=300)
            print(f"[RETINEXFORMER API] 收到响应，状态码: {resp.status_code}", flush=True)
            
            resp.raise_for_status()
            result = resp.json()
            print(f"[RETINEXFORMER API] JSON响应: success={result.get('success')}", flush=True)
            
            if result.get('success'):
                img_b64 = result['image']
                img_bytes = base64.b64decode(img_b64)
                enhanced_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                self.multi_modal_data['image'][0] = enhanced_image
                print(f"[RETINEXFORMER API] ✅ API调用成功，图像增强完成", flush=True)
                return enhanced_image
            else:
                error_msg = result.get('error', 'Unknown API error')
                print(f"[RETINEXFORMER API] ❌ API返回错误: {error_msg}", flush=True)
                raise RuntimeError(f"Retinexformer API error: {error_msg}")
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if "503" in error_msg and "SERVICE UNAVAILABLE" in error_msg:
                raise ConnectionError(f"Retinexformer service is temporarily unavailable (likely due to GPU memory shortage). Please try again later or contact administrator. Error: {e}")
            elif "408" in error_msg or "timeout" in error_msg.lower():
                raise ConnectionError(f"Retinexformer service timeout (server queue might be full). Please try again later. Error: {e}")
            else:
                raise ConnectionError(f"Failed to connect to Retinexformer API at {self.api_url}. Error: {e}")
            
    def extract_answer(self, action_string: str) -> Union[str, None]:
        """从模型的输出中提取 <answer> 标签内的最终答案"""
        answer_match = re.search(r'<answer>(.*?)</answer>', action_string, re.DOTALL)
        return answer_match.group(1) if answer_match else None

    def extract_action(self, action_string: str) -> Union[str, None]:
        """从模型的输出中提取 <tool_call> 标签内的工具调用指令"""
        tool_call_match = re.search(r'<tool_call>(.*?)</tool_call>', action_string, re.DOTALL)
        return tool_call_match.group(1) if tool_call_match else None

    def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """构建API参数 - 子类需要实现"""
        raise NotImplementedError

    def execute(self, action_string: str, **kwargs) -> tuple:
        """
        执行工具调用

        Args:
            action_string: 包含 <tool_call> 或 <answer> 的模型输出字符串

        Returns:
            一个元组 (observation, reward, done, info)
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
            print(f"[RETINEXFORMER DEBUG] 开始处理图像，尺寸: {current_image.size}", flush=True)
            
            # 计算输入图像的统计信息
            import numpy as np
            input_array = np.array(current_image)
            input_mean = np.mean(input_array)
            input_std = np.std(input_array)
            print(f"[RETINEXFORMER DEBUG] 输入图像统计: mean={input_mean:.2f}, std={input_std:.2f}, shape={input_array.shape}", flush=True)
            
            params = self.build_params(args)
            print(f"[RETINEXFORMER DEBUG] API参数: {params}", flush=True)
            
            enhanced_image = self._call_retinexformer_api(current_image, params)
            print(f"[RETINEXFORMER DEBUG] API调用完成，返回图像尺寸: {enhanced_image.size}", flush=True)
            
            # 计算输出图像的统计信息
            output_array = np.array(enhanced_image)
            output_mean = np.mean(output_array)
            output_std = np.std(output_array)
            print(f"[RETINEXFORMER DEBUG] 输出图像统计: mean={output_mean:.2f}, std={output_std:.2f}, shape={output_array.shape}", flush=True)
            
            # 检查图像一致性
            size_changed = current_image.size != enhanced_image.size
            significant_change = abs(input_mean - output_mean) > 10 or abs(input_std - output_std) > 10
            print(f"[RETINEXFORMER DEBUG] 图像变化检查: 尺寸变化={size_changed}, 显著统计变化={significant_change}", flush=True)

            # 使用 USER_PROMPT_V1 的正确格式化方式
            formatted_prompt = self.user_prompt.format(tool_name=self.name) + ' Note that you have already used the low-light enhancement tool and are not allowed to use it a second time.'
            
            obs = {
                "prompt": (
                    "\n<|im_start|>user\n"
                    "<tool_response><image>"
                    + formatted_prompt
                    + "</tool_response>"
                    "<|im_end|>\n<|im_start|>assistant\n"
                ),
                "multi_modal_data": {"image": [enhanced_image]}
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


# ====================== 具体工具类 ======================

class RetinexformerLOLv1Toolbox(BaseRetinexformerToolbox):
    """LOL-v1数据集训练的低光增强模型"""
    name = "retinexformer_lol_v1"
    task_name = "LOL_v1"

    def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        print(f'[DEBUG] RetinexformerLOLv1Toolbox build_params')
        return {"task": self.task_name, "format": "base64"}


class RetinexformerLOLv2RealToolbox(BaseRetinexformerToolbox):
    """LOL-v2真实场景数据集训练的低光增强模型"""
    name = "retinexformer_lol_v2_real"
    task_name = "LOL_v2_real"

    def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        print(f'[DEBUG] RetinexformerLOLv2RealToolbox build_params')
        return {"task": self.task_name, "format": "base64"}


class RetinexformerLOLv2SyntheticToolbox(BaseRetinexformerToolbox):
    """LOL-v2合成数据集训练的低光增强模型"""
    name = "retinexformer_lol_v2_synthetic"
    task_name = "LOL_v2_synthetic"

    def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        print(f'[DEBUG] RetinexformerLOLv2SyntheticToolbox build_params')
        return {"task": self.task_name, "format": "base64"}


class RetinexformerSDSDIndoorToolbox(BaseRetinexformerToolbox):
    """SDSD室内静态场景数据集训练的低光增强模型"""
    name = "retinexformer_sdsd_indoor"
    task_name = "SDSD_indoor"

    def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        print(f'[DEBUG] RetinexformerSDSDIndoorToolbox build_params')
        return {"task": self.task_name, "format": "base64"}


class RetinexformerSDSDOutdoorToolbox(BaseRetinexformerToolbox):
    """SDSD室外静态场景数据集训练的低光增强模型"""
    name = "retinexformer_sdsd_outdoor"
    task_name = "SDSD_outdoor"

    def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        print(f'[DEBUG] RetinexformerSDSDOutdoorToolbox build_params')
        return {"task": self.task_name, "format": "base64"}


class RetinexformerSIDToolbox(BaseRetinexformerToolbox):
    """SID (See in the Dark) 数据集训练的低光增强模型"""
    name = "retinexformer_sid"
    task_name = "SID"

    def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        print(f'[DEBUG] RetinexformerSIDToolbox build_params')
        return {"task": self.task_name, "format": "base64"}


class RetinexformerSMIDToolbox(BaseRetinexformerToolbox):
    """SMID静态多场景数据集训练的低光增强模型"""
    name = "retinexformer_smid"
    task_name = "SMID"

    def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        print(f'[DEBUG] RetinexformerSMIDToolbox build_params')
        return {"task": self.task_name, "format": "base64"}


class RetinexformerFiveKToolbox(BaseRetinexformerToolbox):
    """MIT Adobe FiveK数据集训练的低光增强模型"""
    name = "retinexformer_fivek"
    task_name = "FiveK"

    def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        print(f'[DEBUG] RetinexformerFiveKToolbox build_params')
        return {"task": self.task_name, "format": "base64"}


# ====================== 通用Retinexformer工具（推荐） ======================

class RetinexformerToolbox(BaseRetinexformerToolbox):
    """
    通用Retinexformer低光图像增强工具
    支持通过参数选择不同的预训练模型
    """
    name = "retinexformer_enhance"
    task_name = "LOL_v2_real"  # 默认任务
    
    # 可用的任务列表
    AVAILABLE_TASKS = [
        "LOL_v1", "LOL_v2_real", "LOL_v2_synthetic",
        "SDSD_indoor", "SDSD_outdoor", "SID", "SMID", "FiveK"
    ]

    def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建API参数
        
        Args:
            args: 工具调用参数，可包含:
                - task: 任务名称，默认为 LOL_v2_real
                  可选: LOL_v1, LOL_v2_real, LOL_v2_synthetic, 
                       SDSD_indoor, SDSD_outdoor, SID, SMID, FiveK
        """
        # 从参数中获取任务名称
        task = args.get("task", self.task_name)
        
        # 验证任务名称
        if task not in self.AVAILABLE_TASKS:
            print(f'[WARNING] Invalid task "{task}", using default "{self.task_name}"')
            task = self.task_name
        
        print(f'[DEBUG] RetinexformerToolbox build_params: task={task}')
        return {"task": task, "format": "base64"}


# ====================== 示例：测试自动注册和工具执行 ======================
if __name__ == "__main__":
    # --- 准备工作 ---
    import numpy as np
    from PIL import Image

    # 1. 检查工具是否已自动注册
    print("\n--- Checking Tool Registry ---")
    registered_tools = ToolBase.registry.keys()
    print(f"Available tools in registry: {list(registered_tools)}")

    # 检查所有Retinexformer工具
    expected_tools = [
        "retinexformer_lol_v1",
        "retinexformer_lol_v2_real",
        "retinexformer_lol_v2_synthetic",
        "retinexformer_sdsd_indoor",
        "retinexformer_sdsd_outdoor",
        "retinexformer_sid",
        "retinexformer_smid",
        "retinexformer_fivek",
        "retinexformer_enhance"
    ]
    
    for tool_name in expected_tools:
        if tool_name in registered_tools:
            print(f"✓ {tool_name} successfully registered")
        else:
            print(f"✗ {tool_name} NOT registered")

    # 2. 构造一张低光测试图片（模拟）
    # 创建一张暗图片
    test_img_array = np.random.randint(0, 80, (256, 256, 3), dtype=np.uint8)
    test_image = Image.fromarray(test_img_array)

    initial_prompt = [{"role": "user", "content": "Please enhance this low-light image."}]
    initial_data = {"image": [test_image]}
    
    print(f"\nCreated a test low-light image with size: {test_image.size}")
    print(f"Image mean brightness: {np.mean(test_img_array):.2f}")

    # --- 测试工具 ---

    # 1) 测试通用Retinexformer工具（推荐使用）
    print("\n--- [Test 1] Testing Generic Retinexformer Tool ---")
    try:
        enhance_tool = ToolBase.create("retinexformer_enhance")
        enhance_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
        
        # 构造工具调用字符串（模拟LLM输出）
        tool_call_string = """<tool_call>
{
    "name": "retinexformer_enhance",
    "arguments": {
        "task": "LOL_v2_real"
    }
}
</tool_call>"""
        
        obs, reward, done, info = enhance_tool.execute(tool_call_string)
        
        if info.get("status") == "success":
            print("Generic Retinexformer tool executed successfully.")
            processed_image = obs['multi_modal_data']['image'][0]
            print(f"Enhanced image size: {processed_image.size}")
            enhanced_array = np.array(processed_image)
            print(f"Enhanced image mean brightness: {np.mean(enhanced_array):.2f}")
        else:
            print(f"Tool failed with error: {info.get('error')}")

    except (ValueError, ConnectionError) as e:
        print(f"An error occurred: {e}")
        print("NOTE: This might be expected if the Retinexformer API service is not running")

    # 2) 测试特定任务工具
    print("\n--- [Test 2] Testing Specific Task Tool (LOL_v1) ---")
    try:
        lol_v1_tool = ToolBase.create("retinexformer_lol_v1")
        lol_v1_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
        
        tool_call_string = """<tool_call>
{
    "name": "retinexformer_lol_v1",
    "arguments": {}
}
</tool_call>"""
        
        obs, reward, done, info = lol_v1_tool.execute(tool_call_string)
        
        if info.get("status") == "success":
            print("LOL_v1 tool executed successfully.")
        else:
            print(f"LOL_v1 tool failed with error: {info.get('error')}")
            
    except (ValueError, ConnectionError) as e:
        print(f"An error occurred: {e}")

    # 3) 测试不存在的工具
    print("\n--- [Test 3] Testing a non-existent tool ---")
    try:
        fake_tool = ToolBase.create("retinexformer_nonexistent")
    except ValueError as e:
        print(f"Correctly caught expected error: {e}")
    
    print("\n--- All Tests Completed ---")

