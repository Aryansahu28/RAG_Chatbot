"""
News API router for fetching live news articles.
Provides endpoints for news search and category listing.
"""
import os
import sys
from typing import Optional, List

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Add parent directory to path to import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcp_server.news_mcp_server import fetch_news_articles  # noqa: E402
from logging_Setup import get_logger  # noqa: E402

logger = get_logger(__name__)

router = APIRouter()

# Available news categories
NEWS_CATEGORIES = [
    "business",
    "entertainment",
    "general",
    "health",
    "science",
    "sports",
    "technology"
]


class NewsSearchRequest(BaseModel):
    query: str = Field(..., description="Search query for news articles")
    category: Optional[str] = Field(
        default=None, 
        description="News category filter (business, entertainment, general, health, science, sports, technology)"
    )
    language: str = Field(
        default="en", 
        description="Language code (default: 'en')"
    )
    page_size: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of articles to return (1-100, default: 10)"
    )


@router.post("/search")
async def search_news(payload: NewsSearchRequest):
    """
    Search for news articles based on query, category, and language.
    """
    try:
        # Validate category if provided
        if payload.category and payload.category not in NEWS_CATEGORIES:
            return JSONResponse(
                content={
                    "status": "error",
                    "message": f"Invalid category. Must be one of: {', '.join(NEWS_CATEGORIES)}",
                    "error_type": "validation_error",
                },
                status_code=400,
            )
        
        # Fetch news articles
        articles = fetch_news_articles(
            query=payload.query,
            category=payload.category,
            language=payload.language,
            page_size=payload.page_size
        )
        
        if not articles:
            return JSONResponse(
                content={
                    "status": "success",
                    "message": "No news articles found",
                    "articles": [],
                    "count": 0
                },
                status_code=200,
            )
        
        return JSONResponse(
            content={
                "status": "success",
                "articles": articles,
                "count": len(articles),
                "query": payload.query,
                "category": payload.category,
                "language": payload.language
            },
            status_code=200,
        )
        
    except Exception as exc:
        logger.error(f"Error in news search endpoint: {str(exc)}")
        return JSONResponse(
            content={
                "status": "error",
                "message": str(exc),
                "error_type": "internal_error",
            },
            status_code=500,
        )


@router.get("/categories")
async def get_categories():
    """
    Get list of available news categories.
    """
    try:
        return JSONResponse(
            content={
                "status": "success",
                "categories": NEWS_CATEGORIES,
                "description": "Available news categories for filtering"
            },
            status_code=200,
        )
    except Exception as exc:
        logger.error(f"Error in get categories endpoint: {str(exc)}")
        return JSONResponse(
            content={
                "status": "error",
                "message": str(exc),
                "error_type": "internal_error",
            },
            status_code=500,
        )


class AddNewsArticleRequest(BaseModel):
    title: str = Field(..., description="Article title")
    description: str = Field(default="", description="Article description")
    content: str = Field(default="", description="Article content")
    url: str = Field(..., description="Article URL")
    source: str = Field(..., description="News source")
    publishedAt: str = Field(..., description="Publication date")
    workspace_name: str = Field(..., description="Workspace to add article to")


@router.post("/add-to-workspace")
async def add_news_to_workspace(payload: AddNewsArticleRequest):
    """
    Add a news article to a workspace (stores in vector database).
    """
    try:
        from vector_store import VectorStore
        from sumarizer import Summarizer
        import uuid
        from datetime import datetime
        
        # Generate unique doc_id
        doc_id = str(uuid.uuid4())
        
        # Combine article content
        article_text = f"{payload.title}\n\n{payload.description}\n\n{payload.content}"
        if not article_text.strip():
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "Article content cannot be empty",
                    "error_type": "validation_error",
                },
                status_code=400,
            )
        
        # Generate embedding
        summarizer = Summarizer()
        embedding = summarizer.generate_embeddings(article_text)
        
        # Create metadata
        metadata = {
            "title": payload.title,
            "source": payload.url,
            "document_type": "news",
            "workspace_name": payload.workspace_name,
            "news_source": payload.source,
            "publishedAt": payload.publishedAt,
            "url": payload.url,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Store in vector database
        vs = VectorStore()
        vs.add_text_embedding(
            doc_id=doc_id,
            embedding=embedding,
            text=article_text,
            metadata=metadata
        )
        
        logger.info(f"News article added to workspace '{payload.workspace_name}': {doc_id}")
        
        return JSONResponse(
            content={
                "status": "success",
                "message": "News article added to workspace",
                "doc_id": doc_id
            },
            status_code=200,
        )
        
    except Exception as exc:
        logger.error(f"Error adding news article to workspace: {str(exc)}")
        return JSONResponse(
            content={
                "status": "error",
                "message": str(exc),
                "error_type": "internal_error",
            },
            status_code=500,
        )

