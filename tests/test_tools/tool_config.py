#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具池配置文件
按退化类型分组，可通过注释来选择要测试的工具
"""

# ============================================================
# 工具池配置
# 格式: (tool_name, display_name)
# 使用方法: 在不需要测试的工具前添加 # 注释掉即可
# ============================================================

TOOL_POOL = {
    # ========================================
    # 1. 去雾 (Haze)
    # ========================================
    "haze": [
        ("dehazeformer_dehaze", "DehazeFormer"),
    ],
    
    # ========================================
    # 2. 去噪 (Noise)
    # ========================================
    "noise": [
        # ----- 传统去噪工具 -----
        ("swinir_denoising", "SwinIR"),
        ("mprnet_denoising", "MPRNet"),
        
        # ----- SCUNet系列（真实噪声，推荐）-----
        ("scunet_real_denoising_psnr", "SCUNet-Real-PSNR"),  # PSNR优化，指标更好
        ("scunet_real_denoising_gan", "SCUNet-Real-GAN"),    # GAN优化，视觉效果更好
        
        # ----- SCUNet系列（合成噪声）-----
        ("scunet_color_denoising", "SCUNet-Color"),          # 彩色图像去噪（15/25/50级）
        ("scunet_gray_denoising", "SCUNet-Gray"),            # 灰度图像去噪（15/25/50级）
    ],
    
    # ========================================
    # 3. 运动去模糊 (Motion Blur)
    # ========================================
    "motion_blur": [
        ("restormer_motion_deblurring", "Restormer"),
        ("mprnet_motion_deblurring", "MPRNet"),
        ("xrestormer_motion_deblurring", "XRestormer"),
    ],
    
    # ========================================
    # 4. 散焦去模糊 (Defocus Blur)
    # ========================================
    "defocus_blur": [
        ("restormer_defocus_deblurring", "Restormer"),
        ("drbnet_defocus_deblurring", "DRBNet"),
    ],
    
    # ========================================
    # 5. 去雨 (Rain)
    # ========================================
    "rain": [
        ("restormer_deraining", "Restormer"),
        ("mprnet_deraining", "MPRNet"),
        ("xrestormer_deraining", "XRestormer"),
    ],
    
    # ========================================
    # 6. JPEG伪影去除 (JPEG Compression Artifact)
    # ========================================
    "jpeg": [
        ("swinir_jpeg_artifact_removal", "SwinIR"),
        ("fbcnn_jpeg_artifact_removal", "FBCNN"),
    ],
    
    # ========================================
    # 7. 超分辨率 (Low Resolution)
    # ========================================
    "low_resolution": [
        ("swinir_super_resolution", "SwinIR"),
    ],
    
    # ========================================
    # 8. 低光增强 / 暗图处理 (Dark / Low-Light)
    # ========================================
    "dark": [
        # ----- 传统增亮方法 -----
        ("constant_shift", "Constant Shift"),                # 常数平移（简单快速）
        ("gamma_correction", "Gamma Correction"),            # Gamma校正（常用）
        ("histogram_equalization", "Histogram Equalization"),# 直方图均衡化
        
        # ----- Retinexformer系列（深度学习，推荐）-----
        ("retinexformer_enhance", "Retinexformer-General"),  # 通用工具（推荐）⭐
        
        # ----- Retinexformer专用模型 -----
        # 如果不需要测试特定数据集的模型，可以注释掉下面的工具
        # ("retinexformer_lol_v1", "Retinexformer-LOLv1"),
        # ("retinexformer_lol_v2_real", "Retinexformer-LOLv2-Real"),
        # ("retinexformer_lol_v2_synthetic", "Retinexformer-LOLv2-Syn"),
        ("retinexformer_sdsd_indoor", "Retinexformer-SDSD-Indoor"),
        # ("retinexformer_sdsd_outdoor", "Retinexformer-SDSD-Outdoor"),
        # ("retinexformer_sid", "Retinexformer-SID"),
        # ("retinexformer_smid", "Retinexformer-SMID"),
        # ("retinexformer_fivek", "Retinexformer-FiveK"),
    ],
}


# ============================================================
# 使用示例
# ============================================================

"""
示例1: 只测试部分去噪工具
修改noise配置如下：

"noise": [
    ("swinir_denoising", "SwinIR"),
    # ("mprnet_denoising", "MPRNet"),  # 注释掉不测试
    ("scunet_real_denoising_psnr", "SCUNet-Real-PSNR"),
    # ("scunet_real_denoising_gan", "SCUNet-Real-GAN"),  # 注释掉不测试
    # ("scunet_color_denoising", "SCUNet-Color"),  # 注释掉不测试
    # ("scunet_gray_denoising", "SCUNet-Gray"),  # 注释掉不测试
],

这样就只会测试SwinIR和SCUNet-Real-PSNR两个工具。
"""

"""
示例2: 只测试Retinexformer通用工具
修改dark配置如下：

