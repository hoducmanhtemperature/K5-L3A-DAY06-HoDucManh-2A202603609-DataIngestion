# Day 06 pipeline

Pipeline hiện chạy với corpus Federalist Papers, Sentence Transformers local và Chroma persistent; không cần Docker hoặc API key. Các tệp PostgreSQL + pgvector được giữ làm phương án hạ tầng tham khảo, nhưng `src/run.py` hiện dùng Chroma.

## Cấu trúc

```text
starter/
├── docker-compose.yml     # phương án PostgreSQL tham khảo; không dùng trong run hiện tại
├── init.sql               # cấu hình pgvector cho phương án tham khảo
├── requirements.txt       # Chroma, Sentence Transformers, pypdf
├── .env.example           # cấu hình mẫu; copy thành .env
├── scripts/prepare_gutenberg.py # tách essay units và tạo manifest
├── src/
│   ├── models.py          # cấu trúc dữ liệu mẫu
│   ├── ingestion.py       # PDF/text extraction and normalization
│   ├── chunking.py        # fixed and paragraph chunking
│   ├── embeddings.py      # local Sentence Transformers adapter
│   ├── store.py           # persistent Chroma and PostgreSQL adapters
│   ├── evaluation.py      # retrieval metrics and trace labels
│   └── run.py             # A/B/C orchestration
├── data/                  # source units, manifest, and persistent Chroma
└── results/               # traces and measured metrics
```

## 1. Cài và chạy pipeline

Cần Python **3.11–3.13** và mạng để tải dependencies/model ở lần chạy đầu. Từ thư mục `starter/`:

```bash
cd starter
python3 -m venv .venv
```

Kích hoạt `.venv`: macOS/Linux dùng `source .venv/bin/activate`; Windows PowerShell dùng `.venv\Scripts\Activate.ps1`. Sau đó:

```bash
# Install the CPU-only PyTorch wheel first to avoid CUDA packages on CPU machines.
python -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.7.1+cpu
python -m pip install -r requirements.txt
python scripts/prepare_gutenberg.py
python -m src.run
```

Model local mặc định là `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`; lần đầu sẽ tải model và có thể mất vài phút. Chroma dùng cosine HNSW và lưu tại `data/chroma`. Đổi model hoặc thư mục bằng `DAY6_EMBEDDING_MODEL` hoặc `DAY6_VECTOR_DIR`.

## Kết quả và audit

Output vào `results/`: top-3 chunks, scores, metadata, Hit@1/Evidence Hit@3 per split, resource/timing, chunk-length percentile summaries, filter-compliance figures, and `ingestion_errors.json` (an empty list means no read/empty-page errors were found). The current audit labels are AI-assisted and not independently verified by the student; check the sampled coherence positions, all 5 test questions × top-3 metadata records, and grounding labels before submission as required by [GUIDE.md](../GUIDE.md). Grounding rates retrieved evidence, not LLM answer accuracy. Each rerun clears and rebuilds each strategy collection before upsert so obsolete chunks are removed if the corpus changes.

Lưu code, cấu hình, kết quả và lệnh chạy để người chấm tái lập; không commit key, dữ liệu mật hoặc dữ liệu không có quyền chia sẻ.
