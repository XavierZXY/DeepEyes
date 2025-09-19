import ast
import json
import logging
import os
import random
import re

import requests
from math_verify import parse, verify
from openai import OpenAI

from verl.utils.reward_score.qwen_utils.utils import (
    reverse_convert_to_original_format,
    smart_resize,
)

log = logging.getLogger("rich")

openai_api_key = "EMPTY"
openai_api_base_list = [
    # "http://172.30.52.123:8000/v1",
    # "http://10.39.3.123:18901/v1",
    os.environ.get("LLM_AS_A_JUDGE_BASE", "http://GPUD4FC:9091/v1"),
]

client_list = []
for api_base in openai_api_base_list:
    client = OpenAI(
        api_key=openai_api_key,
        base_url=api_base,
    )
    client_list.append(client)
model_name_list = []
for client in client_list:
    response = requests.get(f"{api_base}/models")
    models = response.json()
    model_name_list.append(models["data"][0]["id"])


def get_chat_template():
    chat_template = """
Below are two answers to a question. Question is [Question], [Standard Answer] is the standard answer to the question, and [Model_answer] is the answer extracted from a model's output to this question.  Determine whether these two answers are consistent.
Note that [Model Answer] is consistent with [Standard Answer] whenever they are essentially the same. If the meaning is expressed in the same way, it is considered consistent, for example, 'pink' and 'it is pink'.
If they are consistent, Judement is 1; if they are different, Judement is 0. Just output Judement and don't output anything else.\n\n
"""
    return chat_template


def get_gpt4_score_ICE():
    example_1 = """
[Question]: Is the countertop tan or blue?
[Standard Answer]: The countertop is tan.
[Model_answer] : tan
Judgement: 1
"""  # noqa

    example_2 = """
[Question]: On which side of the picture is the barrier?
[Standard Answer]: The barrier is on the left side of the picture.
[Model_answer] : left
Judgement: 1
"""  # noqa

    example_3 = """
[Question]: Is the kite brown and large?
[Standard Answer]: Yes, the kite is brown and large.
[Model_answer] : Yes
Judgement: 1
"""  # noqa

    example_4 = """
[Question]: Are the spots on a giraffe?
[Standard Answer]: No, the spots are on a banana.
[Model_answer] : no
Judgement: 1
"""  # noqa

    example_5 = """
[Question]: Who is wearing pants?
[Standard Answer]: The boy is wearing pants.
[Model_answer] : The person in the picture is wearing pants.
Judgement: 1
"""  # noqa

    example_6 = """
[Question]: Is the man phone both blue and closed?
[Standard Answer]: Yes, the man phone is both blue and closed.
[Model_answer] : No.
Judgement: 0
"""  # noqa

    example_7 = """
[Question]: What color is the towel in the center of the picture?
[Standard Answer]: The towel in the center of the picture is blue.
[Model_answer] : The towel in the center of the picture is pink.
Judgement: 0
"""  # noqa

    return [
        example_1,
        example_2,
        example_3,
        example_4,
        example_5,
        example_6,
        example_7,
    ]


COMMON_VERIFY_PROMPT = """# CONTEXT #
You are evaluating a defect detection response for industrial anomaly inspection.
The model must strictly follow this output format with tags in order: <think>, <location>, <type>, <answer>.

# OBJECTIVE #
Judge whether the student's FINAL decision (<answer> tag: yes/no) matches the ground truth decision, regardless of wording.
Do not consider formatting issues here beyond extracting the final decision. Focus on semantic equivalence of the decision.

# TONE #
Professional, scientific.

# RESPONSE: MARKDOWN REPORT #
## Equivalence Judgement
[Whether the student's final decision matches the reference decision. (TRUE or FALSE)]

# ATTENTION #
 - The reference answer is ALWAYS correct.
 - Only evaluate the equivalence of the final decision (yes/no or defect-free vs defective), not the reasoning details.
 - Output only TRUE or FALSE in the judgement section.

**Question**:
{query}

**Reference Answer**
{gold_ans}

## Student Final Answer
{pred_ans}"""


MATH_VERIFY_PROMPT = """# CONTEXT #
I am a teacher, and I have some high-level math problems. I am tasked with evaluating the correctness of a student's answer. 
Below, I am provided with a problem and a reference answer. Additionally, a student's answer is provided. My job is to assess whether the student's answer captures the same meaning as the reference answer, even when expressed with different wording or format.

# OBJECTIVE #
I need you to judge whether the student's answer is correct given the ground truth answer.

Your tasks include:
1. Identify Mathematical or Notational Equivalence: Pay special attention to any LaTeX expressions in both answers. Confirm that the mathematical relationships, variables, and operations conveyed are equivalent.

# TONE #
Professional, scientific.

# RESPONSE: MARKDOWN REPORT #
## Equivalence Judgement
[Whether the student's answer share the same meaning with the reference answer. (TRUE or FALSE)]

# ATTENTION #
 - The reference answer is ALWAYS correct. You should carefully judge whether the student gives the same answer as reference answer.
 - The Equivalence Judgement is only TRUE or FALSE. The answer is FALSE even if the student's final answer almost correct with a minor mistakes.
 - Don't give extra explanation.

**Question**:
{query}

**Reference Answer**
{gold_ans}

## Student Final Answer
{pred_ans}"""


def get_prompt(predict_str, ground_truth, question):
    examples = get_gpt4_score_ICE()
    chat_template = get_chat_template()
    demo_prompt = chat_template
    for example in examples:
        demo_prompt += example + "\n\n"
    test_prompt = f"""
[Question]: {question}
[Standard Answer]: {ground_truth}
[Model_answer] : {predict_str}
Judgement:"""
    full_prompt = f"{demo_prompt}{test_prompt}"

    return full_prompt


