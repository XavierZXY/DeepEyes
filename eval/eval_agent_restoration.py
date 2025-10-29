#!/usr/bin/env python3
"""
Agent-based Image Restoration Evaluation Script

支持两种模式:
1. multi_tool_planning: 一次输出多个工具,链式执行
2. single_tool_iterative: 每次输出一个工具,迭代执行

评估指标:
- 有参考指标: PSNR, SSIM, LPIPS
- 无参考指标: MANIQA, CLIP-IQA, MUSIQ
"""

#!/usr/bin/env python3
import os
import sys
import json
import argparse
import base64
import io
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional, Union
from dataclasses import dataclass, field
from copy import deepcopy
from tqdm import tqdm
import numpy as np
from PIL import Image
import pandas as pd
import torch

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from openai import OpenAI
import pyiqa

# 导入工具系统
from verl.workers.agent.tool_envs import ToolBase
from verl.utils.reward_score.image_quality_metrics import ImageQualityMetrics


@dataclass
class EvaluationConfig:
    """评估配置"""
    # API配置
    api_key: str = "EMPTY"
    api_url: str = "http://localhost:8000/v1"
    model_name: str = None  # 自动检测
    
    # 数据配置
    data_path: str = None  # parquet文件路径
    output_dir: str = "./eval_results"
    
    # Agent配置
    conversation_mode: str = "multi_tool_planning"  # or "single_tool_iterative"
    max_turns: int = 1  # multi_tool_planning通常设为1
    single_response_max_tokens: int = 10240
    temperature: float = 0.7
    top_p: float = 0.9
    
    # System Prompt配置
    use_parquet_system_prompt: bool = True  # 是否使用parquet中的system prompt
    custom_system_prompt: str = None  # 自定义system prompt（当use_parquet_system_prompt=False时使用）
    
    # User Prompt配置
    use_parquet_user_prompt: bool = True  # 是否使用parquet中的user prompt（包含退化类型提示）
    custom_user_prompt: str = None  # 自定义user prompt（为None时使用默认）
    provide_degradation_hint: bool = True  # 是否在用户消息中提供退化类型（仅当use_parquet_user_prompt=False时有效）
    
    # 工具服务配置
    tool_service_ip: str = "10.21.9.6"
    
    # 评估配置
    num_samples: int = None  # None表示全部
    batch_size: int = 1  # 推理batch size
    concurrent_workers: int = 1  # 并发worker数
    
    # 指标配置
    compute_reference_metrics: bool = True  # 是否计算有参考指标(PSNR/SSIM/LPIPS)
    compute_no_reference_metrics: bool = True  # 是否计算无参考指标(MANIQA/CLIP-IQA/MUSIQ)


class ImageQualityEvaluator:
    """图像质量评估器 - 扩展支持 MANIQA 和 MUSIQ"""
    
    def __init__(self, device='cuda' if torch.cuda.is_available() else 'cpu'):
        self.device = device
        print(f"[INFO] 初始化图像质量评估器，设备: {self.device}")
        
        # 初始化有参考指标计算器
        self.ref_metrics_calculator = ImageQualityMetrics()
        
        # 初始化无参考指标
        self.no_ref_metrics = {}
        try:
            print("[INFO] 加载 MANIQA...")
            self.no_ref_metrics['maniqa'] = pyiqa.create_metric('maniqa', device=device)
        except Exception as e:
            print(f"[WARNING] MANIQA 加载失败: {e}")
            
        try:
            print("[INFO] 加载 MUSIQ...")
            self.no_ref_metrics['musiq'] = pyiqa.create_metric('musiq', device=device)
        except Exception as e:
            print(f"[WARNING] MUSIQ 加载失败: {e}")
            
        try:
            print("[INFO] 加载 CLIP-IQA...")
            self.no_ref_metrics['clipiqa'] = pyiqa.create_metric('clipiqa', device=device)
        except Exception as e:
            print(f"[WARNING] CLIP-IQA 加载失败: {e}")
            
        print(f"[INFO] 成功加载的无参考指标: {list(self.no_ref_metrics.keys())}")
    
    def _prepare_image_tensor(self, image: Union[np.ndarray, Image.Image]) -> torch.Tensor:
        """准备图像张量用于pyiqa"""
        if isinstance(image, Image.Image):
            image = np.array(image)
        
        # 转换为 [0, 1] 范围
        if image.dtype == np.uint8:
            image = image.astype(np.float32) / 255.0
        
        # 转换为 (C, H, W) 格式
        if len(image.shape) == 2:  # 灰度图
            image = np.expand_dims(image, axis=0)
        elif len(image.shape) == 3:  # RGB
            image = image.transpose(2, 0, 1)
        
        # 转换为 torch tensor 并添加 batch 维度
        image_tensor = torch.from_numpy(image).unsqueeze(0).float()
        return image_tensor
    
    def compute_reference_metrics(self, restored_img: Union[np.ndarray, Image.Image],
                                  gt_img: Union[np.ndarray, Image.Image]) -> Dict[str, float]:
        """计算有参考指标: PSNR, SSIM, LPIPS"""
        metrics = {}
        
        try:
            all_metrics = self.ref_metrics_calculator.calculate_all_metrics(restored_img, gt_img)
            metrics['psnr'] = all_metrics.get('psnr', 0.0)
            metrics['ssim'] = all_metrics.get('ssim', 0.0)
            metrics['lpips'] = all_metrics.get('lpips', 0.0)
        except Exception as e:
            print(f"[WARNING] 有参考指标计算失败: {e}")
            metrics = {'psnr': 0.0, 'ssim': 0.0, 'lpips': 0.0}
        
        return metrics
    
    def compute_no_reference_metrics(self, restored_img: Union[np.ndarray, Image.Image]) -> Dict[str, float]:
        """计算无参考指标: MANIQA, MUSIQ, CLIP-IQA"""
        metrics = {}
        
        image_tensor = self._prepare_image_tensor(restored_img)
        
        for metric_name, metric_model in self.no_ref_metrics.items():
            try:
                with torch.no_grad():
                    score = metric_model(image_tensor)
                    metrics[metric_name] = float(score.item())
            except Exception as e:
                print(f"[WARNING] {metric_name} 计算失败: {e}")
                metrics[metric_name] = 0.0
        
        # 清理GPU缓存
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        return metrics


