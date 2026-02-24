"""
rag_answer.py
RAG system — retrieves relevant chunks from FAISS, then uses
Groq's free API (llama-3.3-70b) to generate a clean, structured answer.

Supports: ICICI Bank, TCS, Infosys, Reliance Industries, Adani Power
          across FY2023-24 and FY2024-25

Requirements:
    pip install groq python-dotenv
    Create a .env file with: GROQ_API_KEY=your_key_here
"""

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from groq import Groq
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# ======================
# LOAD VECTORSTORE
# ======================
def load_vectorstore(path="vectorstore/mda_faiss"):
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    vectorstore = FAISS.load_local(
        path,
        embeddings,
        allow_dangerous_deserialization=True
    )
    return vectorstore


# ======================
# INTENT DETECTION
# ======================
def detect_intent(query):
    q = query.lower()
    if any(k in q for k in ["risk", "threat", "challenge", "concern", "exposure", "headwind"]):
        return "risk"
    if any(k in q for k in ["outlook", "future", "strategy", "plan", "guidance", "way forward", "priority"]):
        return "outlook"
    if any(k in q for k in ["performance", "revenue", "profit", "growth", "earnings", "margin", "ebitda", "pat"]):
        return "performance"
    if any(k in q for k in ["employee", "talent", "hiring", "attrition", "workforce", "headcount"]):
        return "people"
    return "general"


INTENT_KEYWORDS = {
    "risk": [
        "risk", "threat", "challenge", "concern", "exposure",
        "uncertainty", "adverse", "impact", "pressure", "headwind"
    ],
    "outlook": [
        "future", "strategy", "plan", "outlook", "expect",
        "guidance", "going forward", "initiatives", "focus", "target", "priority"
    ],
    "performance": [
        "revenue", "profit", "growth", "increased", "decreased",
        "performance", "earnings", "margin", "grew", "crore", "billion", "ebitda", "pat"
    ],
    "people": [
        "employee", "talent", "hiring", "attrition", "workforce",
        "headcount", "training", "culture"
    ],
    "general": [
        "information", "detail", "overview", "summary"
    ]
}


# ======================
# COMPANY EXTRACTOR
# ======================
COMPANY_MAP = {
    "icici": "ICICI Bank",
    "hdfc": "HDFC",
    "tcs": "TCS",
    "infosys": "Infosys",
    "reliance": "Reliance Industries",
    "adani": "Adani Power",
}

def extract_company(query):
    q = query.lower()
    for key, name in COMPANY_MAP.items():
        if key in q:
            return key, name
    return None, None


# ======================
# YEAR EXTRACTOR
# ======================
def extract_year(query):
    q = query.lower()
    if "2024" in q or "fy24" in q or "2023-24" in q:
        return "FY2023-24"
    if "2025" in q or "fy25" in q or "2024-25" in q:
        return "FY2024-25"
    return None  # No year filter — search both years


# ======================
# RETRIEVE CONTEXT
# ======================
def retrieve_context(vectorstore, query, company_filter=None,
                     year_filter=None, top_k=10, score_threshold=0.85):
    """
    Retrieve relevant chunks from FAISS.

    Args:
        company_filter : e.g. "ICICI Bank" — filters by company metadata
        year_filter    : e.g. "FY2024-25"  — filters by year metadata
                         Pass None to search across all years
    """
    intent = detect_intent(query)

    # Auto-detect company/year from query if not explicitly passed
    if company_filter is None:
        _, company_filter = extract_company(query)
    if year_filter is None:
        year_filter = extract_year(query)

    company_key = None
    if company_filter:
        company_key = company_filter.lower().split()[0]  # e.g. "icici", "tcs"

    expansion = ' '.join(INTENT_KEYWORDS[intent][:4])
    enhanced_query = f"{query} {expansion}"

    # MMR for diverse results
    try:
        docs = vectorstore.max_marginal_relevance_search(
            enhanced_query,
            k=top_k,
            fetch_k=top_k * 3
        )
        docs_with_scores = [(doc, None) for doc in docs]
    except Exception:
        docs_with_scores = vectorstore.similarity_search_with_score(
            enhanced_query, k=top_k
        )

    chunks = []
    sources = []

    for item in docs_with_scores:
        doc, score = item

        if score is not None and score > score_threshold:
            continue

        meta = doc.metadata
        doc_company = meta.get("company", "").lower()
        doc_year = meta.get("year", "")

        # Company filter
        if company_key and company_key not in doc_company:
            continue

        # Year filter (only apply if a year was detected/specified)
        if year_filter and doc_year != year_filter:
            continue

        text = doc.page_content.strip()
        if len(text) < 100:
            continue

        chunks.append(text)
        sources.append({
            "company": meta.get("company", "Unknown"),
            "year": doc_year,
            "section": meta.get("section", "Unknown"),
            "chunk_index": meta.get("chunk_index", "-")
        })

    return chunks, sources, intent, company_filter, year_filter


