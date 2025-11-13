import logging
import os
from typing import Any, Dict, Iterable, List, Optional, Sequence

from pinecone import Pinecone, ServerlessSpec

from embedding_model import MultiModalEmbedder
import config as cfg
from sumarizer import Summarizer

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self):
        self.embedder = MultiModalEmbedder()
        self.dimension = cfg.PINECONE_DIMENSION
        self.metric = cfg.PINECONE_METRIC

        api_key = cfg.PINECONE_API_KEY or os.environ.get("PINECONE_API_KEY")
        environment = cfg.PINECONE_ENVIRONMENT or os.environ.get("PINECONE_ENVIRONMENT")

        if not api_key:
            raise RuntimeError(
                "Pinecone configuration missing. Set PINECONE_API_KEY in your environment."
            )

        # Initialize Pinecone client (new API v3+)
        self.pc = Pinecone(api_key=api_key)

        self.text_index_name = cfg.PINECONE_TEXT_INDEX
        self.image_index_name = cfg.PINECONE_IMAGE_INDEX

        self._ensure_index(self.text_index_name)
        self._ensure_index(self.image_index_name)

        self.text_index = self.pc.Index(self.text_index_name)
        self.image_index = self.pc.Index(self.image_index_name)

    def _ensure_index(self, index_name: str):
        # Check if index exists using new API with retry logic
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                existing_indexes = self.pc.list_indexes().names()
                if index_name in existing_indexes:
                    return
                break  # Successfully got list, index doesn't exist
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Failed to list indexes (attempt {attempt + 1}/{max_retries}): {str(e)}. Retrying in {retry_delay}s..."
                    )
                    import time
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Failed to list indexes after {max_retries} attempts: {str(e)}")
                    # Assume index doesn't exist and try to create it
                    break

        logger.info(
            "Creating Pinecone index '%s' (dimension=%d, metric=%s)",
            index_name,
            self.dimension,
            self.metric,
        )

        # Use ServerlessSpec for serverless indexes (new API)
        # Get region from PINECONE_REGION, or try to parse from PINECONE_ENVIRONMENT
        region = cfg.PINECONE_REGION or "us-east-1"  # default to us-east-1
        
        if not region and cfg.PINECONE_ENVIRONMENT:
            # Try to parse region from old environment format (e.g., "us-east-1-aws" -> "us-east-1")
            # Common formats: "us-east-1-aws", "gcp-starter", etc.
            env_str = cfg.PINECONE_ENVIRONMENT.lower()
            # Check for common AWS regions
            aws_regions = ["us-east-1", "us-east-2", "us-west-1", "us-west-2", 
                          "eu-west-1", "eu-west-2", "eu-central-1", "ap-southeast-1"]
            for r in aws_regions:
                if r in env_str:
                    region = r
                    break
        
        if not region:
            region = "us-east-1"  # final fallback

        logger.info(f"Creating Pinecone index with region: {region}")

        # Create index with retry logic
        for attempt in range(max_retries):
            try:
                self.pc.create_index(
                    name=index_name,
                    dimension=self.dimension,
                    metric=self.metric,
                    spec=ServerlessSpec(
                        cloud="aws",
                        region=region
                    )
                )
                return
            except Exception as e:
                if "already exists" in str(e).lower() or "already in use" in str(e).lower():
                    logger.info(f"Index '{index_name}' already exists (or being created)")
                    return
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Failed to create index (attempt {attempt + 1}/{max_retries}): {str(e)}. Retrying in {retry_delay}s..."
                    )
                    import time
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Failed to create index after {max_retries} attempts: {str(e)}")
                    raise

    @staticmethod
    def _build_metadata(text: str, metadata: Dict[str, Any], doc_type: str) -> Dict[str, Any]:
        combined = dict(metadata or {})
        combined["document"] = text
        combined["type"] = doc_type
        return combined

    @staticmethod
    def _to_vector_payload(
        doc_id: str,
        embedding: Sequence[float],
        metadata: Dict[str, Any],
    ):
        return {
            "id": doc_id,
            "values": list(embedding),
            "metadata": metadata,
        }

    def add_text_embedding(self, doc_id, embedding, text, metadata):
        try:
            # Check dimension mismatch
            embedding_dim = len(embedding)
            if embedding_dim != self.dimension:
                error_msg = (
                    f"Dimension mismatch: Embedding has {embedding_dim} dimensions, "
                    f"but index '{self.text_index_name}' expects {self.dimension} dimensions. "
                    f"Please update PINECONE_DIMENSION in your .env file to {embedding_dim}, "
                    f"or use an index with dimension {embedding_dim}."
                )
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            payload = self._to_vector_payload(
                doc_id,
                embedding,
                self._build_metadata(text, metadata, "text"),
            )
            self.text_index.upsert(vectors=[payload])
        except Exception as e:  # pragma: no cover - external service
            logger.error(f"Error adding text embedding to Pinecone: {str(e)}")
            raise

    def add_image_embedding(self, doc_id, embedding, text, metadata):
        try:
            payload = self._to_vector_payload(
                doc_id,
                embedding,
                self._build_metadata(text, metadata, "image"),
            )
            self.image_index.upsert(vectors=[payload])
        except Exception as e:  # pragma: no cover
            logger.error(f"Error adding image embedding to Pinecone: {str(e)}")

    def add_embedding(self, doc_id, embedding, text, metadata):
        self.add_text_embedding(doc_id, embedding, text, metadata)

    @staticmethod
    def _process_matches(matches: Iterable[Dict[str, Any]]) -> List[str]:
        processed = [
            (match["id"], match.get("score", 0.0))
            for match in matches or []
        ]
        processed.sort(key=lambda x: x[1], reverse=True)
        return [doc_id for doc_id, _ in processed]

    def query(self, query_embedding, n_results=5):
        text_results = self.text_index.query(
            vector=query_embedding,
            top_k=n_results,
            include_values=False,
            include_metadata=True,
        )
        image_results = self.image_index.query(
            vector=query_embedding,
            top_k=n_results,
            include_values=False,
            include_metadata=True,
        )

        combined = []
        for match in text_results.matches or []:
            combined.append((match["id"], match.get("score", 0.0)))
        for match in image_results.matches or []:
            combined.append((match["id"], match.get("score", 0.0)))

        combined.sort(key=lambda x: x[1], reverse=True)
        return [doc_id for doc_id, _ in combined[:n_results]]

    def image_query(self, query_embedding, n_results=5):
        results = self.image_index.query(
            vector=query_embedding,
            top_k=n_results,
            include_values=False,
            include_metadata=True,
        )
        return self._process_matches(results.matches)

    def text_query(self, query_embedding, n_results=5):
        results = self.text_index.query(
            vector=query_embedding,
            top_k=n_results,
            include_values=False,
            include_metadata=True,
        )
        return self._process_matches(results.matches)

    def filtered_query(
        self,
        query_embedding: Optional[Sequence[float]] = None,
        filter_condition: Optional[Dict[str, Any]] = None,
        collection_type: str = "text",
        n_results: int = 5,
    ):
        index = self.text_index if collection_type == "text" else self.image_index

        if query_embedding is None and not filter_condition:
            return []

        try:
            query_kwargs: Dict[str, Any] = {
                "top_k": n_results,
                "include_values": False,
                "include_metadata": True,
            }
            if query_embedding is not None:
                query_kwargs["vector"] = query_embedding
            if filter_condition:
                query_kwargs["filter"] = filter_condition

            results = index.query(**query_kwargs)
            return self._process_matches(results.matches)
        except Exception as e:  # pragma: no cover
            logger.error(f"Error in filtered query: {str(e)}")
            return []

    def delete_from_text_collection(self, doc_id):
        ids = doc_id if isinstance(doc_id, list) else [doc_id]
        self.text_index.delete(ids=ids)

    def delete_from_image_collection(self, doc_id):
        ids = doc_id if isinstance(doc_id, list) else [doc_id]
        self.image_index.delete(ids=ids)

    def get_document_by_id(self, doc_id, collection_type="text"):
        index = self.text_index if collection_type == "text" else self.image_index
        try:
            result = index.fetch(ids=[doc_id])
            vector_data = result.vectors.get(doc_id)
            if not vector_data:
                return None

            metadata = vector_data.get("metadata", {})
            return {
                "id": doc_id,
                "content": metadata.get("document"),
                "metadata": metadata,
            }
        except Exception as e:  # pragma: no cover
            logger.error(f"Error retrieving document {doc_id}: {str(e)}")
            return None

    def get_all_documents_data(self, collection_type="text"):
        logger.warning(
            "get_all_documents_data is not supported with Pinecone; returning empty list."
        )
        return []

