# Day 06 · Data Ingestion Engineering

**Lab cá nhân** · **4 giờ** · **Dữ liệu tự chọn**

Biến tài liệu thành kho tri thức có thể truy xuất cho AI agent, rồi đo xem cách chuẩn bị dữ liệu nào hiệu quả nhất.

| 📄 Dữ liệu | 🧩 Chiến lược | 🎯 Benchmark |
|---|---|---|
| Tối thiểu **30 trang nội dung** | Tối thiểu **3 cấu hình** | Tối thiểu **20 câu hỏi** |

## Bắt đầu nhanh

Dùng pipeline đã hoàn thiện trong `starter/src/`. Starter PostgreSQL + pgvector vẫn có sẵn làm tùy chọn, nhưng lần chạy đã cấu hình Chroma local để không phụ thuộc Docker.

## 1. Xây pipeline

![Đọc tài liệu, chuẩn hóa, chia chunk, tạo vector, lưu và kiểm tra](assets/ingestion-pipeline.svg)

Chọn tài liệu được phép sử dụng; giữ **ID tài liệu, nguồn, trang/vị trí** và metadata phù hợp. Dùng embedding model thật qua API hoặc chạy local; lưu và truy xuất bằng pgvector, Qdrant, Chroma hoặc một store tương đương.

## 2. So sánh và đánh giá

![Ba chiến lược được đánh giá trên cùng corpus và benchmark dev/test](assets/benchmark-workflow.svg)

Dùng cùng dữ liệu, model và câu hỏi cho cả ba cấu hình. Tách **15 câu dev / 5 câu test** trước khi chạy; chọn cấu hình trên dev, rồi đánh giá test sau khi cố định. Mỗi câu hỏi cần có đoạn bằng chứng và trang nguồn; thiết kế bộ câu hỏi và đánh giá theo [BENCHMARK.md](BENCHMARK.md).

Đánh giá theo năm khía cạnh: **độ chính xác truy xuất**, **tính mạch lạc của chunk**, **tính hữu dụng của metadata**, **chất lượng grounding** và **tác động của chiến lược dữ liệu**. Giải thích lựa chọn bằng kết quả, ví dụ lỗi và các đánh đổi.

## 3. Chuẩn bị bài nộp

1. Chạy pipeline và lưu cấu hình, kết quả top-3, trace cùng nhãn đánh giá thủ công.
2. Điền [thông tin học viên](STUDENT.md), [nhật ký thí nghiệm](artifacts/experiment_log.csv) và bản sao [mẫu báo cáo cá nhân](report/individual/MSSV_HoTen.md).
3. Kiểm tra mã nguồn, cách chạy, manifest dữ liệu và checklist trong [SUBMISSION.md](SUBMISSION.md).

## Bộ khung triển khai trong repo này

Corpus là *The Federalist Papers*, Project Gutenberg eBook #18. Tệp nguồn gốc nằm ở `data/source/federalist-papers.txt`; `starter/scripts/prepare_gutenberg.py` tách 86 essay units, mỗi unit trên 1.500 ký tự, tạo manifest có hash nguồn và line range. Project Gutenberg ghi tác phẩm public domain tại Hoa Kỳ và yêu cầu người dùng ngoài Hoa Kỳ kiểm tra luật địa phương. Tại Việt Nam, luật quy định thời hạn tác phẩm đồng tác giả đến 50 năm sau khi đồng tác giả cuối cùng qua đời; các tác giả của tập này mất trong các năm 1804, 1829 và 1836. Xem [catalog Project Gutenberg](https://www.gutenberg.org/ebooks/18), [điều khoản sử dụng](https://www.gutenberg.org/policy/license.html) và [WIPO Lex về luật Việt Nam](https://www.wipo.int/wipolex/en/legislation/details/12011). Tệp eBook giữ nguyên thông báo và license Project Gutenberg; phần corpus tạo ra chỉ chuẩn hóa xuống dòng và tách theo essay. Không xóa attribution/license khi chia sẻ.

