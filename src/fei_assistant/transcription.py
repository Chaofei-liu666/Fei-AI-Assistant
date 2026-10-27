from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass

import httpx
import oss2


@dataclass(frozen=True)
class ParaformerConfig:
    dashscope_api_key: str
    oss_access_key_id: str
    oss_access_key_secret: str
    oss_endpoint: str
    oss_bucket: str
    workspace_id: str
    region_domain: str = "cn-beijing.maas.aliyuncs.com"
    model: str = "paraformer-v2"


class ParaformerTranscriber:
    def __init__(self, config: ParaformerConfig):
        self.config = config
        auth = oss2.Auth(config.oss_access_key_id, config.oss_access_key_secret)
        self.bucket = oss2.Bucket(auth, config.oss_endpoint, config.oss_bucket)
        self.task_id: str | None = None

    @property
    def api_url(self) -> str:
        return f"https://{self.config.workspace_id}.{self.config.region_domain}/api/v1"

    async def transcribe(
        self,
        data: bytes,
        filename: str,
        *,
        language_hints: list[str],
        vocabulary: list[str],
        diarization: bool,
    ) -> str:
        object_key = f"fei-transcription/{uuid.uuid4()}/{filename}"
        await asyncio.to_thread(self.bucket.put_object, object_key, data)
        vocabulary_id: str | None = None
        try:
            signed_url = self.bucket.sign_url("GET", object_key, 3600)
            if vocabulary:
                vocabulary_id = await self._create_vocabulary(vocabulary)
            task_id = await self._submit(signed_url, language_hints, vocabulary_id, diarization)
            self.task_id = task_id
            result = await self._poll(task_id)
            return await self._read_transcript(result)
        finally:
            try:
                if vocabulary_id:
                    await self._delete_vocabulary(vocabulary_id)
            finally:
                await asyncio.to_thread(self.bucket.delete_object, object_key)

    async def _create_vocabulary(self, words: list[str]) -> str:
        entries = []
        for word in words[:100]:
            word = word.strip()
            if not word:
                continue
            lang = "en" if word.isascii() else "zh"
            if (lang == "zh" and len(word) > 15) or (lang == "en" and len(word.split()) > 7):
                raise ValueError(f"hotword exceeds Aliyun length limit: {word}")
            entries.append({"text": word, "weight": 4, "lang": lang})
        if not entries:
            raise ValueError("hotword list is empty")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.api_url}/services/audio/asr/customization",
                headers={"Authorization": f"Bearer {self.config.dashscope_api_key}", "Content-Type": "application/json"},
                json={
                    "model": "speech-biasing",
                    "input": {
                        "action": "create_vocabulary",
                        "target_model": self.config.model,
                        "prefix": "feijob",
                        "vocabulary": entries,
                    },
                },
            )
            response.raise_for_status()
        vocabulary_id = response.json().get("output", {}).get("vocabulary_id")
        if not vocabulary_id:
            raise RuntimeError("DashScope did not return vocabulary_id")
        return vocabulary_id

    async def _delete_vocabulary(self, vocabulary_id: str) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.api_url}/services/audio/asr/customization",
                headers={"Authorization": f"Bearer {self.config.dashscope_api_key}", "Content-Type": "application/json"},
                json={"model": "speech-biasing", "input": {"action": "delete_vocabulary", "vocabulary_id": vocabulary_id}},
            )
            response.raise_for_status()

    async def _submit(self, url: str, language_hints: list[str], vocabulary_id: str | None, diarization: bool) -> str:
        parameters = {
            "language_hints": language_hints,
            "diarization_enabled": diarization,
        }
        if vocabulary_id:
            parameters["vocabulary_id"] = vocabulary_id
        body = {
            "model": self.config.model,
            "input": {"file_urls": [url]},
            "parameters": parameters,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.api_url}/services/audio/asr/transcription",
                headers={
                    "Authorization": f"Bearer {self.config.dashscope_api_key}",
                    "X-DashScope-Async": "enable",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            response.raise_for_status()
        task_id = response.json().get("output", {}).get("task_id")
        if not task_id:
            raise RuntimeError("DashScope did not return task_id")
        return task_id

    async def _poll(self, task_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            for _ in range(180):
                response = await client.get(
                    f"{self.api_url}/tasks/{task_id}",
                    headers={"Authorization": f"Bearer {self.config.dashscope_api_key}"},
                )
                response.raise_for_status()
                payload = response.json()
                status = payload.get("output", {}).get("task_status")
                if status == "SUCCEEDED":
                    return payload
                if status in {"FAILED", "CANCELED", "UNKNOWN"}:
                    raise RuntimeError(payload.get("message") or f"transcription {status}")
                await asyncio.sleep(2)
        raise TimeoutError("transcription timed out")

    async def _read_transcript(self, payload: dict) -> str:
        results = payload.get("output", {}).get("results") or []
        transcript_url = results[0].get("transcription_url") if results else None
        if not transcript_url:
            raise RuntimeError("transcription result URL is missing")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(transcript_url)
            response.raise_for_status()
            content = response.json()
        chunks: list[str] = []
        for transcript in content.get("transcripts", []):
            for sentence in transcript.get("sentences", []):
                speaker = sentence.get("speaker_id")
                prefix = f"说话人{speaker}: " if speaker is not None else ""
                chunks.append(prefix + sentence.get("text", ""))
        return "\n".join(chunks).strip()
