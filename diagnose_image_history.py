#!/usr/bin/env python3
"""
诊断脚本：Hook到实际的训练代码，检查image_history在哪里丢失
"""

import sys
sys.path.insert(0, '/app/xiaominl/AIR')

# 保存原始函数的引用
original_functions = {}

def hook_parallel_env():
    """Hook ParallelEnv的关键方法"""
    from verl.workers.agent import parallel_env
    
    original_agent_rollout_loop = parallel_env.agent_rollout_loop
    
    def hooked_agent_rollout_loop(*args, **kwargs):
        """Hook agent_rollout_loop来检查图像历史"""
        result = original_agent_rollout_loop(*args, **kwargs)
        
        # 检查返回的DataProto
        if hasattr(result, 'non_tensor_batch'):
            print("\n" + "="*80)
            print("[HOOK] agent_rollout_loop 返回的 DataProto")
            print("="*80)
            print(f"non_tensor_batch keys: {list(result.non_tensor_batch.keys())}")
            
            if 'image_history_list' in result.non_tensor_batch:
                img_hist_list = result.non_tensor_batch['image_history_list']
                print(f"✅ image_history_list 存在，长度: {len(img_hist_list)}")
                
                # 检查前3个样本
                for i in range(min(3, len(img_hist_list))):
                    hist = img_hist_list[i]
                    if isinstance(hist, (list, tuple)):
                        print(f"   样本{i}: {len(hist)}个图像")
                    else:
                        print(f"   样本{i}: 类型={type(hist)}")
            else:
                print(f"❌ image_history_list 不存在!")
            print("="*80 + "\n")
        
        return result
    
    # 替换函数
    parallel_env.agent_rollout_loop = hooked_agent_rollout_loop
    original_functions['agent_rollout_loop'] = original_agent_rollout_loop
    print("[HOOK] ✅ 已 hook agent_rollout_loop")


def hook_reward_manager():
    """Hook NaiveRewardManager的__call__方法"""
    from verl.workers.reward_manager.naive import NaiveRewardManager
    
    original_call = NaiveRewardManager.__call__
    
    def hooked_call(self, data, return_dict=False):
        """Hook __call__来检查接收到的数据"""
        
        # 只在第一次调用时打印
        if not hasattr(self, '_hook_printed'):
            print("\n" + "="*80)
            print("[HOOK] NaiveRewardManager 接收的 DataProto")
            print("="*80)
            print(f"non_tensor_batch keys: {list(data.non_tensor_batch.keys())}")
            
            if 'image_history_list' in data.non_tensor_batch:
                img_hist_list = data.non_tensor_batch['image_history_list']
                print(f"✅ image_history_list 存在，长度: {len(img_hist_list)}")
                
                # 检查前3个样本
                for i in range(min(3, len(img_hist_list))):
                    hist = img_hist_list[i]
                    if isinstance(hist, (list, tuple)):
                        print(f"   样本{i}: {len(hist)}个图像")
                        if len(hist) > 1:
                            print(f"            ✅ 有处理后的图像")
                        else:
                            print(f"            ⚠️  只有初始图像，没有处理后的图像")
                    else:
                        print(f"   样本{i}: 类型={type(hist)}")
            else:
                print(f"❌ image_history_list 不存在!")
            print("="*80 + "\n")
            
            self._hook_printed = True
        
        return original_call(self, data, return_dict)
    
    # 替换方法
    NaiveRewardManager.__call__ = hooked_call
    original_functions['reward_manager_call'] = original_call
    print("[HOOK] ✅ 已 hook NaiveRewardManager.__call__")