class AgentRestoration:
    """Agent图像复原评估"""
    
    def __init__(self, config: EvaluationConfig):
        self.config = config
        
        # 初始化OpenAI客户端
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.api_url,
        )
        
        # 获取模型名称
        if config.model_name is None:
            try:
                import requests
                response = requests.get(f"{config.api_url}/models")
                models = response.json()
                self.model_name = models['data'][0]['id']
                print(f"[INFO] 自动检测到模型: {self.model_name}")
            except Exception as e:
                print(f"[WARNING] 无法自动检测模型名称: {e}")
                self.model_name = "default"
        else:
            self.model_name = config.model_name
        
        # 初始化评估器
        self.evaluator = ImageQualityEvaluator()
        
        # 设置工具服务IP
        os.environ['TOOL_SERVICE_IP'] = config.tool_service_ip
        
        # 注册工具
        self.available_tools = self._register_tools()
        
        print(f"[INFO] 初始化完成，对话模式: {config.conversation_mode}")
        print(f"[INFO] 可用工具: {list(self.available_tools.keys())}")
    
    def _register_tools(self) -> Dict[str, Any]:
        """注册所有可用的工具"""
        # 导入所有工具（通过导入触发自动注册）
        from verl.workers import agent  # 这会自动注册所有工具
        
        # 从ToolBase.registry获取所有注册的工具
        available_tools = {}
        for tool_name, tool_class in ToolBase.registry.items():
            available_tools[tool_name] = tool_class
        
        return available_tools
    
    def _encode_image_to_base64(self, image: Union[str, Image.Image, np.ndarray]) -> str:
        """将图像编码为base64"""
        if isinstance(image, str):
            # 文件路径
            with open(image, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
        elif isinstance(image, Image.Image):
            # PIL图像
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode('utf-8')
        elif isinstance(image, np.ndarray):
            # numpy数组
            pil_image = Image.fromarray(image.astype(np.uint8))
            buffered = io.BytesIO()
            pil_image.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode('utf-8')
        else:
            raise ValueError(f"Unsupported image type: {type(image)}")
    
    def _decode_base64_to_image(self, base64_str: str) -> Image.Image:
        """将base64解码为PIL图像"""
        image_bytes = base64.b64decode(base64_str)
        return Image.open(io.BytesIO(image_bytes))
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        if self.config.conversation_mode == "multi_tool_planning":
            return """You are an expert image restoration agent. Your task is to analyze degraded images and restore them using available tools.

# Tools
You have access to various image restoration tools. Each tool is specialized for specific degradations:
- Denoising tools: For removing noise
- Deblurring tools: For removing motion blur or defocus blur
- Dehazing tools: For removing haze/fog
- Deraining tools: For removing rain streaks
- Low-light enhancement tools: For brightening dark images
- Super-resolution tools: For upscaling images
- And more...

# Multi-Tool Planning Mode
You should analyze the image and plan a complete restoration strategy:
1. Identify all degradations in the image
2. Plan a sequence of tools to address them (you can output multiple tools at once)
3. The tools will be executed in sequence (tool1 → tool2 → tool3...)
4. Evaluate the result and adjust if needed

# Output Format
Your response MUST follow this structure:

<think>
Analyze the image and explain your restoration plan. Be specific about:
- What degradations you observe
- Which tools you will use and why
- The expected order of operations
</think>

<tool_call>
[
    {"name": "tool_name_1", "arguments": {...}},
    {"name": "tool_name_2", "arguments": {...}},
    ...
]
</tool_call>

OR (when satisfied with the result):

<answer>
Final restoration complete. The image quality has been improved.
</answer>

Remember: 
- You can output multiple tools in one turn
- Tools will be executed sequentially on the original degraded image
- Each tool's output becomes the input for the next tool in the chain
"""
        else:  # single_tool_iterative
            return """You are an expert image restoration agent. Your task is to analyze degraded images and restore them step by step.

# Tools
You have access to various image restoration tools for different degradations.

# Single-Tool Iterative Mode
You should restore the image step by step:
1. Analyze the current image state
2. Choose ONE tool to address the most critical degradation
3. See the result and decide the next step
4. Repeat until satisfied

# Output Format
Your response MUST follow this structure:

<think>
Analyze the current image state and explain your next action.
</think>

<tool_call>
{"name": "tool_name", "arguments": {...}}
</tool_call>

OR (when done):

<answer>
Restoration complete.
</answer>

Remember: Output ONLY ONE tool per turn.
"""
    
    def _parse_model_response(self, text: str) -> Dict[str, Any]:
        """解析模型输出"""
        import re
        
        result = {
            'think': None,
            'tool_calls': [],
            'answer': None,
            'is_done': False
        }
        
        # 提取 <think> 块
        think_pattern = r'<think>(.*?)</think>'
        think_match = re.search(think_pattern, text, re.DOTALL)
        if think_match:
            result['think'] = think_match.group(1).strip()
        
        # 提取 <tool_call> 块
        tool_call_pattern = r'<tool_call>(.*?)</tool_call>'
        tool_call_match = re.search(tool_call_pattern, text, re.DOTALL)
        if tool_call_match:
            tool_call_content = tool_call_match.group(1).strip()
            try:
                tool_calls_json = json.loads(tool_call_content)
                if isinstance(tool_calls_json, list):
                    result['tool_calls'] = tool_calls_json
                else:
                    result['tool_calls'] = [tool_calls_json]
            except json.JSONDecodeError as e:
                print(f"[WARNING] 工具调用JSON解析失败: {e}")
                print(f"[WARNING] 内容: {tool_call_content}")
        
        # 提取 <answer> 块
        answer_pattern = r'<answer>(.*?)</answer>'
        answer_match = re.search(answer_pattern, text, re.DOTALL)
        if answer_match:
            result['answer'] = answer_match.group(1).strip()
            result['is_done'] = True
        
        return result
    
    def _execute_tools(self, tool_calls: List[Dict], degraded_image: Image.Image,
                       gt_image: Image.Image = None, raw_prompt: List[Dict] = None) -> Tuple[Image.Image, List[Dict]]:
        """执行工具链"""
        current_image = degraded_image
        tool_results = []
        
        # 准备raw_prompt（如果没有提供，使用默认值）
        if raw_prompt is None:
            raw_prompt = [{"role": "user", "content": "Restore this image."}]
        
        for i, tool_call in enumerate(tool_calls):
            tool_name = tool_call.get('name')
            tool_args = tool_call.get('arguments', {})
            
            if not tool_name or tool_name not in ToolBase.registry:
                print(f"[WARNING] 未知工具: {tool_name}")
                tool_results.append({
                    'tool_name': tool_name,
                    'success': False,
                    'error': f"Unknown tool: {tool_name}"
                })
                continue
            
            try:
                # 使用ToolBase.create()工厂方法创建工具实例（与训练代码一致）
                tool_instance = ToolBase.create(tool_name)
                
                # 准备多模态数据（转换为PIL Image格式）
                multi_modal_data = {
                    'image': [current_image]  # 使用PIL Image，而不是base64
                }
                
                origin_multi_modal_data = {
                    'image': [degraded_image]
                }
                
                # 重置工具（与训练代码一致）
                tool_instance.reset(
                    raw_prompt=raw_prompt,
                    multi_modal_data=deepcopy(multi_modal_data),
                    origin_multi_modal_data=deepcopy(origin_multi_modal_data)
                )
                
                # 执行工具（构造action_string，与训练代码一致）
                print(f"[INFO] 执行工具 {i+1}/{len(tool_calls)}: {tool_name}")
                
                # 构造compatible_action_string（与parallel_env.py:1281一致）
                action_string = f"<tool_call>{json.dumps(tool_call)}</tool_call>"
                
                tool_result, reward, done, info = tool_instance.execute(action_string)
                
                # 获取输出图像
                if 'multi_modal_data' in tool_result and 'image' in tool_result['multi_modal_data']:
                    # 输出是PIL Image列表
                    output_images = tool_result['multi_modal_data']['image']
                    if len(output_images) > 0:
                        current_image = output_images[0]
                        print(f"[INFO] 工具执行成功，图像尺寸: {current_image.size}")
                else:
                    print(f"[WARNING] 工具未返回图像")
                
                tool_results.append({
                    'tool_name': tool_name,
                    'arguments': tool_args,
                    'success': True,
                    'reward': reward,
                    'info': info
                })
                
            except Exception as e:
                error_msg = str(e)
                print(f"[ERROR] 工具执行失败 ({tool_name})")
                print(f"  原因: {error_msg}")
                print(f"  工具调用: {tool_call}")
                
                # 只在非常规错误时打印完整traceback
                if "Connection" in error_msg or "Timeout" in error_msg or "Service" in error_msg:
                    print(f"  详情: 工具服务可能未启动或网络连接失败")
                else:
                    print(f"  详细错误:")
                    import traceback
                    traceback.print_exc()
                
                tool_results.append({
                    'tool_name': tool_name,
                    'arguments': tool_args,
                    'success': False,
                    'error': error_msg
                })
        
        return current_image, tool_results
    
    def _extract_image_from_data(self, image_data: Any) -> Optional[Image.Image]:
        """从不同格式的数据中提取图像"""
        if image_data is None:
            return None
        
        # 如果是字典（parquet中常见格式：{'bytes': b'...'}）
        if isinstance(image_data, dict):
            if 'bytes' in image_data:
                # 直接从bytes创建图像
                image_bytes = image_data['bytes']
                return Image.open(io.BytesIO(image_bytes))
            elif 'path' in image_data:
                # 从路径加载
                return Image.open(image_data['path'])
        
        # 如果是bytes
        elif isinstance(image_data, bytes):
            return Image.open(io.BytesIO(image_data))
        
        # 如果是base64字符串
        elif isinstance(image_data, str):
            return self._decode_base64_to_image(image_data)
        
        else:
            print(f"[WARNING] 不支持的图像数据类型: {type(image_data)}")
            return None
    
    def evaluate_single_sample(self, sample: Dict) -> Dict[str, Any]:
        """评估单个样本"""
        # 解析样本数据
        prompt = sample.get('prompt', [])
        images = sample.get('images', [])
        gt_degradations = sample.get('env_name', '').split(', ')
        
        # 从images数组中提取图像
        # 通常 images[0] 是退化图像
        degraded_image = None
        gt_image = None
        
        if len(images) > 0:
            degraded_image = self._extract_image_from_data(images[0])
        
        # 尝试从extra_info获取GT图像
        extra_info = sample.get('extra_info', {})
        if isinstance(extra_info, dict):
            if 'original_image' in extra_info and extra_info.get('use_original', False):
                gt_image = self._extract_image_from_data(extra_info['original_image'])
        
        if degraded_image is None:
            print("[WARNING] 未找到退化图像")
            return {}
        
        # 为了获取base64用于API调用，重新编码图像
        degraded_image_base64 = self._encode_image_to_base64(degraded_image)
        
        print(f"[DEBUG] 退化图像尺寸: {degraded_image.size}")
        print(f"[DEBUG] GT图像: {'是' if gt_image else '否'}")
        if gt_image:
            print(f"[DEBUG] GT图像尺寸: {gt_image.size}")
        
        # 决定使用哪个系统提示词
        if self.config.use_parquet_system_prompt and isinstance(prompt, (list, np.ndarray)) and len(prompt) > 0:
            # 从parquet读取系统提示词
            system_msg = prompt[0]
            if isinstance(system_msg, dict) and system_msg.get('role') == 'system':
                system_prompt = system_msg.get('content', self._build_system_prompt())
                print(f"[INFO] 使用parquet中的系统提示词（长度: {len(system_prompt)}）")
            else:
                system_prompt = self._build_system_prompt()
                print(f"[WARNING] parquet中的prompt格式不正确，使用默认系统提示词")
        elif self.config.custom_system_prompt:
            # 使用自定义系统提示词
            system_prompt = self.config.custom_system_prompt
            print(f"[INFO] 使用自定义系统提示词（长度: {len(system_prompt)}）")
        else:
            # 使用内置的系统提示词
            system_prompt = self._build_system_prompt()
            print(f"[INFO] 使用内置系统提示词")
        
        # 准备消息
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # 提取用户消息内容
        if self.config.use_parquet_user_prompt and isinstance(prompt, (list, np.ndarray)) and len(prompt) > 1:
            # 从parquet读取用户消息
            user_msg = prompt[1]
            if isinstance(user_msg, dict) and user_msg.get('role') == 'user':
                user_text = user_msg.get('content', '')
                # 移除<image>标记（我们会在下面重新添加）
                user_text = user_text.replace('<image>', '').replace('<image/>', '').strip()
                if not user_text:
                    user_text = "Please analyze and restore this degraded image."
                print(f"[INFO] 使用parquet中的用户消息")
            else:
                user_text = "Please analyze and restore this degraded image."
        elif self.config.custom_user_prompt:
            # 使用自定义用户消息
            user_text = self.config.custom_user_prompt
            print(f"[INFO] 使用自定义用户消息")
        else:
            # 使用默认用户消息
            if self.config.provide_degradation_hint and gt_degradations:
                # 提供退化类型提示
                degradation_list = ', '.join(gt_degradations)
                user_text = f"Detected degradations: {degradation_list}\n\nPlease analyze and restore this degraded image."
                print(f"[INFO] 使用默认用户消息（包含退化类型提示）")
            else:
                # 不提供退化类型，测试模型诊断能力
                user_text = "Please analyze and restore this degraded image."
                print(f"[INFO] 使用默认用户消息（不提供退化类型提示）")
        
        # 添加用户消息（包含图像）
        content = [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{degraded_image_base64}"
                }
            },
            {
                "type": "text",
                "text": user_text
            }
        ]
        messages.append({"role": "user", "content": content})
        
        # 多轮对话
        conversation_history = []
        restored_image = degraded_image
        all_tool_results = []
        
        for turn in range(self.config.max_turns):
            print(f"\n[INFO] Turn {turn + 1}/{self.config.max_turns}")
            
            try:
                # 调用模型
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=self.config.temperature,
                    top_p=self.config.top_p,
                    max_tokens=self.config.single_response_max_tokens
                )
                
                model_output = response.choices[0].message.content
                conversation_history.append({
                    'turn': turn + 1,
                    'model_output': model_output
                })
                
                print(f"[INFO] 模型输出:\n{model_output[:500]}...")
                
                # 解析输出
                parsed = self._parse_model_response(model_output)
                
                # 如果完成，退出循环
                if parsed['is_done']:
                    print(f"[INFO] Agent完成复原")
                    break
                
                # 执行工具
                if parsed['tool_calls']:
                    print(f"[INFO] 执行 {len(parsed['tool_calls'])} 个工具")
                    # 准备raw_prompt（转换numpy数组为列表）
                    raw_prompt_list = prompt.tolist() if isinstance(prompt, np.ndarray) else prompt
                    
                    restored_image, tool_results = self._execute_tools(
                        parsed['tool_calls'],
                        degraded_image,
                        gt_image,
                        raw_prompt=raw_prompt_list  # 传入原始prompt
                    )
                    all_tool_results.extend(tool_results)
                    
                    # 如果是单工具迭代模式，添加工具结果到对话历史
                    if self.config.conversation_mode == "single_tool_iterative":
                        # 编码复原图像
                        restored_image_base64 = self._encode_image_to_base64(restored_image)
                        
                        # 添加助手回复
                        messages.append({"role": "assistant", "content": model_output})
                        
                        # 添加用户反馈（包含新图像）
                        feedback_content = [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{restored_image_base64}"
                                }
                            },
                            {
                                "type": "text",
                                "text": f"Tool executed. Here is the current result. Continue if needed."
                            }
                        ]
                        messages.append({"role": "user", "content": feedback_content})
                else:
                    print(f"[WARNING] 未检测到工具调用")
                    break
                    
            except Exception as e:
                print(f"[ERROR] 推理失败: {e}")
                import traceback
                traceback.print_exc()
                break
        
        # 计算评估指标
        metrics = {}
        
        # 有参考指标
        if self.config.compute_reference_metrics and gt_image is not None:
            # 1. 计算退化图 vs GT（基线）
            print(f"\n[INFO] 计算退化图的基线指标...")
            degraded_ref_metrics = self.evaluator.compute_reference_metrics(
                np.array(degraded_image),
                np.array(gt_image)
            )
            # 添加前缀 degraded_
            for key, val in degraded_ref_metrics.items():
                metrics[f'degraded_{key}'] = val
            print(f"  退化图指标: PSNR={degraded_ref_metrics['psnr']:.2f}, "
                  f"SSIM={degraded_ref_metrics['ssim']:.4f}, LPIPS={degraded_ref_metrics['lpips']:.4f}")
            
            # 2. 计算复原图 vs GT（评估）
            print(f"[INFO] 计算复原图的指标...")
            restored_ref_metrics = self.evaluator.compute_reference_metrics(
                np.array(restored_image),
                np.array(gt_image)
            )
            # 添加前缀 restored_
            for key, val in restored_ref_metrics.items():
                metrics[f'restored_{key}'] = val
            print(f"  复原图指标: PSNR={restored_ref_metrics['psnr']:.2f}, "
                  f"SSIM={restored_ref_metrics['ssim']:.4f}, LPIPS={restored_ref_metrics['lpips']:.4f}")
            
            # 3. 计算改善幅度
            print(f"[INFO] 计算改善幅度...")
            metrics['improvement_psnr'] = restored_ref_metrics['psnr'] - degraded_ref_metrics['psnr']
            metrics['improvement_ssim'] = restored_ref_metrics['ssim'] - degraded_ref_metrics['ssim']
            metrics['improvement_lpips'] = degraded_ref_metrics['lpips'] - restored_ref_metrics['lpips']  # LPIPS越小越好，所以用退化-复原
            
            print(f"  改善幅度: ΔPSNR={metrics['improvement_psnr']:+.2f}dB, "
                  f"ΔSSIM={metrics['improvement_ssim']:+.4f}, ΔLPIPS={metrics['improvement_lpips']:+.4f}")
            
            # 4. 计算改善百分比
            metrics['improvement_psnr_pct'] = (metrics['improvement_psnr'] / max(degraded_ref_metrics['psnr'], 0.1)) * 100
            metrics['improvement_ssim_pct'] = (metrics['improvement_ssim'] / max(degraded_ref_metrics['ssim'], 0.01)) * 100
            metrics['improvement_lpips_pct'] = (metrics['improvement_lpips'] / max(degraded_ref_metrics['lpips'], 0.01)) * 100
            
            print(f"  改善百分比: PSNR {metrics['improvement_psnr_pct']:+.1f}%, "
                  f"SSIM {metrics['improvement_ssim_pct']:+.1f}%, LPIPS {metrics['improvement_lpips_pct']:+.1f}%")
        
        # 无参考指标（仅复原图）
        if self.config.compute_no_reference_metrics:
            # 计算退化图的无参考指标
            print(f"\n[INFO] 计算退化图的无参考指标...")
            degraded_no_ref_metrics = self.evaluator.compute_no_reference_metrics(
                np.array(degraded_image)
            )
            for key, val in degraded_no_ref_metrics.items():
                metrics[f'degraded_{key}'] = val
            print(f"  退化图: {degraded_no_ref_metrics}")
            
            # 计算复原图的无参考指标
            print(f"[INFO] 计算复原图的无参考指标...")
            restored_no_ref_metrics = self.evaluator.compute_no_reference_metrics(
                np.array(restored_image)
            )
            for key, val in restored_no_ref_metrics.items():
                metrics[f'restored_{key}'] = val
            print(f"  复原图: {restored_no_ref_metrics}")
            
            # 计算改善（无参考指标都是越高越好）
            for key in restored_no_ref_metrics.keys():
                improvement = restored_no_ref_metrics[key] - degraded_no_ref_metrics[key]
                metrics[f'improvement_{key}'] = improvement
                metrics[f'improvement_{key}_pct'] = (improvement / max(degraded_no_ref_metrics[key], 0.01)) * 100
            
            print(f"  改善: ", end="")
            for key in restored_no_ref_metrics.keys():
                print(f"{key.upper()} {metrics[f'improvement_{key}']:+.4f} ({metrics[f'improvement_{key}_pct']:+.1f}%), ", end="")
            print()
        
        return {
            'conversation_history': conversation_history,
            'all_tool_results': all_tool_results,
            'metrics': metrics,
            'restored_image': restored_image,
            'degraded_image': degraded_image,  # 也保存退化图
            'gt_image': gt_image,  # 也保存GT图
            'gt_degradations': gt_degradations,
            'predicted_tools': [tr['tool_name'] for tr in all_tool_results if tr.get('success', False)]
        }
    
    def evaluate_dataset(self, data_path: str) -> pd.DataFrame:
        """评估整个数据集"""
        import pyarrow.parquet as pq
        
        # 读取parquet文件
        table = pq.read_table(data_path)
        df = table.to_pandas()
        
        print(f"[INFO] 加载数据集: {len(df)} 个样本")
        
        if self.config.num_samples is not None:
            df = df.head(self.config.num_samples)
            print(f"[INFO] 限制评估样本数: {len(df)}")
        
        # 评估每个样本
        results = []
        for idx, row in tqdm(df.iterrows(), total=len(df), desc="评估进度"):
            print(f"\n{'='*80}")
            print(f"[INFO] 评估样本 {idx + 1}/{len(df)}")
            print(f"{'='*80}")
            
            sample_result = self.evaluate_single_sample(row.to_dict())
            
            # 保存结果
            result_record = {
                'sample_id': idx,
                **sample_result['metrics'],
                'num_tools_used': len(sample_result['predicted_tools']),
                'tools_used': ','.join(sample_result['predicted_tools']),
                'gt_degradations': ','.join(sample_result['gt_degradations']) if sample_result['gt_degradations'] else '',
                'num_turns': len(sample_result['conversation_history'])
            }
            results.append(result_record)
            
            # 保存详细结果
            detail_path = Path(self.config.output_dir) / "details" / f"sample_{idx:04d}.json"
            detail_path.parent.mkdir(parents=True, exist_ok=True)
            with open(detail_path, 'w') as f:
                json.dump({
                    'sample_id': idx,
                    'conversation_history': sample_result['conversation_history'],
                    'tool_results': sample_result['all_tool_results'],
                    'metrics': sample_result['metrics']
                }, f, indent=2, ensure_ascii=False)
            
            # 保存图像（退化图、复原图、GT图）
            img_dir = Path(self.config.output_dir) / "images" / f"sample_{idx:04d}"
            img_dir.mkdir(parents=True, exist_ok=True)
            
            if sample_result.get('degraded_image') is not None:
                sample_result['degraded_image'].save(img_dir / "degraded.png")
            
            if sample_result.get('restored_image') is not None:
                sample_result['restored_image'].save(img_dir / "restored.png")
            
            if sample_result.get('gt_image') is not None:
                sample_result['gt_image'].save(img_dir / "gt.png")
        
        # 转换为DataFrame
        results_df = pd.DataFrame(results)
        
        # 计算统计信息
        self._print_statistics(results_df)
        
        # 保存结果
        output_path = Path(self.config.output_dir) / "evaluation_results.csv"
        results_df.to_csv(output_path, index=False)
        print(f"\n[INFO] 结果已保存到: {output_path}")
        
        # 保存汇总信息
        summary_path = Path(self.config.output_dir) / "summary.txt"
        with open(summary_path, 'w') as f:
            f.write(f"评估配置\n")
            f.write(f"{'='*80}\n")
            f.write(f"对话模式: {self.config.conversation_mode}\n")
            f.write(f"最大轮次: {self.config.max_turns}\n")
            f.write(f"样本数量: {len(results_df)}\n\n")
            
            f.write(f"评估指标统计\n")
            f.write(f"{'='*80}\n")
            f.write(results_df.describe().to_string())
        
        print(f"[INFO] 汇总信息已保存到: {summary_path}")
        
        return results_df
    
    def _print_statistics(self, results_df: pd.DataFrame):
        """打印统计信息"""
        print(f"\n{'='*80}")
        print("评估结果统计")
        print(f"{'='*80}")
        
        # 有参考指标 - 退化图基线
        if 'degraded_psnr' in results_df.columns:
            print(f"\n📉 退化图基线指标（vs GT）:")
            print(f"  PSNR:  Mean={results_df['degraded_psnr'].mean():.2f} ± {results_df['degraded_psnr'].std():.2f} dB")
            print(f"  SSIM:  Mean={results_df['degraded_ssim'].mean():.4f} ± {results_df['degraded_ssim'].std():.4f}")
            print(f"  LPIPS: Mean={results_df['degraded_lpips'].mean():.4f} ± {results_df['degraded_lpips'].std():.4f}")
        
        # 有参考指标 - 复原图
        if 'restored_psnr' in results_df.columns:
            print(f"\n📈 复原图指标（vs GT）:")
            print(f"  PSNR:  Mean={results_df['restored_psnr'].mean():.2f} ± {results_df['restored_psnr'].std():.2f} dB")
            print(f"  SSIM:  Mean={results_df['restored_ssim'].mean():.4f} ± {results_df['restored_ssim'].std():.4f}")
            print(f"  LPIPS: Mean={results_df['restored_lpips'].mean():.4f} ± {results_df['restored_lpips'].std():.4f}")
        
        # 改善幅度
        if 'improvement_psnr' in results_df.columns:
            print(f"\n✨ 改善幅度:")
            print(f"  ΔPSNR:  Mean={results_df['improvement_psnr'].mean():+.2f} ± {results_df['improvement_psnr'].std():.2f} dB ({results_df['improvement_psnr_pct'].mean():+.1f}%)")
            print(f"  ΔSSIM:  Mean={results_df['improvement_ssim'].mean():+.4f} ± {results_df['improvement_ssim'].std():.4f} ({results_df['improvement_ssim_pct'].mean():+.1f}%)")
            print(f"  ΔLPIPS: Mean={results_df['improvement_lpips'].mean():+.4f} ± {results_df['improvement_lpips'].std():.4f} ({results_df['improvement_lpips_pct'].mean():+.1f}%)")
        
        # 无参考指标 - 退化图
        if 'degraded_maniqa' in results_df.columns:
            print(f"\n📉 退化图无参考指标:")
            for metric in ['maniqa', 'musiq', 'clipiqa']:
                if f'degraded_{metric}' in results_df.columns:
                    print(f"  {metric.upper()}: Mean={results_df[f'degraded_{metric}'].mean():.4f} ± {results_df[f'degraded_{metric}'].std():.4f}")
        
        # 无参考指标 - 复原图
        if 'restored_maniqa' in results_df.columns:
            print(f"\n📈 复原图无参考指标:")
            for metric in ['maniqa', 'musiq', 'clipiqa']:
                if f'restored_{metric}' in results_df.columns:
                    print(f"  {metric.upper()}: Mean={results_df[f'restored_{metric}'].mean():.4f} ± {results_df[f'restored_{metric}'].std():.4f}")
        
        # 无参考指标改善
        if 'improvement_maniqa' in results_df.columns:
            print(f"\n✨ 无参考指标改善:")
            for metric in ['maniqa', 'musiq', 'clipiqa']:
                if f'improvement_{metric}' in results_df.columns:
                    print(f"  Δ{metric.upper()}: Mean={results_df[f'improvement_{metric}'].mean():+.4f} ({results_df[f'improvement_{metric}_pct'].mean():+.1f}%)")
        
        # 工具使用统计
        print(f"\n🔧 工具使用统计:")
        print(f"  平均使用工具数: {results_df['num_tools_used'].mean():.2f}")
        print(f"  平均对话轮次: {results_df['num_turns'].mean():.2f}")


