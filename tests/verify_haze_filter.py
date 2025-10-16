#!/usr/bin/env python3
"""验证haze过滤是否生效"""

import sys
sys.path.insert(0, '/app/xiaominl/DeepEyes_v2')

from tests.test_all_tools_metrics import load_parquet_data

parquet_path = '/app/xiaominl/datasets/air_d1_sp9_up2_balanced/shard-test-000000.parquet'

print("=" * 80)
print("🔍 验证haze过滤")
print("=" * 80)

# 加载数据（会自动过滤haze）
samples = load_parquet_data(parquet_path, max_samples=30)

print(f"\n检查加载的样本:")
has_haze = False
for sample in samples:
    if 'haze' in sample['degradation_types']:
        print(f"  ❌ 发现haze样本: {sample['sample_id']}")
        has_haze = True

if not has_haze:
    print(f"  ✅ 没有haze样本（过滤成功）")
    print(f"\n加载的退化类型:")
    all_types = set()
    for sample in samples:
        all_types.update(sample['degradation_types'])
    for deg_type in sorted(all_types):
        print(f"    - {deg_type}")
else:
    print(f"  ❌ 过滤失败，仍有haze样本")

print("\n" + "=" * 80)



