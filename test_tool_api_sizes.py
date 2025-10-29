#!/usr/bin/env python3
"""
直接测试工具API是否会改变图像尺寸
"""

import requests
import io
from PIL import Image
import numpy as np

TOOL_SERVICE_IP = "10.21.9.6"

# 工具配置
tools = {
    'restormer_deraining': {'url': f'http://{TOOL_SERVICE_IP}:5006/process', 'params': {'task': 'deraining'}},
    'retinexformer_sdsd_indoor': {'url': f'http://{TOOL_SERVICE_IP}:5009/enhance', 'params': {'task': 'SDSD_indoor'}},
    'scunet_real_denoising_gan': {'url': f'http://{TOOL_SERVICE_IP}:5008/process', 'params': {'task': 'real_denoising_gan'}},
    'fbcnn_jpeg_artifact_removal': {'url': f'http://{TOOL_SERVICE_IP}:5005/process', 'params': {'task': 'jpeg_artifact_removal', 'jpeg': 40}},
    'swinir_super_resolution': {'url': f'http://{TOOL_SERVICE_IP}:5001/process', 'params': {'task': 'super_resolution', 'scale': 2}},
}

# 创建几个测试尺寸
test_sizes = [
    (924, 956),  # 您看到的案例
    (924, 952),  # 能被8整除
    (800, 804),  # 另一个案例
    (1024, 1020),  # 测试不同尺寸
]

print("="*80)
print("测试工具API是否会改变图像尺寸")
print("="*80)
print(f"\nTOOL_SERVICE_IP: {TOOL_SERVICE_IP}")
print(f"测试的工具: {list(tools.keys())}")

for test_size in test_sizes:
    print(f"\n{'='*80}")
    print(f"测试尺寸: {test_size}")
    print(f"{'='*80}")
    
    # 创建测试图片
    test_img = Image.new('RGB', test_size, color=(128, 128, 128))
    
    # 检查能否被8整除
    w_mod8 = test_size[0] % 8
    h_mod8 = test_size[1] % 8
    print(f"  能否被8整除: width({w_mod8}), height({h_mod8})")
    
    # 测试几个工具
    for tool_name in ['restormer_deraining', 'scunet_real_denoising_gan']:
        if tool_name not in tools:
            continue
            
        tool_config = tools[tool_name]
        print(f"\n  测试工具: {tool_name}")
        print(f"  ----------------------------------------")
        
        try:
            # 准备图片
            buf = io.BytesIO()
            test_img.save(buf, format='PNG')
            buf.seek(0)
            
            # 发送请求
            files = {'image': ('test.png', buf, 'image/png')}
            response = requests.post(
                tool_config['url'], 
                files=files, 
                data=tool_config['params'],
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    import base64
                    img_b64 = result['image']
                    img_bytes = base64.b64decode(img_b64)
                    result_img = Image.open(io.BytesIO(img_bytes))
                    
                    print(f"    输入尺寸: {test_size}")
                    print(f"    输出尺寸: {result_img.size}")
                    
                    if result_img.size == test_size:
                        print(f"    ✅ 尺寸保持不变")
                    else:
                        w_diff = result_img.size[0] - test_size[0]
                        h_diff = result_img.size[1] - test_size[1]
                        print(f"    ⚠️  尺寸改变: Δw={w_diff}, Δh={h_diff}")
                        
                        # 检查输出能否被8整除
                        out_w_mod8 = result_img.size[0] % 8
                        out_h_mod8 = result_img.size[1] % 8
                        print(f"    输出能否被8整除: width({out_w_mod8}), height({out_h_mod8})")
                else:
                    print(f"    ❌ API返回失败: {result.get('error', 'Unknown')}")
            else:
                print(f"    ❌ HTTP错误: {response.status_code}")
                
        except requests.exceptions.Timeout:
            print(f"    ⏰ 超时（30秒）")
        except requests.exceptions.ConnectionError:
            print(f"    ❌ 连接失败（服务可能未运行）")
        except Exception as e:
            print(f"    ❌ 错误: {e}")

print(f"\n{'='*80}")
print("测试完成")
print("="*80)

