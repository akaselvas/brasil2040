import os
import time

import pytest
import requests

SEARCH_ENDPOINT = os.getenv("SEARCH_ENDPOINT", "http://localhost:8000/search")
CHAT_ENDPOINT = os.getenv("CHAT_ENDPOINT", "http://localhost:8000/chat")
PROD_TOP_K = int(os.getenv("PROD_TOP_K", "10"))
CHAT_REQUEST_DELAY_SEC = float(os.getenv("CHAT_REQUEST_DELAY_SEC", "3.0"))
CHAT_TIMEOUT_SEC = float(os.getenv("CHAT_TIMEOUT_SEC", "90"))


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


def get_production_answer(
    question: str,
    top_k: int = PROD_TOP_K,
    retries: int = 2,
    history: list | None = None,
) -> str:
    last_err = None
    for attempt in range(retries + 1):
        try:
            time.sleep(CHAT_REQUEST_DELAY_SEC)
            r = requests.post(
                CHAT_ENDPOINT,
                json={"question": question, "history": history or [], "top_k": top_k},
                timeout=CHAT_TIMEOUT_SEC,
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

        if attempt < retries:
            time.sleep(4.0 * (attempt + 1))

    pytest.fail(
        f"Chat endpoint at {CHAT_ENDPOINT} returned no answer after {retries + 1} attempts: {last_err}"
    )