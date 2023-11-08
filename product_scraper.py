import os
import json
import time
import shutil
import datetime

from config import setup_logging
from selenium.webdriver.firefox.options import Options
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from Product import Product
from app import add_to_db

from concurrent.futures import ThreadPoolExecutor


# Configure logging
logging = setup_logging()

# Set file paths for product URLs and selectors
PRODUCT_URLS_FILE = 'products/product-urls.txt'
SELECTORS_FILE = 'products/product-selectors.txt'

# Set header information
user_agent = 'Mozilla/5.0 (Linux; Android 11; 100011886A Build/RP1A.200720.011) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.5112.69 Safari/537.36'
sec_ch_ua = '"Google Chrome";v="104", " Not;A Brand";v="105", "Chromium";v="104"'
referer = 'https://www.google.com'
cache_control = 'no-cache'
content_type = 'application/json'

# Set up Firefox WebDriver with headless mode
FIREFOX_LOCATION = os.environ.get('FIREFOX_LOCATION', os.getenv('FIREFOX_LOCATION'))
options = Options()
options.add_argument('--headless')
options.add_argument(f'user-agent={user_agent}')

def save_urls_to_txt(urls, base_url):
    # Create the 'products' directory if it doesn't exist
    if not os.path.exists("products"):
        os.makedirs("products")

    file_name = os.path.join("products", "product-urls.txt")  # Fallback filename if parsing fails

    # Create a set to store unique URLs
    unique_urls = set()

    # Check if the file already exists and read existing URLs into the set
    try:
        if os.path.isfile(file_name):
            with open(file_name, 'r') as file:
                existing_urls = file.read().splitlines()
                unique_urls.update(existing_urls)
    except FileNotFoundError:
        pass

    # Add new unique URLs to the set
    unique_urls.update(urls)

    # Write the unique URLs to the file
    with open(file_name, 'w') as file:
        file.writelines(f"{url}\n" for url in unique_urls)

    logging.info(f'Product URLs saved to {file_name}')

def extract_category_urls(page="https://tro.com.au", selector="a.header-menu-level2-anchor"):
    """
    Extracts all URLs from the given page by CSS selector.

    Parameters:
        page (str): The URL of the webpage to scrape.
        selector (str): The CSS selector used to find the elements containing the URLs.

    Returns:
        urls (list): A list containing the extracted URLs.
    """
    driver = webdriver.Firefox(options=options)
    urls = []
    
    try:
        driver.get(page)
        
        # Wait for the elements to be loaded and find them by CSS selector
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
        elements = driver.find_elements(By.CSS_SELECTOR, selector)

        # Use a generator expression to get all "href" attributes from the elements
        urls.extend(element.get_attribute("href") for element in elements if element.get_attribute("href"))
        
    except NoSuchElementException:
        logging.info(f"Selector not found on page: {page}")
    except TimeoutException:
        logging.info(f"Page load timed out for URL: {page}")
    finally:
        driver.quit()

    logging.info(f"Category Urls: {urls}")
    return urls

def extract_product_urls(base_url, selector, next_button_selector=None, max_pages=None, max_products=None):
    driver = webdriver.Firefox(options=options)
    try:
        urls = []
        page_count = 0
        current_url = base_url

        while current_url and (max_pages is None or page_count < max_pages):
            try:
                start_time = time.time()
                driver.get(current_url)

                # Calculate dynamic sleep time based on the website's response time
                response_time = time.time() - start_time
                sleep_time = max(1, min(10, response_time * 2))  # Dynamic sleep time (between 1 and 10 seconds)
                time.sleep(sleep_time)

                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                urls.extend(element.get_attribute("href") for element in elements)

                if max_products and len(urls) >= max_products:
                    urls = urls[:max_products]  # Truncate the list to the specified maximum

                if len(urls) >= max_products:
                    break  # Stop when reaching the maximum number of product URLs

                if next_button_selector:
                    next_button = driver.find_element(By.CSS_SELECTOR, next_button_selector)
                    current_url = next_button.get_attribute("href")
                else:
                    current_url = None

                page_count += 1
            except NoSuchElementException:
                logging.info(f"Selector not found on page: {current_url}")
                break
            except TimeoutException:
                logging.info(f"Page load timed out for URL: {current_url}")
                break

        save_urls_to_txt(urls, base_url)  # Save the URLs to a TXT file

        return urls

    finally:
        driver.quit()

