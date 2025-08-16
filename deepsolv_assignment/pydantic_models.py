from typing import List, Dict, Any, Optional
from pydantic import BaseModel, HttpUrl, validator



class ProductInfo(BaseModel):
    id: int
    title: str
    handle: str
    vendor: str
    product_type: str
    price: Optional[str] = None
    compare_at_price: Optional[str] = None
    available: bool
    tags: List[str] = []
    images: List[str] = []
    description: Optional[str] = None
    variants: List[Dict[str, Any]] = []

class SocialHandle(BaseModel):
    platform: str
    url: str
    handle: Optional[str] = None

class ContactInfo(BaseModel):
    emails: List[str] = []
    phones: List[str] = []
    address: Optional[str] = None

class FAQ(BaseModel):
    question: str
    answer: str

class ImportantLink(BaseModel):
    name: str
    url: str
    description: Optional[str] = None

class BrandInsights(BaseModel):
    store_url: str
    store_name: Optional[str] = None
    product_catalog: List[ProductInfo] = []
    hero_products: List[ProductInfo] = []
    privacy_policy: Optional[str] = None
    return_refund_policy: Optional[str] = None
    faqs: List[FAQ] = []
    social_handles: List[SocialHandle] = []
    contact_info: ContactInfo = ContactInfo()
    brand_context: Optional[str] = None
    important_links: List[ImportantLink] = []
    total_products: int = 0
    currencies_accepted: List[str] = []
    payment_methods: List[str] = []
    shipping_info: Optional[str] = None

class StoreAnalysisRequest(BaseModel):
    website_url: HttpUrl
    use_llm: bool = False
    
    @validator('website_url')
    def validate_shopify_url(cls, v):
        url_str = str(v)
        # Check if it's likely a Shopify store
        if not any(indicator in url_str.lower() for indicator in ['shopify', '.myshopify.com']):
            # We'll still process it as it might be a custom domain
            pass
        return v