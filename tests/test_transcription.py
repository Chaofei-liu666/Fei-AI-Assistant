import pytest

from fei_assistant.transcription import ParaformerTranscriber


class FakeBucket:
    def __init__(self): self.deleted = []
    def put_object(self, key, data): return None
    def sign_url(self, *_): return "https://private.example/signed"
    def delete_object(self, key): self.deleted.append(key)


@pytest.mark.asyncio
async def test_temporary_oss_object_is_deleted_on_failure() -> None:
    transcriber = ParaformerTranscriber.__new__(ParaformerTranscriber)
    transcriber.bucket = FakeBucket()
    transcriber.task_id = None

    async def fail(*_): raise RuntimeError("provider failed")
    transcriber._submit = fail

    with pytest.raises(RuntimeError):
        await transcriber.transcribe(b"audio", "sample.wav", language_hints=["zh"], vocabulary=[], diarization=True)
    assert len(transcriber.bucket.deleted) == 1
