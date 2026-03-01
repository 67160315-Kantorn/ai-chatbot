"""
Fast Granite Scraper for Siamtak.com
Uses requests + BeautifulSoup with concurrent processing
"""
import csv
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Configuration
BASE_URL = "https://www.siamtak.com"
CATEGORY_URL = "https://www.siamtak.com/sub-category/granite"
BASE_DATA_DIR = Path(__file__).resolve().parent / "data" / "granite_images"
CSV_PATH = Path(__file__).resolve().parent / "siamtak_granite.csv"

# Request headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Thread pool size for concurrent requests
MAX_WORKERS = 10


def create_session() -> requests.Session:
    """Create a requests session with retries."""
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # Retry adapter
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session


def get_product_urls_from_page(session: requests.Session, url: str) -> List[str]:
    """Extract all product URLs from a category page."""
    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all product links
        product_urls = []
        
        # Method 1: Find links in product cards
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '/products/' in href:
                full_url = urljoin(BASE_URL, href)
                if full_url not in product_urls:
                    product_urls.append(full_url)
        
        logger.info(f"Found {len(product_urls)} product URLs from {url}")
        return product_urls
        
    except Exception as e:
        logger.error(f"Error fetching product URLs from {url}: {e}")
        return []


def check_for_more_pages(session: requests.Session, soup: BeautifulSoup) -> Optional[str]:
    """Check if there's a 'Load More' or pagination link."""
    # Check for pagination
    pagination = soup.find('nav', class_='pagination')
    if pagination:
        next_link = pagination.find('a', string=re.compile(r'Next|ถัดไป|>'))
        if next_link and next_link.get('href'):
            return urljoin(BASE_URL, next_link['href'])
    
    # Check for load more button (Finsweet CMS Load)
    load_more = soup.find(attrs={'fs-cmsload-element': 'load-more'})
    if load_more and load_more.name == 'a' and load_more.get('href'):
        return urljoin(BASE_URL, load_more['href'])
    
    return None


def scrape_product_detail(session: requests.Session, product_url: str) -> Dict[str, str]:
    """
    Scrape detailed information from a product page.
    Returns product details including full description.
    """
    import html
    
    result = {
        "product_url": product_url,
        "product_title": "",
        "product_description": "",
        "product_price": "",
        "image_url": "",
        "image_path": ""
    }
    
    try:
        response = session.get(product_url, timeout=30)
        response.raise_for_status()
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        raw_html = response.text
        
        # Extract title
        title_elem = (
            soup.find('h1') or
            soup.find(class_=re.compile(r'product.*title', re.I)) or
            soup.find(class_=re.compile(r'title', re.I))
        )
        if title_elem:
            result["product_title"] = title_elem.get_text(strip=True)
        
        # Extract description - try multiple selectors
        descriptions = []
        
        # Method 1: Look for product description class
        desc_selectors = [
            '.product_description',
            '.product-description',
            '.product-details',
            '.description',
            '.product-content',
            '.product-info',
            '[class*="description"]',
            '[class*="detail"]',
        ]
        
        for selector in desc_selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text(separator=' ', strip=True)
                if text and len(text) > 20 and text not in descriptions:
                    descriptions.append(text)
        
        # Method 2: Meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            content = meta_desc['content'].strip()
            if content not in descriptions:
                descriptions.insert(0, content)
        
        # Method 3: OG description
        og_desc = soup.find('meta', property='og:description')
        if og_desc and og_desc.get('content'):
            content = og_desc['content'].strip()
            if content not in descriptions:
                descriptions.insert(0, content)
        
        # Combine descriptions
        if descriptions:
            result["product_description"] = " | ".join(descriptions[:3])  # Take first 3 unique descriptions
        
        # Fallback
        if not result["product_description"]:
            result["product_description"] = f"หินแกรนิต {result['product_title']}"
        
        # Extract price
        price_selectors = [
            '.product_discount-price',
            '.product_price',
            '.price',
            '.product-price',
            '.current-price',
            '.sale-price',
            '[class*="price"]',
        ]
        
        for selector in price_selectors:
            elem = soup.select_one(selector)
            if elem:
                price_text = elem.get_text(strip=True)
                # Extract numeric price
                price_match = re.search(r'[\d,]+', price_text.replace(',', ''))
                if price_match:
                    result["product_price"] = price_match.group().replace(',', '')
                    break
        
        # Extract image - Priority: CDN hero-product images
        # Method 1: Find siamtak.b-cdn.net/hero-product/ (main product image)
        cdn_images = re.findall(r'src="(https://siamtak\.b-cdn\.net/hero-product/[^"]+)"', raw_html)
        if cdn_images:
            # Unescape HTML entities and take first hero-product image
            image_url = html.unescape(cdn_images[0])
            result["image_url"] = image_url
        else:
            # Method 2: Find any siamtak.b-cdn.net image (excluding svg and Main_Structure)
            cdn_images = re.findall(r'src="(https://siamtak\.b-cdn\.net/(?!Main_Structure)[^"]+)"', raw_html)
            for img_url in cdn_images:
                img_url = html.unescape(img_url)
                if not img_url.endswith('.svg') and 'gallery' not in img_url.lower():
                    result["image_url"] = img_url
                    break
            else:
                # Method 3: Try OG image
                og_image = soup.find('meta', property='og:image')
                if og_image and og_image.get('content'):
                    result["image_url"] = og_image['content']
        
        logger.debug(f"Scraped: {result['product_title'][:50] if result['product_title'] else product_url}")
        
    except Exception as e:
        logger.warning(f"Error scraping {product_url}: {e}")
    
    return result


