import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
import json
from dataclasses import dataclass
from typing import List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
KB_PATH = os.getenv("KB_PATH", "data/knowledge_base")

@dataclass
class RetrievedDoc:
    id: str
    title: str
    category: str
    content: str
    score: float
    relevant_snippet: str

class RAGEngine:
    def __init__(self, kb_path: str = KB_PATH):
        self.kb_path = kb_path
        self.docs = []
        self._load_docs()

    def _load_docs(self):
        """Loads all JSON files from the knowledge base directory."""
        if not os.path.exists(self.kb_path):
            return
        for filename in os.listdir(self.kb_path):
            if filename.endswith(".json"):
                filepath = os.path.join(self.kb_path, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        doc_data = json.load(f)
                        # Ensure standard keys exist
                        if all(k in doc_data for k in ("id", "title", "category", "content")):
                            self.docs.append(doc_data)
                except Exception as e:
                    print(f"Error loading {filename}: {e}", file=sys.stderr)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Normalizes and tokenizes text into lowercase alphanumeric words."""
        cleaned = re.sub(r"[^\w\s]", " ", text.lower())
        return [word for word in cleaned.split() if word]

    def retrieve(self, query: str, top_k: int = 3) -> List[RetrievedDoc]:
        """Performs a simple TF-IDF style keyword search and returns top_k docs."""
        query_words = self._tokenize(query)
        if not query_words:
            return []

        scored_docs = []
        for doc in self.docs:
            score = 0.0
            title_tokens = self._tokenize(doc.get("title", ""))
            content_tokens = self._tokenize(doc.get("content", ""))

            # Calculate match score (boost title matches by 2x)
            for word in query_words:
                title_count = title_tokens.count(word)
                content_count = content_tokens.count(word)
                score += (title_count * 2.0) + content_count

            if score > 0:
                # Find matching snippet in content
                content = doc.get("content", "")
                content_lower = content.lower()
                first_match_idx = -1
                for word in query_words:
                    idx = content_lower.find(word)
                    if idx != -1:
                        if first_match_idx == -1 or idx < first_match_idx:
                            first_match_idx = idx

                start_idx = max(0, first_match_idx - 30) if first_match_idx != -1 else 0
                snippet = content[start_idx:start_idx + 300]
                if len(content) > start_idx + 300:
                    snippet += "..."

                retrieved_doc = RetrievedDoc(
                    id=doc["id"],
                    title=doc["title"],
                    category=doc["category"],
                    content=doc["content"],
                    score=score,
                    relevant_snippet=snippet
                )
                scored_docs.append(retrieved_doc)

        # Sort descending by score
        scored_docs = sorted(scored_docs, key=lambda x: x.score, reverse=True)
        return scored_docs[:top_k]

    def retrieve_for_intent(self, intent: str, context_signals: list = None) -> List[RetrievedDoc]:
        """Maps default conversation intents to optimized search queries."""
        intent_queries = {
            "PENALTY_INQUIRY": "late payment penalty charges calculation",
            "PENALTY_WAIVER": "penalty waiver eligibility bank error",
            "PAYMENT_FAILURE": "payment failure bank gateway process",
            "SETTLEMENT_REQUEST": "settlement policy one time payment CIBIL",
            "FORECLOSURE": "foreclosure charges process NOC",
            "EMI_INQUIRY": "EMI calculation amortization schedule",
            "INTEREST_INQUIRY": "interest principal payment breakdown",
            "PAYMENT_COMMITMENT": "overdue recovery promise to pay process",
            "GENERAL_INQUIRY": "loan FAQ borrower rights"
        }
        query = intent_queries.get(intent, "loan FAQ borrower rights")
        return self.retrieve(query)

    @staticmethod
    def format_for_prompt(docs: List[RetrievedDoc]) -> str:
        """Formats the retrieved documents as a unified string block for LLM prompt context."""
        prompt = []
        prompt.append("=== RETRIEVED POLICIES ===")
        for doc in docs:
            prompt.append(f"Document ID: {doc.id}")
            prompt.append(f"Title: {doc.title}")
            prompt.append(f"Category: {doc.category}")
            prompt.append(f"Content:\n{doc.content}")
            prompt.append("-" * 40)
        return "\n".join(prompt)

if __name__ == "__main__":
    engine = RAGEngine()
    
    test_queries = [
        "penalty waiver bank error",
        "foreclosure charges process",
        "settlement CIBIL impact",
        "payment failed NACH mandate"
    ]
    
    print(f"Loaded {len(engine.docs)} documents from '{KB_PATH}'.\n")
    print("=" * 60)
    
    for q in test_queries:
        print(f"Query: \"{q}\"")
        results = engine.retrieve(q, top_k=2)
        for idx, doc in enumerate(results):
            print(f"  Result #{idx + 1}: {doc.title} (Score: {doc.score})")
            print(f"    Snippet: \"{doc.relevant_snippet}\"")
        print("-" * 60)
