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
工具名称到退化类型的映射表

用于从 <tool_call> 中反推模型识别的退化类型
"""

# 工具名称 → 退化类型映射
TOOL_TO_DEGRADATION_TYPE = {
    # ===== 去噪 (Noise) =====
    "swinir_denoising": "noise",
    "mprnet_denoising": "noise",
    
    # ===== 去模糊 (Blur) =====
    # 运动模糊
    "restormer_motion_deblurring": "motion blur",
    "mprnet_motion_deblurring": "motion blur",
    "xrestormer_motion_deblurring": "motion blur",
    # 散焦模糊
    "restormer_defocus_deblurring": "defocus blur",
    "drbnet_defocus_deblurring": "defocus blur",
    
    # ===== 去雨 (Rain) =====
    "restormer_deraining": "rain",
    "mprnet_deraining": "rain",
    "xrestormer_deraining": "rain",
    
    # ===== JPEG伪影去除 (JPEG Compression Artifact) =====
    "swinir_jpeg_artifact_removal": "jpeg compression artifact",
    "fbcnn_jpeg_artifact_removal": "jpeg compression artifact",
    
    # ===== 超分辨率 (Low Resolution) =====
    "swinir_super_resolution": "low resolution",
    
    # ===== 去雾 (Haze) =====
    "dehazeformer_dehaze": "haze",
    
    # ===== 增亮/暗图处理 (Dark) =====
    # BrighteningToolbox中的3个工具都对应dark
    "constant_shift": "dark",
    "gamma_correction": "dark",
    "histogram_equalization": "dark",
    
    # ===== 质量评估工具（不对应具体退化类型）=====
    # "fbcnn_blind_quality_assessment": None,  # 只评估不修复
    
    # ===== 视觉工具箱（通用工具，不对应具体退化）=====
    # "visual_toolbox": None,
    # "visual_toolbox_v2": None,
    # "visual_toolbox_v3": None,
    # "visual_toolbox_v4": None,
    # "visual_toolbox_v5": None,
    # "crop_image": None,
}


def get_degradation_type_from_tool(tool_name: str) -> str:
    """
    从工具名称获取对应的退化类型
    
    Args:
        tool_name: 工具名称（如 "swinir_denoising"）
        
    Returns:
        退化类型（如 "noise"），如果工具不对应具体退化类型则返回None
    """
    return TOOL_TO_DEGRADATION_TYPE.get(tool_name, None)


def get_all_degradation_types():
    """获取所有唯一的退化类型"""
    return sorted(set(TOOL_TO_DEGRADATION_TYPE.values()))


# 测试代码
if __name__ == "__main__":
    print("=" * 80)
    print("工具名称到退化类型映射表")
    print("=" * 80)
    
    print("\n【所有支持的退化类型】")
    degradation_types = get_all_degradation_types()
    for i, deg_type in enumerate(degradation_types, 1):
        print(f"  {i}. {deg_type}")
    
    print(f"\n总共 {len(degradation_types)} 种退化类型")
    
    print("\n【工具到退化类型映射】")
    for tool_name, deg_type in sorted(TOOL_TO_DEGRADATION_TYPE.items()):
        print(f"  {tool_name:<40} → {deg_type}")
    
    print(f"\n总共 {len(TOOL_TO_DEGRADATION_TYPE)} 个工具")
    
    print("\n【测试映射】")
    test_tools = [
        "swinir_denoising",
        "constant_shift",
        "swinir_super_resolution",
        "fbcnn_jpeg_artifact_removal",
        "unknown_tool"
    ]
    
    for tool in test_tools:
        deg_type = get_degradation_type_from_tool(tool)
        status = "✅" if deg_type else "❌"
        print(f"  {status} {tool:<40} → {deg_type}")
    
    print("\n" + "=" * 80)

