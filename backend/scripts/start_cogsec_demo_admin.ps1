$ErrorActionPreference = "Stop"

$backendRoot = "d:\mirofish\MiroFish-main\MIRO_PERSONAL_TEST\backend"
$pythonExe = "d:\mirofish\.conda_envs\mirofish_cogsec312\python.exe"

Set-Location $backendRoot

$env:PYTHONIOENCODING = "utf-8"
$env:COGSEC_USE_LOCAL_GEMMA = "true"
$env:COGSEC_LOCAL_MODEL_PATH = "d:\mirofish\MiroFish-main\MIRO_PERSONAL_TEST\models\google--gemma-4-E2B-it"
$env:COGSEC_LOCAL_GEMMA_DEVICE = "auto"
$env:COGSEC_LOCAL_GEMMA_DTYPE = "float16"
$env:COGSEC_LOCAL_GEMMA_ATTN_IMPLEMENTATION = "eager"
$env:COGSEC_LOCAL_GEMMA_MAX_NEW_TOKENS = "192"
$env:COGSEC_LOCAL_GEMMA_OFFLOAD_DIR = "d:\mirofish\MiroFish-main\MIRO_PERSONAL_TEST\backend\.cache\gemma_offload"
$env:COGSEC_DEMO_HOST = "127.0.0.1"
$env:COGSEC_DEMO_PORT = "5052"
$env:COGSEC_DEMO_DEBUG = "false"

& $pythonExe "d:\mirofish\MiroFish-main\MIRO_PERSONAL_TEST\backend\run_cogsec_demo.py"
