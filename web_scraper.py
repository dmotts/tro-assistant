import requests
import html2text
import json
import os
import time

from bs4 import BeautifulSoup
from config import setup_logging
from urllib.parse import urljoin, urlparse
from selenium.webdriver.firefox.options import Options
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException

#set firefox location
FIREFOX_LOCATION = os.environ.get('FIREFOX_LOCATION', os.getenv('FIREFOX_LOCATION'))

# Configure logging
logging = setup_logging()

# Set Browserless API key
browserless_api_key = os.environ.get('BROWSERLESS_API_KEY', os.getenv('BROWSERLESS_API_KEY'))

# Set header information
user_agent = 'Mozilla/5.0 (Linux; Android 11; 100011886A Build/RP1A.200720.011) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.5112.69 Safari/537.36'
sec_ch_ua = '"Google Chrome";v="104", " Not;A Brand";v="105", "Chromium";v="104"'
referer = 'https://www.google.com'
cache_control = 'no-cache'
content_type = 'application/json'

def interceptor(request):
    # delete the "User-Agent" header and
    # set a new one
    del request.headers["user-agent"]  # Delete the header first
    request.headers["user-agent"] = user_agent
    request.headers["sec-ch-ua"] = sec_ch_ua
    request.headers["referer"] = referer

def scrape(url): 
    try:        
        headers = {
            'Cache-Control': cache_control,
            'Content-Type': content_type,
            "User-Agent": user_agent
        }
        source = requests.get(url, headers=headers)
        source.raise_for_status()

        raw_html  = source.text
        
        # Check the response status code
        if source.status_code == 200:
            logging.info(f'Raw HTML - {url}')
            logging.info(f'{raw_html}')
            logging.info(f'Successfully scraped - {url}')

            return raw_html    
        else:
            logging.info(f'Failed scraped - {url}')
            logging.info(f"HTTP request failed with status code {source.status_code}")
            return '';    
        
    except Exception as e:
        logging.info(e)
        logging.info(f'{url} - Failed scraped')
        logging.info(f"HTTP request failed with status code {source.status_code}")
        return ''    

def browserless_scrape(url: str):
    print(f"Attempting to scrape {url}...")
    # Define the headers for the request
    headers = {
        'Cache-Control': 'no-cache',
        'Content-Type': 'application/json',
        "User-Agent": 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.125 Safari/537.36'
    }

    # Define the data to be sent in the request
    data = {
        "url": url,
        "elements": [{
            "selector": "body"
        }],
        "waitFor": 4000
    }
    
    # Convert Python object to JSON string
    data_json = json.dumps(data)
    
    # Send the POST request
    response = requests.post(
        f"https://chrome.browserless.io/scrape?token={browserless_api_key}",
        headers=headers,
        data=data_json
    )

    print(f'Response: {response}')

    # Check the response status code
    if response.status_code == 200:
        # Decode & Load the string as a JSON object
        result = response.content
        data_str = result.decode('utf-8')
        data_dict = json.loads(data_str)

        # Extract the HTML content from the dictionary
        html_string = data_dict['data'][0]['results'][0]['html']

        print(f'{url} - Successfully scraped')

        return html_string
    else:
        print(f'{url} - Failed scraped')
        print(f"HTTP request failed with status code {response.status_code}")
        return '';    

# 2. Convert html to markdown

def convert_html_to_markdown(html):

    # Create an html2text converter
    converter = html2text.HTML2Text()

    # Configure the converter
    converter.ignore_links = False

    # Convert the HTML to Markdown
    markdown = converter.handle(html)

    return markdown

def get_base_url(url):
    parsed_url = urlparse(url)

    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    return base_url


# Turn relative url to absolute url in html

def convert_to_absolute_url(html, base_url):
    soup = BeautifulSoup(html, 'html.parser')

    for img_tag in soup.find_all('img'):
        if img_tag.get('src'):
            src = img_tag.get('src')
            if src and src.startswith(('http://', 'https://')):
                continue
            absolute_url = urljoin(base_url, src)
            img_tag['src'] = absolute_url
        elif img_tag and img_tag.get('data-src'):
            src = img_tag.get('data-src')
            if src and src.startswith(('http://', 'https://')):
                continue
            absolute_url = urljoin(base_url, src)
            img_tag['data-src'] = absolute_url

    for link_tag in soup.find_all('a'):
        href = link_tag.get('href')
        if href and href.startswith(('http://', 'https://')):
            continue
        absolute_url = urljoin(base_url, href)
        link_tag['href'] = absolute_url

    updated_html = str(soup)

    return updated_html
    
def get_markdown_from_url(url):
    base_url = get_base_url(url)
    html = browserless_scrape(url)  
    if len(html) > 0:
        updated_html = convert_to_absolute_url(html, base_url)
        markdown = convert_html_to_markdown(updated_html)
        logging.info(f'Markdown: {(markdown)}')
        logging.info(f'Markdown length: {len(markdown)}')
        return markdown
    else:
        return ''
        
def scrape_websites(urls):
    info = ""
    n = 0
    total = len(urls)
    for url in urls:
        info += get_markdown_from_url(url)
        logging.info(f'({n} / {total})')
        n = n + 1
        time.sleep(3)
    return info    
    