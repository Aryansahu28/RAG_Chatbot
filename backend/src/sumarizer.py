import json
import uuid
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from sentence_transformers import SentenceTransformer
import os
from embedding_model import MultiModalEmbedder


load_dotenv()


class Summarizer:
    def __init__(self):
        self.embedder = MultiModalEmbedder()
        # Use OpenAI instead of Gemini
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if openai_api_key:
            self.llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0,
                max_retries=3,
                timeout=30,
                api_key=openai_api_key
            )
        else:
            self.llm = None
            print("Warning: OPENAI_API_KEY not configured. Summary generation will fail.")

    def generate_summary(self, text, chunk_size=500000):
        if not self.llm:
            raise ValueError("OpenAI API key not configured. Cannot generate summary.")
        
        chunks = [text[i:i+chunk_size]
                  for i in range(0, len(text), chunk_size)]
        summaries = []
        i=0
        for chunk in chunks:
            prompt = f"Summarize this content briefly:\n{chunk}"
            response = self.llm.invoke(prompt)
            print("this is round",i)
            i+=1
            
            # Extract text from LangChain response
            summary_text = response.content if hasattr(response, "content") else str(response)
            summaries.append(summary_text)
        return "\n".join(summaries)

    def generate_embeddings(self, text):
        """Use only local embeddings for all text types"""
        return self.embedder.get_text_embedding(text)


if __name__ == "__main__":
    summarizer = Summarizer()
    json_file = r"C:\Users\rajsu\Documents\multi_model_ragagent\media\output\cp_plus_manual.pdf\extracted_data.json"
    with open(json_file,"r") as f:
        data=json.load(f)
    metadata_lines = [
                    # Explicit source line
                    f"source: {data['metadata']['source']}",
                    f"title: {data['metadata']['title']}",
                    f"timestamp: {data['metadata']['timestamp']}",
                    f"document_type:{data['metadata']['document_type']}"

                ]

    full_text = " ".join(data["text"].values()) + \
        "\n\nMetadata:\n" + "\n".join(metadata_lines)
    summary = summarizer.generate_summary(full_text)
    print(summary) 