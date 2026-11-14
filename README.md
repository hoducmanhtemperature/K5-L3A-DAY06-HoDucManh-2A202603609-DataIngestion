# Ngày 6 · Kỹ thuật nạp dữ liệu

**Bài thực hành cá nhân** · **4 giờ** · **Dữ liệu tự chọn**

Chuyển tài liệu thành kho tri thức có thể truy xuất cho tác tử AI, sau đó đo hiệu quả của các cách chuẩn bị dữ liệu.

| 📄 Dữ liệu | 🧩 Chiến lược | 🎯 Bộ câu hỏi đánh giá |
|---|---|---|
| Tối thiểu **30 trang nội dung** | Tối thiểu **3 cấu hình** | Tối thiểu **20 câu hỏi** |

## Bắt đầu nhanh

Dùng quy trình đã hoàn thiện trong `starter/src/`. Các tệp PostgreSQL + pgvector vẫn có sẵn làm phương án; lần chạy hiện tại dùng Chroma cục bộ, không cần Docker.

## 1. Xây dựng quy trình

![Đọc tài liệu, chuẩn hóa, chia đoạn, tạo vector, lưu và kiểm tra](assets/ingestion-pipeline.svg)

Chọn tài liệu được phép sử dụng; giữ **ID tài liệu, nguồn, trang/vị trí** và metadata phù hợp. Dùng mô hình embedding thật qua API hoặc chạy cục bộ; lưu và truy xuất bằng pgvector, Qdrant, Chroma hoặc kho tương đương.

## 2. So sánh và đánh giá

![Ba chiến lược được đánh giá trên cùng corpus và bộ câu hỏi dev/test](assets/benchmark-workflow.svg)

Dùng cùng dữ liệu, mô hình và câu hỏi cho cả ba cấu hình. Chốt **15 câu dev / 5 câu test** trước khi chạy; chọn cấu hình bằng dev rồi mới đánh giá test. Mỗi câu cần có đoạn bằng chứng và đơn vị nguồn; thiết kế bộ câu hỏi và cách đánh giá theo [BENCHMARK.md](BENCHMARK.md).

Đánh giá năm khía cạnh: **độ chính xác truy xuất**, **tính mạch lạc của đoạn**, **tính hữu dụng của metadata**, **chất lượng grounding (bằng chứng hỗ trợ)** và **tác động của chiến lược dữ liệu**. Giải thích lựa chọn bằng kết quả, ví dụ lỗi và các đánh đổi.

## 3. Chuẩn bị bài nộp

1. Chạy quy trình và lưu cấu hình, kết quả top-3, trace cùng nhãn đánh giá.
2. Điền [thông tin học viên](STUDENT.md), [nhật ký thí nghiệm](artifacts/experiment_log.csv) và báo cáo cá nhân trong `report/individual/`.
3. Kiểm tra mã nguồn, lệnh chạy, manifest dữ liệu và checklist trong [SUBMISSION.md](SUBMISSION.md).

## Bộ khung triển khai trong repo này

