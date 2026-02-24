from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS


VECTORSTORE_DIR = "vectorstore/mda_faiss"


# -------------------------------
# Query → Section Router
# -------------------------------
def route_section(query: str):
    q = query.lower()

    if any(x in q for x in ["risk", "uncertain", "threat", "exposure"]):
        return "Risks & Risk Management"

    if any(x in q for x in ["outlook", "future", "guidance", "next year"]):
        return "Outlook & Strategy"

    if any(x in q for x in ["strategy", "strategic", "priority", "focus"]):
        return "Outlook & Strategy"

    if any(x in q for x in ["segment", "division", "business unit"]):
        return "Segment Performance"

    return None  # fallback: no filter


# -------------------------------
# Query Enrichment
# -------------------------------
def enrich_query(query: str):
    q = query.lower()

    if "risk" in q:
        return query + " key risks regulatory credit market operational"

    if "outlook" in q:
        return query + " management expectations growth forecast"

    if "strategy" in q:
        return query + " strategic priorities initiatives investment"

    if "segment" in q:
        return query + " segment-wise performance growth margins"

    return query


# -------------------------------
# Retrieval Function
# -------------------------------
def retrieve(query, company="ICICI Bank", k=4):
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True}
    )

    vectorstore = FAISS.load_local(
        VECTORSTORE_DIR,
        embeddings,
        allow_dangerous_deserialization=True
    )

    section = route_section(query)
    enriched_query = enrich_query(query)

    filter_dict = {"company": company}
    if section:
        filter_dict["section"] = section

    docs = vectorstore.similarity_search(
        enriched_query,
        k=k,
        filter=filter_dict
    )

    return docs, section


# -------------------------------
# Pretty Printer
# -------------------------------
def print_results(query, docs, section):
    print(f"\n🔍 Query: {query}")
    if section:
        print(f"🎯 Routed Section: {section}")
    print("=" * 90)

    if not docs:
        print("❌ No relevant information found in documents.")
        return

    for i, doc in enumerate(docs, 1):
        meta = doc.metadata
        print(f"\n📄 Result {i}")
        print(f"Company : {meta.get('company')}")
        print(f"Year    : {meta.get('year')}")
        print(f"Section : {meta.get('section')}")
        print("-" * 90)
        print(doc.page_content[:900])
        print("-" * 90)


# -------------------------------
# Run Tests
# -------------------------------
if __name__ == "__main__":
    test_queries = [
        "What risks did ICICI Bank mention?",
        "Explain ICICI Bank's outlook for the next year",
        "How did ICICI Bank's segment performance change?",
        "What strategic priorities were highlighted by ICICI Bank?"
    ]

    for q in test_queries:
        docs, section = retrieve(q, company="ICICI Bank")
        print_results(q, docs, section)
