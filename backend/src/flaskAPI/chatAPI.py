import os
import sys
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Add parent directory to path to import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chat import answer_question  # noqa: E402
from logging_Setup import get_logger  # noqa: E402

logger = get_logger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    inputData: str = Field(..., description="User question or message")
    workspace: Optional[str] = Field(
        default=None, description="Workspace identifier to scope retrieval"
    )
    questionType: Optional[str] = Field(
        default=None, description="Type of question being asked"
    )


@router.post("/process")
async def chat(payload: ChatRequest):
    try:
        answer = answer_question(
            payload.inputData, payload.questionType, payload.workspace
        )
        return JSONResponse(content={"answer": answer}, status_code=200)
    except Exception as exc:  # pragma: no cover - underlying handler failure
        logger.error(f"Unexpected Error in chat endpoint: {str(exc)}")
        return JSONResponse(
            content={
                "status": "error",
                "message": str(exc),
                "error_type": "internal_error",
            },
            status_code=500,
        )


class VerifyIndexingRequest(BaseModel):
    question: str = Field(..., description="Test question to verify indexing")
    workspace_name: Optional[str] = Field(None, description="Workspace to check")


class CheckIndexesRequest(BaseModel):
    workspace_name: Optional[str] = Field(None, description="Workspace to check")


class DeleteVectorsRequest(BaseModel):
    workspace_name: Optional[str] = Field(None, description="Delete all vectors from this workspace")
    index_name: Optional[str] = Field(None, description="Index to delete from (text or image)")
    delete_all: bool = Field(False, description="Delete ALL vectors from the index (use with caution!)")


@router.post("/delete-vectors")
async def delete_vectors_from_pinecone(payload: DeleteVectorsRequest):
    """
    Delete vectors from Pinecone index.
    Can delete by workspace filter or delete all vectors.
    """
    try:
        from vector_store import VectorStore
        from pinecone import Pinecone
        import config as cfg
        
        if payload.delete_all:
            # Delete entire index (requires recreation)
            pc = Pinecone(api_key=cfg.PINECONE_API_KEY)
            index_to_delete = payload.index_name or cfg.PINECONE_TEXT_INDEX
            pc.delete_index(index_to_delete)
            return JSONResponse(
                content={
                    "status": "success",
                    "message": f"Deleted entire index: {index_to_delete}. You'll need to recreate it.",
                },
                status_code=200,
            )
        
        vs = VectorStore()
        collection_type = "text" if payload.index_name != "image" else "image"
        index = vs.text_index if collection_type == "text" else vs.image_index
        
        if payload.workspace_name:
            # Delete by workspace filter
            # First, get all doc IDs with this workspace
            results = index.query(
                vector=[0.0] * vs.dimension,  # Dummy vector for filter-only query
                top_k=10000,  # Get up to 10k vectors
                filter={"workspace_name": payload.workspace_name},
                include_metadata=False
            )
            
            doc_ids = [match.id for match in results.matches] if results.matches else []
            
            if not doc_ids:
                return JSONResponse(
                    content={
                        "status": "info",
                        "message": f"No vectors found for workspace '{payload.workspace_name}'",
                        "deleted_count": 0
                    },
                    status_code=200,
                )
            
            # Delete in batches (Pinecone allows up to 1000 IDs per delete)
            batch_size = 1000
            deleted_count = 0
            for i in range(0, len(doc_ids), batch_size):
                batch = doc_ids[i:i+batch_size]
                index.delete(ids=batch)
                deleted_count += len(batch)
            
            return JSONResponse(
                content={
                    "status": "success",
                    "message": f"Deleted {deleted_count} vectors from workspace '{payload.workspace_name}'",
                    "deleted_count": deleted_count,
                    "workspace": payload.workspace_name
                },
                status_code=200,
            )
        else:
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "Please provide workspace_name or set delete_all=true",
                },
                status_code=400,
            )
    except Exception as exc:
        logger.error(f"Error deleting vectors: {str(exc)}")
        return JSONResponse(
            content={
                "status": "error",
                "message": str(exc),
                "error_type": "delete_error",
            },
            status_code=500,
        )


