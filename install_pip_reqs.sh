
# 1. Activate environment
source /opt/miniconda3/bin/activate swim_pro

# 2. Fix chumpy specifically
pip install chumpy --no-build-isolation

# 3. Install remaining requirements
pip install -r requirements_cleaned.txt
