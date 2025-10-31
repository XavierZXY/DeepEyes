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
        
        # 奖励权重配置
        format_reward_weight = float(os.environ.get('FORMAT_REWARD_WEIGHT', '0.3'))
        quality_reward_weight = float(os.environ.get('QUALITY_REWARD_WEIGHT', '0.7'))
        
        # 退化类型奖励配置（不考虑顺序，只看集合匹配）
        enable_degradation_type_reward = os.environ.get('ENABLE_DEGRADATION_TYPE_REWARD', 'False').lower() == 'true'
        degradation_type_reward_weight = float(os.environ.get('DEGRADATION_TYPE_REWARD_WEIGHT', '1.0'))
        
        # 增强格式检查配置
        use_enhanced_format = os.environ.get('USE_ENHANCED_FORMAT', 'False').lower() == 'true'
        
        # 单轮最大工具数限制
        max_tools_per_turn = int(os.environ.get('MAX_TOOLS_PER_TURN', '0'))
        
        # 总工具调用数上限检查（防止过度调用工具）
        enable_total_tools_upper_limit = os.environ.get('ENABLE_TOTAL_TOOLS_UPPER_LIMIT', 'False').lower() == 'true'
        
        print(f"[INFO] Image Quality Reward Config: use_no_reference={use_no_reference}, discretize_levels={discretize_levels}")
        print(f"[INFO] Reward Weights: format={format_reward_weight}, quality={quality_reward_weight}")
        print(f"[INFO] Degradation Type Reward Config: enable={enable_degradation_type_reward}, weight={degradation_type_reward_weight}")
        print(f"[INFO] Enhanced Format Check: enabled={use_enhanced_format}")
        print(f"[INFO] Max Tools Per Turn: {max_tools_per_turn if max_tools_per_turn > 0 else 'unlimited'}")
        print(f"[INFO] Total Tools Upper Limit: {'enabled (degradation_count+1)' if enable_total_tools_upper_limit else 'disabled'}")
        
        res = image_restoration.compute_score_v2(
            solution_str, 
            ground_truth, 
            extra_info,
            discretize_levels=discretize_levels,  # 离散化等级 (0=连续，10=每10%，20=每5%)
            use_no_reference=use_no_reference,    # True=无参考(NIQE/BRISQUE等), False=有参考(SSIM/LPIPS/PSNR)
            enable_degradation_type_reward=enable_degradation_type_reward,  # 是否启用退化类型奖励
            degradation_type_reward_weight=degradation_type_reward_weight,  # 退化类型奖励权重
            format_reward_weight=format_reward_weight,      # 格式奖励权重
            quality_reward_weight=quality_reward_weight,    # 图像质量奖励权重
            use_enhanced_format=use_enhanced_format,        # 是否使用增强格式检查
            max_tools_per_turn=max_tools_per_turn,          # 单轮最大工具数限制
            enable_total_tools_upper_limit=enable_total_tools_upper_limit,  # 总工具调用数上限检查
        )
        
        # 注意：
        # - 默认奖励 = 格式奖励 + 图像质量奖励
        # - 退化类型奖励是可选的额外奖励（需要启用）
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