def scrape_single_product(product_url, selectors, download_directory='docs'):
    """
    Scrapes product information from a given URL and downloads datasheets if available.

    Args:
        product_url (str): The URL of the product to scrape.
        selectors (dict): A dictionary of selectors for different attributes of the product.
        download_directory (str, optional): The directory to save downloaded datasheets. Defaults to 'docs'.
        
    Returns:
        dict: A dictionary containing scraped product information.
    """
    options = Options()
    options.add_argument(f'user-agent={user_agent}')
    options.add_argument('--headless')

    driver = webdriver.Firefox(options=options)
    product = Product(driver, product_url, **selectors)
    product.scrape()

    product_info = {}
    for key, selector in selectors.items():
        try:
            if key == "image":
                value = product.get_image_url(selector)
            elif key == "brand":
                value = product.get_brand(selector)
            elif key == "datasheets":
                datasheets = product.get_datasheet_links(selector)
                value = []
                for datasheet_name, datasheet_url in datasheets:
                    # Modify each datasheet link to be a clickable name
                    datasheet_link = f"[{datasheet_name}]({datasheet_url})"
                    value.append(datasheet_link)
                    # Download the datasheet using the download_datasheet method
                    product.download_datasheet(datasheet_url, download_directory)
            else:
                value = product.get_attribute(key)
                # Modify the 'name' key to be a clickable link to the product URL
                if key == "name":
                    value = f"[{value}]({product_url})"
            product_info[key] = value
            logging.info(f"{key.capitalize()}: {value}")
        except Exception as e:
            logging.info(f"Failed to retrieve {key} - {e}")

    driver.quit()

    return product_info

def scrape_multiple_products(urls_and_selectors):
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        results = list(executor.map(lambda x: scrape_single_product(*x), urls_and_selectors))

    return results

def read_selectors_from_file(file_path):
    try:
        with open(file_path, 'r') as file:
            selectors = json.load(file)
        return selectors
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return {}

def scrape_products():
    # Read product URLs from a file
    with open(PRODUCT_URLS_FILE, 'r') as file:
        product_urls = [line.strip() for line in file]

    # Read selectors from a file
    selectors = read_selectors_from_file(SELECTORS_FILE)

    if not selectors:
        print("No selectors found. Please check the product_selectors.txt file.")
        return

    urls_and_selectors = [(url, selectors) for url in product_urls]

    # Scrape multiple products
    product_info_list = scrape_multiple_products(urls_and_selectors)

    # Create the 'products' directory if it doesn't exist
    os.makedirs("products", exist_ok=True)

    # Save product information to a markdown file in the 'products' directory
    base_url = product_urls[0].split('//')[1].split('/')[0]  # Extract the domain name
    markdown_file_name = f"products/products-info.md"

    with open(markdown_file_name, 'w') as md_file:
        for product_info in product_info_list:
            md_file.write("## Product Information\n\n")
            for key, value in product_info.items():
                if key == "image" and value:  # Check if the key is "image" and there are image URLs
                    md_file.write(f"**{key.capitalize()}**: \n")  # Start the line with the image key
                    for img_url in value:
                        md_file.write(f"![Image]({img_url})\n")  # Add the image tag
                else:
                    md_file.write(f"**{key.capitalize()}**: {value}\n\n")  # Regular text for other keys

    # Find the product URLs file with the timestamp suffix in the 'uploaded' directory
    uploaded_files = [f for f in os.listdir("uploaded") if f.startswith("product-urls-processed_")]
    if uploaded_files:
        uploaded_file = os.path.join("uploaded", uploaded_files[0])

        # Amend the contents of the product URLs file
        with open(uploaded_file, 'a') as uploaded_content:
            for url in product_urls:
                uploaded_content.write(f"{url}\n")

        # Rename the file with the current time and date suffix
        current_datetime = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        renamed_file_name = f"uploaded/product-urls-processed_{current_datetime}.txt"
        os.replace(uploaded_file, renamed_file_name)

    return product_info_list

def print_product_list(product_list):
    # Print or process the list of product information as needed
    for product_info in product_list:
        for key, value in product_info.items():
            logging.info(f"{key.capitalize()}: {value}")

if __name__ == '__main__':
    base_url = 'https://www.tro.com.au/enclosures/wall-mount-enclosures/steel-wall-mount-enclosures'
    selector = "a.facets-item-cell-grid-title"
    next_button_selector = ".global-views-pagination-next > a"
    max_pages = 1
    max_products = 5

    urls = [
        'https://www.tro.com.au/industrial-electrical/contactors-overloads/thermal-overloads'
    ]

  #  for base_url in urls:
  #      product_urls = extract_product_urls(base_url, selector, next_button_selector, max_pages=max_pages, max_products=max_products)
  #      logging.info(product_urls)
#
  #  product_info_list = scrape_products()
  #  print_product_list(product_info_list)
  # 
  #  add_to_db()
    extract_category_urls()