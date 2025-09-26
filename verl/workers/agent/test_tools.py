from verl.workers.agent.tool_envs import ToolBase
from verl.workers.agent.envs.mm_process_engine.DeblurToolbox import DeblurToolbox

from verl.workers.agent.envs.mm_process_engine.DehazeFormerToolbox import DehazeFormerToolbox
from verl.workers.agent.envs.mm_process_engine.SwinIRToolbox import SwinIRDenoisingToolbox,SwinIRSrToolbox,SwinIRJpegArtifactRemovalToolbox


dehazetoolbox = ToolBase.create("dehazeformer_dehaze")
drbnettoolbox = ToolBase.create("drbnet_defocus_deblurring")
swinir_denoising_toolbox = ToolBase.create("swinir_denoising")
swinir_jpeg_artifact_removal_toolbox = ToolBase.create("swinir_jpeg_artifact_removal")
swinir_sr_toolbox = ToolBase.create("swinir_super_resolution")  