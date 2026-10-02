"""Small remote job that creates a verifiable artifact."""
import os
from pathlib import Path
import time

root = Path(os.environ['KLC_ROOT'])
time.sleep(5)
(root / 'results/python_smoke.txt').write_text('Python smoke test completed.\n')
print('Python smoke test completed.')
