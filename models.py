from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.sql import func
from database import Base
from datetime import datetime, timedelta
import json

class ShopifyStore(Base):
    __tablename__ = "shopify_stores"
    
    id = Column(Integer, primary_key=True, index=True)
    store_url = Column(String(500), unique=True, index=True, nullable=False)
    store_name = Column(String(200))
    insights_data = Column(MEDIUMTEXT, nullable=False)  
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    is_active = Column(Boolean, default=True)
    
    def is_recent(self, hours=24):
        """Check if the data is recent (within specified hours)."""
        if not self.updated_at:
            return False
        return datetime.utcnow() - self.updated_at < timedelta(hours=hours)
    
    def update_insights(self, insights_dict):
        """Update insights data."""
        self.insights_data = json.dumps(insights_dict)
        self.updated_at = datetime.utcnow()
    
    def get_total_products(self):
        """Get total products from insights data."""
        try:
            data = json.loads(self.insights_data)
            return data.get('total_products', 0)
        except:
            return 0
        