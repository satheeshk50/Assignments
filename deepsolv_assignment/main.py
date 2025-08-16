from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic_models import StoreAnalysisRequest, BrandInsights
import asyncio
import logging
from contextlib import asynccontextmanager

from database import engine, SessionLocal, Base
from models import ShopifyStore
from services.shopify_scraper import ShopifyScraperService
from services.llm_processor import LLMProcessorService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")
    yield
    # Shutdown
    logger.info("Application shutting down")

app = FastAPI(
    title="Shopify Store Insights Fetcher",
    description="Extract comprehensive insights from Shopify stores",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



@app.post("/analyze-store", response_model=BrandInsights)
async def analyze_shopify_store(
    request: StoreAnalysisRequest,
    db = Depends(get_db)
):
    """
    Analyze a Shopify store and extract comprehensive insights.
    """
    try:
        store_url = str(request.website_url)
        logger.info(f"Starting analysis for store: {store_url}")
        
        # Initialize services
        scraper_service = ShopifyScraperService()
        llm_service = LLMProcessorService() if request.use_llm else None
        
        # Check if we have recent data in database
        existing_store = db.query(ShopifyStore).filter(ShopifyStore.store_url == store_url).first()
        
        if existing_store and existing_store.is_recent():
            logger.info(f"Returning cached data for {store_url}")
            return BrandInsights.parse_raw(existing_store.insights_data)
        
        # Scrape the store
        insights = await scraper_service.analyze_store(store_url, llm_service)
        
        # Save to database
        if existing_store:
            existing_store.update_insights(insights.dict())
        else:
            new_store = ShopifyStore(store_url=store_url, insights_data=insights.json())
            db.add(new_store)
        
        db.commit()
        
        logger.info(f"Analysis completed for {store_url}")
        return insights
        
    except Exception as e:
        logger.error(f"Error analyzing store {store_url}: {str(e)}")
        
        if "404" in str(e) or "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Store not found")
        elif "timeout" in str(e).lower():
            raise HTTPException(status_code=408, detail="Request timeout while fetching store data")
        else:
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/stores")
async def get_analyzed_stores(db = Depends(get_db)):
    """
    Get list of previously analyzed stores.
    """
    stores = db.query(ShopifyStore).order_by(ShopifyStore.updated_at.desc()).limit(50).all()
    return [
        {
            "store_url": store.store_url,
            "last_analyzed": store.updated_at,
            "total_products": store.get_total_products()
        }
        for store in stores
    ]

@app.get("/store/{store_id}")
async def get_store_insights(store_id: int, db = Depends(get_db)):
    """
    Get insights for a specific store by ID.
    """
    store = db.query(ShopifyStore).filter(ShopifyStore.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    return BrandInsights.parse_raw(store.insights_data)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "message": "Shopify Insights Fetcher is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
