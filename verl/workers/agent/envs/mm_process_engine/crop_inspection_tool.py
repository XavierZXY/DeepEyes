import ast
import json
import logging
import re
from math import ceil, floor
from typing import Any, Dict, List, Optional, Tuple

# Configure rich logging
from rich.logging import RichHandler

from verl.utils.reward_score.qwen_utils.utils import (
    reverse_convert_to_original_format,
    smart_resize,
)
from verl.workers.agent.tool_envs import ToolBase

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)

log = logging.getLogger("rich")


class CropInspectionTool(ToolBase):
    """
    A crop inspection tool that can extract locations from <location> tags and crop images
    for detailed multi-round inspection of defects.
    """

    name = "crop_inspection_tool"

    user_prompt = """Here is the cropped region returned after calling the crop inspection tool.
This cropped image shows a focused view of the detected area for detailed inspection.
If the images provided are sufficient to answer the user's question, please put your final answer within <answer></answer> and <location></location> and <type></type> tags.
Otherwise, you can continue to call tools within <tool_call></tool_call> for further inspection."""

    def __init__(self, _name=None, _desc=None, _params=None, **kwargs):
        super().__init__(name=self.name)
        self.chatml_history = []
        self.multi_modal_data = None
        self.original_image = None
        self.crop_history = []  # Track cropping history
        self.current_crop_level = 0
        self.max_crop_levels = (
            3  # Limit maximum crop levels to prevent infinite loops
        )

    def extract_answer(self, action_string: str) -> Optional[str]:
        """Extract answer from <answer></answer> tags"""
        answer_matches = re.findall(
            r"<answer>(.*?)</answer>", action_string, re.DOTALL
        )
        return answer_matches[-1].strip() if answer_matches else None

    def extract_location(self, action_string: str) -> Optional[str]:
        """Extract location from <location></location> tags"""
        location_matches = re.findall(
            r"<location>(.*?)</location>", action_string, re.DOTALL
        )
        return location_matches[-1].strip() if location_matches else None

    def extract_type(self, action_string: str) -> Optional[str]:
        """Extract type from <type></type> tags"""
        type_matches = re.findall(
            r"<type>(.*?)</type>", action_string, re.DOTALL
        )
        return type_matches[-1].strip() if type_matches else None

    def extract_action(self, action_string: str) -> Optional[str]:
        """Extract tool call from <tool_call></tool_call> tags"""
        tool_call_matches = re.findall(
            r"<tool_call>(.*?)</tool_call>", action_string, re.DOTALL
        )
        return tool_call_matches[-1].strip() if tool_call_matches else None

    def parse_location_bboxes(self, location_text: str) -> List[List[float]]:
        """Parse bounding boxes from location text (JSON format)"""
        if not location_text:
            return []

        try:
            # Try strict JSON first
            loc_data = json.loads(location_text)
        except Exception:
            # Try Python literal evaluation for single quotes, None, etc.
            try:
                loc_data = ast.literal_eval(location_text)
            except Exception:
                log.error(f"Failed to parse location text: {location_text}")
                return []

        boxes = []
        if isinstance(loc_data, list):
            for item in loc_data:
                if isinstance(item, dict):
                    bbox = item.get("bbox2d") or item.get("bbox_2d")
                    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                        try:
                            boxes.append([float(v) for v in bbox])
                        except Exception:
                            continue

        return boxes

    def validate_bbox(
        self, left: float, top: float, right: float, bottom: float
    ) -> bool:
        """Validate bounding box coordinates"""
        try:
            assert left < right and top < bottom, (
                f"Invalid shape for {left=}, {top=}, {right=}, {bottom=}"
            )
            height = bottom - top
            width = right - left
            assert max(height, width) / min(height, width) <= 100, (
                f"Aspect ratio error: {left=}, {top=}, {right=}, {bottom=}"
            )
            assert min(height, width) > 10, f"{height=}, {width=} is too small"
            return True
        except Exception as err:
            log.error(f"Bbox validation error: {err}")
            return False

    def maybe_resize_bbox(
        self, left: float, top: float, right: float, bottom: float
    ) -> Optional[List[float]]:
        """Resize bbox to fit within image bounds and meet minimum size requirements"""
        left = max(0, left)
        top = max(0, top)
        right = min(self.width, right)
        bottom = min(self.height, bottom)

        if not self.validate_bbox(left, top, right, bottom):
            return None

        height = bottom - top
        width = right - left

        # Ensure minimum size
        min_size = 20
        if height < min_size or width < min_size:
            center_x = (left + right) / 2.0
            center_y = (top + bottom) / 2.0
            ratio = min_size / min(height, width)
            new_half_height = ceil(height * ratio * 0.5)
            new_half_width = ceil(width * ratio * 0.5)
            new_left = floor(center_x - new_half_width)
            new_right = ceil(center_x + new_half_width)
            new_top = floor(center_y - new_half_height)
            new_bottom = ceil(center_y + new_half_height)

            # Clamp to image bounds
            new_left = max(0, new_left)
            new_top = max(0, new_top)
            new_right = min(self.width, new_right)
            new_bottom = min(self.height, new_bottom)

            if not self.validate_bbox(new_left, new_top, new_right, new_bottom):
                return None
            return [new_left, new_top, new_right, new_bottom]

        return [left, top, right, bottom]

    def maybe_rescale_bboxes_to_original(
        self, bboxes: List[List[float]], extra_info: Optional[Dict] = None
    ) -> List[List[float]]:
        """
        If original image shape is available in extra_info (img_shape=(H,W)),
        assume model used smart_resize(H,W) and rescale predicted boxes back to original.
        Similar to _maybe_rescale_pred_boxes_to_original in vl_agent.py
        """
        if not extra_info:
            return bboxes

        img_shape = extra_info.get("img_shape") or extra_info.get("image_shape")
        if (
            not img_shape
            or not isinstance(img_shape, (list, tuple))
            or len(img_shape) < 2
        ):
            return bboxes

        try:
            orig_h, orig_w = int(img_shape[0]), int(img_shape[1])
            new_h, new_w = smart_resize(orig_h, orig_w)
            restored = []
            for box in bboxes:
                x1, y1, x2, y2 = reverse_convert_to_original_format(
                    box, orig_h, orig_w, new_h, new_w
                )
                restored.append([float(x1), float(y1), float(x2), float(y2)])
            return restored
        except Exception as e:
            log.error(f"Failed to rescale predicted boxes: {e}")
            return bboxes

    def execute(
        self, action_string: str, extra_info: Optional[Dict] = None, **kwargs
    ) -> Tuple[Any, float, bool, Dict[str, Any]]:
        """
        Execute the crop inspection tool based on the action string.

        Args:
            action_string: The string containing tool calls or final answer
            extra_info: Additional information including original image shape for rescaling

        Returns:
            observation: The structured observation with processed image
            reward: Reward based on tool usage effectiveness
            done: Whether the episode is terminated
            info: Additional information
        """
        # Check if this is a final answer
        answer = self.extract_answer(action_string)
        location = self.extract_location(action_string)
        type_info = self.extract_type(action_string)

        if answer is not None:
            # Episode is done, return final observation
            info = {
                "status": "completed",
                "answer": answer,
                "location": location,
                "type": type_info,
                "crop_history": self.crop_history,
                "total_crops": len(self.crop_history),
            }
            return "", 0.0, True, info

        # Extract tool call
        action = self.extract_action(action_string)
        if not action:
            return (
                "",
                0.0,
                True,
                {
                    "error": "No valid tool call or answer found",
                    "status": "failed",
                },
            )

        try:
            tool_call = json.loads(action)
        except Exception as e:
            error_msg = f"Invalid tool call format: {action}. Error: {e}"
            obs = (
                "\n<|im_start|>user\n"
                + f"Error: {error_msg}"
                + "<|im_end|>\n<|im_start|>assistant\n"
            )
            return obs, 0.0, False, {"error": str(e), "status": "failed"}

        try:
            tool_name = tool_call["name"]
            args = tool_call["arguments"]

            if tool_name == "crop_from_location":
                # Crop based on location information
                location_text = args.get("location_data", "")
                crop_index = args.get(
                    "crop_index", 0
                )  # Which bbox to crop if multiple

                if self.current_crop_level >= self.max_crop_levels:
                    raise ValueError(
                        f"Maximum crop levels ({self.max_crop_levels}) exceeded"
                    )

                # Parse location data
                bboxes = self.parse_location_bboxes(location_text)
                if not bboxes:
                    raise ValueError(
                        "No valid bounding boxes found in location data"
                    )

                # Rescale bboxes to original image coordinates if needed
                rescaled_bboxes = self.maybe_rescale_bboxes_to_original(
                    bboxes, extra_info
                )

                if crop_index >= len(rescaled_bboxes):
                    crop_index = (
                        0  # Default to first bbox if index out of range
                    )

                bbox = rescaled_bboxes[crop_index]
                resized_bbox = self.maybe_resize_bbox(*bbox)
                if not resized_bbox:
                    raise ValueError("Invalid bounding box coordinates")

                # Get current image (either original or previously cropped)
                current_img = self.multi_modal_data["image"][0]
                cropped_img = current_img.crop(resized_bbox)

                # Update crop history
                crop_info = {
                    "level": self.current_crop_level,
                    "original_bbox": bboxes[
                        crop_index
                    ],  # Original bbox from model prediction
                    "rescaled_bbox": bbox,  # Rescaled bbox to original image coordinates
                    "resized_bbox": resized_bbox,  # Final bbox after bounds checking
                    "crop_size": (cropped_img.width, cropped_img.height),
                    "parent_size": (current_img.width, current_img.height),
                }
                self.crop_history.append(crop_info)
                self.current_crop_level += 1

                # Prepare observation
                obs = {
                    "prompt": "\n<|im_start|>user\n"
                    + "<tool_response>"
                    + "<image>"
                    + self.user_prompt
                    + "</tool_response>"
                    + "<|im_end|>\n<|im_start|>assistant\n",
                    "multi_modal_data": {"image": [cropped_img]},
                }

                # Update current multi_modal_data for next iteration
                self.multi_modal_data = {"image": [cropped_img]}

                reward = self.calculate_crop_reward(crop_info, rescaled_bboxes)
                done = False
                info = {
                    "status": "success",
                    "tool_used": tool_name,
                    "crop_info": crop_info,
                    "total_crops": len(self.crop_history),
                }

                log.info(
                    f"Crop tool executed successfully: level={self.current_crop_level - 1}, bbox={resized_bbox}"
                )
                return obs, reward, done, info

            else:
                raise ValueError(f"Unknown tool name: {tool_name}")

        except Exception as e:
            log.error(f"Crop tool execution failed: {str(e)}")
            obs = (
                "\n<|im_start|>user\n"
                + f"Error: {str(e)}"
                + "<|im_end|>\n<|im_start|>assistant\n"
            )
            return obs, 0.0, False, {"error": str(e), "status": "failed"}

    def calculate_crop_reward(self, crop_info: Dict, all_bboxes: List) -> float:
        """
        Calculate reward for crop operation based on various factors.

        Args:
            crop_info: Information about the current crop operation
            all_bboxes: All available bounding boxes from location

        Returns:
            Reward value between 0.0 and 1.0
        """
        reward = 0.0

        # Base reward for successful crop
        reward += 0.2

        # Reward based on crop level (encourage progressive inspection)
        level_bonus = max(
            0.0, 0.3 - 0.1 * crop_info["level"]
        )  # Decreasing bonus for deeper levels
        reward += level_bonus

        # Reward based on crop size (reasonable size gets bonus)
        crop_width, crop_height = crop_info["crop_size"]
        parent_width, parent_height = crop_info["parent_size"]

        # Calculate crop ratio
        crop_area = crop_width * crop_height
        parent_area = parent_width * parent_height
        crop_ratio = crop_area / parent_area if parent_area > 0 else 0

        # Optimal crop ratio is between 0.1 and 0.5 (not too small, not too large)
        if 0.1 <= crop_ratio <= 0.5:
            size_bonus = 0.3
        elif 0.05 <= crop_ratio < 0.1 or 0.5 < crop_ratio <= 0.8:
            size_bonus = 0.2
        else:
            size_bonus = 0.1
        reward += size_bonus

        # Bonus for selecting from multiple bboxes (shows discrimination)
        if len(all_bboxes) > 1:
            reward += 0.2

        return min(1.0, reward)

    def reset(
        self, raw_prompt, multi_modal_data, origin_multi_modal_data, **kwargs
    ):
        """Reset the tool state for a new episode"""
        self.chatml_history = raw_prompt
        self.multi_modal_data = origin_multi_modal_data.copy()
        self.original_image = origin_multi_modal_data["image"][0].copy()
        self.crop_history = []
        self.current_crop_level = 0

        assert "image" in self.multi_modal_data.keys(), (
            f"[ERROR] {origin_multi_modal_data=}"
        )
        assert len(self.multi_modal_data["image"]) > 0, (
            f'[ERROR] {self.multi_modal_data["image"]=}'
        )

        self.height = self.multi_modal_data["image"][0].height
        self.width = self.multi_modal_data["image"][0].width

        log.info(
            f"Crop inspection tool reset: image size={self.width}x{self.height}"
        )


if __name__ == "__main__":
    # Example usage
    tool = CropInspectionTool()

    # Test crop from location
    crop_action = """
    <tool_call>
    {"name": "crop_from_location", "arguments": {"location_data": "[{\"bbox2d\": [100, 100, 200, 200]}]", "crop_index": 0}}
    </tool_call>
    """

    # Test final answer
    final_answer = """
    <answer>yes</answer>
    <location>[{"bbox2d": [150, 150, 250, 250]}]</location>
    <type>scratch</type>
    """

    print("Crop inspection tool created successfully!")
