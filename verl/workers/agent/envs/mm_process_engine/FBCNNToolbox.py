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
class BaseFBCNNToolbox(ToolBase):
    """
    FBCNN工具箱基类，用于JPEG压缩伪影去除
    这个基类本身不应该是一个可执行的工具。
    """
    # We give it a placeholder name to satisfy the ToolBase requirement,
    # but it won't be registered as a usable tool.
    name = "base_fbcnn_toolbox" 
    
    # These will be overridden by subclasses
    task_name: str = ""
    
    user_prompt = PROMPT.USER_PROMPT_V1
    # 从环境变量读取IP地址，保留端口号5005
    
    @property
    def api_url(self):
        """动态获取API URL，支持负载均衡"""
        ip = get_tool_service_ip()
        return f"http://{ip}:5005/process"

    def __init__(self, _name, _desc, _params, **kwargs):
        # The 'name' is now a class attribute, so we don't need to pass it here.
        super().__init__(name=self.name, **kwargs) 
        self.chatml_history = []
        self.multi_modal_data = None
        print(f"FBCNNToolbox initialized. API endpoint: {self.api_url}")

    def _call_fbcnn_api(self, image: Image.Image, task_params: Dict[str, Any]) -> Image.Image:
        """调用FBCNN API进行图像处理"""
        print(f"[FBCNN API] 🚀 开始调用API: {self.api_url}", flush=True)
        print(f"[FBCNN API] 任务参数: {task_params}", flush=True)
        
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        image_bytes = buf.getvalue()
        files = {'image': ('image.png', image_bytes, 'image/png')}
        
        try:
            print(f"[FBCNN API] 发送POST请求...", flush=True)
            resp = requests.post(self.api_url, files=files, data=task_params, timeout=300)
            print(f"[FBCNN API] 收到响应，状态码: {resp.status_code}", flush=True)
            
            resp.raise_for_status()
            result = resp.json()
            print(f"[FBCNN API] JSON响应: success={result.get('success')}", flush=True)
            
            if result.get('success'):
                img_b64 = result['image']
                img_bytes = base64.b64decode(img_b64)
                restored_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                self.multi_modal_data['image'][0] = restored_image
                print(f"[FBCNN API] ✅ API调用成功，图像处理完成", flush=True)
                return restored_image
            else:
                error_msg = result.get('error', 'Unknown API error')
                print(f"[FBCNN API] ❌ API返回错误: {error_msg}", flush=True)
                raise RuntimeError(f"FBCNN API error: {error_msg}")
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if "503" in error_msg and "SERVICE UNAVAILABLE" in error_msg:
                raise ConnectionError(f"FBCNN service is temporarily unavailable (likely due to GPU memory shortage). Please try again later or contact administrator. Error: {e}")
            elif "408" in error_msg or "timeout" in error_msg.lower():
                raise ConnectionError(f"FBCNN service timeout (likely due to high load). Please try again later. Error: {e}")
            else:
                raise ConnectionError(f"Failed to connect to FBCNN API at {self.api_url}. Error: {e}")
            
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
            return obs, 0.0, False, {"error": error_msg, "status": "failed"}

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
            print(f"[FBCNN DEBUG] 开始处理图像，尺寸: {current_image.size}", flush=True)
            
            params = self.build_params(args)
            print(f"[FBCNN DEBUG] API参数: {params}", flush=True)
            
            restored_image = self._call_fbcnn_api(current_image, params)
            print(f"[FBCNN DEBUG] API调用完成，返回图像尺寸: {restored_image.size}", flush=True)

            # 使用 USER_PROMPT_V1 的正确格式化方式
            formatted_prompt = self.user_prompt.format(tool_name=self.name)
            
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


# ====================== FBCNN工具类 ======================