def extract_answer(text):
    """
    从给定的文本中提取<answer></answer>标签内部的内容。

    参数:
        text (str): 包含<answer>标签的文本

    返回:
        str or None: 标签内部的内容，如果未找到则返回None。
    """
    # 使用非贪婪模式匹配<answer>和</answer>之间的内容
    pattern = r"<answer>(.*?)</answer>"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def extract_location(text):
    """
    从给定的文本中提取<location></location>标签内部的内容。

    参数:
        text (str): 包含<location>标签的文本

    返回:
        str or None: 标签内部的内容，如果未找到则返回None。
    """
    pattern = r"<location>(.*?)</location>"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def extract_type(text):
    """
    从给定的文本中提取<type></type>标签内部的内容。

    参数:
        text (str): 包含<type>标签的文本

    返回:
        str or None: 标签内部的内容，如果未找到则返回None。
    """
    pattern = r"<type>(.*?)</type>"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def _parse_predicted_bboxes(location_text):
    """Parse predicted bboxes from location JSON string into list of [x1,y1,x2,y2]."""
    if not location_text:
        return []
    # Try strict JSON first
    try:
        loc = json.loads(location_text)
    except Exception:
        # Try Python-literal style (single quotes, None, etc.)
        try:
            loc = ast.literal_eval(location_text)
        except Exception:
            loc = None

    boxes = []
    if isinstance(loc, list):
        for item in loc:
            if isinstance(item, dict):
                arr = item.get("bbox2d") or item.get("bbox_2d")
                if isinstance(arr, (list, tuple)) and len(arr) == 4:
                    try:
                        boxes.append([float(v) for v in arr])
                    except Exception:
                        continue
    if boxes:
        return boxes

    # Regex fallback: extract any [x1,y1,x2,y2]
    try:
        import re

        pattern = r"\[\s*([-+]?[0-9]*\.?[0-9]+)\s*,\s*([-+]?[0-9]*\.?[0-9]+)\s*,\s*([-+]?[0-9]*\.?[0-9]+)\s*,\s*([-+]?[0-9]*\.?[0-9]+)\s*\]"
        matches = re.findall(pattern, location_text)
        for m in matches:
            vals = [float(x) for x in m]
            if len(vals) == 4:
                boxes.append(vals)
        return boxes
    except Exception as e:
        log.error(f"Failed to parse predicted bboxes: {e}")
        return []


def _extract_gt_bboxes(ground_truth, extra_info):
    """Extract ground truth bboxes list[[x1,y1,x2,y2]]."""
    boxes = []
    # Prefer ground_truth dict
    try:
        if isinstance(ground_truth, dict) and "bboxes" in ground_truth:
            gt_boxes = ground_truth["bboxes"]
            try:
                iterable = list(gt_boxes)
            except Exception:
                iterable = []
            if iterable:
                for item in iterable:
                    if isinstance(item, dict):
                        arr = item.get("bbox2d") or item.get("bbox_2d")
                        if isinstance(arr, list) and len(arr) == 4:
                            boxes.append([float(v) for v in arr])
        # Fallback to extra_info
        if not boxes and extra_info and "bboxes" in extra_info:
            gt_boxes = extra_info["bboxes"]
            try:
                iterable = list(gt_boxes)
            except Exception:
                iterable = []
            if iterable:
                for item in iterable:
                    if isinstance(item, dict):
                        arr = item.get("bbox2d") or item.get("bbox_2d")
                        if isinstance(arr, list) and len(arr) == 4:
                            boxes.append([float(v) for v in arr])
    except Exception as e:
        log.error(f"Failed to extract GT bboxes: {e}")
    return boxes


