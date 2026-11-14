"""Tạo bảng đánh giá có hỗ trợ của AI từ trace lần chạy cuối."""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.chunking import by_paragraph, fixed_size
from src.models import DocumentPage
REVIEWER = "AI-generated audit draft; pending student review"


def main() -> None:
    manifest = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))
    docs = {doc["document_id"]: doc for doc in manifest["documents"]}
    traces = json.loads((ROOT / "results/traces.json").read_text(encoding="utf-8"))
    rows = []
    coherence_scores = {
        "A": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        "B": [2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
        "C": [2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
    }
    coherence_reasons = {
        "A": "Cửa sổ 500 ký tự bắt đầu hoặc kết thúc giữa câu tại vị trí mẫu; một phần ngữ cảnh bị thiếu.",
        "B": [
            "Đoạn bắt đầu và kết thúc ở ranh giới câu; giữ được mạch ý tại vị trí mẫu.",
        ] * 10,
        "C": [
            "Đoạn bắt đầu và kết thúc ở ranh giới câu; giữ được mạch ý tại vị trí mẫu.",
        ] * 10,
    }
    for n in range(1, 11):
        doc = next(d for d in manifest["documents"] if d["metadata"]["source_unit"] == n)
        text = (ROOT / doc["path"]).read_text(encoding="utf-8").strip()
        marker = text[1010:1020]
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
        "A": {"q16": 2, "q17": 2, "q18": 0, "q19": 1, "q20": 2},
        "B": {"q16": 2, "q17": 2, "q18": 0, "q19": 1, "q20": 2},
        "C": {"q16": 2, "q17": 2, "q18": 2, "q19": 1, "q20": 2},
    }
    grounding_reasons = {
        "q16": "Top-3 chứa đoạn nguồn nêu rõ nguy cơ từ vũ lực và ảnh hưởng bên ngoài; hỗ trợ trực tiếp câu trả lời về mối đe dọa từ nước ngoài.",
        "q17": "Top-3 chứa đoạn nguồn nói mức độ tin tưởng và tuân thủ thường tương ứng với chất lượng quản trị; hỗ trợ trực tiếp câu trả lời.",
        "q18": "C có đoạn ở hạng 3 nêu việc các nhà cải cách hướng tới nỗ lực của một nhà hiền triết thay vì hội đồng công dân. Top-3 của A và B không có bằng chứng tương đương.",
        "q19": "Top-3 bàn về Thượng viện và một phần uy tín của chính quyền, nhưng không giải thích đầy đủ vì sao Thượng viện nhỏ, ổn định hỗ trợ vị thế đối ngoại; chỉ có liên quan một phần.",
        "q20": "Đoạn hạng 1 nêu rõ Tổng thống bổ nhiệm đại sứ và thẩm phán Tòa án Tối cao với sự tư vấn và chấp thuận của Thượng viện; hỗ trợ trực tiếp câu trả lời, kể cả khi một số hit không trùng đơn vị gold.",
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
