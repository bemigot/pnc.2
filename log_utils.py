import logging


class _RedactingFormatter(logging.Formatter):
    def __init__(self, fmt: str, token: str, replacement: str):
        super().__init__(fmt)
        self._token = token
        self._replacement = replacement

    def format(self, record: logging.LogRecord) -> str:
        return super().format(record).replace(self._token, self._replacement)


def install_log_redactor(secret: str, replacement: str = "<REDACTED>", fmt: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s") -> None:
    """Replace the root logger's formatter with one that redacts *secret* from all output."""
    formatter = _RedactingFormatter(fmt, secret, replacement)
    for handler in logging.getLogger().handlers:
        handler.setFormatter(formatter)
