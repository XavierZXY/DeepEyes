#!/usr/bin/env python3
"""
演示负载均衡器的分配机制

使用方式:
    python3 demo_load_balancer.py
"""

import os
import sys
from collections import Counter

# 设置环境变量
os.environ['TOOL_SERVICE_IPS'] = "10.21.9.6,10.21.9.7"
os.environ['TOOL_LOAD_BALANCE_STRATEGY'] = 'round_robin'

# 导入负载均衡器
sys.path.insert(0, 'verl/workers/agent/envs/mm_process_engine')
from tool_load_balancer import get_tool_service_ip, get_all_tool_service_ips, get_tool_service_ip_count

def demo_same_tool():
    """演示：连续调用同一个工具"""
    print("\n" + "="*70)
    print("场景1: 连续5张图片都调用 SwinIR")
    print("="*70)
    
    tool = "SwinIR"
    port = 5001
    
    for i in range(1, 6):
        ip = get_tool_service_ip()
        url = f"http://{ip}:{port}/process"
        print(f"图片{i} → {tool:12s} → {url:40s} → 服务器{'1' if ip.endswith('6') else '2'}-GPU0")

def demo_different_tools():
    """演示：连续调用不同工具"""
    print("\n" + "="*70)
    print("场景2: 5张图片调用不同工具")
    print("="*70)
    
    tools = [
        ("SwinIR", 5001, "GPU0"),
        ("NAFNet", 5012, "GPU1"),
        ("HAT", 5010, "GPU2"),
        ("SwinIR", 5001, "GPU0"),
        ("Restormer", 5006, "GPU3"),
    ]
    
    for i, (tool, port, gpu) in enumerate(tools, 1):
        ip = get_tool_service_ip()
        url = f"http://{ip}:{port}/process"
        server_id = '1' if ip.endswith('6') else '2'
        print(f"图片{i} → {tool:12s} → {url:40s} → 服务器{server_id}-{gpu}")

def demo_complex_scenario():
    """演示：复杂混合场景"""
    print("\n" + "="*70)
    print("场景3: 复杂混合场景（模拟一个batch的所有工具调用）")
    print("="*70)
    print("\n处理任务:")
    print("  图片A: SwinIR → NAFNet → HAT")
    print("  图片B: SwinIR → Restormer")
    print("  图片C: NAFNet")
    print("  图片D: SwinIR → SwinIR")
    print()
    
    tasks = [
        ("图片A", "SwinIR", 5001, "GPU0"),
        ("图片A", "NAFNet", 5012, "GPU1"),
        ("图片A", "HAT", 5010, "GPU2"),
        ("图片B", "SwinIR", 5001, "GPU0"),
        ("图片B", "Restormer", 5006, "GPU3"),
        ("图片C", "NAFNet", 5012, "GPU1"),
        ("图片D", "SwinIR", 5001, "GPU0"),
        ("图片D", "SwinIR", 5001, "GPU0"),
    ]
    
    counter = Counter()
    
    for idx, (img, tool, port, gpu) in enumerate(tasks, 1):
        ip = get_tool_service_ip()
        url = f"http://{ip}:{port}/process"
        server_id = '1' if ip.endswith('6') else '2'
        counter[f"服务器{server_id}"] += 1
        print(f"请求{idx}: {img}-{tool:12s} → {url:40s} → 服务器{server_id}-{gpu}")
    
    print("\n" + "-"*70)
    print("负载统计:")
    for server, count in sorted(counter.items()):
        print(f"  {server}: {count}个请求 ({count/len(tasks)*100:.1f}%)")
    print("-"*70)

def demo_statistics():
    """演示：大量请求的统计分析"""
    print("\n" + "="*70)
    print("场景4: 100次工具调用的负载分布")
    print("="*70)
    
    counter = Counter()
    tools = ["SwinIR", "NAFNet", "HAT", "Restormer", "SwinIR", "NAFNet"]
    
    for i in range(100):
        tool = tools[i % len(tools)]
        ip = get_tool_service_ip()
        counter[ip] += 1
    
    print(f"\n总请求数: 100")
    print(f"服务器数: {get_tool_service_ip_count()}")
    print(f"配置IP: {', '.join(get_all_tool_service_ips())}")
    print()
    
    for ip, count in sorted(counter.items()):
        server_id = '1' if ip.endswith('6') else '2'
        bar = "█" * (count // 2)
        print(f"服务器{server_id} ({ip}): {count:3d} 次 | {bar}")
    
    print(f"\n✅ 负载完全均衡！每台服务器处理 50 次请求")

def main():
    print("="*70)
    print("负载均衡器分配机制演示")
    print("="*70)
    print(f"\n配置:")
    print(f"  TOOL_SERVICE_IPS: {os.environ['TOOL_SERVICE_IPS']}")
    print(f"  策略: {os.environ['TOOL_LOAD_BALANCE_STRATEGY']}")
    print(f"  服务器数量: {get_tool_service_ip_count()}")
    
    demo_same_tool()
    demo_different_tools()
    demo_complex_scenario()
    demo_statistics()
    
    print("\n" + "="*70)
    print("关键结论:")
    print("="*70)
    print("1. 每次工具调用都会重新选择服务器（轮询模式）")
    print("2. 不区分工具类型，统一按请求顺序分配")
    print("3. 连续调用同一工具也会分配到不同服务器")
    print("4. 长期运行后，负载完全均衡")
    print("5. 充分利用所有服务器的所有GPU卡")
    print("="*70)

if __name__ == '__main__':
    main()

