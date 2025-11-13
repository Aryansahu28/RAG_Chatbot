//newsAPI.jsx - API functions for news
import api from './axiosInterceptor';
import { API_BASE_URL } from './apiConfig';

const API_URL = API_BASE_URL;

/**
 * Search for news articles
 * @param {string} query - Search query for news articles
 * @param {string} category - Optional news category filter
 * @param {string} language - Language code (default: 'en')
 * @param {number} pageSize - Number of articles to return (default: 10)
 * @returns {Promise} - Response from the API
 */
export const searchNews = async (query, category = null, language = 'en', pageSize = 10) => {
  try {
    const response = await api.post(`${API_URL}/news/search`, {
      query,
      category,
      language,
      page_size: pageSize
    });
    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    console.error('Error fetching news:', error);
    return {
      success: false,
      error: error.response ? error.response.data : error.message
    };
  }
};

/**
 * Get available news categories
 * @returns {Promise} - Response from the API
 */
export const getNewsCategories = async () => {
  try {
    const response = await api.get(`${API_URL}/news/categories`);
    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    console.error('Error fetching news categories:', error);
    return {
      success: false,
      error: error.response ? error.response.data : error.message
    };
  }
};

/**
 * Add a news article to a workspace (stores in vector database)
 * @param {Object} articleData - Data for the news article
 * @returns {Promise} - Response from the API
 */
export const addNewsToWorkspace = async (articleData) => {
  try {
    const response = await api.post(`${API_URL}/news/add-to-workspace`, articleData);
    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    console.error('Error adding news to workspace:', error);
    return {
      success: false,
      error: error.response ? error.response.data : error.message
    };
  }
};

