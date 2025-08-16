from langchain_google_genai import ChatGoogleGenerativeAI
import json
import os
from typing import Optional
from pydantic_models import BrandInsights
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class LLMProcessorService:
    def __init__(self):
        self.client = ChatGoogleGenerativeAI(
            model="gemini-2.5-pro",
            temperature=0.2,
            max_output_tokens=400,
            top_p=0.95,
            top_k=40
        )
        self.enabled = bool(os.getenv('GOOGLE_API_KEY'))  # changed from OPENAI_API_KEY
    
    async def enhance_insights(self, insights: BrandInsights) -> BrandInsights:
        """Use LLM to enhance and structure the scraped data."""
        if not self.enabled:
            logger.warning("Google Gemini API key not provided, skipping LLM enhancement")
            return insights
        
        try:
            # Enhance brand context
            logger.info("Enhancing brand context using LLM")
            if insights.brand_context:
                insights.brand_context = await self._enhance_brand_context(insights.brand_context)
            
            # Enhance and structure FAQs
            if insights.faqs:
                insights.faqs = await self._enhance_faqs(insights.faqs)
            
            # Extract additional insights from product catalog
            if insights.product_catalog:
                enhanced_data = await self._analyze_product_catalog(insights.product_catalog)
                insights.payment_methods = enhanced_data.get('payment_methods', [])
                insights.currencies_accepted = enhanced_data.get('currencies', [])
            
            return insights
            
        except Exception as e:
            logger.error(f"Error in LLM processing: {e}")
            return insights
    
    async def _enhance_brand_context(self, brand_context: str) -> str:
        """Enhance brand context using LLM."""
        try:
            logger.info("Enhancing brand context using LLM")
            prompt = f"""
            Please analyze and enhance the following brand context text. Make it more concise, 
            professional, and informative. Extract the key value propositions and brand story.
            Keep it under 300 words.
            
            Original text: {brand_context}
            """
            
            response = await self.client.ainvoke([
                ("system", "You are a brand analysis expert. Help structure and enhance brand information."),
                ("user", prompt)
            ])
            
            return response.content.strip()
            
        except Exception as e:
            logger.error(f"Error enhancing brand context: {e}")
            return brand_context
    
    async def _enhance_faqs(self, faqs: list) -> list:
        """Clean and enhance FAQ content using LLM."""
        try:
            logger.info("Enhancing FAQs using LLM")
            if not faqs:
                return faqs
            
            faqs_text = "\n\n".join([f"Q: {faq.question}\nA: {faq.answer}" for faq in faqs])
            
            prompt = f"""
            Please clean up and enhance the following FAQ content. Make questions clearer 
            and answers more helpful. Keep the same structure but improve readability.
            
            FAQs:
            {faqs_text}
            
            Return as JSON array with objects containing 'question' and 'answer' fields.
            """
            
            response = await self.client.ainvoke([
                ("system", "You are a customer service expert. Help improve FAQ content."),
                ("user", prompt)
            ])
            
            try:
                enhanced_faqs = json.loads(response.content)
                from main import FAQ
                return [FAQ(question=faq['question'], answer=faq['answer']) for faq in enhanced_faqs]
            except json.JSONDecodeError:
                return faqs
                
        except Exception as e:
            logger.error(f"Error enhancing FAQs: {e}")
            return faqs
    
    async def _analyze_product_catalog(self, products: list) -> dict:
        """Analyze product catalog to extract additional insights."""
        try:
            logger.info("Analyzing product catalog for additional insights")
            if not products:
                return {}
            
            # Sample first 20 products for analysis
            sample_products = products[:20]
            product_info = "\n".join([
                f"- {p.title} by {p.vendor} (${p.price})" 
                for p in sample_products if p.title and p.vendor
            ])
            
            prompt = f"""
            Analyze the following product catalog and extract insights:
            
            Products:
            {product_info}
            
            Please identify:
            1. Likely payment methods this store would accept
            2. Currencies that might be accepted
            3. Target market demographics
            
            Return as JSON with keys: payment_methods (array), currencies (array), target_demographics (string)
            """
            
            response = await self.client.ainvoke([
                ("system", "You are an e-commerce analyst. Provide insights based on product catalogs."),
                ("user", prompt)
            ])
            
            try:
                return json.loads(response.content)
            except json.JSONDecodeError:
                return {}
                
        except Exception as e:
            logger.error(f"Error analyzing product catalog: {e}")
            return {}
