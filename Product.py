import os
import requests
from config import setup_logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from urllib.parse import urljoin 

# Configure logging
logging = setup_logging()

class Product:
    def __init__(self, driver, url: str, **selectors):
        self.driver = driver
        self.url = url
        self.selectors = selectors
        self.wait = WebDriverWait(driver, 10)  # Initialize WebDriverWait

    def scrape(self):
        try:
            self.driver.get(self.url)
            # Wait for the page to fully load
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'body')))
        except TimeoutException:
            # Handle timeout (e.g., page didn't load within 10 seconds)
            print("Page load timed out")

    def wait_for_element_visibility(self, selector):
        try:
            element = self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))
            return element
        except TimeoutException:
            logging.info(f"Element not found or not visible with selector '{selector}'")
            return None

    def wait_for_element_presence_and_clickable(self, selector):
        try:
            element = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
            return element
        except TimeoutException:
            logging.info(f"Element not found or not clickable with selector '{selector}'")
            return None

    def get_element_text(self, selector: str):
        element = self.wait_for_element_visibility(selector)
        if element:
            return element.text
        return ""

    def get_elements_attribute(self, attribute: str, selector: str):
        elements = self.wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector)))
        return [element.get_attribute(attribute) for element in elements]

    def get_attribute(self, attribute_name: str):
        if attribute_name in self.selectors:
            selector = self.selectors[attribute_name]
            return self.get_element_text(selector)
        return ""

    def get_datasheets(self):
        if "datasheets" in self.selectors:
            datasheets_selector = self.selectors["datasheets"]
            return self.get_elements_attribute("href", datasheets_selector)
        return []

    def get_datasheet_links(self, selector: str):
        datasheets = self.wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector)))
        datasheet_links = []
        for datasheet in datasheets:
            datasheet_name = datasheet.accessible_name
            if datasheet_name.startswith("documents-icon "):
                datasheet_name = datasheet_name[len("document-icon "):] 
            datasheet_url = datasheet.get_attribute("href")
            if datasheet_name and datasheet_url:
                datasheet_links.append((datasheet_name, datasheet_url))
        return datasheet_links

    def get_brand(self, selector: str):
        value = self.get_element_text(selector)
        if value.startswith("BRAND: "):
            value = value[len("BRAND: "):]  # Remove the "BRAND: " prefix
        return value
    
    def get_image_url(self, selector):
        if selector == 'meta[property="og:image"]':
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                if element:
                    return element.get_attribute("content")
            except NoSuchElementException:
                logging.info(f"Image selector not found on the page")
        else:
            elements = self.wait_for_element_presence_and_clickable(selector)
            image_urls = []
            
            if elements:
                for element in elements:
                    src = element.get_attribute("src")
                    if src:
                        # Check if the image URL is relative (doesn't start with "http" or "www")
                        if not src.startswith(("http", "www")):
                            src = urljoin(self.url, src)  # Combine with base URL to make it absolute
                        image_urls.append(src)
            
            return image_urls


    def get_images_src(self, selector: str):
        elements = self.wait_for_element_presence_and_clickable(selector)
        image_urls = []
        
        if elements:
            for element in elements:
                src = element.get_attribute("src")
                if src:
                    # Check if the image URL is relative (doesn't start with "http" or "www")
                    if not src.startswith(("http", "www")):
                        src = urljoin(self.url, src)  # Combine with base URL to make it absolute
                    image_urls.append(src)
        
        return image_urls
    
    def download_datasheet(self, pdf_url, target_directory='docs'):
        """
        Downloads a PDF file from a given URL and saves it in the 'docs' directory.

        Args:
            url (str): The URL of the PDF file to download.
        """
        # Create the target directory if it doesn't exist
        if not os.path.exists(target_directory):
            os.makedirs(target_directory)

        # Extract the PDF file name from the URL
        pdf_filename = os.path.join(target_directory, pdf_url.split("/")[-1])

        try:
            # Send a GET request to the PDF URL
            response = requests.get(pdf_url)

            # Check if the request was successful (status code 200)
            if response.status_code == 200:
                with open(pdf_filename, 'wb') as pdf_file:
                    pdf_file.write(response.content)
                print(f"PDF saved as '{pdf_filename}'")
            else:
                print(f"Failed to download PDF. Status code: {response.status_code}")
        except Exception as e:
            print(f"An error occurred: {str(e)}")

