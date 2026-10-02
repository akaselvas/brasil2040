"""helpers.py — acesso ao pipeline REAL de produção (/search e /chat)."""
import os
import time

import pytest
import requests

SEARCH_ENDPOINT = os.getenv("SEARCH_ENDPOINT", "http://localhost:8000/search")
CHAT_ENDPOINT = os.getenv("CHAT_ENDPOINT", "http://localhost:8000/chat")
PROD_TOP_K = int(os.getenv("PROD_TOP_K", "10"))  # mesmo valor que o app.js envia


def get_chunks(question: str, top_k: int = PROD_TOP_K) -> list[dict]:
    try:
        r = requests.post(
            SEARCH_ENDPOINT,
            json={"question": question, "top_k": top_k},
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("chunks", [])
    except requests.exceptions.ConnectionError:
        pytest.fail(f"Server not reachable at {SEARCH_ENDPOINT}. Must not be skipped in CI.")


def get_production_answer(question: str, top_k: int = PROD_TOP_K, retries: int = 2) -> str:
    """Chama o /chat de produção (mesmo SYSTEM_PROMPT, mesma temperatura, mesmo top_k)."""
    last_err = None
    for attempt in range(retries + 1):
        try:
            time.sleep(3.0)  # respeita o rate limit do free tier
            r = requests.post(
                CHAT_ENDPOINT,
                json={"question": question, "history": [], "top_k": top_k},
                timeout=90,
                stream=True,
            )
            r.raise_for_status()
            text = r.content.decode("utf-8", errors="replace")
            if text.strip():
                return text
            last_err = "empty response"
        except requests.exceptions.ConnectionError:
            pytest.fail(f"Server not reachable at {CHAT_ENDPOINT}.")
        except requests.exceptions.RequestException as e:
            last_err = e
            time.sleep(4.0 * (attempt + 1))
    return f"[ERROR generating answer: {last_err}]"