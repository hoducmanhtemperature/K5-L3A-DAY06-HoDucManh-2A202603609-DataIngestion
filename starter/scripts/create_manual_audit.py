"""Tạo bảng đánh giá có hỗ trợ của AI từ trace lần chạy cuối."""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.chunking import by_paragraph, fixed_size
from src.models import DocumentPage
REVIEWER = "Nhãn đề xuất có hỗ trợ của AI; học viên chưa xác nhận độc lập"


def main() -> None:
    manifest = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))
    docs = {doc["document_id"]: doc for doc in manifest["documents"]}
    traces = json.loads((ROOT / "results/traces.json").read_text(encoding="utf-8"))
    rows = []
    coherence_scores = {
        "A": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        "B": [1, 2, 1, 2, 1, 2, 2, 2, 1, 1],
        "C": [1, 2, 1, 2, 1, 2, 2, 2, 1, 1],
    }
    coherence_reasons = {
        "A": "Cửa sổ 500 ký tự bắt đầu hoặc kết thúc giữa câu tại vị trí mẫu; một phần ngữ cảnh bị thiếu.",
        "B": [
            "Bắt đầu bằng phần cuối của câu trước; ý tiếp theo vẫn đọc hiểu được.",
            "Giữ trọn đoạn văn, gồm ý chính và ngữ cảnh.",
            "Có ý về an toàn nhưng thiếu phần dẫn chiếu trước đó.",
            "Giữ trọn đoạn văn với chủ thể rõ và phần giải thích liên kết.",
            "Bắt đầu giữa đoạn trích dẫn nên chưa rõ đầy đủ người nói và ngữ cảnh.",
            "Giữ trọn lập luận về khả năng xung đột giữa các bang lân cận.",
            "Giữ cùng một đoạn giải thích tranh chấp lãnh thổ và chi tiết hỗ trợ.",
            "Giữ trọn đoạn văn giải thích vấn đề cân bằng quân sự.",
            "Bắt đầu bằng cụm từ phụ thuộc; vẫn hiểu được ý chính nhưng ngữ cảnh bị cắt.",
            "Bắt đầu giữa câu trước phần bàn về cải tiến hiến pháp.",
        ],
        "C": [
            "Bắt đầu bằng phần cuối của câu trước; ý tiếp theo vẫn đọc hiểu được.",
            "Giữ trọn đoạn văn, gồm ý chính và ngữ cảnh.",
            "Có ý về an toàn nhưng thiếu phần dẫn chiếu trước đó.",
            "Giữ trọn đoạn văn với chủ thể rõ và phần giải thích liên kết.",
            "Bắt đầu giữa đoạn trích dẫn nên chưa rõ đầy đủ người nói và ngữ cảnh.",
            "Giữ trọn lập luận về khả năng xung đột giữa các bang lân cận.",
            "Giữ cùng một đoạn giải thích tranh chấp lãnh thổ và chi tiết hỗ trợ.",
            "Giữ trọn đoạn văn giải thích vấn đề cân bằng quân sự.",
            "Bắt đầu bằng cụm từ phụ thuộc; vẫn hiểu được ý chính nhưng ngữ cảnh bị cắt.",
            "Bắt đầu giữa câu trước phần bàn về cải tiến hiến pháp.",
        ],
    }
    for n in range(1, 11):
        doc = next(d for d in manifest["documents"] if d["metadata"]["source_unit"] == n)
        text = (ROOT / doc["path"]).read_text(encoding="utf-8").strip()
        marker = text[1010:1040]
        page = DocumentPage(doc["document_id"], doc["source"], n, text, doc["metadata"])
        chunks_by_strategy = {
            "A": fixed_size(page, size=500, overlap=50),
            "B": by_paragraph(page, max_size=700),
            "C": by_paragraph(page, max_size=700),
        }
        for strategy, chunks in chunks_by_strategy.items():
            chunk = next(c for c in chunks if marker in c.text)
            score = coherence_scores[strategy][n - 1]
            reason = coherence_reasons[strategy] if strategy == "A" else coherence_reasons[strategy][n - 1]
            rows.append({"strategy": strategy, "dimension": "mạch lạc",
                         "question_id_or_source_position": f"unit={n};offset=1010",
                         "chunk_id": chunk.chunk_id, "score_0_to_2": score,
                         "metadata_correct": "", "filter_compliant": "", "reason": reason,
                         "reviewer": REVIEWER})

    test_questions = {json.loads(line)["id"]: json.loads(line)
                      for line in (ROOT / "benchmark/questions.jsonl").read_text(encoding="utf-8").splitlines() if line
                      if json.loads(line)["split"] == "test"}
    grounding_scores = {
        "A": {"q16": 2, "q17": 1, "q18": 1, "q19": 1, "q20": 0},
        "B": {"q16": 2, "q17": 1, "q18": 1, "q19": 1, "q20": 0},
        "C": {"q16": 0, "q17": 1, "q18": 1, "q19": 1, "q20": 0},
    }
    grounding_reasons = {
        "q16": "A và B truy xuất No. 41, lập luận rằng Liên minh thống nhất có thể răn đe tham vọng bên ngoài; bằng chứng hỗ trợ ý chính nhưng thiếu một số chi tiết trong đáp án (điểm 2). C chỉ có ngữ cảnh chung về quân đội thời bình, không giải thích lý do cần tổ chức phòng thủ chung (điểm 0).",
        "q17": "Top-3 có nội dung về dân quân và phòng thủ chung nhưng không nêu điều kiện nổi loạn lan khắp bang hoặc phần chính của bang có thể khiến cần dùng lực lượng khác; chỉ có ngữ cảnh một phần.",
        "q18": "Kết quả nêu ý kiến phản đối rằng Hạ viện nhỏ có thể thiếu hiểu biết về cử tri, nhưng chưa hỗ trợ đầy đủ lời giải thích về đại diện theo khu vực.",
        "q19": "A truy xuất điều khoản điều chỉnh bầu cử trong No. 59; B/C truy xuất các đoạn liên quan trong No. 59. Top-3 chưa nêu đầy đủ ngoại lệ về điều kiện ứng cử mà câu hỏi yêu cầu.",
        "q20": "Top-3 gồm các đoạn hoặc tiêu đề bài luận không liên quan; không đoạn nào hỗ trợ danh sách quyền hạn được hỏi trong No. 41.",
    }
    for trace in traces:
        if trace["split"] != "test":
            continue
        question = test_questions[trace["question_id"]]
        for rank, hit in enumerate(trace["hits"], start=1):
            doc = docs[hit["document_id"]]
            metadata_ok = (hit["page"] in doc["content_pages"] and hit["source"] == doc["source"]
                           and hit["metadata"].get("document_id") == doc["document_id"]
                           and hit["metadata"].get("source") == doc["source"]
                           and hit["metadata"].get("page") == hit["page"]
                           and all(hit["metadata"].get(k) == v for k, v in doc["metadata"].items()))
            filt = question.get("filter", {}) if trace["strategy"] == "C" else {}
            filter_ok = all(hit["metadata"].get(k) == v for k, v in filt.items()) if filt else "Không áp dụng"
            rows.append({"strategy": trace["strategy"], "dimension": "metadata",
                         "question_id_or_source_position": f"{trace['question_id']};rank={rank}",
                         "chunk_id": hit["chunk_id"], "score_0_to_2": "",
                         "metadata_correct": metadata_ok, "filter_compliant": filter_ok,
                         "reason": "Đối chiếu tài liệu, nguồn, đơn vị và category kế thừa với manifest.",
                         "reviewer": REVIEWER})
        score = grounding_scores[trace["strategy"]][trace["question_id"]]
        reason = grounding_reasons.get(trace["question_id"])
        first_id = trace["hits"][0]["chunk_id"] if trace["hits"] else ""
        rows.append({"strategy": trace["strategy"], "dimension": "bằng chứng nền (grounding)",
                     "question_id_or_source_position": trace["question_id"], "chunk_id": first_id,
                     "score_0_to_2": score, "metadata_correct": "", "filter_compliant": "",
                     "reason": reason, "reviewer": REVIEWER})

    path = ROOT / "results/manual_audit.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        columns = [
            ("strategy", "chiến lược"),
            ("dimension", "tiêu chí"),
            ("question_id_or_source_position", "câu hỏi/vị trí mẫu"),
            ("chunk_id", "mã đoạn"),
            ("score_0_to_2", "điểm 0-2"),
            ("metadata_correct", "metadata đúng"),
            ("filter_compliant", "tuân thủ filter"),
            ("reason", "lý do"),
            ("reviewer", "người đánh giá"),
        ]
        writer = csv.DictWriter(f, fieldnames=[label for _, label in columns], lineterminator="\n")
        writer.writeheader()
        writer.writerows({label: row[key] for key, label in columns} for row in rows)
    print(f"Đã ghi {len(rows)} nhãn đánh giá có hỗ trợ của AI vào {path}")


if __name__ == "__main__":
    main()