def _bbox_iou_xyxy(box_a, box_b):
    x1 = max(box_a[0], box_b[0])
    y1 = max(box_a[1], box_b[1])
    x2 = min(box_a[2], box_b[2])
    y2 = min(box_a[3], box_b[3])
    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter = inter_w * inter_h
    area_a = max(0.0, box_a[2] - box_a[0]) * max(0.0, box_a[3] - box_a[1])
    area_b = max(0.0, box_b[2] - box_b[0]) * max(0.0, box_b[3] - box_b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _soft_iou_reward(pred_boxes, gt_boxes):
    """Compute a soft reward based on IoU matching with lenient mapping.
    Quickly gives decent reward for moderate overlap, not requiring very high IoU.
    """
    # Empty cases
    if len(gt_boxes) == 0 and len(pred_boxes) == 0:
        return 1.0
    if len(gt_boxes) == 0 and len(pred_boxes) > 0:
        return 0.0
    if len(gt_boxes) > 0 and len(pred_boxes) == 0:
        return 0.0

    # Compute best matches (gt->pred and pred->gt), then take the better average
    def avg_best_iou(sources, targets):
        if not sources:
            return 0.0
        vals = []
        for s in sources:
            best = 0.0
            for t in targets:
                best = max(best, _bbox_iou_xyxy(s, t))
            vals.append(best)
        return sum(vals) / len(vals) if vals else 0.0

    avg1 = avg_best_iou(gt_boxes, pred_boxes)
    avg2 = avg_best_iou(pred_boxes, gt_boxes)
    base = max(avg1, avg2)
    # Lenient mapping: 0.5 IoU -> full, 0.3 -> good reward
    return min(1.0, base / 0.5)


def _maybe_rescale_pred_boxes_to_original(pred_boxes, extra_info):
    """If original image shape is available in extra_info (img_shape=(H,W)),
    assume model used smart_resize(H,W) and rescale predicted boxes back to original.
    """
    if not extra_info:
        return pred_boxes
    img_shape = extra_info.get("img_shape") or extra_info.get("image_shape")
    if (
        not img_shape
        or not isinstance(img_shape, (list, tuple))
        or len(img_shape) < 2
    ):
        return pred_boxes
    try:
        orig_h, orig_w = int(img_shape[0]), int(img_shape[1])
        new_h, new_w = smart_resize(orig_h, orig_w)
        restored = []
        for box in pred_boxes:
            x1, y1, x2, y2 = reverse_convert_to_original_format(
                box, orig_h, orig_w, new_h, new_w
            )
            restored.append([float(x1), float(y1), float(x2), float(y2)])
        return restored
    except Exception as e:
        log.error(f"Failed to rescale predicted boxes: {e}")
        return pred_boxes


def _extract_ground_truth_answer(ground_truth, extra_info):
    """Return the textual ground truth answer if available."""
    answer = None

    if isinstance(ground_truth, dict):
        answer = ground_truth.get("answer")
    elif isinstance(ground_truth, str):
        answer = ground_truth
    elif ground_truth is not None:
        answer = str(ground_truth)

    if answer is None and extra_info is not None:
        answer_info = extra_info.get("answer")
        if isinstance(answer_info, dict):
            answer = answer_info.get("answer")
        elif isinstance(answer_info, str):
            answer = answer_info

    return (answer or "").strip()


def compute_score(
    predict_str: str, ground_truth: str, extra_info=None, use_bbox_reward=True
) -> float:
    is_format_error = False
    # predict_str = "<think>" + predict_str
    count_think_1 = predict_str.count("<think>")
    count_think_2 = predict_str.count("</think>")
    if count_think_1 != count_think_2:
        is_format_error = True

    count_vision_1 = predict_str.count("<|vision_start|><|image_pad|>")
    count_vision_2 = predict_str.count("<|image_pad|><|vision_end|>")
    if count_vision_1 != count_vision_2:
        is_format_error = True

    predict_no_think = predict_str.split("</think>")[-1].strip()
    count_answer_1 = predict_no_think.count("<answer>")
    count_answer_2 = predict_no_think.count("</answer>")
    if count_answer_1 != count_answer_2:
        is_format_error = True

    count_location_1 = predict_no_think.count("<location>")
    count_location_2 = predict_no_think.count("</location>")
    if count_location_1 != count_location_2:
        is_format_error = True

    count_type_1 = predict_no_think.count("<type>")
    count_type_2 = predict_no_think.count("</type>")
    if count_type_1 != count_type_2:
        is_format_error = True

    answer_text = (
        predict_str.split("<answer>")[-1].split("</answer>")[0].strip()
    )
    location_text = extract_location(predict_no_think)
    type_text = extract_type(predict_no_think)

    # Check bbox format + accuracy with 3-box limit
    bbox_format_ok = False
    if location_text:
        try:
            loc = json.loads(location_text)
            if isinstance(loc, list) and len(loc) <= 3:  # Limit to 3 boxes max
                bbox_format_ok = all(
                    isinstance(item, dict)
                    and ("bbox2d" in item or "bbox_2d" in item)
                    and isinstance(
                        (item.get("bbox2d") or item.get("bbox_2d")), list
                    )
                    and len((item.get("bbox2d") or item.get("bbox_2d"))) == 4
                    for item in loc
                )
        except (json.JSONDecodeError, TypeError):
            pass
    pred_boxes = _parse_predicted_bboxes(location_text)
    pred_boxes = _maybe_rescale_pred_boxes_to_original(pred_boxes, extra_info)
    gt_boxes = _extract_gt_bboxes(ground_truth, extra_info)
    # Use improved IoU calculation with proper intersection/union formula
    bbox_iou_reward = _improved_iou_reward(
        pred_boxes, gt_boxes, max_pred_boxes=3
    )
    bbox_reward = 0.2 * (1.0 if bbox_format_ok else 0.0) + 0.8 * bbox_iou_reward

    # Check type format and match
    ground_truth_answer = _extract_ground_truth_answer(ground_truth, extra_info)
    expected_type = (
        "good"
        if ground_truth_answer.lower().startswith("no")
        else (
            extra_info.get("type", "unspecified")
            if extra_info
            else "unspecified"
        )
    )
    type_reward = 0.0
    if type_text and isinstance(type_text, str):
        type_reward = 1.0 if type_text.lower() == expected_type.lower() else 0.0

    question_text = extra_info["question"] if extra_info else ""
    full_prompt = get_prompt(answer_text, ground_truth_answer, question_text)

    client_idx = random.randint(0, len(client_list) - 1)
    client = client_list[client_idx]
    model_name = model_name_list[client_idx]

    chat_response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": full_prompt},
        ],
        seed=random.randint(0, 1000000),
        temperature=0.3,
    )
    response = chat_response.choices[0].message.content.strip()
    # print(response)
    if "Judgement:" in response:
        response = response.split("Judgement:")[-1].strip()
        if "1" in response:
            acc_reward = 1.0
        elif "0" in response:
            acc_reward = 0.0
        else:
            print(f" [WARNING] resp format error {response=}")
            acc_reward = 0.0
    else:
        if response == "1":
            acc_reward = 1.0
        elif response == "0":
            acc_reward = 0.0
        else:
            print(f" [WARNING] resp format error {response=}")
            acc_reward = 0.0

    # Penalize for model trying to predict longer answer to hack llm-as-judge
    if len(answer_text) >= 1000:
        acc_reward = 0.0
        is_format_error = True

    tool_reward = 1.0 if count_vision_1 > 0 and acc_reward > 0.5 else 0.0
    format_reward = -1.0 if is_format_error else 0.0

    # Final score calculation with optional bbox reward
    if use_bbox_reward:
        return (
            0.8 * acc_reward
            + 0.2 * format_reward
            + 1.2 * tool_reward
            + 0.6 * bbox_reward
            + 0.4 * type_reward
        )
    else:
        # No bbox reward - increased weights for other components
        return (
            1.0 * acc_reward
            + 0.2 * format_reward
            + 1.4 * tool_reward
            + 0.6 * type_reward
        )


