# """
# build_vectorstore.py
# Builds a FAISS vector store from MD&A PDFs.
# Currently scoped to ICICI Bank FY2024-25 for testing.

# To add more companies/years later:
#   - Uncomment entries in COMPANIES / YEARS
#   - Place PDFs at data/<company_dir>/<pdf_filename>
#   - Re-run this script
# """

# import os
# from langchain_community.embeddings import HuggingFaceEmbeddings
# from langchain_community.vectorstores import FAISS

# from ingest_mda import extract_mda_sections, chunk_sections


# DATA_DIR = "data"
# VECTORSTORE_DIR = "vectorstore/mda_faiss"

# # ── Companies to index ──────────────────────────────────────────────────────
# COMPANIES = {
#     "icici": "ICICI Bank",
#     # "tcs":        "TCS",
#     # "infosys":    "Infosys",
#     # "reliance":   "Reliance Industries",
#     # "adani_power":"Adani Power",
# }

# # ── PDFs to include per company ─────────────────────────────────────────────
# # Place files at:  data/<company_dir>/<pdf_filename>
# YEARS = {
#     "mda_2425.pdf": "FY2024-25",
#     # "mda_2324.pdf": "FY2023-24",
# }


# def build_vectorstore():
#     print("🚀 Starting FAISS vectorstore build...\n")

#     embeddings = HuggingFaceEmbeddings(
#         model_name="sentence-transformers/all-MiniLM-L6-v2"
#     )

#     vectorstore = None
#     total_chunks = 0

#     for company_dir, company_name in COMPANIES.items():
#         company_path = os.path.join(DATA_DIR, company_dir)

#         for pdf_filename, year in YEARS.items():
#             pdf_path = os.path.join(company_path, pdf_filename)

#             if not os.path.exists(pdf_path):
#                 print(f"⚠️  Not found — skipping: {pdf_path}")
#                 continue

#             print(f"📄 Processing : {company_name} | {year}")
#             print(f"   Path       : {pdf_path}")

#             sections = extract_mda_sections(pdf_path)
#             chunks = chunk_sections(sections, company_name, year)

#             if not chunks:
#                 print(f"   ⚠️  No chunks extracted — check PDF text layer")
#                 continue

#             texts = [c["content"] for c in chunks]
#             metadatas = [c["metadata"] for c in chunks]

#             print(f"   ✅ {len(chunks)} chunks ready for indexing")
#             total_chunks += len(chunks)

#             if vectorstore is None:
#                 vectorstore = FAISS.from_texts(
#                     texts=texts,
#                     embedding=embeddings,
#                     metadatas=metadatas
#                 )
#             else:
#                 vectorstore.add_texts(texts=texts, metadatas=metadatas)

#     if vectorstore is None:
#         print("\n❌ No documents were processed.")
#         print("   Make sure your PDF is at: data/icici/mda_2425.pdf")
#         return

#     os.makedirs(VECTORSTORE_DIR, exist_ok=True)
#     vectorstore.save_local(VECTORSTORE_DIR)

#     print(f"\n✅ Vectorstore saved to : {VECTORSTORE_DIR}")
#     print(f"📊 Total chunks indexed : {total_chunks}")


# if __name__ == "__main__":
#     build_vectorstore()

"""
build_vectorstore.py
Builds a FAISS vector store from all company MD&A PDFs + Excel financial data.
"""

import os
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

from ingest_mda import extract_mda_sections, chunk_sections
from ingest_excel import ingest_excel


VECTORSTORE_DIR = "vectorstore/mda_faiss"

# ── MD&A PDFs ────────────────────────────────────────────────────────────────
# (folder, filename, company_name, year)
PDF_DOCUMENTS = [
    # ICICI Bank
    ("icici", "icici-bank-ar-2024-managements-discussion-and-analysis.pdf", "ICICI Bank", "FY2023-24"),
    ("icici", "icici-bank-ar-2025-managements-discussion-and-analysis.pdf", "ICICI Bank", "FY2024-25"),

    # TCS
    ("tcs", "TCS MD&A 2024.pdf", "TCS", "FY2023-24"),
    ("tcs", "TCS MD&A 2025.pdf", "TCS", "FY2024-25"),

    # Infosys
    ("infosys", "INFOSYS MD&A 2024.pdf", "Infosys", "FY2023-24"),
    ("infosys", "Infosys MD&A 2025.pdf", "Infosys", "FY2024-25"),

    # Reliance
    ("reliance", "Reliance MD&A 2024.pdf", "Reliance Industries", "FY2023-24"),
    ("reliance", "Reliance MD&A 2025.pdf", "Reliance Industries", "FY2024-25"),

    # Adani Power — note the capitalisation difference in filenames
    ("adani power", "Adani Power MD&A 2024.pdf", "Adani Power", "FY2023-24"),
    ("adani power", "Adani power MD&A 2025.pdf", "Adani Power", "FY2024-25"),
]

