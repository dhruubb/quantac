"""
ingest_mda.py
Extracts MD&A sections from annual report PDFs and chunks them smartly.

Works across all companies in the corpus:
    ICICI Bank, TCS, Infosys, Reliance Industries, Adani Power
"""

import pdfplumber
import re


# ======================
# SECTION KEYWORDS
# Broadened to cover IT, energy, and conglomerate companies
# not just banking terminology
# ======================
SECTION_KEYWORDS = {
    "Macro & Economic Environment": [
        "economic environment",
        "global economic",
        "macroeconomic",
        "economic outlook",
        "interest rate environment",
        "global economy",
        "economic conditions",
        "geopolitical",
    ],
    "Industry & Sector Overview": [
        "banking industry",
        "industry overview",
        "industry scenario",
        "indian banking",
        "it industry",
        "technology industry",
        "software industry",
        "oil and gas",
        "energy sector",
        "telecom sector",
        "retail sector",
        "industry trends",
    ],
    "Business Performance": [
        "business performance",
        "overview of performance",
        "performance during the year",
        "review of the year",
        "business overview",
        "key highlights",
        "year in review",
    ],
    "Operating & Financial Performance": [
        "operating performance",
        "financial performance",
        "review of operations",
        "operational performance",
        "financial results",
        "results of operations",
        "consolidated performance",
    ],
    "Segment Performance": [
        "segment performance",
        "segment-wise performance",
        "business segments",
        "geographic performance",
        "vertical performance",
        "service line",
        "segment results",
    ],
    "Risks & Risk Management": [
        "risk management",
        "key risks",
        "credit risk",
        "market risk",
        "operational risk",
        "risk factors",
        "principal risks",
        "enterprise risk",
        "cybersecurity risk",
        "regulatory risk",
        "liquidity risk",
    ],
    "Outlook & Strategy": [
        "outlook",
        "future outlook",
        "strategy",
        "way forward",
        "forward looking",
        "strategic priorities",
        "strategic focus",
        "growth strategy",
        "digital strategy",
        "sustainability",
        "esg",
    ],
    "Human Capital": [
        "human capital",
        "employees",
        "talent",
        "workforce",
        "people strategy",
        "attrition",
        "hiring",
    ],
    "Technology & Innovation": [
        "technology initiatives",
        "digital transformation",
        "artificial intelligence",
        "cloud",
        "innovation",
        "research and development",
        "r&d",
    ],
}


# ======================
# TEXT CLEANING
# ======================
def clean_text(text):
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"Page \d+", "", text)
    text = re.sub(r"\n+", " ", text)
    return text.strip()


# ======================
# MD&A EXTRACTION
# ======================
def extract_mda_sections(pdf_path):
    extracted = {section: [] for section in SECTION_KEYWORDS}
    extracted["MD&A-General"] = []

    current_section = "MD&A-General"

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if not text:
                continue

            for line in text.split("\n"):
                line_clean = line.strip()
                line_lower = line_clean.lower()

                # ✅ break after first match so first keyword wins
                for section, keywords in SECTION_KEYWORDS.items():
                    if any(keyword in line_lower for keyword in keywords):
                        current_section = section
                        break

                if len(line_clean) > 40:
                    extracted[current_section].append({
                        "text": line_clean,
                        "page": page_num
                    })

    extracted = {k: v for k, v in extracted.items() if v}
    return extracted


# ======================
# SENTENCE SPLITTING
# ======================
def split_into_sentences(text):
    """Split text at sentence boundaries, protecting common abbreviations."""
    abbr_map = {
        "Dr.": "Dr", "Mr.": "Mr", "Ms.": "Ms",
        "Inc.": "Inc", "Ltd.": "Ltd",
        "e.g.": "eg", "i.e.": "ie", "vs.": "vs",
        "Rs.": "Rs", "No.": "No", "Co.": "Co",
        "approx.": "approx", "est.": "est",
    }
    for full, short in abbr_map.items():
        text = text.replace(full, short)

    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    return sentences


# ======================
# SENTENCE-AWARE CHUNKING
# ======================
def chunk_text_by_sentences(text, chunk_size=1000, overlap_sentences=2):
    """
    Chunk text by sentences with sentence-level overlap.
    Overlap is tracked by sentence count so we never cut mid-sentence.
    """
    sentences = split_into_sentences(text)
    sentences = [s.strip() for s in sentences if len(s.strip()) >= 10]

    chunks = []
    current_chunk = []
    current_size = 0

    for sentence in sentences:
        sentence_length = len(sentence)

        if current_size + sentence_length > chunk_size and current_chunk:
            chunks.append(' '.join(current_chunk))
            current_chunk = current_chunk[-overlap_sentences:]
            current_size = sum(len(s) for s in current_chunk)

        current_chunk.append(sentence)
        current_size += sentence_length + 1

    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks


# ======================
# CHUNK SECTIONS WITH METADATA
# ======================
def chunk_sections(sections, company, year):
    chunks = []

    for section, entries in sections.items():
        combined_text = " ".join(clean_text(e["text"]) for e in entries)

        if len(combined_text) < 100:
            continue

        text_chunks = chunk_text_by_sentences(
            combined_text,
            chunk_size=1000,
            overlap_sentences=2
        )

        for i, chunk in enumerate(text_chunks):
            if len(chunk) < 150:
                continue

            chunks.append({
                "content": chunk,
                "metadata": {
                    "company": company,
                    "year": year,
                    "doc_type": "MD&A",
                    "section": section,
                    "chunk_index": i
                }
            })

    return chunks


# ======================
# STANDALONE TEST
# ======================
if __name__ == "__main__":
    import sys

    # Default to ICICI 2025 for quick testing
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else \
        "icici/icici-bank-ar-2025-managements-discussion-and-analysis.pdf"

    company = sys.argv[2] if len(sys.argv) > 2 else "ICICI Bank"
    year = sys.argv[3] if len(sys.argv) > 3 else "FY2024-25"

    print(f"📄 Extracting from : {pdf_path}")
    print(f"🏢 Company         : {company}")
    print(f"📅 Year            : {year}\n")

    sections = extract_mda_sections(pdf_path)
    chunks = chunk_sections(sections, company=company, year=year)

    print(f"✅ Sections found : {list(sections.keys())}")
    print(f"✅ Total chunks   : {len(chunks)}")

    if chunks:
        lengths = [len(c["content"]) for c in chunks]
        print(f"\n📊 Chunk Stats:")
        print(f"   Min : {min(lengths)} chars")
        print(f"   Max : {max(lengths)} chars")
        print(f"   Avg : {sum(lengths) // len(lengths)} chars")
        print("\n--- Sample Chunk ---")
        print(chunks[0]["metadata"])
        print(chunks[0]["content"][:400])