def compute_common_reasoning(
    predict_str: str, ground_truth: str, extra_info=None, use_bbox_reward=True
) -> float:
    is_format_error = False
    # predict_str = "<think>" + predict_str
    count_think_1 = predict_str.count("<think>")
    count_think_2 = predict_str.count("</think>")
    if count_think_1 != count_think_2:
        is_format_error = True

    count_vision_1 = predict_str.count("<|vision_start|><|image_pad|>")
    count_vision_2 = predict_str.count("<|image_pad|><|vision_end|>")
    if count_vision_1 != count_vision_2:
        is_format_error = True

    predict_no_think = predict_str.split("</think>")[-1].strip()
    count_answer_1 = predict_no_think.count("<answer>")
    count_answer_2 = predict_no_think.count("</answer>")
    if count_answer_1 != count_answer_2:
        is_format_error = True

    count_location_1 = predict_no_think.count("<location>")
    count_location_2 = predict_no_think.count("</location>")
    if count_location_1 != count_location_2:
        is_format_error = True

    count_type_1 = predict_no_think.count("<type>")
    count_type_2 = predict_no_think.count("</type>")
    if count_type_1 != count_type_2:
        is_format_error = True

    answer_text = extract_answer(predict_no_think)
    location_text = extract_location(predict_no_think)
    type_text = extract_type(predict_no_think)

    # Check bbox format + accuracy with 3-box limit
    bbox_format_ok = False
    if location_text:
        try:
            loc = json.loads(location_text)
            if isinstance(loc, list) and len(loc) <= 3:  # Limit to 3 boxes max
                bbox_format_ok = all(
                    isinstance(item, dict)
                    and "bbox2d" in item
                    and isinstance(item["bbox2d"], list)
                    and len(item["bbox2d"]) == 4
                    and all(isinstance(x, (int, float)) for x in item["bbox2d"])
                    for item in loc
                )
        except (json.JSONDecodeError, TypeError):
            pass
    pred_boxes = _parse_predicted_bboxes(location_text)
    pred_boxes = _maybe_rescale_pred_boxes_to_original(pred_boxes, extra_info)
    gt_boxes = _extract_gt_bboxes(ground_truth, extra_info)
    # Compute bbox reward (optional) for compute_common_reasoning
    if use_bbox_reward:
        # Use improved IoU calculation with proper intersection/union formula
        bbox_iou_reward = _improved_iou_reward(
            pred_boxes, gt_boxes, max_pred_boxes=3
        )
        bbox_reward = (
            0.2 * (1.0 if bbox_format_ok else 0.0) + 0.8 * bbox_iou_reward
        )
    else:
        bbox_reward = 0.0

    # Check type format and match
    ground_truth_answer = _extract_ground_truth_answer(ground_truth, extra_info)
    expected_type = (
        "good"
        if ground_truth_answer.lower().startswith("no")
        else (
            extra_info.get("type", "unspecified")
            if extra_info
            else "unspecified"
        )
    )
    type_reward = 0.0
    if type_text and isinstance(type_text, str):
        type_reward = 1.0 if type_text.lower() == expected_type.lower() else 0.0

    if not answer_text:
        acc_reward = 0.0
        is_format_error = True
    elif len(answer_text) >= 1000:
        acc_reward = 0.0
        is_format_error = True
    else:
        question_text = extra_info["question"] if extra_info else ""
        client_idx = random.randint(0, len(client_list) - 1)
        client = client_list[client_idx]
        model_name = model_name_list[client_idx]
        full_prompt = COMMON_VERIFY_PROMPT.format(
            query=question_text,
            gold_ans=ground_truth_answer,
            pred_ans=answer_text,
        )

        acc_reward = 0.0
        for ix in range(8):
            chat_response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "user", "content": full_prompt},
                ],
                seed=random.randint(0, 1000000),
                temperature=0.5,
            )
            response = chat_response.choices[0].message.content.strip()
            judgement = response.split("## Equivalence Judgement")[-1].lower()
            if "true" in judgement and "false" not in judgement:
                acc_reward = 1.0
                break
            elif "false" in judgement and "true" not in judgement:
                acc_reward = 0.0
                break
            else:
                print(f" [ERROR] judgement format invalid: {judgement}")
                continue

    tool_reward = 1.0 if count_vision_1 > 0 and acc_reward > 0.5 else 0.0
    format_reward = -1.0 if is_format_error else 0.0
    if extra_info:
        print(
            f" [DEBUG] query={extra_info['question']}, {ground_truth=}, {answer_text=}, {acc_reward=}, {format_reward=}"
        )

    # Final score calculation with optional bbox reward
    if use_bbox_reward:
        return (
            0.8 * acc_reward
            + 0.2 * format_reward
            + 1.2 * tool_reward
            + 0.6 * bbox_reward
            + 0.4 * type_reward
        )
    else:
        # No bbox reward - increased weights for other components
        return (
            1.0 * acc_reward
            + 0.2 * format_reward
            + 1.4 * tool_reward
            + 0.6 * type_reward
        )


def rule_math_verify(ground_truth, model_answer):
    gold = parse(ground_truth)
    answer = parse(model_answer)
    return verify(gold, answer)


def generative_verify(query, ground_truth, model_answer):
    client_idx = random.randint(0, len(client_list) - 1)
    client = client_list[client_idx]
    model_name = model_name_list[client_idx]

    full_prompt = MATH_VERIFY_PROMPT.format(
        query=query,
        gold_ans=ground_truth,
        pred_ans=model_answer,
    )

    response = ""
    for it in range(8):
        try:
            chat_response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "user", "content": full_prompt},
                ],
                seed=random.randint(0, 1000000),
                temperature=0.0,
            )
            response = chat_response.choices[0].message.content.strip()
            break
        except Exception as e:
            print(f" [ERROR math] generative_verify error: {e}")
            continue

    judgement = response.split("## Equivalence Judgement")[-1].lower()
    if "true" in judgement and "false" not in judgement:
        return True
    elif "false" in judgement and "true" not in judgement:
        return False
    else:
        print(" [ERROR math] verify bug output: ")