class FBCNNJpegArtifactRemovalToolbox(BaseFBCNNToolbox):
    """FBCNN JPEG压缩伪影去除工具"""
    name = "fbcnn_jpeg_artifact_removal"
    task_name = "jpeg_compression_artifact_removal"

    def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建FBCNN API参数
        
        Args:
            args: 工具调用参数，支持以下参数：
                - qf: 质量因子，可以是'blind'（盲预测）或1-100的整数
                - gpu: 指定GPU ID（可选）
                - queue: 是否启用队列，默认true
                - format: 返回格式，默认'base64'
        """
        # QF参数处理
        qf = args.get("qf", args.get("quality_factor", "blind"))
        
        # 验证QF参数
        if qf != "blind":
            try:
                qf_int = int(qf)
                if not (1 <= qf_int <= 100):
                    print(f"[WARNING] Invalid QF value {qf}, using blind mode")
                    qf = "blind"
                else:
                    qf = str(qf_int)
            except (ValueError, TypeError):
                print(f"[WARNING] Invalid QF format {qf}, using blind mode")
                qf = "blind"
        
        # GPU参数（可选）
        # gpu_id = args.get("gpu")
        # if gpu_id is not None:
        #     try:
        #         gpu_id = int(gpu_id)
        #     except (ValueError, TypeError):
        #         gpu_id = None
        
        # 队列参数
        enable_queue = args.get("queue", True)
        if isinstance(enable_queue, str):
            enable_queue = enable_queue.lower() == "true"
        
        # 返回格式
        return_format = args.get("format", "base64")
        
        params = {
            "qf": qf,
            "format": return_format,
            "queue": str(enable_queue).lower()
        }
        
        # if gpu_id is not None:
        #     params["gpu"] = str(gpu_id)
        
        print(f'[DEBUG] FBCNNJpegArtifactRemovalToolbox build_params: {params}')
        return params


class FBCNNBlindQualityAssessmentToolbox(BaseFBCNNToolbox):
    """FBCNN盲质量评估工具（仅预测QF，不进行修复）"""
    name = "fbcnn_blind_quality_assessment"
    task_name = "blind_quality_assessment"

    def build_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建盲质量评估参数
        """
        # 强制使用blind模式进行质量评估
        params = {
            "qf": "blind",
            "format": "base64",
            "queue": "true"
        }
        
        # GPU参数（可选）
        gpu_id = args.get("gpu")
        if gpu_id is not None:
            try:
                gpu_id = int(gpu_id)
                params["gpu"] = str(gpu_id)
            except (ValueError, TypeError):
                pass
        
        print(f'[DEBUG] FBCNNBlindQualityAssessmentToolbox build_params: {params}')
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

    assert "fbcnn_jpeg_artifact_removal" in registered_tools
    assert "fbcnn_blind_quality_assessment" in registered_tools
    print("All FBCNN tools successfully auto-registered.")

    # 2. 构造一张测试图片和初始数据
    test_img_array = np.random.randint(0, 200, (128, 128, 3), dtype=np.uint8)
    test_image = Image.fromarray(test_img_array)

    initial_prompt = [{"role": "user", "content": "Please remove JPEG artifacts from this image."}]
    initial_data = {"image": [test_image]}
    
    print(f"\nCreated a test image with size: {test_image.size}")

    # --- 测试每个工具 ---

    # 1) 测试JPEG伪影去除工具
    print("\n--- [Test 1] Testing FBCNN JPEG Artifact Removal Tool ---")
    try:
        # 使用 ToolBase.create() 工厂方法创建工具实例
        fbcnn_tool = ToolBase.create("fbcnn_jpeg_artifact_removal")
        
        # 调用 reset 初始化工具状态
        fbcnn_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
        
        # 准备工具调用字符串（模拟模型输出）
        tool_call_json = json.dumps([{
            "name": "fbcnn_jpeg_artifact_removal",
            "arguments": {"qf": "blind", "queue": True}
        }])
        action_string = f"<tool_call>{tool_call_json}</tool_call>"
        
        # 调用 execute 执行工具
        obs, reward, done, info = fbcnn_tool.execute(action_string)
        
        if info.get("status") == "success":
            print("FBCNN JPEG artifact removal tool executed successfully.")
            # 检查返回的图像
            if isinstance(obs, dict) and 'multi_modal_data' in obs:
                processed_image = obs['multi_modal_data']['image'][0]
                print(f"Returned image size: {processed_image.size}")
        else:
            print(f"FBCNN tool failed with error: {info.get('error')}")

    except (ValueError, ConnectionError) as e:
        print(f"An error occurred: {e}")
        print("NOTE: This might be expected if the FBCNN API service is not running at http://172.18.148.193:5005")

    # 2) 测试盲质量评估工具
    print("\n--- [Test 2] Testing FBCNN Blind Quality Assessment Tool ---")
    try:
        quality_tool = ToolBase.create("fbcnn_blind_quality_assessment")
        quality_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
        
        tool_call_json = json.dumps([{
            "name": "fbcnn_blind_quality_assessment",
            "arguments": {}
        }])
        action_string = f"<tool_call>{tool_call_json}</tool_call>"
        
        obs, reward, done, info = quality_tool.execute(action_string)

        if info.get("status") == "success":
            print("FBCNN blind quality assessment tool executed successfully.")
        else:
            print(f"Quality assessment tool failed with error: {info.get('error')}")
            
    except (ValueError, ConnectionError) as e:
        print(f"An error occurred: {e}")

    # 3) 测试带特定QF参数的工具调用
    print("\n--- [Test 3] Testing FBCNN with specific QF parameter ---")
    try:
        fbcnn_tool = ToolBase.create("fbcnn_jpeg_artifact_removal")
        fbcnn_tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
        
        tool_call_json = json.dumps([{
            "name": "fbcnn_jpeg_artifact_removal",
            "arguments": {"qf": "30", "gpu": "0", "queue": False}
        }])
        action_string = f"<tool_call>{tool_call_json}</tool_call>"
        
        obs, reward, done, info = fbcnn_tool.execute(action_string)

        if info.get("status") == "success":
            print("FBCNN with specific QF parameter executed successfully.")
        else:
            print(f"FBCNN with QF=30 failed with error: {info.get('error')}")

    except (ValueError, ConnectionError) as e:
        print(f"An error occurred: {e}")

    # 4) 测试一个不存在的工具，确保它能正确报错
    print("\n--- [Test 4] Testing a non-existent tool ---")
    try:
        fake_tool = ToolBase.create("a_tool_that_does_not_exist")
    except ValueError as e:
        print(f"Correctly caught expected error: {e}")

    print("\n--- FBCNN Tool Testing Completed ---")