def download_image(session: requests.Session, image_url: str, save_path: Path) -> bool:
    """Download image from URL and save to path."""
    if not image_url:
        return False
    
    try:
        response = session.get(image_url, timeout=15)
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            f.write(response.content)
        
        return True
    except Exception as e:
        logger.warning(f"Failed to download image {image_url}: {e}")
        return False


def process_product(session: requests.Session, product_url: str, index: int, total: int) -> Dict[str, str]:
    """Process a single product: scrape details and download image."""
    logger.info(f"Processing product {index}/{total}: {product_url}")
    
    # Scrape product details
    result = scrape_product_detail(session, product_url)
    
    # Download image
    if result["image_url"]:
        # Create filename from URL slug
        slug = product_url.split('/')[-1] or f"product_{index}"
        slug = re.sub(r'[^\w\-]', '', slug)
        
        # Determine image extension
        ext = '.jpg'
        if '.png' in result["image_url"].lower():
            ext = '.png'
        elif '.webp' in result["image_url"].lower():
            ext = '.webp'
        
        image_filename = f"{slug}{ext}"
        image_path = BASE_DATA_DIR / image_filename
        relative_image_path = os.path.join("data", "granite_images", image_filename)
        
        if download_image(session, result["image_url"], image_path):
            result["image_path"] = relative_image_path
    
    return result


def run_granite_scrape() -> Dict[str, Any]:
    """
    Main function to run the granite scraper.
    Uses concurrent processing for faster execution.
    """
    start_time = time.time()
    
    try:
        logger.info(f"Starting granite scrape for {CATEGORY_URL}")
        
        # Ensure directories exist
        BASE_DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        # Create session
        session = create_session()
        
        # Step 1: Get all product URLs from category page
        logger.info("Step 1: Fetching product URLs...")
        product_urls = get_product_urls_from_page(session, CATEGORY_URL)
        
        if not product_urls:
            logger.warning("No product URLs found")
            return {"success": False, "message": "No product URLs found"}
        
        # Step 2: Scrape each product concurrently
        logger.info(f"Step 2: Scraping {len(product_urls)} products with {MAX_WORKERS} workers...")
        results = []
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(process_product, session, url, i+1, len(product_urls)): url
                for i, url in enumerate(product_urls)
            }
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    url = futures[future]
                    logger.error(f"Error processing {url}: {e}")
        
        if not results:
            logger.warning("No products were successfully scraped")
            return {"success": False, "message": "No products successfully scraped"}
        
        # Step 3: Save results to CSV
        logger.info("Step 3: Saving results to CSV...")
        with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
            fieldnames = ["product_url", "product_title", "product_description", "product_price", "image_url", "image_path"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        
        elapsed_time = time.time() - start_time
        
        logger.info(f"Successfully scraped {len(results)} granite products in {elapsed_time:.2f} seconds")
        logger.info(f"Results saved to: {CSV_PATH}")
        
        return {
            "success": True,
            "message": f"Successfully scraped {len(results)} products in {elapsed_time:.2f} seconds",
            "count": len(results),
            "csv_path": str(CSV_PATH),
            "image_dir": str(BASE_DATA_DIR),
            "elapsed_time": round(elapsed_time, 2)
        }
        
    except Exception as e:
        logger.error(f"Scrape failed: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": f"Scrape failed: {str(e)}"}


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 60)
    print("Fast Granite Scraper - Siamtak.com")
    print("=" * 60)
    
    res = run_granite_scrape()
    
    print("\n" + "=" * 60)
    print("Scrape Result:")
    print("=" * 60)
    for key, value in res.items():
        print(f"  {key}: {value}")
