#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具诊断脚本 - 用于检查单个工具的返回格式
"""

import sys
import os
from pathlib import Path
from PIL import Image

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def diagnose_tool(tool_name: str, test_image_path: str):
    """
    诊断单个工具的返回格式
    
    Args:
        tool_name: 工具名称（如 'mprnet_motion_deblurring'）
        test_image_path: 测试图像路径
    """
    print(f"\n{'='*80}")
    print(f"诊断工具: {tool_name}")
    print(f"测试图像: {test_image_path}")
    print(f"{'='*80}\n")
    
    # 加载测试图像
    if not os.path.exists(test_image_path):
        print(f"[ERROR] 图像文件不存在: {test_image_path}")
        return
    
    test_image = Image.open(test_image_path).convert('RGB')
    print(f"✓ 测试图像已加载: {test_image.size}")
    
    # 动态加载工具
    print(f"\n1. 加载工具...")
    try:
        # DehazeFormer
        if tool_name == "dehazeformer_dehaze":
            from verl.workers.agent.envs.mm_process_engine.DehazeFormerToolbox import DehazeFormerToolbox
            tool = DehazeFormerToolbox(tool_name, "", {})
        # SwinIR
        elif tool_name == "swinir_denoising":
            from verl.workers.agent.envs.mm_process_engine.SwinIRToolbox import SwinIRDenoisingToolbox
            tool = SwinIRDenoisingToolbox(tool_name, "", {})
        elif tool_name == "swinir_jpeg_artifact_removal":
            from verl.workers.agent.envs.mm_process_engine.SwinIRToolbox import SwinIRJpegArtifactRemovalToolbox
            tool = SwinIRJpegArtifactRemovalToolbox(tool_name, "", {})
        elif tool_name == "swinir_super_resolution":
            from verl.workers.agent.envs.mm_process_engine.SwinIRToolbox import SwinIRSrToolbox
            tool = SwinIRSrToolbox(tool_name, "", {})
        # MPRNet
        elif tool_name == "mprnet_motion_deblurring":
            from verl.workers.agent.envs.mm_process_engine.MPRNetToolbox import MPRNetMotionDeblurringToolbox
            tool = MPRNetMotionDeblurringToolbox(tool_name, "", {})
        elif tool_name == "mprnet_denoising":
            from verl.workers.agent.envs.mm_process_engine.MPRNetToolbox import MPRNetDenoisingToolbox
            tool = MPRNetDenoisingToolbox(tool_name, "", {})
        elif tool_name == "mprnet_deraining":
            from verl.workers.agent.envs.mm_process_engine.MPRNetToolbox import MPRNetDeraininingToolbox
            tool = MPRNetDeraininingToolbox(tool_name, "", {})
        # Restormer
        elif tool_name == "restormer_motion_deblurring":
            from verl.workers.agent.envs.mm_process_engine.RestormerToolbox import RestormerMotionDeblurringToolbox
            tool = RestormerMotionDeblurringToolbox(tool_name, "", {})
        elif tool_name == "restormer_defocus_deblurring":
            from verl.workers.agent.envs.mm_process_engine.RestormerToolbox import RestormerDefocusDeblurringToolbox
            tool = RestormerDefocusDeblurringToolbox(tool_name, "", {})
        elif tool_name == "restormer_deraining":
            from verl.workers.agent.envs.mm_process_engine.RestormerToolbox import RestormerDerrainingToolbox
            tool = RestormerDerrainingToolbox(tool_name, "", {})
        # XRestormer
        elif tool_name == "xrestormer_motion_deblurring":
            from verl.workers.agent.envs.mm_process_engine.XRestormerToolbox import XRestormerMotionDeblurringToolbox
            tool = XRestormerMotionDeblurringToolbox(tool_name, "", {})
        elif tool_name == "xrestormer_deraining":
            from verl.workers.agent.envs.mm_process_engine.XRestormerToolbox import XRestormerDerainToolbox
            tool = XRestormerDerainToolbox(tool_name, "", {})
        # FBCNN
        elif tool_name == "fbcnn_jpeg_artifact_removal":
            from verl.workers.agent.envs.mm_process_engine.FBCNNToolbox import FBCNNJpegArtifactRemovalToolbox
            tool = FBCNNJpegArtifactRemovalToolbox(tool_name, "", {})
        # DeblurToolbox (DRBNet)
        elif tool_name == "drbnet_defocus_deblurring":
            from verl.workers.agent.envs.mm_process_engine.DeblurToolbox import DeblurToolbox
            tool = DeblurToolbox(tool_name, "", {})
        # Brightening tools
        elif tool_name in ["constant_shift", "gamma_correction", "histogram_equalization"]:
            from verl.workers.agent.envs.mm_process_engine.BrighteningToolbox import BrighteningToolbox
            tool = BrighteningToolbox(tool_name, "", {})
        # SCUNet系列
        elif tool_name == "scunet_real_denoising_psnr":
            from verl.workers.agent.envs.mm_process_engine.SCUNetToolbox import SCUNetRealDenoisingPSNRToolbox
            tool = SCUNetRealDenoisingPSNRToolbox(tool_name, "", {})
        elif tool_name == "scunet_real_denoising_gan":
            from verl.workers.agent.envs.mm_process_engine.SCUNetToolbox import SCUNetRealDenoisingGANToolbox
            tool = SCUNetRealDenoisingGANToolbox(tool_name, "", {})
        elif tool_name == "scunet_color_denoising":
            from verl.workers.agent.envs.mm_process_engine.SCUNetToolbox import SCUNetColorDenoisingToolbox
            tool = SCUNetColorDenoisingToolbox(tool_name, "", {})
        elif tool_name == "scunet_gray_denoising":
            from verl.workers.agent.envs.mm_process_engine.SCUNetToolbox import SCUNetGrayDenoisingToolbox
            tool = SCUNetGrayDenoisingToolbox(tool_name, "", {})
        # Retinexformer系列
        elif tool_name == "retinexformer_enhance":
            from verl.workers.agent.envs.mm_process_engine.RetinexformerToolbox import RetinexformerToolbox
            tool = RetinexformerToolbox(tool_name, "", {})
        elif tool_name == "retinexformer_lol_v1":
            from verl.workers.agent.envs.mm_process_engine.RetinexformerToolbox import RetinexformerLOLv1Toolbox
            tool = RetinexformerLOLv1Toolbox(tool_name, "", {})
        elif tool_name == "retinexformer_lol_v2_real":
            from verl.workers.agent.envs.mm_process_engine.RetinexformerToolbox import RetinexformerLOLv2RealToolbox
            tool = RetinexformerLOLv2RealToolbox(tool_name, "", {})
        elif tool_name == "retinexformer_lol_v2_synthetic":
            from verl.workers.agent.envs.mm_process_engine.RetinexformerToolbox import RetinexformerLOLv2SyntheticToolbox
            tool = RetinexformerLOLv2SyntheticToolbox(tool_name, "", {})
        elif tool_name == "retinexformer_sdsd_indoor":
            from verl.workers.agent.envs.mm_process_engine.RetinexformerToolbox import RetinexformerSDSDIndoorToolbox
            tool = RetinexformerSDSDIndoorToolbox(tool_name, "", {})
        elif tool_name == "retinexformer_sdsd_outdoor":
            from verl.workers.agent.envs.mm_process_engine.RetinexformerToolbox import RetinexformerSDSDOutdoorToolbox
            tool = RetinexformerSDSDOutdoorToolbox(tool_name, "", {})
        elif tool_name == "retinexformer_sid":
            from verl.workers.agent.envs.mm_process_engine.RetinexformerToolbox import RetinexformerSIDToolbox
            tool = RetinexformerSIDToolbox(tool_name, "", {})
        elif tool_name == "retinexformer_smid":
            from verl.workers.agent.envs.mm_process_engine.RetinexformerToolbox import RetinexformerSMIDToolbox
            tool = RetinexformerSMIDToolbox(tool_name, "", {})
        elif tool_name == "retinexformer_fivek":
            from verl.workers.agent.envs.mm_process_engine.RetinexformerToolbox import RetinexformerFiveKToolbox
            tool = RetinexformerFiveKToolbox(tool_name, "", {})
        else:
            print(f"[ERROR] 未知工具: {tool_name}")
            print("支持的工具:")
            print("  【去雾】dehazeformer_dehaze")
            print("  【去噪】swinir_denoising, mprnet_denoising")
            print("         scunet_real_denoising_psnr, scunet_real_denoising_gan")
            print("         scunet_color_denoising, scunet_gray_denoising")
            print("  【去模糊-运动】restormer_motion_deblurring, mprnet_motion_deblurring, xrestormer_motion_deblurring")
            print("  【去模糊-散焦】restormer_defocus_deblurring, drbnet_defocus_deblurring")
            print("  【去雨】restormer_deraining, mprnet_deraining, xrestormer_deraining")
            print("  【JPEG伪影】swinir_jpeg_artifact_removal, fbcnn_jpeg_artifact_removal")
            print("  【超分辨率】swinir_super_resolution")
            print("  【低光增强】constant_shift, gamma_correction, histogram_equalization")
            print("             retinexformer_enhance, retinexformer_lol_v1, retinexformer_lol_v2_real")
            print("             retinexformer_lol_v2_synthetic, retinexformer_sdsd_indoor, retinexformer_sdsd_outdoor")
            print("             retinexformer_sid, retinexformer_smid, retinexformer_fivek")
            return
        
        print(f"✓ 工具加载成功: {tool.__class__.__name__}")
    except Exception as e:
        print(f"[ERROR] 工具加载失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 准备数据并执行
    print(f"\n2. 执行工具...")
    try:
        # 设置输入图像
        tool.multi_modal_data = {'image': [test_image]}
        
        # 构造调用字符串
        action_string = f'<tool_call>[{{"name": "{tool_name}", "arguments": {{}}}}]</tool_call>'
        
        # 执行
        observation, reward, done, info = tool.execute(action_string)
        
        print(f"✓ 工具执行完成")
        print(f"  - reward: {reward}")
        print(f"  - done: {done}")
        
    except Exception as e:
        print(f"[ERROR] 工具执行失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 分析返回结果
    print(f"\n3. 分析返回结果...")
    print(f"\n--- observation ---")
    print(f"  类型: {type(observation)}")
    if isinstance(observation, dict):
        print(f"  字典键: {list(observation.keys())}")
        if 'image' in observation:
            images = observation['image']
            print(f"  image字段类型: {type(images)}")
            if isinstance(images, list):
                print(f"  image列表长度: {len(images)}")
                if len(images) > 0:
                    print(f"  第一个图像类型: {type(images[0])}")
                    if hasattr(images[0], 'size'):
                        print(f"  第一个图像尺寸: {images[0].size}")
                        print(f"  ✅ 可以从observation['image'][0]获取图像")
    elif isinstance(observation, str):
        print(f"  字符串内容（前200字符）: {observation[:200]}")
    else:
        print(f"  内容: {observation}")
    
    print(f"\n--- info ---")
    print(f"  类型: {type(info)}")
    if isinstance(info, dict):
        print(f"  字典键: {list(info.keys())}")
        for key, value in info.items():
            print(f"    - {key}: {type(value)}")
    
    print(f"\n--- tool.multi_modal_data ---")
    if hasattr(tool, 'multi_modal_data') and tool.multi_modal_data:
        print(f"  字典键: {list(tool.multi_modal_data.keys())}")
        if 'image' in tool.multi_modal_data:
            images = tool.multi_modal_data['image']
            print(f"  image字段类型: {type(images)}")
            if isinstance(images, list):
                print(f"  image列表长度: {len(images)}")
                if len(images) > 0:
                    print(f"  第一个图像类型: {type(images[0])}")
                    if hasattr(images[0], 'size'):
                        print(f"  第一个图像尺寸: {images[0].size}")
                        # 检查是否与输入图像相同
                        if images[0] == test_image:
                            print(f"  ⚠️  图像未变化（与输入相同）")
                        else:
                            print(f"  ✅ 可以从tool.multi_modal_data['image'][0]获取图像")
    
    # 总结
    print(f"\n{'='*80}")
    print(f"诊断总结:")
    print(f"{'='*80}")
    
    # 尝试所有方法提取图像
    success_methods = []
    
    # 方法1
    if isinstance(observation, dict) and 'image' in observation:
        imgs = observation['image']
        if imgs and len(imgs) > 0 and hasattr(imgs[0], 'size'):
            success_methods.append("observation['image'][0]")
    
    # 方法2
    if hasattr(tool, 'multi_modal_data') and tool.multi_modal_data:
        if 'image' in tool.multi_modal_data:
            imgs = tool.multi_modal_data['image']
            if imgs and len(imgs) > 0 and hasattr(imgs[0], 'size'):
                if imgs[0] != test_image:
                    success_methods.append("tool.multi_modal_data['image'][0]")
    
    # 方法3
    if isinstance(info, dict):
        if 'restored_image' in info and hasattr(info['restored_image'], 'size'):
            success_methods.append("info['restored_image']")
        elif 'image' in info and hasattr(info['image'], 'size'):
            success_methods.append("info['image']")
    
    if success_methods:
        print(f"✅ 可用的图像提取方法:")
        for i, method in enumerate(success_methods, 1):
            print(f"  {i}. {method}")
    else:
        print(f"❌ 未找到有效的图像提取方法")
        print(f"\n可能的原因:")
        print(f"  1. 工具API服务未正确返回图像")
        print(f"  2. 工具执行失败但未抛出异常")
        print(f"  3. 图像存储在未检查的字段中")
    
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="诊断图像修复工具的返回格式")
    parser.add_argument('tool_name', type=str, 
                       help='工具名称（如: mprnet_motion_deblurring）')
    parser.add_argument('test_image', type=str,
                       help='测试图像路径')
    parser.add_argument('--tool-service-ip', type=str, default=None,
                       help='工具服务IP地址')
    
    args = parser.parse_args()
    
    # 设置工具服务IP
    if args.tool_service_ip:
        os.environ['TOOL_SERVICE_IP'] = args.tool_service_ip
    
    diagnose_tool(args.tool_name, args.test_image)

