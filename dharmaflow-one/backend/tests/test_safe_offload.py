import pytest
import torch
from safetensors.torch import save_file
from backend.core.safe_offload import read_tensor, install_owned_buffer_offload

@pytest.mark.parametrize('dtype',[torch.bfloat16,torch.float32,torch.float16])
def test_owned_buffer_matches_source(tmp_path,dtype):
    path=tmp_path/'weights.safetensors'
    expected=torch.arange(60,dtype=torch.float32).reshape(3,20).to(dtype)
    save_file({'weight':expected},str(path))
    actual=read_tensor(path,'weight')
    path.unlink()
    assert torch.equal(actual,expected)
    actual[0,0]=9
    assert actual[0,0]==9

def test_offload_reader_honors_dtype_and_rename(tmp_path):
    from accelerate.utils.offload import OffloadedWeightsLoader
    path=tmp_path/'weights.safetensors'
    save_file({'stored':torch.ones(4,dtype=torch.bfloat16)},str(path))
    install_owned_buffer_offload()
    loader=OffloadedWeightsLoader(index={'requested':{'safetensors_file':str(path),'weight_name':'stored','dtype':'float32'}})
    assert torch.equal(loader['requested'],torch.ones(4))
    assert loader['requested'].dtype==torch.float32

def test_truncated_tensor_is_python_error(tmp_path):
    path=tmp_path/'weights.safetensors'
    save_file({'weight':torch.ones(16)},str(path))
    data=path.read_bytes();path.write_bytes(data[:-4])
    with pytest.raises(ValueError,match='truncated'):
        read_tensor(path,'weight')
