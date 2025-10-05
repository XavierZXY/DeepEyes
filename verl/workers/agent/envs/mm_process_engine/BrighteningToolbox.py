import numpy as np
import cv2
import json
import re
from PIL import Image
from typing import Dict, Any, Tuple

# Import the actual ToolBase from your framework
from verl.workers.agent.tool_envs import ToolBase
from .IRprompt import PROMPT
# class PROMPT:
#     USER_PROMPT_V2 = (
#         "Here is the processed image after calling the function {}.\n"
#         "If this image is sufficient to answer the user's question, please provide your final answer within <answer></answer>. "
#         "Otherwise, you can continue to call tools within <tool_call></tool_call>."
#     )

# ====================== 通用本地处理基类 ======================
class LocalImageProcessingTool(ToolBase):
    """
    一个通用的基类，封装了所有工具共享的本地处理逻辑。
    - 继承自真正的 ToolBase 以实现自动注册。
    - 处理动作字符串解析、图像格式转换和返回格式化。
    - 子类只需实现核心的图像处理算法。
    """
    # 占位符名称，这个基类本身不应被直接使用
    name: str = "base_local_image_tool"
    user_prompt = PROMPT.USER_PROMPT_V1

    def __init__(self, _name, _desc, _params, **kwargs):
        super().__init__(name=self.name,**kwargs)
        self.chatml_history = []
        self.multi_modal_data = None

    def extract_answer(self, action_string: str) -> str:
        answer = re.findall(r'<answer>(.*?)</answer>', action_string, re.DOTALL)
        return answer[-1] if answer else None

    def extract_action(self, action_string: str) -> str:
        tool_call_match = re.findall(r'<tool_call>(.*?)</tool_call>', action_string, re.DOTALL)
        return tool_call_match[-1] if tool_call_match else None

    def pil_to_cv2(self, pil_image: Image.Image) -> np.ndarray:
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    def cv2_to_pil(self, cv2_image: np.ndarray) -> Image.Image:
        return Image.fromarray(cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB))

    def process_image(self, image: np.ndarray, args: Dict[str, Any]) -> np.ndarray:
        """
        子类必须覆盖此方法以实现具体的图像处理逻辑。
        输入和输出都应是 OpenCV (BGR) 格式的图像。
        """
        raise NotImplementedError

    def execute(self, action_string: str, **kwargs) -> tuple:
        import time
        start_time = time.time()
        print(f"[TOOL EXECUTE] 🚀 开始执行 {self.name}")
        
        answer = self.extract_answer(action_string)
        if answer:
            return "", 0.0, True, {"status": "finished", "answer": answer}

        action = self.extract_action(action_string)
        if not action:
            return "Error: No valid <tool_call> found.", -1.0, True, {"error": "No tool_call found"}

        try:
            tool_call = json.loads(action.strip())
            if isinstance(tool_call, list):
                tool_call = tool_call[0]
            print('tool_call', tool_call)
            tool_name = tool_call["name"]
            args = tool_call.get("arguments", {})

            if tool_name != self.name:
                raise ValueError(f"Tool name mismatch: action called for '{tool_name}', but this tool is '{self.name}'.")

            assert self.multi_modal_data and 'image' in self.multi_modal_data and self.multi_modal_data['image'], \
                   "No image loaded. Call reset() first."

            pil_img = self.multi_modal_data['image'][0]
            cv2_img = self.pil_to_cv2(pil_img)

            # 调用子类实现的具体处理方法
            processed_cv2_img = self.process_image(cv2_img, args)

            processed_pil_img = self.cv2_to_pil(processed_cv2_img)
            self.multi_modal_data['image'][0] = processed_pil_img

            obs = {
                "prompt": "\n<|im_start|>user\n" + "<tool_response><image>" + self.user_prompt.format(tool_name=self.name) + "</tool_response>" + "<|im_end|>\n<|im_start|>assistant\n",
                "multi_modal_data": {"image": [processed_pil_img]}
            }
            end_time = time.time()
            execution_time = end_time - start_time
            print(f"[TOOL EXECUTE] ✅ {self.name} 执行成功 (耗时: {execution_time:.2f}s)")
            
            return obs, 0., False, {"status": "success", "tool_used": self.name, "execution_time": execution_time}

        except Exception as e:
            end_time = time.time()
            execution_time = end_time - start_time
            print(f"[TOOL EXECUTE] ❌ {self.name} 执行失败 (耗时: {execution_time:.2f}s): {str(e)}")
            
            obs = "\n<|im_start|>user\n" + f"Error: {str(e)}" + "<|im_end|>\n<|im_start|>assistant\n"
            return obs, -0.1, False, {"error": str(e), "status": "failed", "execution_time": execution_time}

    def reset(self, raw_prompt, multi_modal_data, origin_multi_modal_data=None, **kwargs):
        self.chatml_history = raw_prompt
        # 使用当前处理后的图片，如果没有则使用原始图片
        self.multi_modal_data = multi_modal_data if multi_modal_data else origin_multi_modal_data

