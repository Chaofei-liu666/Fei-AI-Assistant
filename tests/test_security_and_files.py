import pytest

from fei_assistant.documents import validate_upload
from fei_assistant.schemas import ProviderConfigInput
from fei_assistant.storage import make_object_key


def test_provider_secrets_are_excluded_from_serialization() -> None:
    payload = ProviderConfigInput(slot="speech", provider="aliyun_paraformer", secret="dashscope-secret", secrets={"oss_secret": "oss-secret"})
    dumped = str(payload.model_dump())
    assert "dashscope-secret" not in dumped
    assert "oss-secret" not in dumped


def test_upload_type_and_size_validation() -> None:
    assert validate_upload("resume.pdf", b"%PDF-content", "resume", 100) == ".pdf"
    with pytest.raises(ValueError): validate_upload("resume.exe", b"content", "resume", 100)
    with pytest.raises(ValueError): validate_upload("resume.pdf", b"x" * 101, "resume", 100)


def test_object_key_cannot_escape_its_prefix() -> None:
    key = make_object_key("resume", "document-1", "../../secret resume.pdf")
    assert key == "resume/document-1/secret_resume.pdf"
    assert ".." not in key