Benchmark có 15 câu dev và 5 câu test trong `starter/benchmark/questions.jsonl`. Evidence quote được đối chiếu trực tiếp với unit gold trước khi chạy. Một lỗi cấu trúc của nguồn được giữ nguyên và ghi rõ: heading Federalist No. LXX xuất hiện hai lần; mỗi occurrence có ID riêng và source unit theo thứ tự.

### Chuẩn bị manifest và benchmark

Manifest và source units đã được tạo. Để tái tạo sau khi thay tệp nguồn, chạy từ `starter/`:

```bash
python scripts/prepare_gutenberg.py
```

Các unit được nạp như text nguồn độc lập; `page` trong trace là số unit nguồn, không phải trang in của một ấn bản. Trường `category` là nhóm chủ đề rộng dựa trên dải tiêu đề trong mục lục nguồn; câu hỏi có filter nêu phạm vi chủ đề trước khi truy xuất, không truyền gold document hoặc đáp án vào filter.

### Chạy pipeline

Từ thư mục `starter/`, cài dependencies và chạy:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.7.1+cpu
python -m pip install -r requirements.txt
python scripts/prepare_gutenberg.py
python -m src.run
```

Pipeline dùng `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` theo mặc định; có thể đổi bằng `DAY6_EMBEDDING_MODEL`. Vector store là Chroma PersistentClient với cosine HNSW; có thể đổi thư mục bằng `DAY6_VECTOR_DIR`. Cấu hình C chỉ áp dụng metadata filter của câu hỏi; A dùng cửa sổ 500 ký tự/overlap 50, B và C gom đoạn đến 700 ký tự. Cả ba dùng cùng model/store/metric. Kết quả chạy thật ghi vào `starter/results/traces.json`, `retrieval_metrics.json`, `resource_metrics.json`; `ingestion_errors.json` luôn được ghi, kể cả khi không có lỗi. Resource metrics có phân vị độ dài chunk. Embedding chạy local, nên chi phí API là 0. Chroma dùng cosine HNSW; mỗi lần nạp strategy sẽ xóa collection cũ rồi nạp lại toàn bộ chunk, tránh giữ chunk lỗi thời khi corpus đổi. Model có thể cần tải lần đầu và tốn tài nguyên.

Hit@1 và Evidence Hit@3 tự động yêu cầu chunk khớp document/page gold và chứa evidence quote. Nếu evidence bị chia qua chunk hoặc cách diễn đạt tương đương, hãy xác minh trace và ghi sửa nhãn có lý do; không thay nhãn vàng để làm điểm cao hơn. Tự chấm coherence trên cùng 10 vị trí nguồn, metadata trên 5 câu test × top-3, và grounding trên 5 câu test cho cả ba cấu hình theo [GUIDE.md](GUIDE.md). Ghi công cụ AI và cách bạn tự kiểm tra trong báo cáo, theo [RULES.md](RULES.md).

## Tài liệu hướng dẫn

| Bạn cần tìm | Tài liệu |
|---|---|
| Setup baseline PostgreSQL + pgvector | [starter/README.md](starter/README.md) |
| Các bước làm và cách tính chỉ số | [GUIDE.md](GUIDE.md) |
| Tiến độ trong 4 giờ | [CHECKPOINTS.md](CHECKPOINTS.md) |
| Năm tiêu chí benchmark và bộ câu hỏi | [BENCHMARK.md](BENCHMARK.md) |
| Tiêu chí chấm điểm | [RUBRIC.md](RUBRIC.md) |
| Quy tắc sử dụng dữ liệu, AI và API | [RULES.md](RULES.md) |
| Cách nộp bài | [SUBMISSION.md](SUBMISSION.md) |

[data/format-example.json](data/format-example.json) chỉ minh họa định dạng, không phải corpus đủ điều kiện. Không bắt buộc xây chatbot.