@router.post("/check-indexes")
async def check_indexes(payload: CheckIndexesRequest):
    """
    Check which Pinecone indexes contain documents and their counts.
    """
    try:
        from pinecone import Pinecone
        import config as cfg
        
        pc = Pinecone(api_key=cfg.PINECONE_API_KEY)
        
        # Get all indexes with retry logic
        max_retries = 3
        all_indexes = []
        for attempt in range(max_retries):
            try:
                all_indexes = pc.list_indexes().names()
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Failed to list indexes (attempt {attempt + 1}/{max_retries}): {str(e)}")
                    import time
                    time.sleep(2)
                else:
                    raise
        
        index_stats = {}
        
        # Check each index
        for index_name in all_indexes:
            try:
                index = pc.Index(index_name)
                
                # Get stats
                stats = index.describe_index_stats()
                total_vectors = stats.total_vector_count if hasattr(stats, 'total_vector_count') else 0
                
                # Try to query with workspace filter if provided
                workspace_docs = []
                if payload.workspace_name:
                    try:
                        # Query with filter
                        results = index.query(
                            vector=[0.0] * (stats.dimension if hasattr(stats, 'dimension') else 768),  # Dummy vector
                            top_k=10,
                            filter={"workspace_name": payload.workspace_name},
                            include_metadata=True
                        )
                        workspace_docs = [m.id for m in results.matches] if results.matches else []
                    except Exception as e:
                        # If filter doesn't work, try fetching some vectors
                        pass
                
                index_stats[index_name] = {
                    "total_vectors": total_vectors,
                    "dimension": stats.dimension if hasattr(stats, 'dimension') else None,
                    "workspace_docs_found": len(workspace_docs) if payload.workspace_name else None,
                    "sample_doc_ids": workspace_docs[:5] if workspace_docs else []
                }
            except Exception as e:
                index_stats[index_name] = {
                    "error": str(e)
                }
        
        # Also check configured indexes
        configured_text = cfg.PINECONE_TEXT_INDEX
        configured_image = cfg.PINECONE_IMAGE_INDEX
        
        return JSONResponse(
            content={
                "status": "success",
                "workspace": payload.workspace_name,
                "configured_text_index": configured_text,
                "configured_image_index": configured_image,
                "all_indexes": all_indexes,
                "index_stats": index_stats,
                "recommendation": f"Update PINECONE_TEXT_INDEX to 'maindocuments' if that's where your data is"
            },
            status_code=200,
        )
    except Exception as exc:
        logger.error(f"Error checking indexes: {str(exc)}")
        return JSONResponse(
            content={
                "status": "error",
                "message": str(exc),
                "error_type": "check_error",
            },
            status_code=500,
        )


@router.post("/verify-indexing")
async def verify_indexing(payload: VerifyIndexingRequest):
    """
    Verification endpoint to check if documents are properly indexed and retrievable.
    Returns matched document IDs, scores, and sample content.
    """
    try:
        from sumarizer import Summarizer
        from vector_store import VectorStore
        
        summarizer = Summarizer()
        vs = VectorStore()
        
        # Generate query embedding
        query_embedding = summarizer.generate_embeddings(payload.question)
        
        # Query with workspace filter if provided
        if payload.workspace_name:
            doc_ids = vs.filtered_query(
                query_embedding=query_embedding,
                filter_condition={"workspace_name": payload.workspace_name},
                collection_type="text",
                n_results=10
            )
        else:
            doc_ids = vs.text_query(query_embedding, n_results=10)
        
        # Get detailed information about matched documents
        matched_docs = []
        for doc_id in doc_ids[:5]:  # Limit to top 5 for response
            doc_data = vs.get_document_by_id(doc_id, collection_type="text")
            if doc_data:
                matched_docs.append({
                    "doc_id": doc_id,
                    "content_preview": doc_data.get("content", "")[:200] + "..." if len(doc_data.get("content", "")) > 200 else doc_data.get("content", ""),
                    "metadata": doc_data.get("metadata", {}),
                })
        
        # Also check if we can query without embedding (just filter)
        if payload.workspace_name:
            all_workspace_docs = vs.filtered_query(
                query_embedding=None,
                filter_condition={"workspace_name": payload.workspace_name},
                collection_type="text",
                n_results=20
            )
        else:
            all_workspace_docs = []
        
        return JSONResponse(
            content={
                "status": "success",
                "query": payload.question,
                "workspace": payload.workspace_name,
                "matched_document_count": len(doc_ids),
                "matched_documents": matched_docs,
                "all_workspace_docs_count": len(all_workspace_docs),
                "all_workspace_doc_ids": all_workspace_docs[:10],  # First 10 IDs
            },
            status_code=200,
        )
    except Exception as exc:
        logger.error(f"Error in verify-indexing: {str(exc)}")
        return JSONResponse(
            content={
                "status": "error",
                "message": str(exc),
                "error_type": "verification_error",
            },
            status_code=500,
        )