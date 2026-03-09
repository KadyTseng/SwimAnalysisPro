
import sys
import os

# 設定絕對路徑
BASE_DIR = '/home/kady6582/SwimAnalysisPro'
INPUT_FILE = os.path.join(BASE_DIR, 'requirements.txt')
OUTPUT_FILE = os.path.join(BASE_DIR, 'requirements_safe.txt')

# Windows 導出的 requirements 可能包含這些無法在 Linux 使用或我們想用 Conda 管理的套件
IGNORE_LIST = [
    'torch', 'torchvision', 'torchaudio', 
    'numpy', 'scipy', 
    'opencv-python', 'opencv-contrib-python', 'opencv-python-headless',
    'ffmpeg-python', 'pywin32', 'pywinpty', 'pyreadline3',
    'mkl', 'nomkl', 'intel-openmp',
    'nvidia-', 'triton'  # 讓 PyTorch 自己處理 CUDA 依賴
]

def clean_line(line):
    # 移除 @ file://... 之後的路徑
    if ' @ file:' in line:
        line = line.split(' @ ')[0]
    return line.strip()

def is_safe(line):
    if not line or line.startswith('#'):
        return False
    
    pkg_name = line.split('==')[0].split('<')[0].split('>')[0].strip().lower()
    
    for ignore in IGNORE_LIST:
        if pkg_name == ignore or pkg_name.startswith(ignore):
            return False
    return True

try:
    print(f"📂 正在讀取: {INPUT_FILE}")
    # 嘗試讀取 UTF-16 (Windows 常見)，失敗則試 UTF-8
    try:
        with open(INPUT_FILE, 'r', encoding='utf-16') as f:
            content = f.read()
    except:
        with open(INPUT_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

    lines = content.splitlines()
    safe_lines = []
    
    for line in lines:
        cleaned = clean_line(line)
        if is_safe(cleaned):
            safe_lines.append(cleaned)

    print(f"💾 正在寫入: {OUTPUT_FILE}")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(safe_lines))
        
    print(f"✅ 已過濾不安全套件，產生 requirements_safe.txt (共 {len(safe_lines)} 個套件)")

except Exception as e:
    print(f"❌ 處理 requirements.txt 失敗: {e}")
    sys.exit(1)
