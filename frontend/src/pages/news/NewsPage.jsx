import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { searchNews, getNewsCategories, addNewsToWorkspace } from "../../api_calls/newsAPI";
import styles from "./NewsPage.module.css";

function NewsPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [language, setLanguage] = useState("en");
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [categories, setCategories] = useState([]);
  const [addedArticles, setAddedArticles] = useState(new Set());
  const [activeWorkspace, setActiveWorkspace] = useState(null);
  const [isAdding, setIsAdding] = useState({});
  const [successMessage, setSuccessMessage] = useState("");

  // Load categories on mount
  useEffect(() => {
    const loadCategories = async () => {
      const response = await getNewsCategories();
      if (response.success) {
        setCategories(response.data.categories || []);
      }
    };
    loadCategories();
  }, []);

  // Load active workspace on mount
  useEffect(() => {
    const saved = localStorage.getItem("activeWorkspace");
    if (saved) {
      setActiveWorkspace(JSON.parse(saved));
    }
  }, []);

  const handleSearch = async (e) => {
    e.preventDefault();
    
    if (!query.trim()) {
      setError("Please enter a search query");
      return;
    }

    setLoading(true);
    setError("");
    setArticles([]);

    try {
      const response = await searchNews(
        query,
        category || null,
        language,
        20
      );

      if (response.success) {
        setArticles(response.data.articles || []);
        if (response.data.articles.length === 0) {
          setError("No news articles found. Try a different search query.");
        }
      } else {
        setError(response.error?.message || "Failed to fetch news articles");
      }
    } catch (err) {
      setError("An error occurred while fetching news. Please try again.");
      console.error("News search error:", err);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return "Date not available";
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateString;
    }
  };

  const handleAddToWorkspace = async (article) => {
    if (!activeWorkspace) {
      setError("Please select a workspace first. Go to dashboard and select a workspace.");
      setSuccessMessage("");
      return;
    }

    const articleKey = article.url || article.title;
    setIsAdding({ ...isAdding, [articleKey]: true });
    setError("");
    setSuccessMessage("");

    try {
      const response = await addNewsToWorkspace({
        title: article.title || "",
        description: article.description || "",
        content: article.content || article.description || "",
        url: article.url || "",
        source: article.source || "Unknown",
        publishedAt: article.publishedAt || new Date().toISOString(),
        workspace_name: activeWorkspace.name
      });

      if (response.success) {
        setAddedArticles(new Set([...addedArticles, articleKey]));
        setSuccessMessage(`"${article.title}" added to ${activeWorkspace.name} workspace!`);
        setError("");
        // Clear success message after 3 seconds
        setTimeout(() => setSuccessMessage(""), 3000);
      } else {
        setError(response.error?.message || "Failed to add article to workspace");
        setSuccessMessage("");
      }
    } catch (err) {
      console.error("Error adding article:", err);
      setError("Failed to add article to workspace");
      setSuccessMessage("");
    } finally {
      setIsAdding({ ...isAdding, [articleKey]: false });
    }
  };

  return (
    <div className={styles.newsPage}>
      <div className={styles.container}>
        <div className={styles.header}>
          <div>
            <h1 className={styles.title}>Live News Search</h1>
            <p className={styles.subtitle}>
              Search for the latest news articles from around the world
            </p>
            {activeWorkspace && (
              <p className={styles.workspaceInfo}>
                Active Workspace: <span className={styles.workspaceName}>{activeWorkspace.name}</span>
              </p>
            )}
            {!activeWorkspace && (
              <p className={styles.workspaceWarning}>
                ⚠️ No workspace selected. Select a workspace from dashboard to add articles.
              </p>
            )}
          </div>
          <button
            className={styles.backButton}
            onClick={() => navigate('/dashboard')}
            aria-label="Back to dashboard"
          >
            ← Back to Dashboard
          </button>
        </div>

        <form onSubmit={handleSearch} className={styles.searchForm}>
          <div className={styles.searchRow}>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search for news articles..."
              className={styles.searchInput}
              disabled={loading}
            />
            <button
              type="submit"
              className={styles.searchButton}
              disabled={loading || !query.trim()}
            >
              {loading ? "Searching..." : "Search News"}
            </button>
          </div>

          <div className={styles.filters}>
            <div className={styles.filterGroup}>
              <label htmlFor="category">Category (Optional):</label>
              <select
                id="category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className={styles.select}
                disabled={loading}
                style={{
                  backgroundColor: '#1a1a2e',
                  color: '#fff',
                }}
              >
                <option value="" style={{ backgroundColor: '#1a1a2e', color: '#fff' }}>All Categories</option>
                {categories.map((cat) => (
                  <option 
                    key={cat} 
                    value={cat}
                    style={{ backgroundColor: '#1a1a2e', color: '#fff' }}
                  >
                    {cat.charAt(0).toUpperCase() + cat.slice(1)}
                  </option>
                ))}
              </select>
            </div>

            <div className={styles.filterGroup}>
              <label htmlFor="language">Language:</label>
              <select
                id="language"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className={styles.select}
                disabled={loading}
                style={{
                  backgroundColor: '#1a1a2e',
                  color: '#fff',
                }}
              >
                <option value="en" style={{ backgroundColor: '#1a1a2e', color: '#fff' }}>English</option>
                <option value="es" style={{ backgroundColor: '#1a1a2e', color: '#fff' }}>Spanish</option>
                <option value="fr" style={{ backgroundColor: '#1a1a2e', color: '#fff' }}>French</option>
                <option value="de" style={{ backgroundColor: '#1a1a2e', color: '#fff' }}>German</option>
                <option value="it" style={{ backgroundColor: '#1a1a2e', color: '#fff' }}>Italian</option>
                <option value="pt" style={{ backgroundColor: '#1a1a2e', color: '#fff' }}>Portuguese</option>
              </select>
            </div>
          </div>
        </form>

        {error && <div className={styles.error}>{error}</div>}
        {successMessage && <div className={styles.success}>{successMessage}</div>}

        {loading && (
          <div className={styles.loading}>
            <div className={styles.spinner}></div>
            <p>Fetching news articles...</p>
          </div>
        )}

        {!loading && articles.length > 0 && (
          <div className={styles.results}>
            <h2 className={styles.resultsTitle}>
              Found {articles.length} article{articles.length !== 1 ? "s" : ""}
            </h2>
            <div className={styles.articlesList}>
              {articles.map((article, index) => {
                const articleKey = article.url || article.title;
                const isAdded = addedArticles.has(articleKey);
                const isAddingArticle = isAdding[articleKey];
                
                return (
                  <div key={index} className={styles.articleCard}>
                    <h3 className={styles.articleTitle}>{article.title || "No title"}</h3>
                    <div className={styles.articleMeta}>
                      <span className={styles.source}>
                        {article.source || "Unknown source"}
                      </span>
                      <span className={styles.date}>
                        {formatDate(article.publishedAt)}
                      </span>
                    </div>
                    {article.description && (
                      <p className={styles.articleDescription}>
                        {article.description}
                      </p>
                    )}
                    <div className={styles.articleActions}>
                      {article.url && (
                        <a
                          href={article.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className={styles.readMore}
                        >
                          Read full article →
                        </a>
                      )}
                      <button
                        className={styles.addButton}
                        onClick={() => handleAddToWorkspace(article)}
                        disabled={isAdded || isAddingArticle || !activeWorkspace}
                        data-added={isAdded}
                      >
                        {isAdded ? "✓ Added to Workspace" : isAddingArticle ? "Adding..." : "Add to Workspace"}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {!loading && articles.length === 0 && !error && (
          <div className={styles.emptyState}>
            <p>Enter a search query above to find news articles</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default NewsPage;

