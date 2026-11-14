# Quy tắc chọn cấu hình cho lần đánh giá cuối

Bốn bộ test thăm dò trước đây đã được chạy và xem kết quả; câu hỏi, trace và chỉ số được lưu trong các thư mục `starter/benchmark/exploratory_superseded/`, `exploratory_second/`, `exploratory_third/`, `exploratory_hybrid/` và các thư mục kết quả tương ứng. Những bộ này không phải holdout. Bộ câu hỏi hiện tại là bộ thứ năm, gồm các đơn vị nguồn chưa có trong dev và được cố định trước lần chạy toàn bộ cuối. Việc đã xem bốn bộ trước làm giảm tính độc lập của đánh giá hiện tại; kết quả test cần được hiểu thận trọng.

Quy tắc chọn cấu hình dựa trên dev:

1. Chọn cấu hình có Evidence Hit@3 cao nhất.
2. Nếu hòa, chọn cấu hình có Hit@1 cao hơn.
3. Nếu vẫn hòa, chọn phương án đơn giản hơn, không cần filter theo từng câu.

Kết quả dev cuối: A đạt 7/15 Evidence Hit@3 và 6/15 Hit@1; B và C cùng đạt 12/15 Evidence Hit@3 và 7/15 Hit@1. Vì hòa cả hai chỉ số, chọn B theo tiêu chí đơn giản hơn. C chỉ khác B ở việc áp dụng filter category do câu hỏi cung cấp.

Kết quả test được ghi nhận sau khi đã khóa lựa chọn: A đạt 2/5 Evidence Hit@3, B đạt 3/5 và C đạt 4/5. Không dùng kết quả test để đổi cấu hình được chọn. C tuân thủ filter ở cả 4/4 câu test có filter. Xem toàn bộ số liệu trong `starter/results/retrieval_metrics.json` và `artifacts/experiment_log.csv`.
