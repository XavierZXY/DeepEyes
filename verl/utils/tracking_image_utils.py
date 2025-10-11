# Copyright 2024 Bytedance Ltd. and/or its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Utilities for uploading rollout images to wandb
"""

import io
import re
import json
import numpy as np
from typing import List, Dict, Any, Optional
from PIL import Image


def extract_pil_image_from_data(image_data):
    """
    Extract PIL Image from various data formats
    
    Args:
        image_data: Can be PIL Image, dict with 'image' key, bytes, etc.
        
    Returns:
        PIL.Image or None
    """
    # Already a PIL Image
    if isinstance(image_data, Image.Image):
        return image_data
    
    # Dict with 'image' list
    if isinstance(image_data, dict) and 'image' in image_data:
        images = image_data['image']
        if isinstance(images, list) and len(images) > 0:
            return extract_pil_image_from_data(images[0])
    
    # Bytes data
    if isinstance(image_data, bytes):
        try:
            return Image.open(io.BytesIO(image_data))
        except Exception as e:
            print(f"[WARNING] Failed to decode image from bytes: {e}")
            return None
    
    # Dict with 'bytes' key
    if isinstance(image_data, dict) and 'bytes' in image_data:
        try:
            return Image.open(io.BytesIO(image_data['bytes']))
        except Exception as e:
            print(f"[WARNING] Failed to decode image from dict bytes: {e}")
            return None
    
    # Numpy array
    if isinstance(image_data, np.ndarray):
        try:
            if len(image_data.shape) == 3:
                return Image.fromarray(image_data.astype('uint8'))
            elif len(image_data.shape) == 2:
                return Image.fromarray(image_data.astype('uint8'), mode='L')
        except Exception as e:
            print(f"[WARNING] Failed to convert numpy array to image: {e}")
            return None
    
    print(f"[WARNING] Unsupported image data type: {type(image_data)}")
    return None


def create_trajectory_visualization(
    image_history: List, 
    conversation_text: Optional[str] = None,
    original_image: Optional[Any] = None,
    conversation_history: Optional[List[Dict]] = None,
    max_steps: int = 10,
    text_height: int = 300
):
    """
    Create a vertical layout with conversation text on top and trajectory images below
    
    Args:
        image_history: List of image data at each step (退化图在[0]，处理后的图在后面)
        conversation_text: Text containing system prompt, user input (初始prompt)
        original_image: Original image (ground truth, 未退化的原图，来自extra_info)
        conversation_history: List of intermediate conversations [{'turn': 1, 'response': '...', 'is_done': False}, ...]
        max_steps: Maximum number of steps to show
        text_height: Height reserved for text section
        
    Returns:
        PIL.Image showing the trajectory with conversation, or None if failed
    """
    if not image_history or len(image_history) == 0:
        return None
    
    # Extract PIL images from history
    pil_images = []
    
    # 1. 添加原图（如果有）
    if original_image is not None:
        original_pil = extract_pil_image_from_data(original_image)
        if original_pil is not None:
            pil_images.append(original_pil)
    
    # 2. 添加图像历史（退化图 + 处理过程）
    for img_data in image_history[:max_steps]:
        pil_img = extract_pil_image_from_data(img_data)
        if pil_img is not None:
            pil_images.append(pil_img)
    
    if len(pil_images) == 0:
        return None
    
    # 提取每个步骤的工具名称
    tool_names_per_step = []
    if conversation_history and len(conversation_history) > 0:
        print(f"[DEBUG TOOL NAMES] conversation_history length: {len(conversation_history)}")
        for conv_idx, conv in enumerate(conversation_history):
            response = conv.get('response', '')
            turn_num = conv.get('turn', '?')
            tool_match = re.search(r'<tool_call>(.*?)</tool_call>', response, re.DOTALL)
            
            if tool_match:
                try:
                    import json
                    tool_content = tool_match.group(1).strip()
                    tools = json.loads(tool_content)
                    if isinstance(tools, list) and len(tools) > 0:
                        # 提取所有工具名称
                        names = [t.get('name', '?') for t in tools if isinstance(t, dict)]
                        tool_name = ', '.join(names)
                        tool_names_per_step.append(tool_name)
                        print(f"[DEBUG TOOL NAMES] Turn {turn_num}: {tool_name}")
                    else:
                        tool_names_per_step.append('None')
                        print(f"[DEBUG TOOL NAMES] Turn {turn_num}: None (empty list)")
                except Exception as e:
                    tool_names_per_step.append('Parse Error')
                    print(f"[DEBUG TOOL NAMES] Turn {turn_num}: Parse Error - {e}")
            else:
                # 检查是否有answer
                answer_match = re.search(r'<answer>', response)
                if answer_match:
                    tool_names_per_step.append('Answer')
                    print(f"[DEBUG TOOL NAMES] Turn {turn_num}: Answer")
                else:
                    tool_names_per_step.append('None')
                    print(f"[DEBUG TOOL NAMES] Turn {turn_num}: None (no tool_call or answer)")
        
        print(f"[DEBUG TOOL NAMES] Total extracted: {tool_names_per_step}")
    else:
        print(f"[DEBUG TOOL NAMES] No conversation_history available")
    
    # Resize all images to the same height (use the first image's height)
    target_height = pil_images[0].height
    resized_images = []
    image_labels = []
    
    # 生成图像标签和工具名称
    has_original = original_image is not None
    for i, img in enumerate(pil_images):
        if img.height != target_height:
            aspect_ratio = img.width / img.height
            new_width = int(target_height * aspect_ratio)
            img = img.resize((new_width, target_height), Image.Resampling.LANCZOS)
        resized_images.append(img)
    
        # 添加标签和工具名称
        if has_original and i == 0:
            image_labels.append(("Ground Truth", ""))
        elif has_original and i == 1:
            image_labels.append(("Degraded Input", ""))
        elif not has_original and i == 0:
            image_labels.append(("Degraded Input", ""))
        elif i == len(pil_images) - 1:
            image_labels.append(("Restored", ""))
        else:
            # 中间处理步骤
            step_idx = i - 1 if has_original else i
            tool_name = tool_names_per_step[step_idx - 1] if step_idx > 0 and (step_idx - 1) < len(tool_names_per_step) else "None"
            image_labels.append((f"Step {step_idx}", tool_name))
    
    # Calculate total width for images (add padding and borders)
    padding = 15  # 增加间距
    border = 2  # 图像边框
    total_width = sum(img.width + 2*border for img in resized_images) + padding * (len(resized_images) - 1)
    
    # Add extra height for labels and tool names
    label_height = 30  # 上方标签高度
    tool_label_height = 40  # 下方工具名称高度
    
    # Create trajectory image with better layout
    trajectory_img = Image.new('RGB', (total_width, label_height + target_height + 2*border + tool_label_height), color='white')
    
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(trajectory_img)
    
    try:
        label_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except:
        try:
            label_font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 14)
        except:
            label_font = ImageFont.load_default()
    
    try:
        tool_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 9)
    except:
        try:
            tool_font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf", 9)
        except:
            tool_font = ImageFont.load_default()
    
    x_offset = 0
    for i, (img, label_tuple) in enumerate(zip(resized_images, image_labels)):
        # Unpack label tuple
        label, tool_name = label_tuple if isinstance(label_tuple, tuple) else (label_tuple, "")
        
        # Draw border
        draw.rectangle(
            [(x_offset, label_height), (x_offset + img.width + 2*border - 1, label_height + target_height + 2*border - 1)],
            outline='gray',
            width=border
        )
        
        # Paste image (inside border)
        trajectory_img.paste(img, (x_offset + border, label_height + border))
        
        # Draw label on top with background
        bbox = draw.textbbox((0, 0), label, font=label_font)
        text_width = bbox[2] - bbox[0]
        text_height_val = bbox[3] - bbox[1]
        text_x = x_offset + (img.width + 2*border - text_width) // 2  # Center text
        
        # Draw label background
        label_bg_color = 'lightblue' if 'Ground Truth' in label else ('lightgreen' if 'Restored' in label else 'lightyellow')
        draw.rectangle(
            [(text_x - 3, 3), (text_x + text_width + 3, 3 + text_height_val + 6)],
            fill=label_bg_color
        )
        
        # Draw label text
        draw.text((text_x, 5), label, fill='black', font=label_font)
        
        # Draw tool name below the image
        if tool_name:
            # 处理过长的工具名称
            display_tool_name = tool_name
            if len(tool_name) > 30:
                display_tool_name = tool_name[:27] + "..."
            
            tool_bbox = draw.textbbox((0, 0), display_tool_name, font=tool_font)
            tool_text_width = tool_bbox[2] - tool_bbox[0]
            tool_text_x = x_offset + (img.width + 2*border - tool_text_width) // 2  # Center text
            tool_y = label_height + target_height + 2*border + 5
            
            # Draw tool name with light background
            draw.rectangle(
                [(tool_text_x - 2, tool_y - 2), (tool_text_x + tool_text_width + 2, tool_y + 15)],
                fill='lightgray'
            )
            draw.text((tool_text_x, tool_y), display_tool_name, fill='darkblue', font=tool_font)
        
        x_offset += img.width + 2*border + padding
    
    # 直接返回图像轨迹（只有图片 + 顶部标签 + 底部工具名）
    # 不添加对话文本区域，用户可以在wandb表格中查看对话内容
    return trajectory_img


def build_conversation_text_with_history(
    raw_prompt: Any,
    model_response: str,
    conversation_history: Optional[List[Dict]] = None,
    system_prompt: Optional[str] = None,
    max_system_prompt_lines: int = 5,
) -> str:
    """
    Build conversation text including intermediate agent conversations
    
    Args:
        raw_prompt: Raw prompt data (could be list of messages or string)
        model_response: Model's final response text
        conversation_history: List of intermediate conversations
        system_prompt: System prompt text (shown once)
        max_system_prompt_lines: Maximum lines to show from system prompt
        
    Returns:
        Formatted conversation text with all turns
    """
    # First build initial conversation
    initial_text = build_conversation_text(raw_prompt, model_response, system_prompt, max_system_prompt_lines)
    
    # Add conversation history if available
    if conversation_history and len(conversation_history) > 0:
        import re
        import json
        
        initial_text += "\n\n=== AGENT CONVERSATION HISTORY ==="
        for conv in conversation_history:
            turn_num = conv.get('turn', '?')
            response = conv.get('response', '')
            
            initial_text += f"\n\n--- Turn {turn_num} ---"
            
            # Extract and format each component
            think_match = re.search(r'<think>(.*?)</think>', response, re.DOTALL)
            if think_match:
                think_content = think_match.group(1).strip()
                if len(think_content) > 150:
                    think_content = think_content[:147] + "..."
                initial_text += f"\n[Think] {think_content}"
            
            tool_match = re.search(r'<tool_call>(.*?)</tool_call>', response, re.DOTALL)
            if tool_match:
                try:
                    tools = json.loads(tool_match.group(1))
                    if isinstance(tools, list):
                        tool_names = [t.get('name', '?') for t in tools if isinstance(t, dict)]
                        initial_text += f"\n[Tools] {', '.join(tool_names)}"
                except:
                    initial_text += f"\n[Tools] (parse error)"
            
            answer_match = re.search(r'<answer>(.*?)</answer>', response, re.DOTALL)
            if answer_match:
                initial_text += f"\n[Answer] ✓ Done"
    
    return initial_text


def build_conversation_text(
    raw_prompt: Any,
    model_response: str,
    system_prompt: Optional[str] = None,
    max_system_prompt_lines: int = 5,
) -> str:
    """
    Build conversation text from raw prompt and model response
    
    Args:
        raw_prompt: Raw prompt data (could be list of messages or string)
        model_response: Model's response text
        system_prompt: System prompt (shown only once)
        max_system_prompt_lines: Maximum lines to show from system prompt
        
    Returns:
        Formatted conversation text
    """
    lines = []
    
    # Add system prompt (only once, truncated)
    if system_prompt:
        lines.append("=== SYSTEM (shown once, same for all) ===")
        system_lines = system_prompt.split('\n')
        if len(system_lines) > max_system_prompt_lines:
            lines.extend(system_lines[:max_system_prompt_lines])
            lines.append(f"... ({len(system_lines) - max_system_prompt_lines} more lines)")
        else:
            lines.extend(system_lines)
        lines.append("")
    
    # Add user input
    lines.append("=== USER ===")
    if isinstance(raw_prompt, list):
        # It's a conversation format
        for msg in raw_prompt:
            if isinstance(msg, dict):
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                if role == 'user':
                    lines.append(content)
            elif isinstance(msg, str):
                lines.append(msg)
    elif isinstance(raw_prompt, str):
        lines.append(raw_prompt)
    else:
        lines.append(str(raw_prompt))
    lines.append("")
    
    # Add model response
    lines.append("=== ASSISTANT ===")
    lines.append(model_response)
    
    return '\n'.join(lines)


def log_rollout_images_to_wandb(
    wandb_logger,
    batch_data: Dict,
    image_quality_scores: Optional[List[float]] = None,
    detailed_metrics: Optional[Dict[str, List]] = None,
    step: int = 0,
    mode: str = "train",
    num_samples_train: int = 5,
    num_best_worst: int = 2,
    tokenizer=None,
    system_prompt: Optional[str] = None,
):
    """
    Log rollout trajectory images to wandb
    
    Args:
        wandb_logger: wandb logger instance
        batch_data: Batch data containing image_history, raw_prompt, responses, original_images
        image_quality_scores: List of image quality scores (same order as batch)
        detailed_metrics: Dict containing detailed metrics (ssim, lpips, psnr, etc.)
        step: Current training step
        mode: "train" or "val"
        num_samples_train: Number of random samples to log during training
        num_best_worst: Number of best/worst samples to log during training
        tokenizer: Tokenizer for decoding responses
        system_prompt: System prompt text (shown once)
    """
    try:
        import wandb
    except ImportError:
        print("[WARNING] wandb not available, skipping image logging")
        return
    
    # Get data from batch
    image_histories = batch_data.get('image_history', [])
    raw_prompts = batch_data.get('raw_prompt', [])
    responses = batch_data.get('responses', [])  # Token IDs
    original_images = batch_data.get('original_images', [])  # 原图（ground truth，来自extra_info）
    conversation_histories = batch_data.get('conversation_history', [])  # 中间对话历史
    
    # 检查image_histories是否为空（兼容numpy数组和列表）
    if image_histories is None or len(image_histories) == 0:
        print(f"[DEBUG WANDB IMAGE] No image_history found in batch_data")
        return
    
    print(f"[DEBUG WANDB IMAGE] Found {len(image_histories)} image histories")
    print(f"[DEBUG WANDB IMAGE] Found {len(original_images) if original_images is not None else 0} original images")
    print(f"[DEBUG WANDB IMAGE] Found {len(conversation_histories) if conversation_histories is not None else 0} conversation histories")
    if detailed_metrics:
        print(f"[DEBUG WANDB IMAGE] Detailed metrics keys: {list(detailed_metrics.keys())}")
    
    # Validation mode: log all samples
    if mode == "val":
        images_to_log = []
        for idx, img_history in enumerate(image_histories):
            # 检查是否为空（兼容各种格式）
            if img_history is None:
                continue
            if isinstance(img_history, np.ndarray) and img_history.size == 0:
                continue
            if isinstance(img_history, list) and len(img_history) == 0:
                continue
            
            # Build conversation text
            conversation_text = None
            if idx < len(raw_prompts) and idx < len(responses):
                try:
                    raw_prompt = raw_prompts[idx]
                    # Decode response
                    if tokenizer is not None:
                        response_ids = responses[idx]
                        model_response = tokenizer.decode(response_ids, skip_special_tokens=True)
                    else:
                        model_response = str(responses[idx])
                    
                    # Only show system prompt for the first sample
                    sp = system_prompt if idx == 0 else None
                    conversation_text = build_conversation_text(raw_prompt, model_response, sp)
                except Exception as e:
                    print(f"[WARNING] Failed to build conversation text for sample {idx}: {e}")
            
            # 获取原图（如果有）
            original_img = None
            if idx < len(original_images) and original_images[idx] is not None:
                original_img = original_images[idx]
            
            trajectory_img = create_trajectory_visualization(img_history, conversation_text, original_img)
            if trajectory_img is not None:
                caption = f"Val Sample {idx}"
                if image_quality_scores is not None and idx < len(image_quality_scores):
                    caption += f" | Quality: {image_quality_scores[idx]:.3f}"
                
                # 添加详细指标到caption（有参考和无参考都显示）
                if detailed_metrics:
                    # Debug: 打印前3个样本的指标值
                    if idx < 3:
                        print(f"[DEBUG CAPTION] Sample {idx}: Building caption with detailed_metrics")
                        if 'ssim_score_ref' in detailed_metrics:
                            print(f"[DEBUG CAPTION] Sample {idx}: ssim_score_ref[{idx}] = {detailed_metrics['ssim_score_ref'][idx] if idx < len(detailed_metrics['ssim_score_ref']) else 'OUT OF RANGE'}")
                        if 'lpips_score_ref' in detailed_metrics:
                            print(f"[DEBUG CAPTION] Sample {idx}: lpips_score_ref[{idx}] = {detailed_metrics['lpips_score_ref'][idx] if idx < len(detailed_metrics['lpips_score_ref']) else 'OUT OF RANGE'}")
                        if 'psnr_score_ref' in detailed_metrics:
                            print(f"[DEBUG CAPTION] Sample {idx}: psnr_score_ref[{idx}] = {detailed_metrics['psnr_score_ref'][idx] if idx < len(detailed_metrics['psnr_score_ref']) else 'OUT OF RANGE'}")
                    
                    # 退化类型（优先显示）
                    if 'degradation_type' in detailed_metrics and idx < len(detailed_metrics['degradation_type']):
                        deg_type = detailed_metrics['degradation_type'][idx]
                        caption += f" | Type: {deg_type}"
                    # 有参考指标（基于GT）
                    if 'ssim_score_ref' in detailed_metrics and idx < len(detailed_metrics['ssim_score_ref']):
                        ssim_val = detailed_metrics['ssim_score_ref'][idx]
                        caption += f" | SSIM: {ssim_val:.3f}"
                        if idx < 3:
                            print(f"[DEBUG CAPTION] Sample {idx}: Added SSIM={ssim_val:.3f} to caption")
                    if 'lpips_score_ref' in detailed_metrics and idx < len(detailed_metrics['lpips_score_ref']):
                        lpips_val = detailed_metrics['lpips_score_ref'][idx]
                        caption += f" | LPIPS: {lpips_val:.3f}"
                        if idx < 3:
                            print(f"[DEBUG CAPTION] Sample {idx}: Added LPIPS={lpips_val:.3f} to caption")
                    if 'psnr_score_ref' in detailed_metrics and idx < len(detailed_metrics['psnr_score_ref']):
                        psnr_val = detailed_metrics['psnr_score_ref'][idx]
                        caption += f" | PSNR: {psnr_val:.1f}"
                        if idx < 3:
                            print(f"[DEBUG CAPTION] Sample {idx}: Added PSNR={psnr_val:.1f} to caption")
                    # 无参考指标
                    if 'niqe_score' in detailed_metrics and idx < len(detailed_metrics['niqe_score']):
                        caption += f" | NIQE: {detailed_metrics['niqe_score'][idx]:.2f}"
                
                if idx < 3:
                    print(f"[DEBUG CAPTION] Sample {idx}: Final caption = {caption}")
                
                images_to_log.append(wandb.Image(trajectory_img, caption=caption))
        
        if len(image_histories) > 0:
            # 直接记录到表格，不需要独立的Media上传
            print(f"[DEBUG WANDB IMAGE] Logging {len(image_histories)} validation samples to table...")
            
            # 记录到对话表格（包含图片）
            _log_conversation_table(
                wandb_logger=wandb_logger,
                image_histories=image_histories,
                raw_prompts=raw_prompts,
                responses=responses,
                conversation_histories=conversation_histories,
                original_images=original_images,
                image_quality_scores=image_quality_scores,
                tokenizer=tokenizer,
                step=step,
                mode=mode,
                indices=list(range(len(image_histories)))
            )
            
            print(f"[DEBUG WANDB IMAGE] ✓ Successfully logged {len(image_histories)} validation samples to table")
    
    # Training mode: sample strategically
    else:
        batch_size = len(image_histories)
        
        # Filter out empty histories
        valid_indices = []
        for idx, img_history in enumerate(image_histories):
            if img_history is None:
                continue
            if isinstance(img_history, np.ndarray):
                if img_history.size > 0:
                    valid_indices.append(idx)
            elif isinstance(img_history, list):
                if len(img_history) > 0:
                    valid_indices.append(idx)
            else:
                # 其他类型，假设非空
                    valid_indices.append(idx)
        
        if len(valid_indices) == 0:
            print(f"[DEBUG WANDB IMAGE] No valid image histories found")
            return
        
        print(f"[DEBUG WANDB IMAGE] Found {len(valid_indices)} valid histories out of {batch_size}")
        
        selected_indices = []
        worst_samples = []
        best_samples = []
        
        # 1. Select best and worst by image quality (if scores provided)
        if image_quality_scores is not None and len(image_quality_scores) > 0:
            # Filter scores for valid indices only
            valid_scores = [(idx, image_quality_scores[idx]) for idx in valid_indices if idx < len(image_quality_scores)]
            
            if len(valid_scores) > 0:
                # Sort by score
                sorted_by_score = sorted(valid_scores, key=lambda x: x[1])
                
                # Get worst samples (lowest quality)
                worst_samples = [idx for idx, _ in sorted_by_score[:num_best_worst]]
                selected_indices.extend(worst_samples)
                
                # Get best samples (highest quality)
                best_samples = [idx for idx, _ in sorted_by_score[-num_best_worst:]]
                selected_indices.extend(best_samples)
                
                print(f"[DEBUG WANDB IMAGE] Selected {len(worst_samples)} worst and {len(best_samples)} best samples")
        
        # 2. Random sample from remaining valid indices
        remaining_indices = [idx for idx in valid_indices if idx not in selected_indices]
        if len(remaining_indices) > 0:
            num_random = min(num_samples_train, len(remaining_indices))
            random_indices = np.random.choice(remaining_indices, size=num_random, replace=False).tolist()
            selected_indices.extend(random_indices)
            print(f"[DEBUG WANDB IMAGE] Selected {len(random_indices)} random samples")
        
        # Create visualizations
        images_to_log = []
        for vis_idx, idx in enumerate(selected_indices):
            img_history = image_histories[idx]
            
            # Build conversation text
            conversation_text = None
            if idx < len(raw_prompts) and idx < len(responses):
                try:
                    raw_prompt = raw_prompts[idx]
                    # Decode response
                    if tokenizer is not None:
                        response_ids = responses[idx]
                        model_response = tokenizer.decode(response_ids, skip_special_tokens=True)
                    else:
                        model_response = str(responses[idx])
                    
                    # Only show system prompt for the first visualization
                    sp = system_prompt if vis_idx == 0 else None
                    conversation_text = build_conversation_text(raw_prompt, model_response, sp)
                except Exception as e:
                    print(f"[WARNING] Failed to build conversation text for sample {idx}: {e}")
            
            # 获取原图（如果有）
            original_img = None
            if idx < len(original_images) and original_images[idx] is not None:
                original_img = original_images[idx]
            
            # 获取对话历史（如果有）
            conv_hist = None
            if idx < len(conversation_histories) and conversation_histories[idx] is not None:
                conv_hist = conversation_histories[idx]
            
            trajectory_img = create_trajectory_visualization(img_history, conversation_text, original_img, conv_hist)
            
            if trajectory_img is not None:
                # Create caption
                caption = f"Sample {idx}"
                if image_quality_scores is not None and idx < len(image_quality_scores):
                    quality = image_quality_scores[idx]
                    caption += f" | Quality: {quality:.3f}"
                    
                    # Add tag for best/worst
                    if idx in worst_samples:
                        caption += " [WORST]"
                    elif idx in best_samples:
                        caption += " [BEST]"
                
                # 添加详细指标到caption（显示有参考和无参考）
                if detailed_metrics:
                    # Debug: 对于worst和best样本打印指标值
                    if idx in (worst_samples + best_samples):
                        print(f"[DEBUG TRAIN CAPTION] Sample {idx}: Building caption with detailed_metrics")
                        if 'ssim_score_ref' in detailed_metrics and idx < len(detailed_metrics['ssim_score_ref']):
                            print(f"[DEBUG TRAIN CAPTION] Sample {idx}: ssim_score_ref[{idx}] = {detailed_metrics['ssim_score_ref'][idx]}")
                        if 'lpips_score_ref' in detailed_metrics and idx < len(detailed_metrics['lpips_score_ref']):
                            print(f"[DEBUG TRAIN CAPTION] Sample {idx}: lpips_score_ref[{idx}] = {detailed_metrics['lpips_score_ref'][idx]}")
                        if 'psnr_score_ref' in detailed_metrics and idx < len(detailed_metrics['psnr_score_ref']):
                            print(f"[DEBUG TRAIN CAPTION] Sample {idx}: psnr_score_ref[{idx}] = {detailed_metrics['psnr_score_ref'][idx]}")
                    
                    # 退化类型（优先显示）
                    if 'degradation_type' in detailed_metrics and idx < len(detailed_metrics['degradation_type']):
                        deg_type = detailed_metrics['degradation_type'][idx]
                        caption += f" | Type: {deg_type}"
                    # 有参考指标
                    if 'ssim_score_ref' in detailed_metrics and idx < len(detailed_metrics['ssim_score_ref']):
                        ssim_val = detailed_metrics['ssim_score_ref'][idx]
                        caption += f" | SSIM: {ssim_val:.3f}"
                    if 'lpips_score_ref' in detailed_metrics and idx < len(detailed_metrics['lpips_score_ref']):
                        lpips_val = detailed_metrics['lpips_score_ref'][idx]
                        caption += f" | LPIPS: {lpips_val:.3f}"
                    if 'psnr_score_ref' in detailed_metrics and idx < len(detailed_metrics['psnr_score_ref']):
                        psnr_val = detailed_metrics['psnr_score_ref'][idx]
                        caption += f" | PSNR: {psnr_val:.1f}"
                    # 无参考指标
                    if 'niqe_score' in detailed_metrics and idx < len(detailed_metrics['niqe_score']):
                        niqe_val = detailed_metrics['niqe_score'][idx]
                        caption += f" | NIQE: {niqe_val:.2f}"
                    
                    if idx in (worst_samples + best_samples):
                        print(f"[DEBUG TRAIN CAPTION] Sample {idx}: Final caption = {caption}")
                
                images_to_log.append(wandb.Image(trajectory_img, caption=caption))
        
        if len(selected_indices) > 0:
            # 直接记录到表格（包含图片）
            print(f"[DEBUG WANDB IMAGE] Logging {len(selected_indices)} training samples to table...")
            
            # 记录到对话表格
            _log_conversation_table(
                wandb_logger=wandb_logger,
                image_histories=image_histories,
                raw_prompts=raw_prompts,
                responses=responses,
                conversation_histories=conversation_histories,
                original_images=original_images,
                image_quality_scores=image_quality_scores,
                tokenizer=tokenizer,
                step=step,
                mode=mode,
                indices=selected_indices
            )
            
            print(f"[DEBUG WANDB IMAGE] ✓ Successfully logged {len(selected_indices)} training samples to table")


def _log_images_by_step(
    wandb_logger,
    images_to_log: List,
    image_histories: List,
    raw_prompts: List,
    responses: List,
    conversation_histories: List,
    original_images: List,
    image_quality_scores: Optional[List[float]],
    detailed_metrics: Optional[Dict[str, List]],
    tokenizer,
    step: int,
    mode: str,
    indices: List[int],
):
    """
    记录validation图像和汇总统计指标（不记录每个sample的单独指标）
    """
    try:
        import wandb
    except ImportError:
        return
    
    # 1. 记录所有图像（wandb会自动提供slider）
    wandb_logger.log({f"{mode}/step{step}/trajectories": images_to_log}, step=step)
    
    # 2. 只记录汇总统计指标（所有step共享同一个图表，横坐标为step）
    if image_quality_scores and len(image_quality_scores) > 0:
        valid_scores = [s for s in image_quality_scores if s > 0]
        if valid_scores:
            wandb_logger.log({
                f"{mode}/quality_mean": sum(valid_scores) / len(valid_scores),
                f"{mode}/quality_max": max(valid_scores),
                f"{mode}/quality_min": min(valid_scores),
            }, step=step)
    
    # 3. 记录有参考指标的汇总统计（所有step共享同一个图表）
    if detailed_metrics:
        if 'ssim_score_ref' in detailed_metrics:
            ssim_vals = [s for s in detailed_metrics['ssim_score_ref'] if s > 0]
            if ssim_vals:
                wandb_logger.log({
                    f"{mode}/ssim_mean": sum(ssim_vals) / len(ssim_vals),
                    f"{mode}/ssim_max": max(ssim_vals),
                }, step=step)
        
        if 'lpips_score_ref' in detailed_metrics:
            lpips_vals = [s for s in detailed_metrics['lpips_score_ref'] if s > 0]
            if lpips_vals:
                wandb_logger.log({
                    f"{mode}/lpips_mean": sum(lpips_vals) / len(lpips_vals),
                    f"{mode}/lpips_min": min(lpips_vals),
                }, step=step)
        
        if 'psnr_score_ref' in detailed_metrics:
            psnr_vals = [s for s in detailed_metrics['psnr_score_ref'] if s > 0]
            if psnr_vals:
                wandb_logger.log({
                    f"{mode}/psnr_mean": sum(psnr_vals) / len(psnr_vals),
                    f"{mode}/psnr_max": max(psnr_vals),
                }, step=step)
    
    print(f"[DEBUG WANDB STEP] ✓ Logged step{step} images and aggregated metrics for {len(indices)} samples")


def _log_conversation_table(
    wandb_logger,
    image_histories: List,
    raw_prompts: List,
    responses: List,
    conversation_histories: List,
    original_images: List,
    image_quality_scores: Optional[List[float]],
    tokenizer,
    step: int,
    mode: str,
    indices: List[int],
):
    """
    Log conversation details as a wandb Table with cumulative updates
    每个turn单独一列，对话不截断，质量分数准确，按step累积保存
    """
    try:
        import wandb
        import json
    except ImportError:
        return
    
    # 添加调试信息
    print(f"[DEBUG CONV TABLE] {mode} mode: len(image_histories)={len(image_histories)}, len(conversation_histories)={len(conversation_histories)}, len(responses)={len(responses)}, len(indices)={len(indices)}")
    
    if len(conversation_histories) > 0:
        print(f"[DEBUG CONV TABLE] conversation_histories[0] type: {type(conversation_histories[0])}, value: {conversation_histories[0] if conversation_histories[0] is not None else 'None'}")
    else:
        print(f"[DEBUG CONV TABLE] ⚠️  conversation_histories is empty!")
    
    if len(responses) > 0:
        print(f"[DEBUG CONV TABLE] responses[0] type: {type(responses[0])}, tokenizer: {tokenizer is not None}")
    else:
        print(f"[DEBUG CONV TABLE] ⚠️  responses is empty!")
    
    # 固定最大turn数（避免列数动态变化）
    MAX_TURNS = 5  # 根据max_turns配置调整
    
    # 创建固定列：基础信息 + 图像轨迹 + 每个turn的think和tools
    columns = ["Step", "Sample_ID", "Trajectory_Image", "Quality_Score", "Num_Tools", "User_Input"]
    for turn_idx in range(MAX_TURNS):
        columns.append(f"Turn{turn_idx+1}_Think")
        columns.append(f"Turn{turn_idx+1}_Tools")
    
    # 使用累积table（类似ValidationGenerationsLogger的实现）
    table_key = f"{mode}_conversation_table"
    if not hasattr(_log_conversation_table, table_key):
        # 第一次调用，创建新table
        setattr(_log_conversation_table, table_key, wandb.Table(columns=columns))
    
    # 获取现有table
    existing_table = getattr(_log_conversation_table, table_key)
    
    # 创建新table with existing data
    new_table = wandb.Table(columns=columns, data=existing_table.data)
    
    # 准备新行
    rows_added = 0
    for idx in indices:
        # 不再跳过image_history为None的样本，对话数据与图片无关
        
        # 获取图片历史（可能为None）
        img_hist = image_histories[idx] if idx < len(image_histories) else None
        
        # 获取质量分数
        quality = 0.0
        if image_quality_scores is not None and idx < len(image_quality_scores):
            quality = float(image_quality_scores[idx])
        
        # 统计工具数量（如果没有图片历史则为0）
        num_tools = 0
        if img_hist is not None and isinstance(img_hist, (list, tuple)):
            num_tools = max(0, len(img_hist) - 1)
        
        # 获取用户输入（增强版，支持多种格式）
        user_input = ""
        if idx < len(raw_prompts):
            raw_prompt = raw_prompts[idx]
            
            # 调试第一个样本
            if idx == 0:
                print(f"[DEBUG USER INPUT] raw_prompt type: {type(raw_prompt)}")
            
            # 处理OpenAI消息格式（列表）
            if isinstance(raw_prompt, list):
                for msg in raw_prompt:
                    if isinstance(msg, dict) and msg.get('role') == 'user':
                        user_input = msg.get('content', '')
                        break
            # 处理字符串格式
            elif isinstance(raw_prompt, str):
                user_input = raw_prompt
            # 处理其他格式（numpy等）
            elif raw_prompt is not None:
                user_input = str(raw_prompt)
            
            if idx == 0:
                print(f"[DEBUG USER INPUT] Extracted user_input length: {len(user_input)}")
        
        # 创建trajectory图像（用于表格显示）
        trajectory_img = None
        if img_hist is not None:
            # 获取原图和对话历史
            original_img = original_images[idx] if idx < len(original_images) else None
            conv_hist = conversation_histories[idx] if idx < len(conversation_histories) else None
            
            # 创建可视化图像
            trajectory_img = create_trajectory_visualization(
                image_history=img_hist,
                conversation_text=None,  # 不添加文本，节省空间
                original_image=original_img,
                conversation_history=conv_hist
            )
            
            if trajectory_img is not None:
                # 转换为wandb.Image对象
                trajectory_img = wandb.Image(trajectory_img)
        
        # 构建行数据（添加trajectory_img列）
        row = [step, f"{mode}_step{step}_idx{idx}", trajectory_img, quality, num_tools, user_input]
        
        # 提取每个turn的内容
        turn_data = {}
        
        # 优先从conversation_histories提取（训练时有）
        has_conv_hist = False
        if idx < len(conversation_histories) and conversation_histories[idx] is not None:
            conv_hist = conversation_histories[idx]
            if isinstance(conv_hist, list) and len(conv_hist) > 0:
                has_conv_hist = True
                if idx == 0:
                    print(f"[DEBUG CONV TABLE] Sample 0: Extracting from conversation_history, len={len(conv_hist)}")
                for turn in conv_hist:
                    turn_num = turn.get('turn', 1)
                    response = turn.get('response', '')
                    
                    # 提取think（完整）
                    think_text = ""
                    think_match = re.search(r'<think>(.*?)</think>', response, re.DOTALL)
                    if think_match:
                        think_text = think_match.group(1).strip()
                    
                    # 提取tools（完整JSON）
                    tools_text = ""
                    tool_match = re.search(r'<tool_call>(.*?)</tool_call>', response, re.DOTALL)
                    if tool_match:
                        tools_text = tool_match.group(1).strip()
                    elif '<answer>' in response:
                        tools_text = "[ANSWER]"
                    
                    turn_data[turn_num] = {
                        'think': think_text,
                        'tools': tools_text
                    }
        
        # 如果没有conversation_history或为空，从responses提取（验证时的情况）
        if not has_conv_hist and idx < len(responses) and tokenizer:
            if idx == 0:
                print(f"[DEBUG CONV TABLE] Sample 0: No conversation_history, extracting from responses")
            try:
                # Validation可能没有保存conversation_history，从最终response中提取
                response_ids = responses[idx]
                
                # 处理tensor类型
                import torch
                if isinstance(response_ids, torch.Tensor):
                    response_ids = response_ids.cpu().tolist()
                
                full_response = tokenizer.decode(response_ids, skip_special_tokens=True)
                
                if idx == 0:  # 只打印第一个样本的调试信息
                    print(f"[DEBUG CONV TABLE] Extracting from response: {full_response[:100]}...")
                
                # 尝试分割多个turn
                turn_matches = list(re.finditer(r'<think>(.*?)</think>', full_response, re.DOTALL))
                for turn_idx, match in enumerate(turn_matches):
                    turn_num = turn_idx + 1
                    # 找这个turn的范围
                    start_pos = match.start()
                    end_pos = turn_matches[turn_idx + 1].start() if turn_idx + 1 < len(turn_matches) else len(full_response)
                    turn_content = full_response[start_pos:end_pos]
                    
                    # 提取think
                    think_match = re.search(r'<think>(.*?)</think>', turn_content, re.DOTALL)
                    think_text = think_match.group(1).strip() if think_match else ""
                    
                    # 提取tools
                    tools_text = ""
                    tool_match = re.search(r'<tool_call>(.*?)</tool_call>', turn_content, re.DOTALL)
                    if tool_match:
                        tools_text = tool_match.group(1).strip()
                    elif '<answer>' in turn_content:
                        tools_text = "[ANSWER]"
                    
                    turn_data[turn_num] = {'think': think_text, 'tools': tools_text}
                
                if idx == 0 and len(turn_data) > 0:
                    print(f"[DEBUG CONV TABLE] Extracted {len(turn_data)} turns from response")
            except Exception as e:
                print(f"[WARNING CONV TABLE] Failed to extract turns from response at idx={idx}: {e}")
        
        # 填充每个turn的列
        for turn_idx in range(MAX_TURNS):
            turn_num = turn_idx + 1
            if turn_num in turn_data:
                row.append(turn_data[turn_num]['think'])
                row.append(turn_data[turn_num]['tools'])
            else:
                row.append("")  # Think为空
                row.append("")  # Tools为空
        
        # 调试：打印第一行的内容
        if idx == 0:
            print(f"[DEBUG CONV TABLE] First row data: quality={quality}, num_tools={num_tools}, user_input_len={len(user_input)}, turn_data_count={len(turn_data)}, total_cols={len(row)}")
        
        new_table.add_data(*row)
        rows_added += 1
    
    # 更新并上传
    old_count = len(existing_table.data)
    new_count = len(new_table.data)
    print(f"[DEBUG WANDB TABLE] {mode} mode: old_count={old_count}, new_count={new_count}, rows_added={rows_added}, should_upload={new_count > old_count}")
    
    if new_count > old_count:
        wandb_logger.log({f"{mode}/conversation_details": new_table}, step=step)
        setattr(_log_conversation_table, table_key, new_table)
        new_rows = new_count - old_count
        print(f"[DEBUG WANDB TABLE] ✓ Added {new_rows} rows to {mode}/conversation_details (total: {new_count} rows)")
    else:
        print(f"[DEBUG WANDB TABLE] ⚠️  No new rows added (rows_added={rows_added}), table not uploaded")


def save_conversations_to_markdown(
    batch_data: Dict,
    image_quality_scores: Optional[List[float]],
    detailed_metrics: Optional[Dict[str, List]],
    step: int,
    mode: str,
    tokenizer,
    output_dir: str,
):
    """
    Save conversations to markdown file for local viewing
    
    Args:
        batch_data: Batch data containing all information
        image_quality_scores: List of quality scores
        detailed_metrics: Dict of detailed metrics
        step: Current step
        mode: "train" or "val"
        tokenizer: Tokenizer
        output_dir: Output directory for markdown files
    """
    import os
    import json
    from datetime import datetime
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Create filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{output_dir}/{mode}_step{step}_{timestamp}.md"
    
    image_histories = batch_data.get('image_history', [])
    raw_prompts = batch_data.get('raw_prompt', [])
    responses = batch_data.get('responses', [])
    conversation_histories = batch_data.get('conversation_history', [])
    
    # Build markdown content
    lines = [
        f"# {mode.upper()} Conversations - Step {step}",
        f"",
        f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total samples: {len(image_histories)}",
        f"",
        "---",
        ""
    ]
    
    for idx in range(len(image_histories)):
        img_hist = image_histories[idx]
        quality = image_quality_scores[idx] if image_quality_scores and idx < len(image_quality_scores) else 0.0
        
        # Count tools
        num_tools = 0
        if isinstance(img_hist, (list, tuple)):
            num_tools = max(0, len(img_hist) - 1)
        
        lines.append(f"## Sample {idx}")
        lines.append(f"")
        lines.append(f"**Quality Score**: {quality:.3f} | **Tools Used**: {num_tools}")
        
        # Add detailed metrics
        if detailed_metrics:
            metrics_line = "**Metrics**: "
            if 'ssim_score' in detailed_metrics and idx < len(detailed_metrics['ssim_score']):
                metrics_line += f"SSIM={detailed_metrics['ssim_score'][idx]:.3f} "
            if 'lpips_score' in detailed_metrics and idx < len(detailed_metrics['lpips_score']):
                metrics_line += f"LPIPS={detailed_metrics['lpips_score'][idx]:.3f} "
            if 'psnr_score' in detailed_metrics and idx < len(detailed_metrics['psnr_score']):
                metrics_line += f"PSNR={detailed_metrics['psnr_score'][idx]:.1f}"
            lines.append(metrics_line)
        
        lines.append("")
        
        # User input
        if idx < len(raw_prompts):
            lines.append("### 用户输入")
            lines.append("```")
            raw_prompt = raw_prompts[idx]
            if isinstance(raw_prompt, list):
                for msg in raw_prompt:
                    if isinstance(msg, dict) and msg.get('role') == 'user':
                        lines.append(msg.get('content', ''))
            lines.append("```")
            lines.append("")
        
        # Agent conversation history
        if idx < len(conversation_histories) and conversation_histories[idx]:
            conv_hist = conversation_histories[idx]
            if isinstance(conv_hist, list) and len(conv_hist) > 0:
                lines.append("### Agent执行过程")
                for turn in conv_hist:
                    turn_num = turn.get('turn', '?')
                    response = turn.get('response', '')
                    
                    lines.append(f"")
                    lines.append(f"**Turn {turn_num}**")
                    
                    # Extract think
                    think_match = re.search(r'<think>(.*?)</think>', response, re.DOTALL)
                    if think_match:
                        lines.append("- **Think**: " + think_match.group(1).strip()[:200])
                    
                    # Extract tools
                    tool_match = re.search(r'<tool_call>(.*?)</tool_call>', response, re.DOTALL)
                    if tool_match:
                        try:
                            tools = json.loads(tool_match.group(1))
                            if isinstance(tools, list):
                                for tool in tools:
                                    if isinstance(tool, dict):
                                        lines.append(f"- **Tool**: {tool.get('name', '?')}")
                                        args = tool.get('arguments', {})
                                        if args:
                                            lines.append(f"  - Args: {json.dumps(args, ensure_ascii=False)}")
                        except:
                            lines.append("- **Tool**: [parse error]")
                    
                    # Extract answer
                    if '<answer>' in response:
                        lines.append("- **Answer**: ✓ Done")
                
                lines.append("")
        
        # Final response
        if idx < len(responses) and tokenizer:
            lines.append("### 最终响应")
            lines.append("```")
            response_ids = responses[idx]
            final_text = tokenizer.decode(response_ids, skip_special_tokens=True)
            lines.append(final_text[:500])  # 截断
            lines.append("```")
        
        lines.append("")
        lines.append("---")
        lines.append("")
    
    # Write to file
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"[DEBUG MARKDOWN] ✓ Saved conversations to {filename}")


def compute_reference_metrics_for_batch(
    batch_data: Dict,
    reward_extra_infos_dict: Dict,
) -> Dict[str, List]:
    """
    为batch中有original_image且工具已执行的样本计算有参考指标
    
    直接使用batch_data中的original_images（真正的GT）和image_history[-1]（复原图）
    计算PSNR, SSIM, LPIPS
    
    Args:
        batch_data: 包含image_history和original_images的batch数据
        reward_extra_infos_dict: 现有的reward信息
        
    Returns:
        Dict包含有参考指标的列表（工具未执行的样本为0.0）
    """
    try:
        from verl.utils.reward_score.image_quality_metrics import get_image_quality_metrics
    except ImportError:
        print("[WARNING] Image quality metrics not available")
        return {'ssim_score_ref': [], 'lpips_score_ref': [], 'psnr_score_ref': []}
    
    image_histories = batch_data.get('image_history', [])
    original_images = batch_data.get('original_images', [])
    
    # 添加调试信息
    print(f"[DEBUG REF METRICS] len(image_histories)={len(image_histories)}, len(original_images)={len(original_images)}")
    if len(original_images) > 0:
        print(f"[DEBUG REF METRICS] original_images[0] type: {type(original_images[0])}, is None: {original_images[0] is None}")
    
    # 初始化结果列表（默认0.0，工具未执行或计算失败的样本）
    num_samples = len(image_histories)
    ssim_scores = [0.0] * num_samples
    lpips_scores = [0.0] * num_samples
    psnr_scores = [0.0] * num_samples
    
    # 使用全局单例（避免重复初始化模型）
    metrics_calculator = get_image_quality_metrics()
    
    # 对每个样本计算有参考指标
    calculated_count = 0
    skip_reasons = {"no_original_image": 0, "no_image_history": 0, "tool_not_executed": 0, "extraction_failed": 0, "calculation_failed": 0}
    
    for idx in range(num_samples):
        # 检查是否有original_image
        if idx >= len(original_images):
            skip_reasons["no_original_image"] += 1
            continue
        
        if original_images[idx] is None:
            skip_reasons["no_original_image"] += 1
            if idx < 3:  # 只打印前3个
                print(f"[DEBUG REF METRICS] Sample {idx}: SKIP - original_images[idx] is None")
            continue
        
        # 检查是否有image_history且工具已执行
        if idx >= len(image_histories):
            skip_reasons["no_image_history"] += 1
            continue
        
        img_hist = image_histories[idx]
        if img_hist is None:
            skip_reasons["tool_not_executed"] += 1
            continue
        
        if not isinstance(img_hist, (list, tuple)):
            skip_reasons["tool_not_executed"] += 1
            if idx < 3:
                print(f"[DEBUG REF METRICS] Sample {idx}: SKIP - img_hist not list/tuple, type={type(img_hist)}")
            continue
        
        if len(img_hist) < 2:
            skip_reasons["tool_not_executed"] += 1
            if idx < 3:
                print(f"[DEBUG REF METRICS] Sample {idx}: SKIP - img_hist length {len(img_hist)} < 2 (工具未执行)")
            continue
        
        try:
            # 提取复原图
            if idx < 3:
                print(f"[DEBUG REF METRICS] Sample {idx}: Extracting restored image from img_hist[-1], type={type(img_hist[-1])}...")
            restored_img = extract_pil_image_from_data(img_hist[-1])
            if restored_img is None:
                skip_reasons["extraction_failed"] += 1
                if idx < 3:
                    print(f"[DEBUG REF METRICS] Sample {idx}: SKIP - restored_img is None after extraction")
                continue
            if idx < 3:
                print(f"[DEBUG REF METRICS] Sample {idx}: Restored image size: {restored_img.size}")
            
            # 提取原图并应用相同的fetch_image处理（确保尺寸对齐）
            if idx < 3:
                print(f"[DEBUG REF METRICS] Sample {idx}: Extracting original image, type={type(original_images[idx])}...")
            original_img_raw = extract_pil_image_from_data(original_images[idx])
            if original_img_raw is None:
                skip_reasons["extraction_failed"] += 1
                if idx < 3:
                    print(f"[DEBUG REF METRICS] Sample {idx}: SKIP - original_img_raw is None after extraction")
                continue
            if idx < 3:
                print(f"[DEBUG REF METRICS] Sample {idx}: Original image (raw) size: {original_img_raw.size if hasattr(original_img_raw, 'size') else 'no size attr'}")
            
            # 对原图应用fetch_image处理（与复原图相同的预处理）
            try:
                from qwen_vl_utils import fetch_image
                from PIL import Image
                
                # 如果original_img_raw是PIL Image，转换为fetch_image所需的格式
                if isinstance(original_img_raw, Image.Image):
                    original_dict = {"image": original_img_raw}
                    original_img = fetch_image(original_dict)
                elif isinstance(original_img_raw, bytes):
                    import io
                    pil_img = Image.open(io.BytesIO(original_img_raw))
                    original_dict = {"image": pil_img}
                    original_img = fetch_image(original_dict)
                else:
                    original_img = original_img_raw
                
                print(f"[DEBUG REF METRICS] Sample {idx}: original_img size after fetch_image: {original_img.size if hasattr(original_img, 'size') else 'unknown'}")
            except Exception as e:
                print(f"[DEBUG REF METRICS] Sample {idx}: fetch_image failed, using raw: {e}")
                original_img = original_img_raw
            
            # 计算有参考指标（现在尺寸应该匹配）
            if idx < 3:
                print(f"[DEBUG REF METRICS] Sample {idx}: Calling calculate_all_metrics...")
                print(f"[DEBUG REF METRICS] Sample {idx}: restored_img type={type(restored_img)}, size={restored_img.size if hasattr(restored_img, 'size') else 'N/A'}")
                print(f"[DEBUG REF METRICS] Sample {idx}: original_img type={type(original_img)}, size={original_img.size if hasattr(original_img, 'size') else 'N/A'}")
            
            metrics = metrics_calculator.calculate_all_metrics(restored_img, original_img)
            
            if idx < 3:
                print(f"[DEBUG REF METRICS] Sample {idx}: metrics returned: {metrics}")
            
            ssim_scores[idx] = metrics.get('ssim', 0.0)
            lpips_scores[idx] = metrics.get('lpips', 0.0)
            psnr_scores[idx] = metrics.get('psnr', 0.0)
            
            if idx < 3:
                print(f"[DEBUG REF METRICS] Sample {idx}: ✓ SSIM={ssim_scores[idx]:.4f}, LPIPS={lpips_scores[idx]:.4f}, PSNR={psnr_scores[idx]:.4f}")
            
            calculated_count += 1
            
        except Exception as e:
            # 计算失败，保持0.0
            skip_reasons["calculation_failed"] += 1
            if idx < 3:
                print(f"[DEBUG REF METRICS] Sample {idx} failed with exception: {e}")
                import traceback
                traceback.print_exc()
            continue
    
    # 打印统计摘要
    print(f"\n[DEBUG REF METRICS] ========== Summary ==========")
    print(f"[DEBUG REF METRICS] Total samples: {num_samples}")
    print(f"[DEBUG REF METRICS] Successfully calculated: {calculated_count}")
    print(f"[DEBUG REF METRICS] Skip reasons:")
    for reason, count in skip_reasons.items():
        if count > 0:
            print(f"[DEBUG REF METRICS]   - {reason}: {count}")
    
    # 显示前5个样本的指标值（非零的）
    print(f"[DEBUG REF METRICS] Sample values (first 5 non-zero):")
    shown_count = 0
    for i in range(num_samples):
        if shown_count >= 5:
            break
        if ssim_scores[i] != 0.0 or lpips_scores[i] != 0.0 or psnr_scores[i] != 0.0:
            print(f"[DEBUG REF METRICS]   Sample {i}: SSIM={ssim_scores[i]:.4f}, LPIPS={lpips_scores[i]:.4f}, PSNR={psnr_scores[i]:.2f}")
            shown_count += 1
    print(f"[DEBUG REF METRICS] ================================\n")
    
    result = {
        'ssim_score_ref': ssim_scores,
        'lpips_score_ref': lpips_scores,
        'psnr_score_ref': psnr_scores,
    }
    
    print(f"[DEBUG REF METRICS] Returning dict with keys: {list(result.keys())}")
    print(f"[DEBUG REF METRICS] List lengths: SSIM={len(ssim_scores)}, LPIPS={len(lpips_scores)}, PSNR={len(psnr_scores)}")
    
    return result


def extract_image_quality_scores_from_rewards(reward_info: Dict) -> Optional[List[float]]:
    """
    Extract image quality scores from reward computation results
    
    Args:
        reward_info: Dictionary containing reward computation results
        
    Returns:
        List of image quality scores, or None if not available
    """
    # 优先顺序：
    # 1. ir_accuracy_score - 图像复原的准确性分数（包含质量奖励）
    # 2. accuracy_score - 通用准确性分数
    # 3. score - 总分（包含格式+质量）
    # 4. image_quality_reward - 纯质量奖励
    
    for key in ['ir_accuracy_score', 'accuracy_score', 'score', 'image_quality_reward', 
                'quality_score', 'image_quality_score', 'restoration_quality']:
        if key in reward_info:
            scores = reward_info[key]
            if isinstance(scores, (list, np.ndarray)):
                print(f"[DEBUG EXTRACT SCORES] Using '{key}' from reward_info, found {len(scores)} scores")
                return [float(s) for s in scores]
            elif isinstance(scores, (int, float)):
                return [float(scores)]
    
    print(f"[DEBUG EXTRACT SCORES] No quality scores found in reward_info keys: {list(reward_info.keys())}")
    return None