def hook_compute_score():
    """Hook compute_image_quality_reward_v2"""
    from verl.utils.reward_score import image_restoration
    
    original_compute = image_restoration.compute_image_quality_reward_v2
    
    def hooked_compute(solution_str, extra_info=None, discretize_levels=0, use_no_reference=True):
        """Hook compute函数来检查接收到的数据"""
        
        # 统计调用次数
        if not hasattr(hooked_compute, 'call_count'):
            hooked_compute.call_count = 0
            hooked_compute.zero_reward_count = 0
        
        hooked_compute.call_count += 1
        
        # 只打印前3次调用
        if hooked_compute.call_count <= 3:
            print(f"\n[HOOK] compute_image_quality_reward_v2 调用 #{hooked_compute.call_count}")
            print(f"  extra_info: {extra_info is not None}")
            
            if extra_info is not None:
                print(f"  extra_info keys: {list(extra_info.keys())}")
                
                if 'image_history' in extra_info:
                    img_hist = extra_info['image_history']
                    if isinstance(img_hist, (list, tuple)):
                        print(f"  image_history 长度: {len(img_hist)}")
                        if len(img_hist) < 2:
                            print(f"  ⚠️  长度<2，将返回0")
                    else:
                        print(f"  image_history 类型: {type(img_hist)}")
                else:
                    print(f"  ❌ image_history 不在 extra_info 中")
            else:
                print(f"  ❌ extra_info 为 None")
        
        # 调用原函数
        result = original_compute(solution_str, extra_info, discretize_levels, use_no_reference)
        
        # 统计返回0的次数
        if isinstance(result, (int, float)) and result == 0.0:
            hooked_compute.zero_reward_count += 1
        
        # 每10次调用打印一次统计
        if hooked_compute.call_count % 10 == 0:
            zero_rate = hooked_compute.zero_reward_count / hooked_compute.call_count * 100
            print(f"\n[HOOK STATS] compute_image_quality_reward_v2:")
            print(f"  总调用次数: {hooked_compute.call_count}")
            print(f"  返回0次数: {hooked_compute.zero_reward_count}")
            print(f"  零奖励率: {zero_rate:.1f}%")
        
        return result
    
    # 替换函数
    image_restoration.compute_image_quality_reward_v2 = hooked_compute
    original_functions['compute_image_quality'] = original_compute
    print("[HOOK] ✅ 已 hook compute_image_quality_reward_v2")


def hook_env_step():
    """Hook ParallelEnv.step来检查工具执行"""
    from verl.workers.agent.parallel_env import ParallelEnv
    
    original_step = ParallelEnv.step
    
    def hooked_step(self, active_indices, actions, current_turn=1):
        """Hook step来统计工具执行"""
        
        # 调用原函数
        result = original_step(self, active_indices, actions, current_turn)
        
        # 检查multi_modal_data_history_list的更新
        if hasattr(self, 'multi_modal_data_history_list'):
            if not hasattr(hooked_step, 'printed_stats'):
                hooked_step.printed_stats = False
            
            if not hooked_step.printed_stats and current_turn == 1:
                print(f"\n[HOOK] ParallelEnv.step (turn={current_turn})")
                print(f"  multi_modal_data_history_list 长度: {len(self.multi_modal_data_history_list)}")
                
                tool_executed_count = 0
                for idx, hist in enumerate(self.multi_modal_data_history_list[:3]):
                    if isinstance(hist, list):
                        print(f"  样本{idx}: {len(hist)}个图像")
                        if len(hist) > 1:
                            tool_executed_count += 1
                
                if tool_executed_count == 0:
                    print(f"  ⚠️  没有样本执行工具（所有样本都只有1张初始图像）")
                
                hooked_step.printed_stats = True
        
        return result
    
    # 替换方法
    ParallelEnv.step = hooked_step
    original_functions['env_step'] = original_step
    print("[HOOK] ✅ 已 hook ParallelEnv.step")


def install_hooks():
    """安装所有hook"""
    print("\n" + "="*80)
    print("安装诊断 Hooks")
    print("="*80)
    
    try:
        hook_parallel_env()
        hook_reward_manager()
        hook_compute_score()
        hook_env_step()
        
        print("\n✅ 所有 hooks 安装完成!")
        print("\n使用方法:")
        print("  在训练脚本开头添加:")
        print("  import diagnose_image_history")
        print("  diagnose_image_history.install_hooks()")
        print("\n然后正常运行训练，会自动打印诊断信息")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"\n❌ Hook 安装失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    install_hooks()
    
    # 示例：如何在训练脚本中使用
    print("\n" + "="*80)
    print("示例：在训练脚本中使用")
    print("="*80)
    print("""
在你的训练脚本（例如 examples/agent/IR.sh 调用的Python脚本）开头添加：

```python
# 在所有其他import之前
import sys
sys.path.insert(0, '/app/xiaominl/AIR')
import diagnose_image_history
diagnose_image_history.install_hooks()

# 然后是你的正常训练代码
from verl.trainer.ppo.ray_trainer import RayPPOTrainer
...
```

这会自动在关键位置打印诊断信息，帮助定位问题。
    """)

