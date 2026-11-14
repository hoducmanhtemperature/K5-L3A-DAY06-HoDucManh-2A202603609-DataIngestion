# Quy trình nạp dữ liệu — Ngày 6

Quy trình hiện dùng corpus *The Federalist Papers*, Sentence Transformers chạy cục bộ và Chroma lưu bền vững; không cần Docker hay khóa API. Các tệp PostgreSQL + pgvector được giữ làm phương án tham khảo, nhưng `src/run.py` hiện chạy Chroma.

## Cấu trúc

```text
starter/
├── docker-compose.yml      # phương án PostgreSQL tham khảo, không dùng trong lần chạy này
├── init.sql                # cấu hình pgvector cho phương án tham khảo
├── requirements.txt        # thư viện Chroma, Sentence Transformers, pypdf
├── .env.example            # cấu hình tùy chọn; sao chép thành .env nếu cần
├── scripts/prepare_gutenberg.py # tách bài luận và tạo manifest
├── src/
│   ├── models.py           # cấu trúc dữ liệu
│   ├── ingestion.py        # trích xuất và chuẩn hóa PDF/văn bản
│   ├── chunking.py         # chia cửa sổ cố định hoặc gộp đoạn, tôn trọng câu
│   ├── embeddings.py       # bộ kết nối Sentence Transformers cục bộ
│   ├── store.py            # kho Chroma lưu bền vững và bộ kết nối PostgreSQL
│   ├── evaluation.py       # chỉ số truy xuất và trace
│   └── run.py              # điều phối A/B/C
├── data/                   # đơn vị nguồn, manifest và Chroma cục bộ
└── results/                # trace và kết quả đo
```

## Cài đặt và chạy

Cần Python **3.11–3.13** và kết nối mạng để tải thư viện/mô hình lần đầu. Từ thư mục `starter/`:

```bash
python3 -m venv .venv
```

Kích hoạt môi trường: macOS/Linux dùng `source .venv/bin/activate`; Windows PowerShell dùng `.venv\\Scripts\\Activate.ps1`. Sau đó:

```bash
# Cài PyTorch bản CPU trước để tránh tải gói CUDA trên máy không có GPU.
python -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.7.1+cpu
python -m pip install -r requirements.txt
python scripts/prepare_gutenberg.py
python -m src.run
```

Mô hình mặc định là `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`; lần chạy đầu có thể cần tải mô hình. Chroma dùng cosine với chỉ mục HNSW, 50 ứng viên và `ef_search=300`; BM25 kết hợp cosine để xếp hạng lại. B và C dùng chung chỉ mục B; C áp dụng filter category trước truy xuất. Dữ liệu lưu tại `data/chroma`. Có thể đổi mô hình hoặc thư mục lưu bằng `DAY6_EMBEDDING_MODEL` và `DAY6_VECTOR_DIR`.

## Kết quả và đánh giá

Thư mục `results/` lưu top-3 đoạn truy xuất, điểm, metadata, Hit@1/Evidence Hit@3 theo tập, thời gian/tài nguyên, phân vị chiều dài đoạn và mức tuân thủ filter. `ingestion_errors.json` luôn được ghi; danh sách rỗng nghĩa là lần đọc không phát hiện trang rỗng hoặc lỗi trích xuất.

Các nhãn coherence và grounding hiện được đề xuất với hỗ trợ của AI từ trace đã lưu, chưa phải đánh giá độc lập của học viên. Trước khi nộp, hãy kiểm tra mẫu vị trí coherence, 45 bản ghi metadata (5 câu test × top-3) và grounding theo [GUIDE.md](../GUIDE.md). Grounding đo mức độ bằng chứng truy xuất, không phải độ chính xác câu trả lời của mô hình ngôn ngữ.

Mỗi lần chạy lại sẽ xóa và dựng lại collection A và B trước khi nạp vector; C dùng chỉ mục B nên không tạo bản sao. Nhờ vậy các đoạn cũ được loại bỏ khi corpus thay đổi. Lưu mã nguồn, cấu hình, kết quả và lệnh chạy để người chấm có thể tái lập. Không đưa khóa API, dữ liệu riêng tư hoặc dữ liệu không có quyền chia sẻ vào repo.
