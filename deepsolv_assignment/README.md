# Shopify Store Insights Fetcher

This project is a FastAPI-based web service that extracts and analyzes comprehensive insights from Shopify stores. It scrapes product catalogs, brand context, policies, contact information, social handles, FAQs, and other important links, and optionally enhances the data using Google Gemini LLM.

## Features

- **Shopify Store Analysis:** Scrapes product data, policies, contact info, social handles, FAQs, and more.
- **LLM Enhancement:** Optionally uses Google Gemini LLM to enhance and structure scraped data.
- **Database Storage:** Stores analyzed insights in a MySQL database for caching and retrieval.
- **REST API:** Provides endpoints to analyze stores, retrieve analyzed stores, and fetch insights.
- **Async Scraping:** Uses asyncio for efficient parallel scraping.
- **Extensible Models:** Uses Pydantic and SQLAlchemy for data validation and persistence.

## Project Structure

```
.
├── main.py                # FastAPI app and API endpoints
├── models.py              # SQLAlchemy models for database
├── database.py            # Database setup and session management
├── pydantic_models.py     # Pydantic models for API and data validation
├── services/
│   ├── shopify_scraper.py # Shopify scraping logic
│   └── llm_processor.py   # LLM enhancement logic
├── requirements.txt       # Python dependencies
├── pyproject.toml         # Project metadata
├── .env                   # Environment variables (DB and API keys)
├── .gitignore
└── README.md
```

## API Endpoints

- `POST /analyze-store`  
  Analyze a Shopify store and extract insights.  
  **Request Body:**  
  ```json
  {
    "website_url": "https://examplestore.myshopify.com",
    "use_llm": true
  }
  ```
  **Response:**  
  Returns a structured BrandInsights object.

- `GET /stores`  
  List previously analyzed stores.

- `GET /store/{store_id}`  
  Get insights for a specific store by ID.

- `GET /health`  
  Health check endpoint.

## Setup & Installation

1. **Clone the repository**
   ```sh
   git clone <repo-url>
   cd deepsolv_assignment
   ```

2. **Install dependencies**
   ```sh
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   - Copy `.env` and set your `DATABASE_URL` and (optionally) `GOOGLE_API_KEY`.

4. **Run the application**
   ```sh
   uvicorn main:app --reload
   ```

## Environment Variables

- `DATABASE_URL` (required):  
  Example:  
  ```
  mysql+pymysql://user:password@localhost:3306/shopify_insights
  ```
- `GOOGLE_API_KEY` (optional):  
  For LLM enhancement using Gemini.

## Dependencies

See `requirements.txt`.

## License

MIT License (add your license here if different).

---

**Note:**  
- Ensure your MySQL server is running and accessible.
- For LLM features, set up your Google Gemini API key in `.env`.
- The service is designed for