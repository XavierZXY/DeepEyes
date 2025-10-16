#!/usr/bin/env python3
"""
验证数据集格式是否符合baseline测试的要求
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
from PIL import Image
import io

sys.path.insert(0, '/app/xiaominl/DeepEyes_v2')


def load_image_from_data(image_data):
    """从数据中加载图像"""
    import numpy as np
    try:
        if isinstance(image_data, Image.Image):
            return image_data
        elif isinstance(image_data, bytes):
            return Image.open(io.BytesIO(image_data)).convert('RGB')
        elif isinstance(image_data, np.ndarray):
            # numpy array - 获取第一个元素
            if len(image_data) > 0:
                return load_image_from_data(image_data[0])
            else:
                return None
        elif isinstance(image_data, dict):
            if 'bytes' in image_data:
                return Image.open(io.BytesIO(image_data['bytes'])).convert('RGB')
            elif 'image' in image_data:
                return load_image_from_data(image_data['image'])
        elif isinstance(image_data, list) and len(image_data) > 0:
            return load_image_from_data(image_data[0])
        else:
            return None
    except Exception as e:
        print(f"Failed to load image: {e}")
        return None


def verify_dataset(parquet_path: str, num_samples: int = 5):
    """验证数据集格式"""
    
    print(f"\n{'='*80}")
    print(f"Verifying Dataset: {parquet_path}")
    print(f"{'='*80}\n")
    
    # 检查文件是否存在
    if not Path(parquet_path).exists():
        print(f"❌ File does not exist: {parquet_path}")
        return False
    
    try:
        # 读取数据
        df = pd.read_parquet(parquet_path)
        print(f"✅ Successfully loaded parquet file")
        print(f"   Total samples: {len(df)}")
        print(f"   Columns: {df.columns.tolist()}")
        
        # 检查必需的列
        required_columns = ['images', 'extra_info', 'reward_model']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            print(f"\n❌ Missing required columns: {missing_columns}")
            return False
        
        print(f"\n✅ All required columns present: {required_columns}")
        
        # 检查样本数据
        print(f"\n{'='*80}")
        print(f"Checking Sample Data (first {min(num_samples, len(df))} samples)")
        print(f"{'='*80}")
        
        all_degradation_types = set()
        valid_samples = 0
        
        for idx in range(min(num_samples, len(df))):
            print(f"\n--- Sample {idx} ---")
            row = df.iloc[idx]
            
            # 检查images
            try:
                images_data = row['images']
                if isinstance(images_data, list):
                    degraded_image = load_image_from_data(images_data[0])
                else:
                    degraded_image = load_image_from_data(images_data)
                
                if degraded_image:
                    print(f"✅ Degraded image: {degraded_image.size} {degraded_image.mode}")
                else:
                    print(f"❌ Failed to load degraded image")
                    continue
            except Exception as e:
                print(f"❌ Error loading degraded image: {e}")
                continue
            
            # 检查extra_info
            try:
                extra_info = row['extra_info']
                if 'original_image' not in extra_info:
                    print(f"❌ No 'original_image' in extra_info")
                    continue
                
                original_image = load_image_from_data(extra_info['original_image'])
                if original_image:
                    print(f"✅ Original image: {original_image.size} {original_image.mode}")
                else:
                    print(f"❌ Failed to load original image")
                    continue
            except Exception as e:
                print(f"❌ Error loading original image: {e}")
                continue
            
            # 检查reward_model
            try:
                reward_model = row['reward_model']
                if not isinstance(reward_model, np.ndarray):
                    print(f"❌ reward_model is not numpy array: {type(reward_model)}")
                    continue
                
                print(f"✅ Reward model: {len(reward_model)} degradation(s)")
                
                for i, deg_info in enumerate(reward_model):
                    deg_type = deg_info.get('degradation_type', 'unknown')
                    deg_level = deg_info.get('degradation_level', 'unknown')
                    all_degradation_types.add(deg_type)
                    print(f"   [{i+1}] {deg_type} (level: {deg_level})")
                
                valid_samples += 1
                
            except Exception as e:
                print(f"❌ Error processing reward_model: {e}")
                continue
        
        # 汇总信息
        print(f"\n{'='*80}")
        print(f"Summary")
        print(f"{'='*80}")
        print(f"Valid samples checked: {valid_samples}/{min(num_samples, len(df))}")
        print(f"\nAll degradation types found:")
        for deg_type in sorted(all_degradation_types):
            print(f"  - {deg_type}")
        
        # 检查工具支持
        print(f"\n{'='*80}")
        print(f"Tool Support Check")
        print(f"{'='*80}")
        
        from test_baseline_restoration import DEGRADATION_TO_TOOLS
        
        supported_types = set(DEGRADATION_TO_TOOLS.keys())
        unsupported_types = all_degradation_types - supported_types
        
        print(f"\nSupported degradation types ({len(all_degradation_types & supported_types)}):")
        for deg_type in sorted(all_degradation_types & supported_types):
            tools = DEGRADATION_TO_TOOLS[deg_type]
            print(f"  ✅ {deg_type}: {len(tools)} tool(s) available")
        
        if unsupported_types:
            print(f"\n⚠️  Unsupported degradation types ({len(unsupported_types)}):")
            for deg_type in sorted(unsupported_types):
                print(f"  ❌ {deg_type}: No tools available")
        else:
            print(f"\n✅ All degradation types are supported!")
        
        # 最终结果
        print(f"\n{'='*80}")
        if valid_samples == min(num_samples, len(df)) and not unsupported_types:
            print(f"✅ Dataset verification PASSED")
            print(f"{'='*80}\n")
            return True
        else:
            print(f"⚠️  Dataset verification completed with warnings")
            print(f"{'='*80}\n")
            return True
    
    except Exception as e:
        print(f"\n❌ Error verifying dataset: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Verify dataset format for baseline testing')
    parser.add_argument('--data-path', type=str, 
                        default='/app/xiaominl/datasets/air_sp11np_up3_sample1_nosw/shard-test-000000.parquet',
                        help='Path to parquet file')
    parser.add_argument('--num-samples', type=int, default=5,
                        help='Number of samples to check')
    
    args = parser.parse_args()
    
    success = verify_dataset(args.data_path, args.num_samples)
    
    if success:
        print("\n🎉 You can now run the baseline test:")
        print(f"   cd /app/xiaominl/DeepEyes_v2/tests/baseline")
        print(f"   ./run_baseline_test.sh --num-samples 10")
    else:
        print("\n❌ Please fix the dataset issues before running the baseline test.")
        sys.exit(1)


if __name__ == '__main__':
    main()

