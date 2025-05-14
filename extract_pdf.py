import fitz  # PyMuPDF
import re
import json
from pathlib import Path

# === CONFIG ===
PDF_PATH = "Questions_Professional_Data_engineer.pdf"  # Make sure the PDF file is in the same folder
OUTPUT_JSON = "clean_exam_questions.json"
IMAGE_FOLDER = "extracted_images"
Path(IMAGE_FOLDER).mkdir(exist_ok=True)

# === UTILITY FUNCTIONS ===
def clean_text(text):
    return re.sub(r"[•\u2022\u2023\u25CF\u25E6\u2026🗳️]", "", text).strip()

def is_case_study(text):
    return "case study" in text.lower()

def extract_images(doc, page, question_number, skip_first_image=False):
    images = []
    skipped = False
    for img_index, img in enumerate(page.get_images(full=True)):
        xref = img[0]
        base_image = doc.extract_image(xref)
        ext = base_image["ext"]
        width = base_image.get("width", 0)
        height = base_image.get("height", 0)

        if width <= 20 and height <= 20:
            continue

        if skip_first_image and not skipped:
            skipped = True
            continue

        image_bytes = base_image["image"]
        filename = f"{question_number}_{img_index}.{ext}"
        image_path = Path(IMAGE_FOLDER) / filename
        with open(image_path, "wb") as f:
            f.write(image_bytes)
        images.append(str(image_path))
    return images

def extract_vote_distribution(lines):
    for line in lines:
        if "Community vote distribution" in line:
            return clean_text(line.split("Community vote distribution", 1)[-1].strip())
    return None

def parse_question_block(block):
    q = {
        "question_number": None,
        "question_text": "",
        "answers": {},
        "correct_answer": None,
        "Community vote distribution": None,
        "images": []
    }

    lines = block.strip().splitlines()
    current_letter = None
    correct_found = False

    for line in lines:
        line = clean_text(line)

        if match := re.match(r"Question\s+#(\d+)", line, re.IGNORECASE):
            q["question_number"] = int(match.group(1))

        elif line.lower().startswith("correct answer:"):
            full_correct = re.sub(r"[^\w]", "", line.split("Correct Answer:", 1)[-1])
            if full_correct:
                q["correct_answer"] = full_correct
                correct_found = True

        elif re.match(r"^[A-Z]\.", line):
            current_letter = line[0]
            answer_text = line[2:].strip()
            answer_text = re.sub(r"\bMost Voted\b.*", "", answer_text).strip()
            q["answers"][current_letter] = answer_text

        elif current_letter and not line.lower().startswith("community vote distribution"):
            q["answers"][current_letter] += " " + re.sub(r"\bMost Voted\b.*", "", line).strip()

        elif not current_letter and not line.lower().startswith("topic"):
            q["question_text"] += line + " "

    q["Community vote distribution"] = extract_vote_distribution(lines)

    return (q if not is_case_study(q["question_text"]) else None), correct_found

# === MAIN EXTRACT ===
doc = fitz.open(PDF_PATH)
questions = []
current_block = ""

for page in doc:
    text = page.get_text()
    lines = text.splitlines()
    for line in lines:
        if re.match(r"Question\s+#\d+", line, re.IGNORECASE):
            if current_block:
                q, skip_image = parse_question_block(current_block)
                if q:
                    q["images"] = extract_images(doc, page, q["question_number"], skip_first_image=skip_image)
                    questions.append(q)
            current_block = line + "\n"
        else:
            current_block += line + "\n"

# Final block
if current_block:
    q, skip_image = parse_question_block(current_block)
    if q:
        q["images"] = extract_images(doc, page, q["question_number"], skip_first_image=skip_image)
        questions.append(q)

# === SAVE TO JSON ===
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(questions, f, indent=2, ensure_ascii=False)

print(f"✅ Extracted {len(questions)} questions to {OUTPUT_JSON}")