def main():
    parser = argparse.ArgumentParser(description="Agent-based Image Restoration Evaluation")
    
    # API配置
    parser.add_argument('--api_key', type=str, default='EMPTY', help='OpenAI API key')
    parser.add_argument('--api_url', type=str, default='http://localhost:8000/v1', help='vLLM API URL')
    parser.add_argument('--model_name', type=str, default=None, help='Model name (auto-detect if None)')
    
    # 数据配置
    parser.add_argument('--data_path', type=str, required=True, help='Path to evaluation parquet file')
    parser.add_argument('--output_dir', type=str, default='./eval_results', help='Output directory')
    
    # Agent配置
    parser.add_argument('--conversation_mode', type=str, default='multi_tool_planning',
                       choices=['multi_tool_planning', 'single_tool_iterative'],
                       help='Conversation mode')
    parser.add_argument('--max_turns', type=int, default=1, help='Maximum conversation turns')
    parser.add_argument('--temperature', type=float, default=0.7, help='Sampling temperature')
    parser.add_argument('--top_p', type=float, default=0.9, help='Top-p sampling')
    
    # System Prompt配置
    parser.add_argument('--no_parquet_system_prompt', action='store_true',
                       help='Do not use system prompt from parquet file')
    parser.add_argument('--custom_system_prompt', type=str, default=None,
                       help='Path to custom system prompt file or direct prompt text')
    
    # User Prompt配置
    parser.add_argument('--no_parquet_user_prompt', action='store_true',
                       help='Do not use user prompt from parquet file')
    parser.add_argument('--custom_user_prompt', type=str, default=None,
                       help='Custom user prompt text')
    parser.add_argument('--no_degradation_hint', action='store_true',
                       help='Do not provide degradation type hints (test model diagnosis ability)')
    
    # 工具服务配置
    parser.add_argument('--tool_service_ip', type=str, default='10.21.9.6', help='Tool service IP')
    
    # 评估配置
    parser.add_argument('--num_samples', type=int, default=None, help='Number of samples to evaluate')
    parser.add_argument('--no_reference_metrics', action='store_true', help='Disable reference metrics')
    parser.add_argument('--no_no_reference_metrics', action='store_true', help='Disable no-reference metrics')
    
    args = parser.parse_args()
    
    # 处理自定义系统提示词
    custom_prompt = None
    if args.custom_system_prompt:
        # 检查是否是文件路径
        if os.path.exists(args.custom_system_prompt):
            with open(args.custom_system_prompt, 'r', encoding='utf-8') as f:
                custom_prompt = f.read()
            print(f"[INFO] 从文件加载自定义系统提示词: {args.custom_system_prompt}")
        else:
            # 直接使用作为提示词内容
            custom_prompt = args.custom_system_prompt
            print(f"[INFO] 使用命令行提供的自定义系统提示词")
    
    # 创建配置
    config = EvaluationConfig(
        api_key=args.api_key,
        api_url=args.api_url,
        model_name=args.model_name,
        data_path=args.data_path,
        output_dir=args.output_dir,
        conversation_mode=args.conversation_mode,
        max_turns=args.max_turns,
        temperature=args.temperature,
        top_p=args.top_p,
        use_parquet_system_prompt=not args.no_parquet_system_prompt,
        custom_system_prompt=custom_prompt,
        use_parquet_user_prompt=not args.no_parquet_user_prompt,
        custom_user_prompt=args.custom_user_prompt,
        provide_degradation_hint=not args.no_degradation_hint,
        tool_service_ip=args.tool_service_ip,
        num_samples=args.num_samples,
        compute_reference_metrics=not args.no_reference_metrics,
        compute_no_reference_metrics=not args.no_no_reference_metrics
    )
    
    # 创建输出目录
    Path(config.output_dir).mkdir(parents=True, exist_ok=True)
    
    # 保存配置
    config_path = Path(config.output_dir) / "config.json"
    with open(config_path, 'w') as f:
        json.dump(vars(config), f, indent=2)
    
    print(f"[INFO] 配置已保存到: {config_path}")
    
    # 开始评估
    evaluator = AgentRestoration(config)
    results_df = evaluator.evaluate_dataset(args.data_path)
    
    print(f"\n[INFO] 评估完成！结果保存在: {config.output_dir}")


if __name__ == "__main__":
    main()

