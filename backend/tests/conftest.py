"""Tests always run on the bundled demo dataset with AI switched off.

This keeps them independent of whatever real data is in backend/data and of the
API keys in backend/.env. It runs before any `app` import, so settings see it.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "demo_data"
_TMP = Path(tempfile.mkdtemp(prefix="pardarshi-test-")) / "data"
shutil.copytree(_FIXTURE, _TMP)
(_TMP / "eval").mkdir(exist_ok=True)

os.environ["DATA_DIR"] = str(_TMP)
# Empty values win over backend/.env (python-dotenv never overrides set variables).
for key in ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "MISTRAL_API_KEY",
            "OPENAI_COMPAT_BASE_URL", "OLLAMA_URL", "LLM_ORDER"):
    os.environ[key] = ""