def compute_score_math(
    predict_str: str, ground_truth: str, extra_info=None
) -> float:
    is_format_error = False
    # predict_str = "<think>" + predict_str
    count_think_1 = predict_str.count("<think>")
    count_think_2 = predict_str.count("</think>")
    if count_think_1 != count_think_2:
        is_format_error = True

    count_vision_1 = predict_str.count("<|vision_start|><|image_pad|>")
    count_vision_2 = predict_str.count("<|image_pad|><|vision_end|>")
    if count_vision_1 != count_vision_2:
        is_format_error = True

    predict_no_think = predict_str.split("</think>")[-1].strip()
    count_answer_1 = predict_no_think.count("<answer>")
    count_answer_2 = predict_no_think.count("</answer>")
    if count_answer_1 != count_answer_2:
        is_format_error = True

    count_location_1 = predict_no_think.count("<location>")
    count_location_2 = predict_no_think.count("</location>")
    if count_location_1 != count_location_2:
        is_format_error = True

    count_type_1 = predict_no_think.count("<type>")
    count_type_2 = predict_no_think.count("</type>")
    if count_type_1 != count_type_2:
        is_format_error = True

    location_text = extract_location(predict_no_think)
    type_text = extract_type(predict_no_think)

    # Check bbox format
    bbox_format_ok = False
    if location_text:
        try:
            loc = json.loads(location_text)
            if isinstance(loc, list):
                bbox_format_ok = all(
                    isinstance(item, dict)
                    and "bbox2d" in item
                    and isinstance(item["bbox2d"], list)
                    and len(item["bbox2d"]) == 4
                    and all(isinstance(x, (int, float)) for x in item["bbox2d"])
                    for item in loc
                )
        except (json.JSONDecodeError, TypeError):
            pass
    bbox_reward = 1.0 if bbox_format_ok else 0.0

    # Check type format and match
    ground_truth_answer = _extract_ground_truth_answer(ground_truth, extra_info)
    expected_type = (
        "good"
        if ground_truth_answer.lower().startswith("no")
        else (
            extra_info.get("type", "unspecified")
            if extra_info
            else "unspecified"
        )
    )
    type_reward = 0.0
    if type_text and isinstance(type_text, str):
        type_reward = 1.0 if type_text.lower() == expected_type.lower() else 0.0

    model_answer = ""
    answer_pattern = r"\\boxed{([^}]+)}"
    answer_list = re.findall(answer_pattern, predict_no_think, flags=re.DOTALL)
    if len(answer_list) == 0:
        acc_reward = 0.0
        is_format_error = True
    else:
        if len(answer_list) > 1:
            is_format_error = True

        model_answer = answer_list[-1]
        if rule_math_verify(ground_truth_answer, model_answer):
            acc_reward = 1.0
        else:
            acc_reward = (
                1.0
                if generative_verify(
                    extra_info["question"], ground_truth_answer, model_answer
                )
                else 0.0
            )

    format_reward = -1.0 if is_format_error else 0.0
    if extra_info:
        print(
            f" [DEBUG] query={extra_info['question']}, {ground_truth=}, {model_answer=}, {acc_reward=}, {format_reward=}"
        )
    return (
        1.2 * acc_reward
        + 0.4 * format_reward
        + 0.4 * bbox_reward
        + 0.4 * type_reward
    )


# Enhanced prompt for defect detection with type evaluation
ENHANCED_DEFECT_VERIFY_PROMPT = """# CONTEXT #
You are evaluating a defect detection response for industrial anomaly inspection. The model should identify defects accurately and provide proper defect type classification when defects are present.

# OBJECTIVE #
Evaluate the student's response on multiple dimensions:
1. Defect detection accuracy (yes/no decision)
2. Defect type classification accuracy (when defects are present)
3. Overall reasoning quality for industrial inspection

# EVALUATION CRITERIA #
For defect detection:
- "yes" responses should match when defects are present
- "no" responses should match when no defects are present

For defect type classification:
- When defects are present, the predicted type should semantically match the ground truth type
- Common defect types: crack, scratch, hole, discoloration, surface anomaly, contamination
- "good" type should only be used when no defects are present
- Minor variations in terminology are acceptable if semantically equivalent

# TONE #
Professional, scientific, focused on industrial quality control.

# RESPONSE: MARKDOWN REPORT #
## Detection Accuracy
[Whether the student's defect detection decision (yes/no) matches the reference. (TRUE or FALSE)]

## Type Accuracy  
[Whether the student's defect type classification matches the reference when applicable. (TRUE or FALSE or N/A)]

## Overall Equivalence
[Whether the overall response is equivalent to the reference answer. (TRUE or FALSE)]

# ATTENTION #
- The reference answer is ALWAYS correct
- Consider both detection accuracy and type accuracy in overall judgment
- For "no defect" cases, type should be "good"
- Output only TRUE, FALSE, or N/A in each judgment section

**Question**:
{query}

**Reference Answer**
{gold_ans}

**Reference Type**
{gold_type}

## Student Answer
{pred_ans}

## Student Type
{pred_type}"""


def _improved_iou_reward(pred_boxes, gt_boxes, max_pred_boxes=3):
    """
    Improved IoU-based reward calculation with proper union computation.
    Limits predicted boxes to max_pred_boxes and uses proper IoU formula.
    """
    # Limit predicted boxes to avoid excessive outputs
    if len(pred_boxes) > max_pred_boxes:
        # Keep the first max_pred_boxes predictions
        pred_boxes = pred_boxes[:max_pred_boxes]

    # Empty cases
    if len(gt_boxes) == 0 and len(pred_boxes) == 0:
        return 1.0
    if len(gt_boxes) == 0 and len(pred_boxes) > 0:
        # Penalty for false positive detections
        return max(0.0, 1.0 - 0.2 * len(pred_boxes))
    if len(gt_boxes) > 0 and len(pred_boxes) == 0:
        # Penalty for missing detections
        return 0.0

    # Compute proper IoU with intersection/union formula
    def compute_proper_iou(box1, box2):
        """Compute IoU = intersection / union"""
        x1_inter = max(box1[0], box2[0])
        y1_inter = max(box1[1], box2[1])
        x2_inter = min(box1[2], box2[2])
        y2_inter = min(box1[3], box2[3])

        inter_area = max(0.0, x2_inter - x1_inter) * max(
            0.0, y2_inter - y1_inter
        )

        area1 = max(0.0, box1[2] - box1[0]) * max(0.0, box1[3] - box1[1])
        area2 = max(0.0, box2[2] - box2[0]) * max(0.0, box2[3] - box2[1])
        union_area = area1 + area2 - inter_area

        return inter_area / union_area if union_area > 0 else 0.0

    # Compute best matching IoU for each GT box
    gt_ious = []
    for gt_box in gt_boxes:
        best_iou = 0.0
        for pred_box in pred_boxes:
            iou = compute_proper_iou(gt_box, pred_box)
            best_iou = max(best_iou, iou)
        gt_ious.append(best_iou)

    # Compute best matching IoU for each predicted box
    pred_ious = []
    for pred_box in pred_boxes:
        best_iou = 0.0
        for gt_box in gt_boxes:
            iou = compute_proper_iou(pred_box, gt_box)
            best_iou = max(best_iou, iou)
        pred_ious.append(best_iou)

    # Use the average of both directions, weighted by recall and precision
    recall = sum(gt_ious) / len(gt_ious) if gt_ious else 0.0
    precision = sum(pred_ious) / len(pred_ious) if pred_ious else 0.0

    # F1-score like combination
    if recall + precision > 0:
        f1_score = 2 * (recall * precision) / (recall + precision)
    else:
        f1_score = 0.0

    # Apply progressive IoU thresholds for better reward shaping
    if f1_score >= 0.7:
        return 1.0
    elif f1_score >= 0.5:
        return 0.8 + 0.2 * (f1_score - 0.5) / 0.2
    elif f1_score >= 0.3:
        return 0.5 + 0.3 * (f1_score - 0.3) / 0.2
    else:
        return f1_score / 0.3 * 0.5