# ====================== 三个独立的本地工具 ======================

class ConstantShiftTool(LocalImageProcessingTool):
    """
    常量亮度偏移工具。
    """
    name = "constant_shift"

    def process_image(self, image: np.ndarray, args: Dict[str, Any]) -> np.ndarray:
        shift = args.get("shift", 40)
        print(f'[DEBUG] ConstantShiftTool process_image: {shift}')
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        v_updated = np.clip(np.int16(v) + shift, 0, 255).astype(np.uint8)
        final_hsv = cv2.merge((h, s, v_updated))
        return cv2.cvtColor(final_hsv, cv2.COLOR_HSV2BGR)


class GammaCorrectionTool(LocalImageProcessingTool):
    """
    Gamma 矫正工具。
    """
    name = "gamma_correction"

    def process_image(self, image: np.ndarray, args: Dict[str, Any]) -> np.ndarray:
        gamma = args.get("gamma", 1.5)
        print(f'[DEBUG] GammaCorrectionTool process_image: {gamma}')
        if gamma <= 0:
            raise ValueError("Gamma value must be positive.")
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        # 应用 gamma 矫正
        v_updated = (np.power(v / 255.0, 1.0 / gamma) * 255).astype(np.uint8)
        final_hsv = cv2.merge((h, s, v_updated))
        return cv2.cvtColor(final_hsv, cv2.COLOR_HSV2BGR)


class HistogramEqualizationTool(LocalImageProcessingTool):
    """
    CLAHE 直方图均衡工具。
    """
    name = "histogram_equalization"

    def process_image(self, image: np.ndarray, args: Dict[str, Any]) -> np.ndarray:
        clip_limit = args.get("clipLimit", 2.0)
        print(f'[DEBUG] HistogramEqualizationTool process_image: {clip_limit}')
        tile_grid_size = tuple(args.get("tileGridSize", (8, 8)))
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
        v_updated = clahe.apply(v)
        final_hsv = cv2.merge((h, s, v_updated))
        return cv2.cvtColor(final_hsv, cv2.COLOR_HSV2BGR)


# ====================== 示例测试代码 ======================
if __name__ == "__main__":
    # 1. 检查工具是否已通过继承 ToolBase 和定义 name 来自动注册
    print("\n--- Checking Tool Registry ---")
    registered_tools = ToolBase.registry.keys()
    print(f"Available tools in registry: {list(registered_tools)}")
    assert "constant_shift" in registered_tools
    assert "gamma_correction" in registered_tools
    assert "histogram_equalization" in registered_tools
    print("All three brightening tools are correctly registered.")

    # 2. 准备测试数据
    dummy_image = Image.new('RGB', (100, 100), color=(50, 20, 80)) # 一个较暗的彩色图像
    initial_data = {"image": [dummy_image.copy()]}
    print("\nCreated a dark test image.")

    # 3. 测试 Constant Shift Tool
    print("\n--- Testing Constant Shift Tool ---")
    const_tool = ToolBase.create("constant_shift_tool")
    const_tool.reset(raw_prompt="", multi_modal_data=initial_data)
    action = '<tool_call>{"name": "constant_shift", "arguments": {"shift": 60}}</tool_call>'
    obs, _, _, info = const_tool.execute(action)
    if info.get("status") == "success":
        print("Constant Shift executed successfully.")
        # obs['multi_modal_data']['image'][0].show(title="Constant Shift Result")

    # 4. 测试 Gamma Correction Tool
    print("\n--- Testing Gamma Correction Tool ---")
    gamma_tool = ToolBase.create("gamma_correction")
    # 必须重置，因为上一个工具修改了 initial_data 中的图像
    initial_data = {"image": [dummy_image.copy()]} 
    gamma_tool.reset(raw_prompt="", multi_modal_data=initial_data)
    action = '<tool_call>{"name": "gamma_correction", "arguments": {"gamma": 0.4}}</tool_call>'
    obs, _, _, info = gamma_tool.execute(action)
    if info.get("status") == "success":
        print("Gamma Correction executed successfully.")
        # obs['multi_modal_data']['image'][0].show(title="Gamma Correction Result")

    # 5. 测试 Histogram Equalization Tool
    print("\n--- Testing Histogram Equalization Tool ---")
    he_tool = ToolBase.create("histogram_equalization")
    initial_data = {"image": [dummy_image.copy()]} 
    he_tool.reset(raw_prompt="", multi_modal_data=initial_data)
    action = '<tool_call>{"name": "histogram_equalization", "arguments": {"clipLimit": 3.0, "tileGridSize": [4, 4]}}</tool_call>'
    obs, _, _, info = he_tool.execute(action)
    if info.get("status") == "success":
        print("Histogram Equalization executed successfully.")
        # obs['multi_modal_data']['image'][0].show(title="Histogram Equalization Result")