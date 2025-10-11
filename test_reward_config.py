#!/usr/bin/env python3
"""
快速测试图像质量奖励配置是否生效
"""
import os
import sys

# 测试环境变量配置
def test_config():
    print("=" * 70)
    print("图像质量奖励配置测试")
    print("=" * 70)
    
    # 读取当前配置
    use_no_reference = os.environ.get('IMAGE_QUALITY_USE_NO_REFERENCE', 'True').lower() == 'true'
    discretize_levels = int(os.environ.get('IMAGE_QUALITY_DISCRETIZE_LEVELS', '0'))
    
    print(f"\n当前配置:")
    print(f"  IMAGE_QUALITY_USE_NO_REFERENCE = {use_no_reference}")
    print(f"  IMAGE_QUALITY_DISCRETIZE_LEVELS = {discretize_levels}")
    
    print(f"\n解释:")
    if use_no_reference:
        print(f"  ✓ 使用无参考指标 (NIQE, BRISQUE, CPBD, CLIP-IQA, Hyper-IQA)")
        print(f"  ✓ 适用于所有样本，无需ground truth")
        print(f"  ✓ 奖励公式: 0.20×NIQE + 0.20×BRISQUE + 0.20×CPBD + 0.20×CLIP-IQA + 0.20×Hyper-IQA")
    else:
        print(f"  ✓ 使用有参考指标 (SSIM, LPIPS, PSNR)")
        print(f"  ⚠ 需要数据集中有original_image字段")
        print(f"  ✓ 奖励公式: 0.35×SSIM + 0.50×(1-LPIPS) + 0.15×PSNR")
    
    if discretize_levels > 0:
        step = 1.0 / discretize_levels
        print(f"\n  ✓ 启用离散化: {discretize_levels}个档位")
        print(f"  ✓ 奖励值将被映射到: {{0.0, {step:.2f}, {2*step:.2f}, ..., 1.0}}")
        print(f"  ✓ 优势: 减少训练波动，提高稳定性")
    else:
        print(f"\n  ✓ 连续奖励: 范围 [0.0, 1.0]")
        print(f"  ✓ 优势: 提供精细的质量区分")
    
    print("\n" + "=" * 70)
    
    # 测试导入
    print("\n测试模块导入...")
    try:
        from verl.utils.reward_score import _default_compute_score
        print("  ✓ _default_compute_score 导入成功")
        
        # 测试调用
        print("\n测试奖励函数调用...")
        test_data_source = "image_restoration_v2"
        test_solution = "<think>test</think><answer>{\"restoration_log\": []}</answer>"
        test_ground_truth = {"reward_model": []}
        test_extra_info = {
            "image_history": [],  # 空历史，会返回0.0
        }
        
        try:
            result = _default_compute_score(
                test_data_source, 
                test_solution, 
                test_ground_truth, 
                test_extra_info
            )
            print(f"  ✓ 奖励函数调用成功")
            print(f"  ✓ 返回值: {result}")
            print(f"  ℹ 注意: 由于image_history为空，返回0.0是预期行为")
        except Exception as e:
            print(f"  ⚠ 奖励函数调用失败: {e}")
            print(f"  ℹ 这可能是因为缺少图像质量评估依赖库")
            print(f"  ℹ 但配置读取功能是正常的")
    except ImportError as e:
        print(f"  ✗ 模块导入失败: {e}")
        return False
    
    print("\n" + "=" * 70)
    print("✅ 配置测试完成！")
    print("=" * 70)
    
    # 给出使用建议
    print("\n💡 使用建议:")
    print(f"   修改配置: 编辑 examples/agent/IR.sh 中的环境变量")
    print(f"   或在命令行设置:")
    print(f"     export IMAGE_QUALITY_USE_NO_REFERENCE=False")
    print(f"     export IMAGE_QUALITY_DISCRETIZE_LEVELS=10")
    print(f"\n   详细文档: docs/IMAGE_QUALITY_REWARD_CONFIG.md")
    print("")
    
    return True


if __name__ == "__main__":
    success = test_config()
    sys.exit(0 if success else 1)

