import logging
import math
import os

import numpy as np
from datasets import load_dataset
from PIL import Image

# from qwen_vl_utils import smart_resize
from rich.logging import RichHandler

# Configure rich logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)

log = logging.getLogger("rich")

# --- Important: Please set the correct dataset root directory path ---
# This path should contain the actual image file subdirectories (e.g., bottle/test/good/000.png)
data_root = "/data1/huggingface/hub/datasets--XimiaoZhang--MVTec-2K/snapshots/d52ff40b834d44cfcbea1fafc204666fc0da5b18"

IMAGE_FACTOR = 28
MIN_PIXELS = 4 * 28 * 28
MAX_PIXELS = 16384 * 28 * 28
MAX_RATIO = 200


def round_by_factor(number: int, factor: int) -> int:
    """Returns the closest integer to 'number' that is divisible by 'factor'."""
    return round(number / factor) * factor


def floor_by_factor(number: int, factor: int) -> int:
    """Returns the largest integer less than or equal to 'number' that is divisible by 'factor'."""
    return math.floor(number / factor) * factor


def ceil_by_factor(number: int, factor: int) -> int:
    """Returns the smallest integer greater than or equal to 'number' that is divisible by 'factor'."""
    return math.ceil(number / factor) * factor


def smart_resize(
    height: int,
    width: int,
    factor: int = IMAGE_FACTOR,
    min_pixels: int = MIN_PIXELS,
    max_pixels: int = MAX_PIXELS,
) -> tuple[int, int]:
    """
    Rescales the image so that the following conditions are met:

    1. Both dimensions (height and width) are divisible by 'factor'.

    2. The total number of pixels is within the range ['min_pixels', 'max_pixels'].

    3. The aspect ratio of the image is maintained as closely as possible.
    """
    if max(height, width) / min(height, width) > MAX_RATIO:
        raise ValueError(
            f"absolute aspect ratio must be smaller than {MAX_RATIO}, got {max(height, width) / min(height, width)}"
        )
    h_bar = max(factor, round_by_factor(height, factor))
    w_bar = max(factor, round_by_factor(width, factor))
    if h_bar * w_bar > max_pixels:
        beta = math.sqrt((height * width) / max_pixels)
        h_bar = floor_by_factor(height / beta, factor)
        w_bar = floor_by_factor(width / beta, factor)
    elif h_bar * w_bar < min_pixels:
        beta = math.sqrt(min_pixels / (height * width))
        h_bar = ceil_by_factor(height * beta, factor)
        w_bar = ceil_by_factor(width * beta, factor)
    return h_bar, w_bar


def reverse_convert_to_original_format(
    bbox_new, orig_height, orig_width, new_height, new_width
):
    """
    从修改后的坐标恢复原始坐标值。

    参数:
    - bbox_new: 修改后的边界框坐标 [x1_new, y1_new, x2_new, y2_new]
    - orig_height: 原始图像的高度
    - orig_width: 原始图像的宽度
    - new_height: 修改后的图像高度
    - new_width: 修改后的图像宽度

    返回:
    - 原始坐标 [x1, y1, x2, y2]
    """
    scale_w = new_width / orig_width
    scale_h = new_height / orig_height

    x1_new, y1_new, x2_new, y2_new = bbox_new

    # 反向计算原始坐标
    x1 = round(x1_new / scale_w)
    y1 = round(y1_new / scale_h)
    x2 = round(x2_new / scale_w)
    y2 = round(y2_new / scale_h)

    # 确保原始坐标在原始图像范围内
    x1 = max(0, min(x1, orig_width - 1))
    y1 = max(0, min(y1, orig_height - 1))
    x2 = max(0, min(x2, orig_width - 1))
    y2 = max(0, min(y2, orig_height - 1))

    return [x1, y1, x2, y2]


def calculate_iou(predicted_boxes: list, gt_mask_path: str, img_shape: tuple) -> float:
    """
    Calculate the Intersection over Union (IoU) between predicted bounding boxes and ground truth mask.

    Args:
        predicted_boxes: List of predicted bounding boxes, e.g., [[x1, y1, x2, y2], ...].
        gt_mask_path: Path to the ground truth mask image file.
        img_shape: Shape of the original image (height, width).

    Returns:
        IoU score (float).
    """
    try:
        height, width = img_shape
        # 1. Create prediction mask from bounding boxes
        pred_mask = np.zeros((height, width), dtype=np.uint8)
        new_height, new_width = smart_resize(
            height,
            width,
        )
        for box in predicted_boxes:
            if isinstance(box, dict):
                if "bbox_2d" in box:
                    box = box["bbox_2d"]
                elif "bbox2d" in box:
                    box = box["bbox2d"]
                else:
                    box = box
            log.info(f"Original box: {box}")
            x1, y1, x2, y2 = reverse_convert_to_original_format(
                box, height, width, new_height, new_width
            )
            pred_mask[y1:y2, x1:x2] = 1

        # 2. Load and binarize ground truth mask
        if not os.path.exists(gt_mask_path):
            log.error(
                f"Ground truth mask file not found: {gt_mask_path}. Returning IoU of 0."
            )
            return 0.0

        gt_mask_img = Image.open(gt_mask_path).convert("L").resize((width, height))
        gt_mask = np.array(gt_mask_img)
        gt_mask = (gt_mask > 0).astype(
            np.uint8
        )  # Binarize: 0 for background, 1 for defect

        # 3. Calculate intersection and union
        intersection = np.logical_and(pred_mask, gt_mask).sum()
        union = np.logical_or(pred_mask, gt_mask).sum()
        gt_area = gt_mask.sum()
        if union == 0:
            # If both prediction and ground truth are empty (no defects), IoU is 1.0
            return 1.0
        if gt_area == 0:
            # If ground truth mask is empty (no defects) but prediction is not, IoU is 0.0
            return 0.0

        iou = intersection / gt_area
        return float(iou)

    except Exception as e:
        log.error(f"Error in IoU calculation for {gt_mask_path}: {e}")
        return 0.0
