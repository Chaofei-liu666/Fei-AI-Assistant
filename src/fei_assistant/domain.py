from enum import StrEnum


class ProviderKind(StrEnum):
    DEEPSEEK = "deepseek"
    OPENAI_COMPATIBLE = "openai_compatible"
    ALIYUN_PARAFORMER = "aliyun_paraformer"
    EMAIL_163 = "email_163"


class ApplicationStatus(StrEnum):
    SAVED = "saved"
    APPLIED = "applied"
    SCREENING = "screening"
    ASSESSMENT = "assessment"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class MailType(StrEnum):
    INTERVIEW_INVITE = "interview_invite"
    ASSESSMENT = "assessment"
    REJECTION = "rejection"
    OFFER = "offer"
    RECRUITER_MESSAGE = "recruiter_message"
    IRRELEVANT = "irrelevant"


class MatchLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
