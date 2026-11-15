import pytest
import numpy as np
from backend.providers.lipsync_worker import face_box

class Detector:
    def __init__(self,faces): self.faces=faces
    def detectMultiScale(self,*args,**kwargs): return self.faces

def test_lipsync_rejects_missing_or_multiple_faces():
    frame=np.zeros((300,300,3),dtype=np.uint8)
    for faces in [[],[(10,10,100,100),(120,10,100,100)]]:
        with pytest.raises(ValueError,match='exactly one'):
            face_box(frame,Detector(faces))
    assert face_box(frame,Detector([(50,50,120,120)]))==[50,50,170,173]

@pytest.mark.asyncio
async def test_missing_lipsync_install_blocks_project_early(async_client,monkeypatch):
    from backend.services import lipsync_service
    monkeypatch.setattr(lipsync_service,'lipsync_ready',lambda:False)
    result=await async_client.post('/api/projects',json={'topic':'A character says hello','lip_sync':True})
    assert result.status_code==503

@pytest.mark.asyncio
async def test_speaking_project_runs_lipsync_for_every_scene(async_client,monkeypatch):
    from backend.services import lipsync_service
    monkeypatch.setattr(lipsync_service,'lipsync_ready',lambda:True)
    calls=[]
    async def animate(source,audio,output,duration_ms,**kwargs):
        calls.append((source,audio,duration_ms))
        return source  # Pipeline integration fixture, not AI quality evidence.
    monkeypatch.setattr(lipsync_service,'animate_speech',animate)
    response=await async_client.post('/api/projects',json={'topic':'A character says hello','mode':'TURBO','lip_sync':True})
    assert response.status_code==200
    pid=response.json()['id']
    project=(await async_client.get(f'/api/projects/{pid}')).json()
    assert project['status']=='WAIT_VIDEO_REVIEW'
    assert project['lip_sync'] is True
    assert len(calls)==len(project['scenes'])==3
    quality=(await async_client.get(f'/api/projects/{pid}/quality')).json()
    assert quality['lip_sync']=='generated_not_independently_scored'