def _progressive_grounding_reward(
    pred_boxes,
    gt_boxes,
    pred_type,
    gt_type,
    max_pred_boxes=3,
    training_stage="early",
):
    """
    Progressive grounding reward that adapts to different training stages.
    More lenient in early stages, gradually becomes more strict.
    """
    # Stage-specific parameters
    stage_params = {
        "early": {"iou_base": 0.1, "iou_good": 0.3, "type_weight": 0.1},
        "mid": {"iou_base": 0.2, "iou_good": 0.5, "type_weight": 0.2},
        "late": {"iou_base": 0.3, "iou_good": 0.7, "type_weight": 0.3},
    }
    params = stage_params.get(training_stage, stage_params["mid"])

    # Limit predicted boxes
    if len(pred_boxes) > max_pred_boxes:
        pred_boxes = pred_boxes[:max_pred_boxes]

    # Case 1: No defects expected
    if len(gt_boxes) == 0:
        if len(pred_boxes) == 0:
            return 1.0  # Perfect - no false positives
        else:
            # Gentle penalty for false positives
            return max(0.5, 1.0 - 0.1 * len(pred_boxes))

    # Case 2: Defects expected but none predicted
    if len(pred_boxes) == 0:
        return 0.2  # Small reward for at least trying to detect

    # Case 3: Both GT and predictions exist - compute staged IoU reward
    def compute_staged_iou_reward():
        max_ious = []
        for gt_box in gt_boxes:
            best_iou = 0.0
            for pred_box in pred_boxes:
                iou = _bbox_iou_xyxy(gt_box, pred_box)
                best_iou = max(best_iou, iou)
            max_ious.append(best_iou)

        avg_iou = sum(max_ious) / len(max_ious) if max_ious else 0.0

        # Progressive IoU scoring
        if avg_iou >= params["iou_good"]:
            return 1.0
        elif avg_iou >= params["iou_base"]:
            # Linear interpolation between base and good
            ratio = (avg_iou - params["iou_base"]) / (
                params["iou_good"] - params["iou_base"]
            )
            return 0.5 + 0.5 * ratio
        else:
            # Even small IoU gets some reward
            return min(0.5, avg_iou / params["iou_base"] * 0.5)

    spatial_reward = compute_staged_iou_reward()

    # Detection attempt bonus - reward for trying to locate defects
    detection_bonus = min(len(pred_boxes), len(gt_boxes)) / max(
        len(pred_boxes), len(gt_boxes), 1
    )
    detection_bonus *= 0.3  # Bonus weight

    # Type consistency (lighter weight in early stages)
    type_reward = 0.0
    if pred_type and gt_type:
        if pred_type.lower() == gt_type.lower():
            type_reward = 1.0
        elif pred_type.lower() != "good" and gt_type.lower() != "good":
            type_reward = 0.5  # Partial credit for detecting something

    # Combine with stage-adaptive weights
    final_reward = (
        0.6 * spatial_reward
        + 0.3 * detection_bonus
        + params["type_weight"] * type_reward
    )

    return min(1.0, final_reward)


def _curriculum_grounding_reward(
    pred_boxes,
    gt_boxes,
    pred_type,
    gt_type,
    max_pred_boxes=3,
    curriculum_step=0,
    total_steps=10000,
):
    """
    Curriculum learning approach - gradually increase difficulty.
    """
    # Calculate curriculum progress (0.0 to 1.0)
    progress = min(1.0, curriculum_step / total_steps)

    # Adaptive thresholds based on progress
    easy_threshold = 0.1 + 0.2 * progress  # 0.1 -> 0.3
    hard_threshold = 0.3 + 0.4 * progress  # 0.3 -> 0.7

    # Limit predicted boxes
    if len(pred_boxes) > max_pred_boxes:
        pred_boxes = pred_boxes[:max_pred_boxes]

    # Base case handling
    if len(gt_boxes) == 0 and len(pred_boxes) == 0:
        return 1.0
    if len(gt_boxes) == 0 and len(pred_boxes) > 0:
        return max(0.3, 1.0 - 0.2 * len(pred_boxes))
    if len(gt_boxes) > 0 and len(pred_boxes) == 0:
        return 0.1 + 0.2 * (1 - progress)  # More forgiving early on

    # Compute adaptive IoU reward
    ious = []
    for gt_box in gt_boxes:
        best_iou = 0.0
        for pred_box in pred_boxes:
            iou = _bbox_iou_xyxy(gt_box, pred_box)
            best_iou = max(best_iou, iou)
        ious.append(best_iou)

    avg_iou = sum(ious) / len(ious) if ious else 0.0

    # Multi-tier reward structure
    if avg_iou >= hard_threshold:
        iou_reward = 1.0
    elif avg_iou >= easy_threshold:
        # Smooth transition between easy and hard
        ratio = (avg_iou - easy_threshold) / (hard_threshold - easy_threshold)
        iou_reward = 0.5 + 0.5 * ratio
    else:
        # Even minimal overlap gets some reward early in training
        early_bonus = (1 - progress) * 0.3
        iou_reward = early_bonus + (avg_iou / easy_threshold) * 0.5

    # Participation reward - encourage trying
    participation = min(len(pred_boxes), 3) / 3 * 0.2

    # Type bonus (grows with progress)
    type_bonus = 0.0
    if pred_type and gt_type and pred_type.lower() == gt_type.lower():
        type_bonus = progress * 0.3

    final_reward = iou_reward + participation + type_bonus
    return min(1.0, final_reward)


