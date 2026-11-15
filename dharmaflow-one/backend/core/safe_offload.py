"""Bounded, owned-buffer reads for Accelerate offload on Windows Torch 2.5.

Avoid safetensors.get_tensor's memory-mapped torch storage slicing, which
access-violated in the recorded UMT5 worker stack. Never read an entire shard.
"""
import json
import math
import struct
from functools import lru_cache
from pathlib import Path

@lru_cache(maxsize=32)
def _header(path, size, modified):
    with open(path, 'rb') as file:
        raw = file.read(8)
        if len(raw) != 8:
            raise ValueError('Truncated safetensors header')
        length = struct.unpack('<Q', raw)[0]
        if length > min(size - 8, 100_000_000):
            raise ValueError('Invalid safetensors header size')
        return json.loads(file.read(length)), 8 + length


def read_tensor(path, name):
    import torch
    path = Path(path)
    stat = path.stat()
    header, base = _header(str(path), stat.st_size, stat.st_mtime_ns)
    entry = header[name]
    dtypes = {'BF16': torch.bfloat16, 'F16': torch.float16, 'F32': torch.float32,
              'F64': torch.float64, 'I64': torch.int64, 'I32': torch.int32,
              'I16': torch.int16, 'I8': torch.int8, 'U8': torch.uint8, 'BOOL': torch.bool}
    dtype = dtypes[entry['dtype']]
    start, end = entry['data_offsets']
    count = math.prod(entry['shape'])
    expected = count * torch.empty((), dtype=dtype).element_size()
    if start < 0 or end - start != expected or base + end > stat.st_size:
        raise ValueError(f'Invalid or truncated tensor data: {name}')
    if not count:
        return torch.empty(entry['shape'], dtype=dtype)
    buffer = bytearray(expected)
    with path.open('rb', buffering=0) as file:
        file.seek(base + start)
        view = memoryview(buffer)
        offset = 0
        while offset < expected:
            n = file.readinto(view[offset:])
            if not n:
                raise ValueError(f'Truncated tensor: {name}')
            offset += n
    # Tensor owns a reference to the bytearray; there is no file mapping lifetime.
    return torch.frombuffer(buffer, dtype=dtype).reshape(entry['shape'])


def install_owned_buffer_offload():
    import torch
    from accelerate.utils.offload import OffloadedWeightsLoader
    if getattr(OffloadedWeightsLoader, '_dharmaflow_owned_buffers', False):
        return
    original = OffloadedWeightsLoader.__getitem__
    def getitem(self, key):
        info = self.index.get(key, {})
        if key in self.state_dict or not info.get('safetensors_file'):
            return original(self, key)
        tensor = read_tensor(info['safetensors_file'], info.get('weight_name', key))
        return tensor.to(device=self.device or 'cpu', dtype=getattr(torch, info['dtype']) if 'dtype' in info else tensor.dtype)
    OffloadedWeightsLoader.__getitem__ = getitem
    OffloadedWeightsLoader._dharmaflow_owned_buffers = True
