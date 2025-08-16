import asyncio
import aiohttp
import requests
from bs4 import BeautifulSoup
from typing import List, Optional, Dict, Any
import re
import json
from urllib.parse import urljoin, urlparse
import logging
from pydantic_models import BrandInsights, ProductInfo, SocialHandle, ContactInfo, FAQ, ImportantLink

logger = logging.getLogger(__name__)

class ShopifyScraperService:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    async def analyze_store(self, store_url: str, llm_service=None) -> BrandInsights:
        """Main method to analyze a Shopify store."""
        try:
            # Normalize URL
            if not store_url.startswith(('http://', 'https://')):
                store_url = 'https://' + store_url
            
            insights = BrandInsights(store_url=store_url)
            
            # Parallel execution of different scraping tasks
            tasks = [
                self._scrape_products(store_url),
                self._scrape_homepage(store_url),
                self._scrape_policies(store_url),
                self._scrape_contact_info(store_url),
                self._scrape_social_handles(store_url),
                self._scrape_faqs(store_url),
                self._scrape_important_links(store_url)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            products, homepage_data, policies, contact_info, social_handles, faqs, important_links = results
            
            if isinstance(products, list):
                insights.product_catalog = products[:500]  # Limit to 500 products
                insights.total_products = len(products)
            
            if isinstance(homepage_data, dict):
                insights.hero_products = homepage_data.get('hero_products', [])
                insights.store_name = homepage_data.get('store_name')
                insights.brand_context = homepage_data.get('brand_context')
            
            if isinstance(policies, dict):
                insights.privacy_policy = policies.get('privacy_policy')
                insights.return_refund_policy = policies.get('return_refund_policy')
            
            if isinstance(contact_info, ContactInfo):
                insights.contact_info = contact_info
            
            if isinstance(social_handles, list):
                insights.social_handles = social_handles
            
            if isinstance(faqs, list):
                insights.faqs = faqs
            
            if isinstance(important_links, list):
                insights.important_links = important_links
            
            # Use LLM to enhance and structure data if available
            if llm_service:
                insights = await llm_service.enhance_insights(insights)
            
            return insights
            
        except Exception as e:
            logger.error(f"Error analyzing store {store_url}: {str(e)}")
            raise
    
    async def _scrape_products(self, store_url: str) -> List[ProductInfo]:
        """Scrape products from /products.json endpoint."""
        try:
            products_url = urljoin(store_url, '/products.json')
            response = self.session.get(products_url, timeout=30)
            
            if response.status_code == 404:
                # Try alternative product discovery methods
                return await self._scrape_products_from_sitemap(store_url)
            
            response.raise_for_status()
            data = response.json()
            
            products = []
            for product_data in data.get('products', []):
                try:
                    product = ProductInfo(
                        id=product_data.get('id', 0),
                        title=product_data.get('title', ''),
                        handle=product_data.get('handle', ''),
                        vendor=product_data.get('vendor', ''),
                        product_type=product_data.get('product_type', ''),
                        price=self._extract_price(product_data),
                        available=product_data.get('available', False),
                        tags=product_data.get('tags', []),
                        images=self._extract_images(product_data),
                        description=product_data.get('body_html', ''),
                        variants=product_data.get('variants', [])
                    )
                    products.append(product)
                except Exception as e:
                    logger.warning(f"Error processing product: {e}")
                    continue
            
            return products
            
        except Exception as e:
            logger.error(f"Error scraping products: {e}")
            return []
    
    async def _scrape_products_from_sitemap(self, store_url: str) -> List[ProductInfo]:
        """Alternative method to discover products from sitemap."""
        try:
            sitemap_url = urljoin(store_url, '/sitemap_products_1.xml')
            response = self.session.get(sitemap_url, timeout=30)
            
            if response.status_code != 200:
                return []
            
            # Parse XML and extract product URLs
            from xml.etree import ElementTree as ET
            root = ET.fromstring(response.content)
            
            product_urls = []
            for url_elem in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
                loc_elem = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                if loc_elem is not None and '/products/' in loc_elem.text:
                    product_urls.append(loc_elem.text)
            
            # Scrape individual products (limit to first 50 for performance)
            products = []
            for url in product_urls[:50]:
                try:
                    product = await self._scrape_individual_product(url)
                    if product:
                        products.append(product)
                except Exception as e:
                    logger.warning(f"Error scraping individual product {url}: {e}")
                    continue
            
            return products
            
        except Exception as e:
            logger.error(f"Error scraping products from sitemap: {e}")
            return []
    
    async def _scrape_individual_product(self, product_url: str) -> Optional[ProductInfo]:
        """Scrape individual product page."""
        try:
            response = self.session.get(product_url, timeout=20)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract product data from JSON-LD or meta tags
            json_ld = soup.find('script', type='application/ld+json')
            if json_ld:
                try:
                    data = json.loads(json_ld.string)
                    if isinstance(data, list):
                        data = data[0]
                    
                    if data.get('@type') == 'Product':
                        return ProductInfo(
                            id=hash(product_url),
                            title=data.get('name', ''),
                            handle=product_url.split('/')[-1],
                            vendor=data.get('brand', {}).get('name', '') if isinstance(data.get('brand'), dict) else str(data.get('brand', '')),
                            product_type='',
                            price=str(data.get('offers', {}).get('price', '')) if data.get('offers') else '',
                            available=data.get('offers', {}).get('availability') == 'InStock' if data.get('offers') else False,
                            tags=[],
                            images=[data.get('image', '')] if data.get('image') else [],
                            description=data.get('description', '')
                        )
                except json.JSONDecodeError:
                    pass
            
            # Fallback to HTML parsing
            title_elem = soup.find('h1') or soup.find('title')
            title = title_elem.get_text().strip() if title_elem else ''
            
            price_elem = soup.find(class_=re.compile(r'price', re.I))
            price = price_elem.get_text().strip() if price_elem else ''
            
            return ProductInfo(
                id=hash(product_url),
                title=title,
                handle=product_url.split('/')[-1],
                vendor='',
                product_type='',
                price=price,
                available=True,
                tags=[],
                images=[],
                description=''
            )
            
        except Exception as e:
            logger.error(f"Error scraping individual product {product_url}: {e}")
            return None
    
    async def _scrape_homepage(self, store_url: str) -> Dict[str, Any]:
        """Scrape homepage for hero products and brand context."""
        try:
            response = self.session.get(store_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract store name
            title_elem = soup.find('title')
            store_name = title_elem.get_text().strip() if title_elem else ''
            
            # Extract brand context from about section or meta description
            brand_context = ''
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                brand_context = meta_desc.get('content', '')
            
            # Look for about section
            about_section = soup.find(text=re.compile(r'about', re.I))
            if about_section and about_section.parent:
                brand_context = about_section.parent.get_text().strip()[:500]
            
            # Extract hero products (featured products on homepage)
            hero_products = []
            product_links = soup.find_all('a', href=re.compile(r'/products/'))
            
            for link in product_links[:10]:  # Limit to first 10
                href = link.get('href')
                if href:
                    full_url = urljoin(store_url, href)
                    product = await self._scrape_individual_product(full_url)
                    if product:
                        hero_products.append(product)
            
            return {
                'store_name': store_name,
                'brand_context': brand_context,
                'hero_products': hero_products
            }
            
        except Exception as e:
            logger.error(f"Error scraping homepage: {e}")
            return {}
    
    async def _scrape_policies(self, store_url: str) -> Dict[str, str]:
        """Scrape privacy policy and return/refund policy."""
        policies = {}
        
        policy_urls = {
            'privacy_policy': ['/pages/privacy-policy', '/policies/privacy-policy', '/privacy'],
            'return_refund_policy': ['/pages/refund-policy', '/pages/returns', '/policies/refund-policy', '/refund-policy']
        }
        
        for policy_type, urls in policy_urls.items():
            for url_path in urls:
                try:
                    full_url = urljoin(store_url, url_path)
                    response = self.session.get(full_url, timeout=20)
                    
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        
                        # Remove script and style elements
                        for script in soup(["script", "style"]):
                            script.decompose()
                        
                        content = soup.get_text()
                        # Clean up whitespace
                        content = re.sub(r'\s+', ' ', content).strip()
                        
                        if len(content) > 100:  # Ensure it's substantial content
                            policies[policy_type] = content[:2000]  # Limit length
                            break
                            
                except Exception as e:
                    logger.warning(f"Error fetching policy {url_path}: {e}")
                    continue
        
        return policies
    
    async def _scrape_contact_info(self, store_url: str) -> ContactInfo:
        """Scrape contact information."""
        try:
            # Try contact page first
            contact_urls = ['/pages/contact', '/contact', '/pages/contact-us']
            
            contact_info = ContactInfo()
            
            for contact_path in contact_urls:
                try:
                    contact_url = urljoin(store_url, contact_path)
                    response = self.session.get(contact_url, timeout=20)
                    
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        text = soup.get_text()
                        
                        # Extract emails
                        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
                        contact_info.emails.extend(emails)
                        
                        # Extract phone numbers
                        phones = re.findall(r'[\+]?[1-9]?[\d\s\-\(\)]{10,}', text)
                        contact_info.phones.extend([phone.strip() for phone in phones if len(re.sub(r'[^\d]', '', phone)) >= 10])
                        
                        # Extract address (basic approach)
                        address_pattern = r'\d+\s+[\w\s,]+\s+\d{5}'
                        addresses = re.findall(address_pattern, text)
                        if addresses:
                            contact_info.address = addresses[0]
                        
                        break
                        
                except Exception as e:
                    logger.warning(f"Error fetching contact page {contact_path}: {e}")
                    continue
            
            # Remove duplicates
            contact_info.emails = list(set(contact_info.emails))
            contact_info.phones = list(set(contact_info.phones))
            
            return contact_info
            
        except Exception as e:
            logger.error(f"Error scraping contact info: {e}")
            return ContactInfo()
    
    async def _scrape_social_handles(self, store_url: str) -> List[SocialHandle]:
        """Scrape social media handles."""
        try:
            response = self.session.get(store_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            social_handles = []
            social_platforms = {
                'instagram': ['instagram.com', 'instagr.am'],
                'facebook': ['facebook.com', 'fb.com'],
                'twitter': ['twitter.com', 'x.com'],
                'tiktok': ['tiktok.com'],
                'youtube': ['youtube.com', 'youtu.be'],
                'linkedin': ['linkedin.com'],
                'pinterest': ['pinterest.com']
            }
            
            # Find all links
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link.get('href', '')
                for platform, domains in social_platforms.items():
                    for domain in domains:
                        if domain in href:
                            # Extract handle from URL
                            handle = self._extract_social_handle(href, platform)
                            social_handles.append(SocialHandle(
                                platform=platform,
                                url=href,
                                handle=handle
                            ))
                            break
            
            # Remove duplicates based on platform
            seen_platforms = set()
            unique_handles = []
            for handle in social_handles:
                if handle.platform not in seen_platforms:
                    unique_handles.append(handle)
                    seen_platforms.add(handle.platform)
            
            return unique_handles
            
        except Exception as e:
            logger.error(f"Error scraping social handles: {e}")
            return []
    
    async def _scrape_faqs(self, store_url: str) -> List[FAQ]:
        """Scrape FAQ section."""
        try:
            faq_urls = ['/pages/faq', '/faq', '/pages/frequently-asked-questions', '/help']
            
            for faq_path in faq_urls:
                try:
                    faq_url = urljoin(store_url, faq_path)
                    response = self.session.get(faq_url, timeout=20)
                    
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        
                        faqs = []
                        
                        # Method 1: Look for structured FAQ elements
                        faq_items = soup.find_all(class_=re.compile(r'faq|question', re.I))
                        
                        for item in faq_items:
                            question_elem = item.find(class_=re.compile(r'question|title', re.I))
                            answer_elem = item.find(class_=re.compile(r'answer|content', re.I))
                            
                            if question_elem and answer_elem:
                                question = question_elem.get_text().strip()
                                answer = answer_elem.get_text().strip()
                                
                                if question and answer and len(question) > 10:
                                    faqs.append(FAQ(question=question, answer=answer[:500]))
                        
                        # Method 2: Look for h3/h4 followed by p tags
                        if not faqs:
                            headings = soup.find_all(['h3', 'h4', 'h5'])
                            for heading in headings:
                                question = heading.get_text().strip()
                                if '?' in question:
                                    # Look for the next sibling that contains text
                                    answer_elem = heading.find_next_sibling(['p', 'div'])
                                    if answer_elem:
                                        answer = answer_elem.get_text().strip()
                                        if answer and len(answer) > 20:
                                            faqs.append(FAQ(question=question, answer=answer[:500]))
                        
                        if faqs:
                            return faqs[:20]  # Limit to 20 FAQs
                            
                except Exception as e:
                    logger.warning(f"Error fetching FAQ page {faq_path}: {e}")
                    continue
            
            return []
            
        except Exception as e:
            logger.error(f"Error scraping FAQs: {e}")
            return []
    
    async def _scrape_important_links(self, store_url: str) -> List[ImportantLink]:
        """Scrape important links like order tracking, blogs, etc."""
        try:
            response = self.session.get(store_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            important_keywords = [
                'track', 'order', 'blog', 'news', 'contact', 'support', 
                'help', 'shipping', 'size-guide', 'careers', 'about'
            ]
            
            important_links = []
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link.get('href', '')
                text = link.get_text().strip().lower()
                
                # Skip if it's just a fragment or external link to social media
                if href.startswith('#') or any(social in href for social in ['facebook', 'instagram', 'twitter']):
                    continue
                
                for keyword in important_keywords:
                    if keyword in text or keyword in href.lower():
                        full_url = urljoin(store_url, href)
                        important_links.append(ImportantLink(
                            name=link.get_text().strip() or keyword.title(),
                            url=full_url,
                            description=f"Link related to {keyword}"
                        ))
                        break
            
            # Remove duplicates
            seen_urls = set()
            unique_links = []
            for link in important_links:
                if link.url not in seen_urls:
                    unique_links.append(link)
                    seen_urls.add(link.url)
            
            return unique_links[:15]  # Limit to 15 links
            
        except Exception as e:
            logger.error(f"Error scraping important links: {e}")
            return []
    
    def _extract_price(self, product_data: Dict[str, Any]) -> str:
        """Extract price from product data."""
        variants = product_data.get('variants', [])
        if variants:
            price = variants[0].get('price', '0')
            return str(price)
        return '0'
    
    def _extract_images(self, product_data: Dict[str, Any]) -> List[str]:
        """Extract image URLs from product data."""
        images = product_data.get('images', [])
        return [img.get('src', '') for img in images if img.get('src')]
    
    def _extract_social_handle(self, url: str, platform: str) -> str:
        """Extract social media handle from URL."""
        try:
            if platform == 'instagram':
                match = re.search(r'instagram\.com/([^/?]+)', url)
                return match.group(1) if match else ''
            elif platform == 'twitter':
                match = re.search(r'(?:twitter\.com|x\.com)/([^/?]+)', url)
                return match.group(1) if match else ''
            elif platform == 'facebook':
                match = re.search(r'facebook\.com/([^/?]+)', url)
                return match.group(1) if match else ''
            elif platform == 'tiktok':
                match = re.search(r'tiktok\.com/@([^/?]+)', url)
                return match.group(1) if match else ''
            elif platform == 'youtube':
                match = re.search(r'youtube\.com/(?:c/|channel/|user/)?([^/?]+)', url)
                return match.group(1) if match else ''
            else:
                return ''
        except Exception:
            return ''