# ── Excel Financial Data ─────────────────────────────────────────────────────
# (folder, filename, company_name)
EXCEL_DOCUMENTS = [
    ("icici",       "ICICI Bank.xlsx",          "ICICI Bank"),
    ("tcs",         "TCS.xlsx",                 "TCS"),
    ("infosys",     "Infosys.xlsx",             "Infosys"),
    ("reliance",    "Reliance Industr.xlsx",    "Reliance Industries"),
    ("adani power", "Adani Power.xlsx",         "Adani Power"),
]


def build_vectorstore():
    print("🚀 Starting FAISS vectorstore build...\n")

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    vectorstore = None
    total_chunks = 0
    pdf_processed = 0
    excel_processed = 0
    skipped = 0

    # ── Step 1: Ingest MD&A PDFs ─────────────────────────────────────────────
    print("=" * 55)
    print("📄 INGESTING MD&A PDFs")
    print("=" * 55)

    for folder, filename, company_name, year in PDF_DOCUMENTS:
        pdf_path = os.path.join(folder, filename)

        if not os.path.exists(pdf_path):
            print(f"⚠️  Not found — skipping : {pdf_path}")
            skipped += 1
            continue

        print(f"\n📄 {company_name} | {year}")
        print(f"   {pdf_path}")

        try:
            sections = extract_mda_sections(pdf_path)
            chunks = chunk_sections(sections, company_name, year)
        except Exception as e:
            print(f"   ❌ Error: {e}")
            skipped += 1
            continue

        if not chunks:
            print(f"   ⚠️  No chunks extracted")
            skipped += 1
            continue

        texts = [c["content"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]
        total_chunks += len(chunks)
        pdf_processed += 1
        print(f"   ✅ {len(chunks)} chunks")

        if vectorstore is None:
            vectorstore = FAISS.from_texts(texts=texts, embedding=embeddings, metadatas=metadatas)
        else:
            vectorstore.add_texts(texts=texts, metadatas=metadatas)

    # ── Step 2: Ingest Excel Financial Data ──────────────────────────────────
    print(f"\n{'='*55}")
    print("📊 INGESTING EXCEL FINANCIAL DATA")
    print("=" * 55)

    for folder, filename, company_name in EXCEL_DOCUMENTS:
        excel_path = os.path.join(folder, filename)

        if not os.path.exists(excel_path):
            print(f"⚠️  Not found — skipping : {excel_path}")
            skipped += 1
            continue

        print(f"\n📊 {company_name} — {excel_path}")

        try:
            chunks = ingest_excel(excel_path, company_name)
        except Exception as e:
            print(f"   ❌ Error: {e}")
            skipped += 1
            continue

        if not chunks:
            print(f"   ⚠️  No chunks extracted")
            skipped += 1
            continue

        texts = [c["content"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]
        total_chunks += len(chunks)
        excel_processed += 1
        print(f"   ✅ {len(chunks)} chunks ({', '.join(set(m['section'] for m in metadatas))})")

        if vectorstore is None:
            vectorstore = FAISS.from_texts(texts=texts, embedding=embeddings, metadatas=metadatas)
        else:
            vectorstore.add_texts(texts=texts, metadatas=metadatas)

    # ── Save ─────────────────────────────────────────────────────────────────
    if vectorstore is None:
        print("\n❌ No documents processed. Check file paths.")
        return

    os.makedirs(VECTORSTORE_DIR, exist_ok=True)
    vectorstore.save_local(VECTORSTORE_DIR)

    print(f"\n{'='*55}")
    print(f"✅ Vectorstore saved to : {VECTORSTORE_DIR}")
    print(f"📊 Total chunks indexed : {total_chunks}")
    print(f"📄 PDFs processed       : {pdf_processed}")
    print(f"📊 Excel files processed: {excel_processed}")
    print(f"⚠️  Files skipped        : {skipped}")
    print(f"{'='*55}")


if __name__ == "__main__":
    build_vectorstore()