"dark": [
    # ("constant_shift", "Constant Shift"),  # 注释掉传统方法
    # ("gamma_correction", "Gamma Correction"),
    # ("histogram_equalization", "Histogram Equalization"),
    
    ("retinexformer_enhance", "Retinexformer-General"),  # 只保留通用工具
    
    # 注释掉所有专用模型
    # ("retinexformer_lol_v1", "Retinexformer-LOLv1"),
    # ("retinexformer_lol_v2_real", "Retinexformer-LOLv2-Real"),
    # ...
],
"""

"""
示例3: 快速测试（每种类型只保留1-2个代表性工具）
"noise": [
    ("swinir_denoising", "SwinIR"),
    ("scunet_real_denoising_psnr", "SCUNet-Real-PSNR"),
],

"motion_blur": [
    ("restormer_motion_deblurring", "Restormer"),
],

"dark": [
    ("gamma_correction", "Gamma Correction"),
    ("retinexformer_enhance", "Retinexformer-General"),
],
"""


# ============================================================
# 工具类名映射（自动生成，无需修改）
# ============================================================

TOOL_CLASS_MAP = {
    # DehazeFormer
    "dehazeformer_dehaze": ("DehazeFormerToolbox", "DehazeFormerToolbox"),
    
    # SwinIR
    "swinir_denoising": ("SwinIRToolbox", "SwinIRDenoisingToolbox"),
    "swinir_jpeg_artifact_removal": ("SwinIRToolbox", "SwinIRJpegArtifactRemovalToolbox"),
    "swinir_super_resolution": ("SwinIRToolbox", "SwinIRSrToolbox"),
    
    # MPRNet
    "mprnet_denoising": ("MPRNetToolbox", "MPRNetDenoisingToolbox"),
    "mprnet_motion_deblurring": ("MPRNetToolbox", "MPRNetMotionDeblurringToolbox"),
    "mprnet_deraining": ("MPRNetToolbox", "MPRNetDeraininingToolbox"),
    
    # Restormer
    "restormer_motion_deblurring": ("RestormerToolbox", "RestormerMotionDeblurringToolbox"),
    "restormer_defocus_deblurring": ("RestormerToolbox", "RestormerDefocusDeblurringToolbox"),
    "restormer_deraining": ("RestormerToolbox", "RestormerDerrainingToolbox"),
    
    # XRestormer
    "xrestormer_motion_deblurring": ("XRestormerToolbox", "XRestormerMotionDeblurringToolbox"),
    "xrestormer_deraining": ("XRestormerToolbox", "XRestormerDerainToolbox"),
    
    # FBCNN
    "fbcnn_jpeg_artifact_removal": ("FBCNNToolbox", "FBCNNJpegArtifactRemovalToolbox"),
    
    # DeblurToolbox
    "drbnet_defocus_deblurring": ("DeblurToolbox", "DeblurToolbox"),
    
    # BrighteningToolbox
    "constant_shift": ("BrighteningToolbox", "BrighteningToolbox"),
    "gamma_correction": ("BrighteningToolbox", "BrighteningToolbox"),
    "histogram_equalization": ("BrighteningToolbox", "BrighteningToolbox"),
    
    # SCUNet
    "scunet_real_denoising_psnr": ("SCUNetToolbox", "SCUNetRealDenoisingPSNRToolbox"),
    "scunet_real_denoising_gan": ("SCUNetToolbox", "SCUNetRealDenoisingGANToolbox"),
    "scunet_color_denoising": ("SCUNetToolbox", "SCUNetColorDenoisingToolbox"),
    "scunet_gray_denoising": ("SCUNetToolbox", "SCUNetGrayDenoisingToolbox"),
    
    # Retinexformer
    "retinexformer_enhance": ("RetinexformerToolbox", "RetinexformerToolbox"),
    "retinexformer_lol_v1": ("RetinexformerToolbox", "RetinexformerLOLv1Toolbox"),
    "retinexformer_lol_v2_real": ("RetinexformerToolbox", "RetinexformerLOLv2RealToolbox"),
    "retinexformer_lol_v2_synthetic": ("RetinexformerToolbox", "RetinexformerLOLv2SyntheticToolbox"),
    "retinexformer_sdsd_indoor": ("RetinexformerToolbox", "RetinexformerSDSDIndoorToolbox"),
    "retinexformer_sdsd_outdoor": ("RetinexformerToolbox", "RetinexformerSDSDOutdoorToolbox"),
    "retinexformer_sid": ("RetinexformerToolbox", "RetinexformerSIDToolbox"),
    "retinexformer_smid": ("RetinexformerToolbox", "RetinexformerSMIDToolbox"),
    "retinexformer_fivek": ("RetinexformerToolbox", "RetinexformerFiveKToolbox"),
}


# ============================================================
# 工具API端口配置
# ============================================================

TOOL_API_PORTS = {
    "SwinIR": 5001,
    "DehazeFormer": 5002,
    "DRBNet": 5003,
    "MPRNet": 5004,
    "FBCNN": 5005,
    "Restormer": 5006,
    "XRestormer": 5007,
    "SCUNet": 5008,
    "Retinexformer": 5009,
}


# ============================================================
# 预设配置方案
# ============================================================

# 快速测试配置（每种类型1-2个代表性工具）
PRESET_QUICK = {
    "haze": [
        ("dehazeformer_dehaze", "DehazeFormer"),
    ],
    "noise": [
        ("swinir_denoising", "SwinIR"),
        ("scunet_real_denoising_psnr", "SCUNet-Real-PSNR"),
    ],
    "motion_blur": [
        ("restormer_motion_deblurring", "Restormer"),
    ],
    "defocus_blur": [
        ("restormer_defocus_deblurring", "Restormer"),
    ],
    "rain": [
        ("restormer_deraining", "Restormer"),
    ],
    "jpeg": [
        ("swinir_jpeg_artifact_removal", "SwinIR"),
    ],
    "low_resolution": [
        ("swinir_super_resolution", "SwinIR"),
    ],
    "dark": [
        ("gamma_correction", "Gamma Correction"),
        ("retinexformer_enhance", "Retinexformer-General"),
    ],
}

# 标准测试配置（每种类型的主要工具）
PRESET_STANDARD = {
    "haze": [
        ("dehazeformer_dehaze", "DehazeFormer"),
    ],
    "noise": [
        ("swinir_denoising", "SwinIR"),
        ("mprnet_denoising", "MPRNet"),
        ("scunet_real_denoising_psnr", "SCUNet-Real-PSNR"),
        ("scunet_real_denoising_gan", "SCUNet-Real-GAN"),
    ],
    "motion_blur": [
        ("restormer_motion_deblurring", "Restormer"),
        ("mprnet_motion_deblurring", "MPRNet"),
        ("xrestormer_motion_deblurring", "XRestormer"),
    ],
    "defocus_blur": [
        ("restormer_defocus_deblurring", "Restormer"),
        ("drbnet_defocus_deblurring", "DRBNet"),
    ],
    "rain": [
        ("restormer_deraining", "Restormer"),
        ("mprnet_deraining", "MPRNet"),
        ("xrestormer_deraining", "XRestormer"),
    ],
    "jpeg": [
        ("swinir_jpeg_artifact_removal", "SwinIR"),
        ("fbcnn_jpeg_artifact_removal", "FBCNN"),
    ],
    "low_resolution": [
        ("swinir_super_resolution", "SwinIR"),
    ],
    "dark": [
        ("gamma_correction", "Gamma Correction"),
        ("histogram_equalization", "Histogram Equalization"),
        ("retinexformer_enhance", "Retinexformer-General"),
        ("retinexformer_lol_v2_real", "Retinexformer-LOLv2-Real"),
    ],
}

# 完整测试配置（所有工具）
PRESET_FULL = TOOL_POOL


# ============================================================
# 导出当前激活的工具配置
# ============================================================

# 选择使用哪个配置:
# - TOOL_POOL: 完整工具池（可自定义注释）
# - PRESET_QUICK: 快速测试
# - PRESET_STANDARD: 标准测试
# - PRESET_FULL: 完整测试

# 默认使用完整工具池（可在TOOL_POOL中自定义注释）
ACTIVE_TOOL_CONFIG = TOOL_POOL

# 如果要使用预设配置，取消下面的注释：
# ACTIVE_TOOL_CONFIG = PRESET_QUICK     # 快速测试
# ACTIVE_TOOL_CONFIG = PRESET_STANDARD  # 标准测试
# ACTIVE_TOOL_CONFIG = PRESET_FULL      # 完整测试


# ============================================================
# 工具统计信息
# ============================================================

def get_tool_statistics():
    """获取工具池统计信息"""
    stats = {}
    total_tools = 0
    
    for deg_type, tools in TOOL_POOL.items():
        stats[deg_type] = len(tools)
        total_tools += len(tools)
    
    return stats, total_tools


def print_tool_config():
    """打印当前激活的工具配置"""
    print("\n" + "="*80)
    print("当前激活的工具配置")
    print("="*80)
    
    total = 0
    for deg_type, tools in ACTIVE_TOOL_CONFIG.items():
        print(f"\n【{deg_type}】 - {len(tools)} 个工具")
        for tool_name, display_name in tools:
            print(f"  ✓ {display_name:<35} ({tool_name})")
            total += 1
    
    print(f"\n" + "="*80)
    print(f"总计: {total} 个工具")
    print("="*80 + "\n")


if __name__ == "__main__":
    print_tool_config()
    
    print("\n完整工具池统计:")
    stats, total = get_tool_statistics()
    for deg_type, count in stats.items():
        print(f"  {deg_type}: {count} 个工具")
    print(f"\n总计: {total} 个工具")

