# Quy tắc chọn cấu hình cho bộ test cuối

Bộ test đầu tiên và bộ thay thế thứ hai đã được chạy thử, xem kết quả rồi lưu lại. Câu hỏi, trace và chỉ số của hai bộ này nằm tại `starter/benchmark/exploratory_superseded/`, `starter/results/exploratory_superseded/`, `starter/benchmark/exploratory_second/` và `starter/results/exploratory_second/`. Hai bộ này không được tính là holdout cuối. Bộ test hiện tại là bộ thứ ba, được cố định trước lần chạy cuối; việc đã xem hai bộ trước vẫn làm giảm tính độc lập của đánh giá.

Quy tắc được chốt dựa trên dev trước khi chạy bộ câu hỏi test thay thế:

1. Chọn cấu hình có Evidence Hit@3 trên dev cao nhất.
2. Nếu hòa, chọn cấu hình có Hit@1 trên dev cao hơn.
3. Nếu vẫn hòa, chọn cấu hình đơn giản hơn, không cần áp dụng filter theo từng câu.

Trong lần chạy được báo cáo, B có Evidence Hit@3 trên dev cao nhất (11/15), tiếp theo là C (10/15) và A (7/15), nên chọn B. Một lần chạy trước đó cho C kết quả 11/15; sau khi dựng lại chỉ mục Chroma HNSW, C đạt 10/15 dù câu hỏi và cấu hình không đổi. Chưa xác định nguyên nhân; biến thiên của tìm kiếm gần đúng là một khả năng. Đây là giới hạn của phép đo chỉ chạy một lần. Bộ test năm câu hiện tại trong `starter/benchmark/questions.jsonl` được dùng cho kết quả cuối. Không thay đổi cấu hình sau khi chốt bộ này.