if __name__=="__main__":
    vector_store = VectorStore()
    summarizer = Summarizer()
    query="do you have my java backend certificate"
    # query_embeddings=summarizer.generate_embeddings(query)

    # filtered_docs=vector_store.filtered_query(query_embedding=query_embeddings,filter_condition={"workspace_name": "certificates"}, collection_type="text")
    # all_docs = [vector_store.get_document_by_id(doc_id) for doc_id in filtered_docs]


    # doc_ids_to_delete=["b1200ec3-9e9b-45e1-94da-cc77a1ff295e","50efaac3-c7b0-4224-8042-97ee8b2c8a64","5924c436-ee43-4b0a-b6f8-b5f2d264431c","5ad5ab97-9bbb-479c-8db8-836fe5dc83de"]
    vector_store.delete_from_text_collection("9971867e-3b92-429a-9c9f-4399f7841da2-0")
    
    #all_docs = vector_store.get_all_documents_data("text")

    # print("\nTotal documents found:", len(all_docs))

    # # Print the first few documents
    # for i, doc in enumerate(all_docs):  # Show first 3 docs
    #     print(f"\nDocument {i+1}:")
    #     print(f"  ID: {doc['id']}")
    #     print(f"  Content preview: {doc['content'][:100]}..." if doc['content'] else "  No content")
    #     print(f"  Metadata: {doc['metadata']}")
    
    #vector_store.delete_from_image_collection(["27c0dd1a-2a2d-496d-94ea-18202896c1a4","fa7b1826-fa89-4ca9-970b-3316e371ad4a"])


