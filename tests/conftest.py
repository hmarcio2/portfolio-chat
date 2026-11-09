import pytest


@pytest.fixture(autouse=True)
def _no_real_langfuse(monkeypatch):
    """Os testes nunca enviam traces de verdade, mesmo que haja chaves do Langfuse no ambiente."""
    for name in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL", "LANGFUSE_HOST"):
        monkeypatch.delenv(name, raising=False)
