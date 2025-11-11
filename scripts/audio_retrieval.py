#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Audio Retrieval (STAPI + FAISS) — 合併版
- 使用你本地 STAPI 服務 (http://localhost:8080) 產生嵌入
- 以 FAISS 做向量檢索（cosine，相當於 inner product on L2-normalized vectors）
- 回傳含時間碼的片段，提供可跳播 URL (audio_url#t=start,end)
- 內含互動式播放（browser / ffplay / mpv / vlc）

依賴：
  pip install requests faiss-cpu numpy
（若已安裝 faiss-gpu 且有 CUDA，可替換）

環境變數（可選）：
  STAPI_BASE_URL (default: http://localhost:8080)
  STAPI_API_KEY  (default: "")
  STAPI_MODEL    (default: BAAI/bge-large-zh-v1.5)
  EMBED_BATCH    (default: 64)
"""

import os, time, json, math, re
from pathlib import Path
from collections import Counter
import numpy as np
import requests
import faiss
import unicodedata
import subprocess
import webbrowser
import sys

# ------------------------------
# Config
# ------------------------------
STAPI_BASE_URL = os.getenv("STAPI_BASE_URL")
STAPI_API_KEY  = os.getenv("STAPI_API_KEY")
STAPI_MODEL    = os.getenv("STAPI_MODEL")
BATCH_SIZE     = int(os.getenv("EMBED_BATCH", "64"))
TIMEOUT        = 60

# Normalize to Simplified Chinese for consistency (recommended for better search)
# Set to True to convert both index and queries to Simplified Chinese
NORMALIZE_TO_SIMPLIFIED = os.getenv("NORMALIZE_TO_SIMPLIFIED", "true").lower() == "true"

# 你的檔案路徑（可依需要改）
STT_FILE   = os.getenv("STT_FILE", "/home/chiweic/repo/web_scrape/data/stt/世間禪悅1.json")
LINKS_FILE = os.getenv("LINKS_FILE", "raw_data/audio_links.json")


# ------------------------------
# Utilities
# ------------------------------
try:
    from opencc import OpenCC
    OPENCC_AVAILABLE = True
    # Converter: Simplified -> Traditional (for query normalization)
    s2t = OpenCC('s2t')
    # Converter: Traditional -> Simplified (for consistent indexing)
    t2s = OpenCC('t2s')
except ImportError:
    OPENCC_AVAILABLE = False
    print("⚠️  OpenCC not available. Install with: pip install opencc-python-reimplemented")
    print("   Without OpenCC, Simplified/Traditional Chinese mixing may reduce search quality.")

def normalize(s: str, to_simplified: bool = False) -> str:
    """
    基本正規化：NFKC、去多餘空白、繁簡轉換（可選）。

    Args:
        s: Input text
        to_simplified: If True and OpenCC available, convert to Simplified Chinese

    Returns:
        Normalized text
    """
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", " ", s.strip())

    # Convert to Simplified Chinese for consistency (if enabled)
    if to_simplified and OPENCC_AVAILABLE:
        s = t2s.convert(s)

    return s

def highlight(text: str, query: str, maxlen: int = 120) -> str:
    """簡單關鍵詞高亮（對英數大小寫不敏感；單字過短不高亮）。"""
    def tokenize_for_highlight(s: str):
        s = s.lower()
        return re.findall(r"[\u4e00-\u9fff]+|\w+", s)

    q_terms = [t for t in tokenize_for_highlight(query) if t]
    snippet = text
    for t in q_terms:
        if len(t) == 1:  # 避免單字過短造成過亮
            continue
        snippet = re.sub(re.escape(t), f"[{t}]", snippet, flags=re.IGNORECASE)
    snippet = snippet[:maxlen] + ("…" if len(snippet) > maxlen else "")
    return snippet

def stapi_embed(texts, model=STAPI_MODEL, base_url=STAPI_BASE_URL, api_key=STAPI_API_KEY,
                batch_size=BATCH_SIZE, timeout=TIMEOUT, max_retries=3, sleep_sec=1.0):
    """
    呼叫 STAPI /v1/embeddings 產生向量，並做 L2 normalize。
    期望回傳格式：
    {
      "data": [{"embedding": [...], "index": 0}, ...],
      "model": "...", "object": "list"
    }
    """
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    url = f"{base_url.rstrip('/')}/v1/embeddings"
    all_vecs = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        payload = {"input": batch, "model": model}

        for attempt in range(1, max_retries+1):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
                resp.raise_for_status()
                data = resp.json()
                vecs = [np.array(item["embedding"], dtype="float32") for item in data["data"]]
                vecs = np.vstack(vecs)
                # L2 normalize → cosine ready
                norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12
                vecs = (vecs / norms).astype("float32")
                all_vecs.append(vecs)
                break
            except Exception:
                if attempt == max_retries:
                    raise
                time.sleep(sleep_sec)

    return np.vstack(all_vecs) if all_vecs else np.zeros((0, 1), dtype="float32")


# ------------------------------
# Load data
# ------------------------------
with open(STT_FILE, "r", encoding="utf-8") as f:
    doc = json.load(f)
segments = doc["segments"]  # 每段有 start / end / text

with open(LINKS_FILE, "r", encoding="utf-8") as f:
    links = json.load(f)

# ------------------------------
# Resolve audio URL (robust matching)
# ------------------------------
title = Path(STT_FILE).stem  # e.g. "世間禪悅1"
audio_url = None
stem_digits = "".join(re.findall(r"\d+", title))
title_lower = title.lower()

candidates = []
for audios in links.get('audios', []):
    for audio_file in audios.get('audio_files', []):
        candidates.append(audio_file)

# 1) exact match
for a in candidates:
    if a.get('title') == title:
        audio_url = a['url']; break

# 2) fallback: 尾碼數字相同（如 …1）
if not audio_url and stem_digits:
    for a in candidates:
        tail_digits = "".join(re.findall(r"\d+", a.get('title', '')))
        if tail_digits == stem_digits:
            audio_url = a['url']; break

# 3) fallback: 子字包含
if not audio_url:
    for a in candidates:
        if title_lower in a.get('title', '').lower():
            audio_url = a['url']; break

# 4) fallback: 第一支
if not audio_url and candidates:
    audio_url = candidates[0]['url']

if not audio_url:
    raise RuntimeError("找不到對應的 audio_url，請檢查 audio_links.json 與 STT_FILE 標題對應。")

print(f"audio_url: {audio_url}")
DEFAULT_AUDIO_URL = audio_url


# ------------------------------
# Build embedding index (FAISS)
# ------------------------------
print(f"📊 正規化設定: {'簡體中文' if NORMALIZE_TO_SIMPLIFIED else '保持原文'}")
seg_texts = [normalize(seg["text"], to_simplified=NORMALIZE_TO_SIMPLIFIED) for seg in segments]
print(f"🔧 建立 FAISS 索引（{len(seg_texts)} 個片段）...")
seg_emb = stapi_embed(seg_texts)          # (num_segments, dim) 已 L2 normalize
dim = seg_emb.shape[1]
index = faiss.IndexFlatIP(dim)            # inner product == cosine (因為已 L2-norm)
index.add(seg_emb)
print(f"✅ 索引建立完成（維度: {dim}）")


# ------------------------------
# Retrieval
# ------------------------------
def audio_retrieval(query: str, top_k: int = 8):
    q = normalize(query, to_simplified=NORMALIZE_TO_SIMPLIFIED)
    q_emb = stapi_embed([q])               # (1, dim)

    # 多取一點再裁切（之後可做鄰近合併）
    D, I = index.search(q_emb, top_k * 3)
    hits = []
    for score, idx in zip(D[0], I[0]):
        if idx == -1:
            continue
        seg = segments[idx]
        start = float(seg["start"]); end = float(seg["end"])
        text = normalize(seg["text"])
        jump = f"{DEFAULT_AUDIO_URL}#t={int(start)},{int(end)}"
        hits.append({
            "score": float(round(score, 4)),   # cosine similarity
            "snippet": highlight(text, query),
            "audio_url": DEFAULT_AUDIO_URL,
            "start": start,
            "end": end,
            "jump_to": jump
        })
    return {"query": query, "hits": hits[:top_k]}


# ------------------------------
# Playback helpers (optional)
# ------------------------------
def play_audio_clip(audio_url: str, start_time: float, end_time: float, method: str = "browser"):
    """在瀏覽器或本地播放器播放片段。"""
    duration = max(0.0, float(end_time - start_time))

    if method == "browser":
        jump_url = f"{audio_url}#t={int(start_time)},{int(end_time)}"
        print(f"🎵 在瀏覽器中播放: {jump_url}")
        webbrowser.open(jump_url)
        return

    if method == "ffplay":
        cmd = ["ffplay", "-ss", str(start_time), "-t", str(duration), "-nodisp", "-autoexit", audio_url]
    elif method == "mpv":
        cmd = ["mpv", f"--start={start_time}", f"--end={end_time}", "--no-video", audio_url]
    elif method == "vlc":
        cmd = ["vlc", "--start-time", str(int(start_time)), "--stop-time", str(int(end_time)),
               "--play-and-exit", audio_url]
    else:
        print(f"❌ 不支援的播放方法: {method}")
        return

    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        print(f"❌ 找不到播放器：{method}。請安裝對應工具或改用 browser。")
    except Exception as e:
        print(f"❌ 播放失敗: {e}")


def interactive_play(results: dict, method: str = "browser"):
    """互動式從搜尋結果播放片段。"""
    hits = results.get("hits", [])
    if not hits:
        print("❌ 沒有搜索結果")
        return

    print("\n" + "="*80)
    print(f"搜索結果: {results['query']}")
    print("="*80)
    for i, hit in enumerate(hits, 1):
        print(f"\n[{i}] 分數: {hit['score']:.4f}")
        print(f"    時間: {hit['start']:.1f}s - {hit['end']:.1f}s")
        print(f"    內容: {hit['snippet']}")

    print("\n" + "-"*80)
    print("輸入編號播放 (1-{}) | 'a' 播放全部 | 'q' 退出".format(len(hits)))
    print("-"*80)

    while True:
        try:
            choice = input("\n選擇 > ").strip().lower()
            if choice == 'q':
                print("👋 退出"); break
            elif choice == 'a':
                print(f"\n🎵 播放全部 {len(hits)} 個片段...")
                for i, hit in enumerate(hits, 1):
                    print(f"\n--- 片段 {i}/{len(hits)} ---")
                    play_audio_clip(hit["audio_url"], hit["start"], hit["end"], method=method)
                    if i < len(hits):
                        input("按 Enter 繼續下一個...")
                break
            elif choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(hits):
                    hit = hits[idx]
                    print(f"\n🎵 播放片段 {choice}: {hit['snippet']}")
                    play_audio_clip(hit["audio_url"], hit["start"], hit["end"], method=method)
                else:
                    print(f"❌ 無效編號，請輸入 1-{len(hits)}")
            else:
                print(f"❌ 無效輸入，請輸入 1-{len(hits)}, 'a', 或 'q'")
        except KeyboardInterrupt:
            print("\n👋 退出"); break
        except Exception as e:
            print(f"❌ 錯誤: {e}")


# ------------------------------
# CLI
# ------------------------------
if __name__ == "__main__":
    query  = sys.argv[1] if len(sys.argv) > 1 else "禪法"
    method = sys.argv[2] if len(sys.argv) > 2 else "browser"

    print(f"🔍 搜索: {query}")
    demo = audio_retrieval(query, top_k=8)

    if not demo["hits"]:
        print("（沒有命中，試試換詞或放寬查詢）")
    else:
        print(f"\n找到 {len(demo['hits'])} 個結果:\n")
        for i, h in enumerate(demo["hits"], 1):
            print(f"{i}. [分數 {h['score']:.4f}] {h['start']:.1f}s-{h['end']:.1f}s")
            print(f"   {h['snippet']}")
            print(f"   跳轉: {h['jump_to']}\n")

        # 互動播放
        interactive_play(demo, method=method)
