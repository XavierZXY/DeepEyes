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
# from . import gsm8k, math, prime_math, prime_code
import torch
import os

def _default_compute_score(data_source, solution_str, ground_truth, extra_info=None):
    if data_source == "openai/gsm8k":
        from . import gsm8k

        res = gsm8k.compute_score(solution_str, ground_truth)
    elif data_source in ["lighteval/MATH", "DigitalLearningGmbH/MATH-lighteval"]:
        from . import math

        res = math.compute_score(solution_str, ground_truth)
        # [Optional] Math-Verify Integration
        # For enhanced accuracy, consider utilizing Math-Verify (https://github.com/huggingface/Math-Verify).
        # Note: Math-Verify needs to be manually installed via pip: `pip install math-verify`.
        # To use it, override the `compute_score` function with the following implementation:

        # from . import math_verify
        # res = math_verify.compute_score(solution_str, ground_truth)
    elif data_source == "math_dapo" or data_source.startswith("aime"):
        from . import math_dapo

        res = math_dapo.compute_score(solution_str, ground_truth)
    elif data_source in [
        "numina_aops_forum",
        "numina_synthetic_math",
        "numina_amc_aime",
        "numina_synthetic_amc",
        "numina_cn_k12",
        "numina_olympiads",
    ]:
        from . import prime_math

        res = prime_math.compute_score(solution_str, ground_truth)
    elif data_source in ["codecontests", "apps", "codeforces", "taco"]:
        from . import prime_code

        res = prime_code.compute_score(solution_str, ground_truth, continuous=True)
    elif data_source in ["hiyouga/geometry3k"]:
        from . import geo3k

        res = geo3k.compute_score(solution_str, ground_truth)

    elif data_source in ['rag_v2-train']:
        from . import agent
        res = agent.compute_score(solution_str, ground_truth)
    elif data_source in ['rag_v2-test']:
        from . import agent
        res = agent.compute_score_eval(solution_str, ground_truth)

    elif data_source in ['vstar', 'vl_agent', 'chart']:
        from . import vl_agent
        res = vl_agent.compute_score(solution_str, ground_truth, extra_info)

    elif data_source in ['geoguessr']:
        from . import vl_agent
        res = vl_agent.compute_common_reasoning(solution_str, ground_truth, extra_info)

    elif data_source in ['thinklite_eureka', 'xince']:
        from . import vl_agent
        res = vl_agent.compute_score_math(solution_str, ground_truth, extra_info)

    elif data_source in ["frozenlake"]:
        res = 0.0

    elif data_source in ["image_restoration"]:
        from . import image_restoration
        res = image_restoration.compute_score(solution_str, ground_truth, extra_info)
    
    elif data_source in ["image_restoration_v2"]:
        from . import image_restoration
        
        # 从环境变量读取配置（可在训练脚本中设置）
        use_no_reference = os.environ.get('IMAGE_QUALITY_USE_NO_REFERENCE', 'True').lower() == 'true'
        discretize_levels = int(os.environ.get('IMAGE_QUALITY_DISCRETIZE_LEVELS', '0'))
        
        print(f"[INFO] Image Quality Reward Config: use_no_reference={use_no_reference}, discretize_levels={discretize_levels}")
        
        res = image_restoration.compute_score_v2(
            solution_str, 
            ground_truth, 
            extra_info,
            discretize_levels=discretize_levels,  # 离散化等级 (0=连续，10=每10%，20=每5%)
            use_no_reference=use_no_reference,    # True=无参考(NIQE/BRISQUE等), False=有参考(SSIM/LPIPS/PSNR)
        )
        
        # 注意：
        # - use_no_reference=True (默认): 使用无参考指标，适合训练，所有样本都能计算
        # - use_no_reference=False: 使用有参考指标，需要original_image，只对工具执行的样本有效
        # - Wandb展示时会按需计算有参考指标用于可视化

    else:
        raise NotImplementedError(f"Reward function is not implemented for {data_source=}")

    if isinstance(res, dict):
        return res
    elif isinstance(res, (int, float, bool)):
        return float(res)
    else:
        return float(res[0])
