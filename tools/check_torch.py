import sys
try:
    import torch
    print('PY:', sys.executable)
    print('TORCH_OK', torch.__version__)
except Exception as e:
    print('PY:', sys.executable)
    print('TORCH_ERR', repr(e))