# ======================
# LLM GENERATION VIA GROQ
# ======================
def generate_answer(query, chunks, intent, company_name, year_filter):
    if not chunks:
        return "No relevant information found in the documents for this query."

    context = "\n\n---\n\n".join(chunks)

    intent_instructions = {
        "risk": "Identify and clearly categorise the specific risks mentioned. Group similar risks together (e.g. credit risk, market risk, operational risk, regulatory risk).",
        "outlook": "Focus on future plans, strategic priorities, and management's expectations. Present as forward-looking structured points.",
        "performance": "Focus on specific financial figures, growth rates, and year-on-year comparisons. Be precise with numbers and percentages.",
        "people": "Focus on workforce metrics, hiring, attrition, and talent strategy.",
        "general": "Provide a clear, well-structured overview of the relevant information."
    }

    instruction = intent_instructions.get(intent, intent_instructions["general"])
    company = company_name or "the company"
    year_context = f" for {year_filter}" if year_filter else " across available years"

    system_prompt = """You are a senior financial analyst assistant specialising in analysing 
Management Discussion & Analysis (MD&A) sections of annual reports.

Answer questions clearly and concisely based ONLY on the provided document excerpts.
Do not use outside knowledge. If something is not in the excerpts, say so explicitly.

Rules:
- Write in clear, professional financial language
- Use bullet points for lists of items
- Bold (**text**) important figures, percentages, and key terms
- Group related points under short sub-headings where it helps clarity
- Always cite specific numbers when they appear in the context
- Do not repeat the same point
- If comparing across years, clearly label each year's data"""

    user_prompt = f"""Based on the following excerpts from {company}'s MD&A report{year_context}, answer this question:

**Question:** {query}

**Instruction:** {instruction}

**Document Excerpts:**
{context}

Provide a well-structured, clear answer. Use sub-headings if there are multiple distinct categories to cover."""

    try:
        api_key = os.getenv("GROQ_API_KEY")
        
        if not api_key:
            return "❌ GROQ_API_KEY not found. Create a .env file with: GROQ_API_KEY=your_key_here\n\nGet a free key at https://console.groq.com"
        
        # Initialize Groq client - it automatically uses GROQ_API_KEY from environment
        client = Groq()

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=1024
        )

        return response.choices[0].message.content

    except Exception as e:
        err = str(e)
        if "api_key" in err.lower() or "authentication" in err.lower():
            return "❌ Invalid Groq API key. Check your .env file.\n\nGet a free key at https://console.groq.com"
        if "rate_limit" in err.lower():
            return "❌ Groq rate limit hit. Wait a moment and try again."
        return f"❌ Groq API error: {err}"


# ======================
# MAIN ENTRY POINT
# ======================
def retrieve_and_answer(vectorstore, query, company_filter=None,
                        year_filter=None, top_k=10, score_threshold=0.85):
    """
    Full RAG pipeline.

    Args:
        company_filter : Override company (e.g. "TCS"). Auto-detected from query if None.
        year_filter    : Override year (e.g. "FY2024-25"). Auto-detected from query if None.

    Returns:
        dict: answer, sources, intent, company, year
    """
    chunks, sources, intent, company_name, year = retrieve_context(
        vectorstore, query, company_filter, year_filter, top_k, score_threshold
    )

    if not chunks:
        return {
            "answer": "No relevant information found. Try rephrasing, selecting a specific company/year, or ensure the vectorstore is built.",
            "sources": [],
            "intent": intent,
            "company": company_name or "All Companies",
            "year": year or "All Years"
        }

    answer = generate_answer(query, chunks, intent, company_name, year)

    return {
        "answer": answer,
        "sources": sources,
        "intent": intent,
        "company": company_name or "All Companies",
        "year": year or "All Years"
    }


# ======================
# CLI TEST
# ======================
if __name__ == "__main__":
    import sys

    if not os.getenv("GROQ_API_KEY"):
        print("⚠️  GROQ_API_KEY not set.")
        print("   Create a .env file in your project root with:")
        print("   GROQ_API_KEY=your_actual_key_here")
        print("   Get a free key at https://console.groq.com")
        exit(1)

    print("🚀 Loading vectorstore...")
    vs = load_vectorstore()
    print("✅ Ready!\n")

    queries = sys.argv[1:] or [
        "What risks did ICICI Bank mention?",
        "What is TCS's strategy for FY2025?",
        "How did Infosys perform in terms of revenue growth?",
        "Compare the outlook of Reliance and Adani Power",
    ]

    for q in queries:
        print("\n" + "=" * 70)
        print(f"🔍 Q: {q}")
        result = retrieve_and_answer(vs, q)
        print(f"📊 Intent  : {result['intent'].upper()}")
        print(f"🏢 Company : {result['company']}  |  📅 Year: {result['year']}")
        print(f"\n🧠 Answer:\n{result['answer']}")
        print(f"\n📌 Sources ({len(result['sources'])}):")
        for s in result["sources"]:
            print(f"   • {s['company']} ({s['year']}) — {s['section']}")
        print("=" * 70)