"""Which chat models does YOUR key actually reach? Lists them, then sends each a tiny test call.

The /models list shows everything the provider hosts, not what your key may
use, so only a real call proves access. Uses LLM_BASE_URL and LLM_API_KEY
from .env (the key is never printed).

  python labs/check_models.py              # test every chat model in the list
  python labs/check_models.py nemotron     # only models whose id contains "nemotron"
"""

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
SKIP = ("embed", "rerank", "reward", "guard", "safety", "vision", "-vl", "clip", "parse", "ocr", "pii",
        "retriev", "calib", "translate", "detector", "deplot", "neva", "vila", "cosmos", "fuyu", "kosmos")

client = OpenAI(base_url=os.getenv("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1"),
                api_key=os.environ["LLM_API_KEY"], timeout=25, max_retries=0)


def probe(model: str) -> tuple[str, str]:
    start = time.time()
    try:
        r = client.chat.completions.create(model=model, max_tokens=10, temperature=0,
                                           messages=[{"role": "user", "content": "Reply with: OK"}])
        text = (r.choices[0].message.content or "").strip().replace("\n", " ")[:20]
        return "OK", f"{time.time() - start:4.1f}s  {model}  -> {text!r}"
    except Exception as e:  # noqa: BLE001 - any failure means "not usable right now"
        return "NO", f"{time.time() - start:4.1f}s  {model}  ({type(e).__name__})"


def main() -> None:
    word = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    ids = sorted(m.id for m in client.models.list())
    chat = [i for i in ids if word in i.lower() and not any(s in i.lower() for s in SKIP)]
    print(f"{len(ids)} models listed, testing {len(chat)} chat models (25 s timeout each)...\n")
    with ThreadPoolExecutor(12) as ex:
        results = list(ex.map(probe, chat))
    for status in ("OK", "NO"):
        print("WORKS with your key:" if status == "OK" else "\nlisted but NOT usable now:")
        for s, line in results:
            if s == status:
                print("  " + line)
    print("\nUse one in .env:  LLM_MODEL=<id>   (and QLLM_MODEL=<id> for the second model)")


if __name__ == "__main__":
    main()
