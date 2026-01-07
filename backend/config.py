import os
import re
from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential

# Allow overrides via environment variables
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT", "https://models.github.ai/inference")
MODEL_NAME = os.getenv("MODEL_NAME", "openai/gpt-4.1")


def _load_github_token() -> str:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        apikey_path = os.path.join(os.path.dirname(__file__), "..", "apikey.txt")
        apikey_path = os.path.abspath(apikey_path)
        try:
            with open(apikey_path, "r", encoding="utf-8") as f:
                token = f.read()
        except FileNotFoundError:
            token = None

    if not token:
        return ""

    raw = str(token)
    compact = raw.replace("\r", "\n").strip()
    if ("\n" in compact) or (" " in compact or "\t" in compact):
        m = re.search(r"(github_pat_[A-Za-z0-9_]{50,})", compact)
        if not m:
            m = re.search(r"(ghp_[A-Za-z0-9]{20,})", compact)
        if m:
            return m.group(1)
        if re.search(r"\bsk-[A-Za-z0-9_-]+", compact):
            raise RuntimeError(
                "GITHUB_TOKEN appears to be an OpenAI key (starts with sk-). "
                "Use a GitHub token (ghp_ or github_pat_) for https://models.github.ai/inference."
            )
        raise RuntimeError(
            "GITHUB_TOKEN contains multiple lines or invalid characters. "
            "Put a single GitHub token (ghp_... or github_pat_...) in .env or apikey.txt."
        )

    compact = compact.strip()
    if compact.startswith("sk-"):
        raise RuntimeError(
            "GITHUB_TOKEN appears to be an OpenAI key (starts with sk-). "
            "Use a GitHub token (ghp_ or github_pat_) for https://models.github.ai/inference."
        )
    return compact


GITHUB_TOKEN = _load_github_token()
if not GITHUB_TOKEN:
    raise RuntimeError(
        "Missing GITHUB_TOKEN. Set the environment variable or create an 'apikey.txt' "
        "file with the token (one line) next to app.py."
    )

client = ChatCompletionsClient(
    endpoint=AZURE_ENDPOINT,
    credential=AzureKeyCredential(GITHUB_TOKEN),
)

# Paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "recipes.db")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
DIST_DIR = os.path.join(FRONTEND_DIR, "dist")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