Corpus là *The Federalist Papers*, Project Gutenberg ebook số 18. Lấy tệp nguồn tại `https://www.gutenberg.org/cache/epub/18/pg18.txt`; hướng dẫn tải và dựng lại 86 đơn vị bài luận (mỗi đơn vị trên 1.500 ký tự) nằm trong `starter/README.md`. Manifest ghi mã băm nguồn và khoảng dòng để kiểm tra bản tải. Project Gutenberg ghi tác phẩm thuộc phạm vi công cộng tại Hoa Kỳ và yêu cầu người dùng ở quốc gia khác kiểm tra luật địa phương. Xem [catalog Project Gutenberg](https://www.gutenberg.org/ebooks/18), [điều khoản sử dụng](https://www.gutenberg.org/policy/license.html) và [WIPO Lex về luật Việt Nam](https://www.wipo.int/wipolex/en/legislation/details/12011). Không lưu bản ebook gốc hay các đơn vị corpus trong Git; hãy tải nguồn từ Project Gutenberg và tạo lại corpus theo hướng dẫn. Giữ nguyên ghi công và điều khoản khi chia sẻ.

Bộ câu hỏi có 15 câu dev và 5 câu test tại `starter/benchmark/questions.jsonl`. Bằng chứng được đối chiếu trực tiếp với đơn vị nguồn gold trước khi chạy. Một điểm bất thường của nguồn được giữ lại và ghi rõ: tiêu đề Federalist No. LXX xuất hiện hai lần; mỗi occurrence có ID riêng và số đơn vị theo thứ tự.

### Chuẩn bị manifest và bộ câu hỏi

Manifest đã được lưu trong repo; tệp nguồn và các đơn vị corpus được tải và tạo lại theo hướng dẫn bên dưới, không lưu trong Git:

```bash
python scripts/prepare_gutenberg.py
```

Mỗi đơn vị được nạp như một vị trí nguồn riêng; trường `page` trong trace là số đơn vị, không phải trang in. `category` là nhóm chủ đề rộng dựa trên dải tiêu đề trong mục lục nguồn. Câu hỏi filter nêu phạm vi chủ đề trước khi truy xuất; không truyền tài liệu gold hoặc đáp án vào filter.

### Chạy quy trình

Từ thư mục `starter/`, cài thư viện rồi chạy:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.7.1+cpu
python -m pip install -r requirements.txt
python scripts/prepare_gutenberg.py
python -m src.run
```

Quy trình dùng mặc định `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`; có thể đổi bằng `DAY6_EMBEDDING_MODEL`. Kho vector là Chroma PersistentClient với cosine HNSW; thư mục lưu có thể đổi bằng `DAY6_VECTOR_DIR`. A dùng cửa sổ 500 ký tự/chồng lấn 50; B và C gộp đoạn văn, chia đoạn dài tại ranh giới câu khi có thể, tối đa 700 ký tự. C dùng chung chỉ mục B và áp dụng filter metadata lấy từ câu hỏi. Cả ba dùng 50 ứng viên, `ef_search=300` và xếp hạng lại kết hợp BM25 với cosine (trọng số BM25 0,30). Kết quả chạy được ghi tại `starter/results/traces.json`, `retrieval_metrics.json`, `resource_metrics.json`; `ingestion_errors.json` luôn được tạo, kể cả khi danh sách lỗi rỗng. Thống kê tài nguyên có các phân vị độ dài đoạn. Embedding chạy cục bộ nên chi phí API là $0. Mỗi lần nạp sẽ xóa collection cũ rồi ghi lại để không giữ các đoạn lỗi thời nếu corpus thay đổi. Mô hình có thể cần tải lần đầu và sử dụng tài nguyên máy.

Hit@1 và Evidence Hit@3 tự động yêu cầu đoạn khớp tài liệu/đơn vị nguồn gold và chứa câu trích dẫn evidence. Nếu evidence bị chia giữa nhiều đoạn hoặc cách diễn đạt tương đương, hãy kiểm tra trace và ghi rõ lý do điều chỉnh nhãn; không sửa nhãn chỉ để tăng điểm. Đánh giá coherence tại cùng 10 vị trí nguồn, metadata trên 5 câu test × top-3, và grounding trên 5 câu test cho cả ba cấu hình theo [GUIDE.md](GUIDE.md). Khai báo công cụ AI và cách kiểm tra trong báo cáo, theo [RULES.md](RULES.md).

## Tài liệu hướng dẫn

| Nội dung | Tài liệu |
|---|---|
| Cài đặt PostgreSQL + pgvector tham khảo | [starter/README.md](starter/README.md) |
| Các bước và cách tính chỉ số | [GUIDE.md](GUIDE.md) |
| Mốc tiến độ trong 4 giờ | [CHECKPOINTS.md](CHECKPOINTS.md) |
| Năm tiêu chí đánh giá và bộ câu hỏi | [BENCHMARK.md](BENCHMARK.md) |
| Tiêu chí chấm điểm | [RUBRIC.md](RUBRIC.md) |
| Quy tắc dùng dữ liệu, AI và API | [RULES.md](RULES.md) |
| Cách nộp bài | [SUBMISSION.md](SUBMISSION.md) |

[data/format-example.json](data/format-example.json) chỉ minh họa định dạng, không phải corpus đủ điều kiện. Không bắt buộc xây chatbot.