def _multi_level_grounding_reward(
    pred_boxes, gt_boxes, pred_type, gt_type, max_pred_boxes=3
):
    """
    Multi-level reward system that gives partial credit at different levels.
    """
    # Limit predicted boxes
    if len(pred_boxes) > max_pred_boxes:
        pred_boxes = pred_boxes[:max_pred_boxes]

    # Level 0: Basic detection attempt (always some reward for trying)
    attempt_reward = 0.1 if len(pred_boxes) > 0 and len(gt_boxes) > 0 else 0.0

    # Level 1: Rough localization (very low IoU threshold)
    rough_localization = 0.0
    if len(gt_boxes) > 0 and len(pred_boxes) > 0:
        any_overlap = False
        for gt_box in gt_boxes:
            for pred_box in pred_boxes:
                iou = _bbox_iou_xyxy(gt_box, pred_box)
                if iou > 0.05:  # Very low threshold
                    any_overlap = True
                    break
            if any_overlap:
                break
        rough_localization = 0.2 if any_overlap else 0.0

    # Level 2: Reasonable localization
    reasonable_localization = 0.0
    if len(gt_boxes) > 0 and len(pred_boxes) > 0:
        good_matches = 0
        for gt_box in gt_boxes:
            best_iou = 0.0
            for pred_box in pred_boxes:
                iou = _bbox_iou_xyxy(gt_box, pred_box)
                best_iou = max(best_iou, iou)
            if best_iou > 0.2:
                good_matches += 1
        reasonable_localization = (good_matches / len(gt_boxes)) * 0.3

    # Level 3: Precise localization
    precise_localization = 0.0
    if len(gt_boxes) > 0 and len(pred_boxes) > 0:
        precise_matches = 0
        for gt_box in gt_boxes:
            best_iou = 0.0
            for pred_box in pred_boxes:
                iou = _bbox_iou_xyxy(gt_box, pred_box)
                best_iou = max(best_iou, iou)
            if best_iou > 0.5:
                precise_matches += 1
        precise_localization = (precise_matches / len(gt_boxes)) * 0.3

    # Level 4: Type consistency bonus
    type_bonus = 0.0
    if pred_type and gt_type:
        if len(gt_boxes) == 0 and pred_type.lower() == "good":
            type_bonus = 0.1
        elif len(gt_boxes) > 0 and pred_type.lower() == gt_type.lower():
            type_bonus = 0.1

    # Perfect case bonus
    perfect_bonus = 0.0
    if len(gt_boxes) == 0 and len(pred_boxes) == 0:
        perfect_bonus = 1.0
    elif len(gt_boxes) > 0 and len(pred_boxes) > 0:
        all_precise = True
        for gt_box in gt_boxes:
            best_iou = 0.0
            for pred_box in pred_boxes:
                iou = _bbox_iou_xyxy(gt_box, pred_box)
                best_iou = max(best_iou, iou)
            if best_iou < 0.7:
                all_precise = False
                break
        if (
            all_precise
            and pred_type
            and gt_type
            and pred_type.lower() == gt_type.lower()
        ):
            perfect_bonus = 0.1

    total_reward = (
        attempt_reward
        + rough_localization
        + reasonable_localization
        + precise_localization
        + type_bonus
        + perfect_bonus
    )

    return min(1.0, total_reward)


