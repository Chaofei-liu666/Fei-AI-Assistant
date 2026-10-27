import keyring


SERVICE_NAME = "FeiAssistant"


class SecretStore:
    def set(self, reference: str, value: str) -> None:
        keyring.set_password(SERVICE_NAME, reference, value)

    def get(self, reference: str | None) -> str | None:
        return keyring.get_password(SERVICE_NAME, reference) if reference else None

    def delete(self, reference: str | None) -> None:
        if reference:
            try:
                keyring.delete_password(SERVICE_NAME, reference)
            except keyring.errors.PasswordDeleteError:
                pass


def secret_metadata(secret: str | None) -> tuple[str | None, bool]:
    return ((secret[-4:] if secret else None), bool(secret))
