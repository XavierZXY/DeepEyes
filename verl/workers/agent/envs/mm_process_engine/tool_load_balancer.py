"""
工具服务负载均衡器

支持多个IP地址的负载均衡，用于加速图像处理工具请求。
通过环境变量 TOOL_SERVICE_IPS 配置多个IP地址（逗号分隔）。

使用方法:
    from tool_load_balancer import get_tool_service_ip
    
    # 自动负载均衡选择IP
    ip = get_tool_service_ip()
    api_url = f"http://{ip}:5001/process"
"""

import os
import random
import threading
from typing import List


class ToolLoadBalancer:
    """工具服务负载均衡器"""
    
    def __init__(self):
        self._ips: List[str] = []
        self._current_index = 0
        self._lock = threading.Lock()
        self._strategy = 'round_robin'  # 'round_robin' or 'random'
        self._initialized = False
        
    def initialize(self):
        """初始化负载均衡器，从环境变量读取IP配置"""
        if self._initialized:
            return
            
        # 优先读取多IP配置
        multi_ips = os.environ.get('TOOL_SERVICE_IPS', '').strip()
        
        if multi_ips:
            # 支持多IP配置，逗号或分号分隔
            self._ips = [ip.strip() for ip in multi_ips.replace(';', ',').split(',') if ip.strip()]
            print(f"[LoadBalancer] 初始化成功: 已配置 {len(self._ips)} 个IP地址")
            for idx, ip in enumerate(self._ips):
                print(f"[LoadBalancer]   IP{idx+1}: {ip}")
        else:
            # 向后兼容：如果没有配置多IP，使用单IP
            single_ip = os.environ.get('TOOL_SERVICE_IP', '10.21.9.6').strip()
            self._ips = [single_ip]
            print(f"[LoadBalancer] 初始化成功: 使用单IP模式 - {single_ip}")
        
        # 读取负载均衡策略
        strategy = os.environ.get('TOOL_LOAD_BALANCE_STRATEGY', 'round_robin').lower()
        if strategy in ['round_robin', 'random']:
            self._strategy = strategy
        else:
            print(f"[LoadBalancer] 警告: 未知策略 '{strategy}'，使用默认策略 'round_robin'")
            self._strategy = 'round_robin'
        
        print(f"[LoadBalancer] 负载均衡策略: {self._strategy}")
        self._initialized = True
    
    def get_ip(self) -> str:
        """
        获取一个IP地址（负载均衡）
        
        Returns:
            str: 选中的IP地址
        """
        if not self._initialized:
            self.initialize()
        
        if not self._ips:
            # 降级处理：如果没有配置IP，返回默认值
            return '10.21.9.6'
        
        if len(self._ips) == 1:
            # 只有一个IP，直接返回
            return self._ips[0]
        
        # 根据策略选择IP
        if self._strategy == 'random':
            return random.choice(self._ips)
        else:  # round_robin
            with self._lock:
                ip = self._ips[self._current_index]
                self._current_index = (self._current_index + 1) % len(self._ips)
                return ip
    
    def get_all_ips(self) -> List[str]:
        """
        获取所有配置的IP地址
        
        Returns:
            List[str]: IP地址列表
        """
        if not self._initialized:
            self.initialize()
        return self._ips.copy()
    
    def get_ip_count(self) -> int:
        """
        获取配置的IP数量
        
        Returns:
            int: IP数量
        """
        if not self._initialized:
            self.initialize()
        return len(self._ips)
    
    def reset(self):
        """重置负载均衡器状态"""
        with self._lock:
            self._current_index = 0
        print(f"[LoadBalancer] 已重置轮询索引")


# 全局单例
_load_balancer = ToolLoadBalancer()


def get_tool_service_ip() -> str:
    """
    获取工具服务IP地址（负载均衡）
    
    这是推荐的获取IP的方式，支持自动负载均衡。
    
    Returns:
        str: 选中的IP地址
        
    Example:
        >>> ip = get_tool_service_ip()
        >>> api_url = f"http://{ip}:5001/process"
    """
    return _load_balancer.get_ip()


def get_all_tool_service_ips() -> List[str]:
    """
    获取所有配置的工具服务IP地址
    
    Returns:
        List[str]: IP地址列表
    """
    return _load_balancer.get_all_ips()


def get_tool_service_ip_count() -> int:
    """
    获取配置的工具服务IP数量
    
    Returns:
        int: IP数量
    """
    return _load_balancer.get_ip_count()


def reset_load_balancer():
    """重置负载均衡器状态"""
    _load_balancer.reset()


# 向后兼容：直接读取环境变量的函数
def get_tool_service_ip_legacy() -> str:
    """
    【已弃用】直接从环境变量读取IP（不使用负载均衡）
    
    仅用于向后兼容，新代码请使用 get_tool_service_ip()
    
    Returns:
        str: IP地址
    """
    return os.environ.get('TOOL_SERVICE_IP', '10.21.9.6')


if __name__ == "__main__":
    # 测试代码
    print("="*70)
    print("工具负载均衡器测试")
    print("="*70)
    
    # 测试1: 单IP模式
    print("\n【测试1: 单IP模式】")
    os.environ['TOOL_SERVICE_IP'] = '192.168.1.100'
    os.environ.pop('TOOL_SERVICE_IPS', None)
    
    balancer1 = ToolLoadBalancer()
    balancer1.initialize()
    for i in range(5):
        print(f"  请求{i+1}: {balancer1.get_ip()}")
    
    # 测试2: 多IP轮询模式
    print("\n【测试2: 多IP轮询模式】")
    os.environ['TOOL_SERVICE_IPS'] = '192.168.1.100,192.168.1.101,192.168.1.102'
    os.environ['TOOL_LOAD_BALANCE_STRATEGY'] = 'round_robin'
    
    balancer2 = ToolLoadBalancer()
    balancer2.initialize()
    for i in range(7):
        print(f"  请求{i+1}: {balancer2.get_ip()}")
    
    # 测试3: 多IP随机模式
    print("\n【测试3: 多IP随机模式】")
    os.environ['TOOL_SERVICE_IPS'] = '192.168.1.100,192.168.1.101'
    os.environ['TOOL_LOAD_BALANCE_STRATEGY'] = 'random'
    
    balancer3 = ToolLoadBalancer()
    balancer3.initialize()
    for i in range(6):
        print(f"  请求{i+1}: {balancer3.get_ip()}")
    
    print("\n" + "="*70)
    print("测试完成")
    print("="*70)