def compute_enhanced_score(
    predict_str: str,
    ground_truth: str,
    extra_info=None,
    grounding_strategy="multi_level",
    training_stage="mid",
    curriculum_step=None,
    use_bbox_reward=True,
    bbox_reward_weight=0.8,
) -> float:
    """
    Enhanced scoring function with multiple grounding reward strategies.

    Args:
        grounding_strategy: "multi_level", "progressive", "curriculum", or "original"
        training_stage: "early", "mid", "late" (for progressive strategy)
        curriculum_step: Current training step (for curriculum strategy)
        use_bbox_reward: Whether to include bbox/grounding reward in final score
        bbox_reward_weight: Weight for bbox reward component (default: 0.8)
    """
    is_format_error = False

    # Format validation (same as before)
    count_think_1 = predict_str.count("<think>")
    count_think_2 = predict_str.count("</think>")
    if count_think_1 != count_think_2:
        is_format_error = True

    count_vision_1 = predict_str.count("<|vision_start|><|image_pad|>")
    count_vision_2 = predict_str.count("<|image_pad|><|vision_end|>")
    if count_vision_1 != count_vision_2:
        is_format_error = True

    predict_no_think = predict_str.split("</think>")[-1].strip()
    count_answer_1 = predict_no_think.count("<answer>")
    count_answer_2 = predict_no_think.count("</answer>")
    if count_answer_1 != count_answer_2:
        is_format_error = True

    count_location_1 = predict_no_think.count("<location>")
    count_location_2 = predict_no_think.count("</location>")
    if count_location_1 != count_location_2:
        is_format_error = True

    count_type_1 = predict_no_think.count("<type>")
    count_type_2 = predict_no_think.count("</type>")
    if count_type_1 != count_type_2:
        is_format_error = True

    # Extract components
    answer_text = extract_answer(predict_no_think)
    location_text = extract_location(predict_no_think)
    type_text = extract_type(predict_no_think)

    # Validate bbox format with 3-box limit
    bbox_format_ok = False
    if location_text:
        try:
            loc = json.loads(location_text)
            if isinstance(loc, list) and len(loc) <= 3:  # Limit to 3 boxes
                bbox_format_ok = all(
                    isinstance(item, dict)
                    and ("bbox2d" in item or "bbox_2d" in item)
                    and isinstance(
                        (item.get("bbox2d") or item.get("bbox_2d")), list
                    )
                    and len((item.get("bbox2d") or item.get("bbox_2d"))) == 4
                    for item in loc
                )
        except (json.JSONDecodeError, TypeError):
            pass

    # Parse bounding boxes and ground truth
    pred_boxes = _parse_predicted_bboxes(location_text)
    pred_boxes = _maybe_rescale_pred_boxes_to_original(pred_boxes, extra_info)
    gt_boxes = _extract_gt_bboxes(ground_truth, extra_info)

    # Get ground truth information
    ground_truth_answer = _extract_ground_truth_answer(ground_truth, extra_info)
    expected_type = (
        "good"
        if ground_truth_answer.lower().startswith("no")
        else (
            extra_info.get("type", "unspecified")
            if extra_info
            else "unspecified"
        )
    )

    # Choose grounding reward strategy (optional)
    if use_bbox_reward:
        if grounding_strategy == "multi_level":
            grounding_reward = _multi_level_grounding_reward(
                pred_boxes, gt_boxes, type_text, expected_type
            )
        elif grounding_strategy == "progressive":
            grounding_reward = _progressive_grounding_reward(
                pred_boxes,
                gt_boxes,
                type_text,
                expected_type,
                training_stage=training_stage,
            )
        elif grounding_strategy == "curriculum":
            curriculum_step = curriculum_step or 0
            grounding_reward = _curriculum_grounding_reward(
                pred_boxes,
                gt_boxes,
                type_text,
                expected_type,
                curriculum_step=curriculum_step,
            )
        else:  # "original" or fallback
            grounding_reward = _improved_iou_reward(pred_boxes, gt_boxes)
    else:
        # No bbox reward - set to neutral value
        grounding_reward = 0.0

    # Enhanced LLM judge evaluation with type consideration
    if not answer_text:
        acc_reward = 0.0
        type_acc_reward = 0.0
        is_format_error = True
    elif len(answer_text) >= 1000:
        acc_reward = 0.0
        type_acc_reward = 0.0
        is_format_error = True
    else:
        question_text = extra_info["question"] if extra_info else ""
        client_idx = random.randint(0, len(client_list) - 1)
        client = client_list[client_idx]
        model_name = model_name_list[client_idx]

        full_prompt = ENHANCED_DEFECT_VERIFY_PROMPT.format(
            query=question_text,
            gold_ans=ground_truth_answer,
            gold_type=expected_type,
            pred_ans=answer_text,
            pred_type=type_text or "N/A",
        )

        acc_reward = 0.0
        type_acc_reward = 0.0

        for ix in range(3):  # Reduced attempts for efficiency
            try:
                chat_response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "user", "content": full_prompt},
                    ],
                    seed=random.randint(0, 1000000),
                    temperature=0.3,
                )
                response = chat_response.choices[0].message.content.strip()

                # Parse detection accuracy
                detection_part = (
                    response.split("## Detection Accuracy")[-1]
                    .split("## Type Accuracy")[0]
                    .lower()
                )
                if "true" in detection_part and "false" not in detection_part:
                    acc_reward = 1.0
                elif "false" in detection_part and "true" not in detection_part:
                    acc_reward = 0.0

                # Parse type accuracy
                type_part = (
                    response.split("## Type Accuracy")[-1]
                    .split("## Overall Equivalence")[0]
                    .lower()
                )
                if "true" in type_part and "false" not in type_part:
                    type_acc_reward = 1.0
                elif "false" in type_part and "true" not in type_part:
                    type_acc_reward = 0.0
                elif "n/a" in type_part:
                    type_acc_reward = 0.5  # Neutral for N/A cases

                break  # Success, exit retry loop

            except Exception as e:
                log.error(f"LLM judge error attempt {ix + 1}: {e}")
                continue

    # Tool usage reward
    tool_reward = 1.0 if count_vision_1 > 0 and acc_reward > 0.5 else 0.0

    # Format penalty
    format_reward = -1.0 if is_format_error else 0.0

    # Bbox format reward
    bbox_format_reward = 1.0 if bbox_format_ok else 0.0

    # Final score calculation with optional bbox reward
    if use_bbox_reward:
        final_score = (
            0.6 * acc_reward  # Answer accuracy
            + bbox_reward_weight
            * grounding_reward  # Configurable grounding reward weight
            + 0.4 * type_acc_reward  # Type accuracy reward
            + 0.8 * tool_reward  # Tool usage reward
            + 0.2 * format_reward  # Format penalty
            + 0.2 * bbox_format_reward  # Bbox format reward
        )
    else:
        # No bbox reward - focus on other components
        final_score = (
            0.8 * acc_reward  # Answer accuracy (increased weight)
            + 0.6 * type_acc_reward  # Type accuracy reward (increased weight)
            + 1.0 * tool_reward  # Tool usage reward (increased weight)
            + 0.2 * format_reward  # Format penalty
            # bbox_format_reward omitted when bbox reward disabled
        )

    if extra_info:
        if use_bbox_reward:
            log.info(
                f"Enhanced score breakdown: acc={acc_reward:.2f}, grounding={grounding_reward:.2f}, "
                f"type={type_acc_reward:.2f}, tool={tool_reward:.2f}, format={format_reward:.2f}, "
                f"bbox_fmt={bbox_format_reward:.2f}, final={final_score:.2f}"
            )
        else:
            log.info(
                f"Score breakdown (no bbox): acc={acc_reward:.2f}, "
                f"type={type_acc_reward:.2f}, tool={tool_reward:.2f}, format={format_reward:.2f}, "
                f"final={final_score:.2f}"
            )

    return final_score


if __name__ == "__main__":
    predict_str = "The answer is <think> 2 + 2 = 4 </think> <answer> right </answer> <answer> left </answer>"
    ground_truth = "left"
    extra_info = {
        "answer": "The woman is to the left of the man who is holding the camera.",
        "id": 0,
        "image": "/cpfs/user/honglingyi/DATA/LLM/Vstar/gqa/images/713270.jpg",
        "pred_ans": "The woman is to the right of the man who is holding the camera.",
        "question": "Is the woman to the left or to the right of the man who is holding the camera?",
    }

    score = compute_score(predict_str, ground_truth, extra_info)
    print(f"Score: {score}")
