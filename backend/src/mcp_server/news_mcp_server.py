"""
MCP Server for fetching live news articles using NewsAPI.
Provides both MCP server interface and helper functions for direct use.
"""
import os
import sys
import requests
from typing import List, Dict, Optional
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as cfg
from logging_Setup import get_logger

logger = get_logger(__name__)


class NewsMCPServer:
    """MCP Server for news article fetching."""
    
    def __init__(self):
        self.api_key = cfg.NEWS_API_KEY
        self.base_url = cfg.NEWS_API_BASE_URL
        if not self.api_key:
            logger.warning("NEWS_API_KEY not configured. News features will be limited.")
    
    def fetch_news_articles(
        self, 
        query: str, 
        category: Optional[str] = None, 
        language: str = 'en',
        page_size: int = 10
    ) -> List[Dict]:
        """
        Fetch news articles from NewsAPI.
        
        Args:
            query: Search query string
            category: News category (business, entertainment, general, health, science, sports, technology)
            language: Language code (default: 'en')
            page_size: Number of articles to return (default: 10, max: 100)
        
        Returns:
            List of news articles with title, description, url, publishedAt, source
        """
        if not self.api_key:
            logger.error("NEWS_API_KEY not configured")
            return []
        
        try:
            # Build API URL
            if category:
                # Use top headlines endpoint for categories
                url = f"{self.base_url}/top-headlines"
                params = {
                    "apiKey": self.api_key,
                    "category": category,
                    "language": language,
                    "pageSize": min(page_size, 100)
                }
            else:
                # Use everything endpoint for search queries
                url = f"{self.base_url}/everything"
                params = {
                    "apiKey": self.api_key,
                    "q": query,
                    "language": language,
                    "pageSize": min(page_size, 100),
                    "sortBy": "publishedAt"  # Most recent first
                }
            
            logger.info(f"Fetching news articles: query={query}, category={category}")
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("status") != "ok":
                logger.error(f"NewsAPI error: {data.get('message', 'Unknown error')}")
                return []
            
            articles = data.get("articles", [])
            
            # Format articles
            formatted_articles = []
            for article in articles:
                formatted_article = {
                    "title": article.get("title", ""),
                    "description": article.get("description", ""),
                    "url": article.get("url", ""),
                    "publishedAt": article.get("publishedAt", ""),
                    "source": article.get("source", {}).get("name", "Unknown"),
                    "author": article.get("author"),
                    "content": article.get("content", "")
                }
                formatted_articles.append(formatted_article)
            
            logger.info(f"Fetched {len(formatted_articles)} news articles")
            return formatted_articles
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching news articles: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in fetch_news_articles: {str(e)}")
            return []
    
    def search_news(
        self,
        query: str,
        category: Optional[str] = None,
        language: str = 'en'
    ) -> List[Dict]:
        """
        MCP tool: Search for news articles.
        
        Args:
            query: Search query string
            category: Optional news category filter
            language: Language code (default: 'en')
        
        Returns:
            List of news articles
        """
        return self.fetch_news_articles(query, category, language)


# Global instance for easy import
_news_server_instance = None

def get_news_server() -> NewsMCPServer:
    """Get or create global NewsMCPServer instance."""
    global _news_server_instance
    if _news_server_instance is None:
        _news_server_instance = NewsMCPServer()
    return _news_server_instance


def fetch_news_articles(
    query: str,
    category: Optional[str] = None,
    language: str = 'en',
    page_size: int = 10
) -> List[Dict]:
    """
    Helper function to fetch news articles.
    Can be called from both chat.py and newsAPI.py.
    
    Args:
        query: Search query string
        category: Optional news category
        language: Language code
        page_size: Number of articles to return
    
    Returns:
        List of formatted news articles
    """
    server = get_news_server()
    return server.fetch_news_articles(query, category, language, page_size)

