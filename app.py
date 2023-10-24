import os
import time
import glob
import shutil
import datetime
import streamlit as st
import pinecone
import json 
import requests
import langsmith

from config import setup_logging, setup_langsmith
from web_scraper import get_markdown_from_url
from pdf_scraper import get_pdf_text
from langchain.chains import LLMChain
from langchain.llms import OpenAI
from langchain.memory import ConversationSummaryBufferMemory, ConversationBufferMemory
from langchain.memory.chat_message_histories import StreamlitChatMessageHistory
from langchain.prompts import PromptTemplate, MessagesPlaceholder
from langchain.schema.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter  
from langchain.document_loaders import TextLoader
from langchain.vectorstores import Pinecone
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.agents import initialize_agent, Tool
from langchain.agents import AgentType
from langchain.chat_models import ChatOpenAI, ChatAnthropic
from langchain.chains.summarize import load_summarize_chain
from langchain.schema import SystemMessage
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type
from bs4 import BeautifulSoup
from pinecone.core.client.configuration import Configuration as OpenApiConfiguration

import requests
from fastapi import FastAPI, Form


# Configure logger 
logging = setup_logging()

# Configure OpenAI api key
openai_api_key = os.environ.get('OPENAI_API_KEY', os.getenv('OPENAI_API_KEY'))

# Configure Serper api key
serper_api_key = os.environ.get('SERPER_API_KEY', os.getenv('SERPER_API_KEY'))

openapi_config = OpenApiConfiguration.get_default_copy()
openapi_config.proxy = "http://proxy.server:3128"

# Intialise Pinecone
pinecone.init(
    api_key = os.environ.get('PINECONE_API_KEY', os.getenv('PINECONE_API_KEY')),
    environment=os.environ.get('PINECONE_ENVIRONMENT', os.getenv('PINECONE_ENVIRONMENT')),
 #   openapi_config=openapi_config
)

# Set embeddings
embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)

# Set index name
index_name="tro-pacific"

# Set llm
llm = ChatOpenAI(temperature=0, model='gpt-3.5-turbo-16k', openai_api_key=openai_api_key)

# Create langsmith client
#client = setup_langsmith(llm, "tro-queries")

if index_name not in pinecone.list_indexes():
    print(f'Creating Pinecone index: {index_name}')

    # Create new pinecone index
    pinecone.create_index(
        name=index_name,
        metric="cosine",
        dimension=512
    )
else:
    print(f'Pinecone {index_name} exists!')
    vectorstore = Pinecone.from_existing_index(index_name, embeddings)

index = pinecone.Index(index_name)

def add_to_db():
    store_data_to_pinecone()

def refresh_db():
    
    if index_name in pinecone.list_indexes():
        logging.info(f'Deleting index: {index_name}')
        pinecone.delete_index(name=index_name)
        
    # Create new pinecone index
    logging.info(f'Creating new index: {index_name}')
    pinecone.create_index(
        name=index_name,
        metric="cosine",
        dimension=1536
    )

    # Store Data
    store_data_to_pinecone()

def filter_valid_urls():
    # VALIDATE AND FILTER URLS / CONVERT TO TRUE ABSOLUTE URLS
    return

def get_urls(directory_path='website'):
    urls = []
    
    # List all files in the 'urls' directory
    for root, _, files in os.walk(directory_path):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            
            # Read URLs from each file and append them to the 'urls' list
            with open(file_path, 'r', encoding='utf-8') as file:
                for line in file:
                    urls.append(line.strip())
    
    # VALIDATE AND FILTER URLS

    return urls    

def get_context_chunks(text, header_tag='##',header='Product Information', metadata={}):
    headers_to_split_on = [
        (header_tag, header) 
    ]

    data = [
        Document(
            page_content = text,
            metadata = metadata
        )   
    ]

    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on)
    context_chunks = markdown_splitter.split_text(text)
    chunk_size = 250
    chunk_overlap = 30
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )

    # Split
    splits = text_splitter.split_documents(context_chunks)
    
    logging.info(f'context splits: {splits}')

    return splits

def get_text_chunks(text, metadata={}):
    chunk_size = 2000
    chunk_overlap = 0
    separators=[" ", ",", "\n"]

    logging.info(f'Markdown Text: {text}')
    
    data = [
        Document(
            page_content = text,
            metadata = metadata
        )   
    ]

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap, separators=separators)
    text_chunks = text_splitter.split_documents(data)

    logging.info(f'Text chunks: {text_chunks}')

    return text_chunks

def store_products_data_to_pinecone():
    products_directory = os.path.join(os.getcwd(), 'products')
    uploaded_directory = os.path.join(os.getcwd(), 'uploaded')

    if not os.path.exists(uploaded_directory):
        os.makedirs(uploaded_directory)

    # Get .md files from the 'products' directory
    md_files = glob.glob(os.path.join(products_directory, '*.md'))

    p = 1
    total_md_files = len(md_files)

    # Get data from .md files and add to Pinecone
    for md_file in md_files:
        with open(md_file, 'r', encoding='utf-8') as file:
            # Perform processing on each .md file
            logging.info(f'Retrieving data from {md_file}...')

            # Read the content of the .md file
            md_data = file.read()

            # Split data into chunks (if needed)
            md_data_chunks = get_context_chunks(md_data)

            # Add chunks to Pinecone index
            logging.info(f'Adding md data chunks to Pinecone...')

            Pinecone.from_documents(md_data_chunks, embeddings, index_name=index_name)

            logging.info(f'({p} / {total_md_files})')

            p += 1

            # Move the processed .md file to the 'uploaded' directory after processing
            current_datetime = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            file_name, file_extension = os.path.splitext(os.path.basename(md_file))
            new_file_name = f"{file_name}_{current_datetime}{file_extension}"
            new_file_path = os.path.join(uploaded_directory, new_file_name)

            # Create a new .md file with the same content in the 'uploaded' directory
            with open(new_file_path, 'w', encoding='utf-8') as new_file:
                new_file.write(md_data)

            # Delete the original .md file
            os.remove(md_file)

    # Optional: Return a list of processed file paths
    processed_files = [os.path.join(uploaded_directory, f"{file_name}_{current_datetime}{file_extension}") for file_name, file_extension in [os.path.splitext(os.path.basename(md_file)) for md_file in md_files]]
    return processed_files

def store_pdf_data_to_pinecone(docs_directory='docs', uploaded_directory='uploaded'):
    """
    Store PDF data to Pinecone, add a timestamp, and move the documents from 'docs' to 'uploaded/docs'.

    Args:
        docs_directory (str): The directory where PDF documents are stored. Defaults to 'docs'.
        uploaded_directory (str): The directory where uploaded documents will be moved. Defaults to 'uploaded'.
    """
    docs_directory = os.path.join(os.getcwd(), docs_directory)
    uploaded_directory = os.path.join(os.getcwd(), uploaded_directory, 'docs')

    if not os.path.exists(uploaded_directory):
        os.makedirs(uploaded_directory)

    # Get pdf documents from 'docs' directory
    pdf_files = glob.glob(os.path.join(docs_directory, '*.pdf'))

    p = 1
    total_pdfs = len(pdf_files)
    processed_files = []

    # Get data from pdf files
    for pdf_file in pdf_files:
        with open(pdf_file, 'rb') as file:
            # Perform processing on each PDF file
            logging.info(f'Retrieving pdf file data...')

            pdf_data = get_pdf_text([file])

            # Split data to chunks

            logging.info(f'Splitting pdf file data into chunks...')

            pdf_data_chunks = get_context_chunks(pdf_data, header_tag='##', header='Product Information', metadata={'Document Type': 'Datasheet'})

            # Add chunks to Pinecone index

            logging.info(f'Adding pdf data chunks to Pinecone...')

            Pinecone.from_documents(pdf_data_chunks, embeddings, index_name=index_name)

            logging.info(f'({p} / {total_pdfs})')

            p = p + 1

            # Move the processed PDF file to 'uploaded/docs' with a timestamp
            current_datetime = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            file_name, file_extension = os.path.splitext(os.path.basename(pdf_file))
            new_file_name = f"{file_name}_{current_datetime}{file_extension}"
            new_file_path = os.path.join(uploaded_directory, new_file_name)

            # Create a new PDF file with the same content in 'uploaded/docs'
            shutil.move(pdf_file, new_file_path)

            processed_files.append(new_file_path)

    return processed_files

def store_website_data_to_pinecone():

    # Get Urls for scrapping
    urls = get_urls()
    success_scrapes = []
    failed_scrapes = []

    n = 1
    s = 0
    f = 0
    total_urls = len(urls)
    
    for url in urls:
        logging.info(f'Retrieving webpage data: \'{url}\'' )

        webpage_data = get_markdown_from_url(url)

        if len(webpage_data) > 0:
            s += 1

            logging.info(f'Splitting webpage into chunks..')

            webpage_data_chunks = get_text_chunks(webpage_data, metadata = {"href": url, 'Distributor\'s Webpage URL': url})

            logging.info(f'Storing webpage chunks to Pinecone')

            Pinecone.from_documents(webpage_data_chunks, embeddings, index_name=index_name)

            logging.info(f'Successfully scraped: ({s} / {total_urls})')

            success_scrapes.append(url)

          #  time.sleep(1) #Add delay
        else:
            f += 1

            logging.info(f'Failed scraped: ({f} / {total_urls})')

            failed_scrapes.append(url)

        n += 1

    logging.info(f'### Summary of Websites Scrapped ###')
    logging.info(f'Total Website URLs: {total_urls}')
    logging.info(f'No. of successful scrapes: {s}')
    logging.info(f'No. of failed scrapes: {f}')
    logging.info(f'')
    
    logging.info(f'- Successful Website URLs Scraped -')
    q = 1
    for url in success_scrapes: 
        logging.info(f'{q}. {url}')

    logging.info(f'')

    logging.info(f'- Failed Website URLs Scraped -')
    w = 1
    for url in failed_scrapes:
        logging.info(f'{w}. {url}')

def store_data_to_pinecone(): 

    store_products_data_to_pinecone()

    store_pdf_data_to_pinecone()

    store_website_data_to_pinecone()

def get_texts_from_pinecone(query):
    docs = vectorstore.similarity_search(query)
    
    #texts = docs[0].page_content 
    #embedding_vector = OpenAIEmbeddings().embed_query(query)
  
    #retriever  = vectorstore.as_retriever(search_type="mmr", search_kwargs={"k": 1})
    retriever  = vectorstore.max_marginal_relevance_search(query, k=1, fetch_k=1)
    #matched_docs = retriever.get_relevant_documents(query)
    matched_docs = retriever
 
    joined_docs = ""
    for i, d in enumerate(matched_docs):
        print(f"\n## Document {i}\n")
        print(d.page_content)
        joined_docs = ''.join(d.page_content)

    texts = joined_docs

    logging.info(f'Pinecone joined docs: {texts}')

    return texts    

def search(query):
    url = "https://google.serper.dev/search"

    payload = json.dumps({
        "q": query
    })

    headers = {
        'X-API-KEY': serper_api_key,
        'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    print(response.text)

    return response.text

def set_up_interface():
    # Set up Streamlit interface
    st.markdown("<div style='text-align:center;'> <img style='width:340px;' src='https://www.ipenclosures.com.au/wp-content/uploads/IP-EnclosuresNZ-Logo-.png.webp' /></div>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align:center;'>IP Enclosures AI Assistant</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;'>Welcome to IP Enclosures AI Assistant! Please feel free to ask any question.</p>", unsafe_allow_html=True)

def get_prompt_template(docs):
    template = "Tro Pacific Information: "
    template += ''.join(docs) # convert docs from list to str
    
    template += """

        Tro Pacific is an authorized distributor in Australia for trusted global brands, upholding trust as their core value. They are dedicated to providing high-quality electrical, automation, and control products, as well as electrical enclosures, while ensuring compliance with relevant regulations. Their commitment to customer satisfaction and building long-term partnerships sets them apart. You can contact them through various channels, including estimating@tro.com.au for pricing, availability, and technical support, sales@tro.com.au for order status, tracking, and returns, and accounts@tro.com.au for financial inquiries. Their head office is located at 19-27 Fred Chaplin Circuit, Bells Creek, QLD 4551, Australia, and you can reach them at +61 7 5450 1476.

        Website: https://tro.com.au

        "I want you to act as a Tro Pacific representative. Your goal is make the user feel special and provide accurate information.

        The user may not know exact what they want, ask follow up questions to get better queries from the user.

        When responding about a product, check the Tro Pacific information provided first for the facts. If you have found factual information about a product, provide the information in the format below. If you do not have the information or cannot find it, simply respond with "I'm sorry, I do not have that information. Is there something else that I may assist you with?"

        Do not provide an empty product information format, if you can not find the information, do not provide it just respond with 
        
        Product name [product link]
        Price: price
        Price inc. GST: price with tax
        Brand: Brand
        SKU: SKU
        Details: details
        Datasheets: Datasheet name [datasheet link]

        If you cannot find the datasheets in the Tro Pacific information, do not add it to the format.

        To ensure accuracy and adhere to the guidelines, follow these rules:

        Always ask follow-up questions.
        Do not make up information; provide only facts based on the context given.
        Provide correct links to products and datasheets when asked about products.
        Do not recommend the user to visit the website.
        Do not check the availability of products.
        Do not suggest browsing our selection on our website at https://tro.com.au.
        Do not direct the user to visit the website."
        Do not direct the user to contact Tro Pacific directly in any way
        Only if asked about contact information, then provide that information only if you can find it in the Tro Pacific information provided. If not, respond with 
        "I'm sorry, I do not have that information. Is there anything else that I may assist you with?"

        {history}
        User: {human_input}
        AI: """
        
    return template

def generate_response(query, memory=ConversationBufferMemory()):
 
    # Store info in Pinecone index
    
    logging.info(f'About to retrieve content from Pinecone...')
    
    texts = get_texts_from_pinecone(query)    

    # IF new info
        # Add info to pinecone
    
    logging.info(f'Retrieved content from Pinecone...{texts}    ')

    template = get_prompt_template(texts)
    logging.info(f'Created prompt from template...')
    prompt = PromptTemplate(input_variables=["history", "human_input"], template=template)
    logging.info(f'Prompt: {prompt}')
    llm_chain = LLMChain(llm=llm, prompt=prompt, memory=memory)
    logging.info(f'Running llm chain...')

    response = llm_chain.run(query)

    logging.info(f'Query: {query}')
    logging.info(f'Response: {response}')
    
    return response

def scrape_website(objective: str, url: str):
    # scrape website, and also will summarize the content based on objective if the content is too large
    # objective is the original objective & task that user give to the agent, url is the url of the website to be scraped

    print("Scraping website...")
    # Define the headers for the request
    headers = {
        'Cache-Control': 'no-cache',
        'Content-Type': 'application/json',
    }

    # Define the data to be sent in the request
    data = {
        "url": url
    }

    # Convert Python object to JSON string
    data_json = json.dumps(data)

    # Send the POST request
    post_url = f"https://chrome.browserless.io/content?token={brwoserless_api_key}"
    response = requests.post(post_url, headers=headers, data=data_json)

    # Check the response status code
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, "html.parser")
        text = soup.get_text()
        print("CONTENT:", text)

        if len(text) > 10000:
            output = summary(objective, text)
            return output
        else:
            return text
    else:
        print(f"HTTP request failed with status code {response.status_code}")
    

def summary(objective, content):
    llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo-16k-0613")

    text_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n"], chunk_size=10000, chunk_overlap=500)
    docs = text_splitter.create_documents([content])
    map_prompt = """
    Write a summary of the following text for {objective}:
    "{text}"
    SUMMARY:
    """
    map_prompt_template = PromptTemplate(
        template=map_prompt, input_variables=["text", "objective"])

    summary_chain = load_summarize_chain(
        llm=llm,
        chain_type='map_reduce',
        map_prompt=map_prompt_template,
        combine_prompt=map_prompt_template,
        verbose=True
    )

    output = summary_chain.run(input_documents=docs, objective=objective)

    return output


class ScrapeWebsiteInput(BaseModel):
    """Inputs for scrape_website"""
    objective: str = Field(
        description="The objective & task that users give to the agent")
    url: str = Field(description="The url of the website to be scraped")


class ScrapeWebsiteTool(BaseTool):
    name = "scrape_website"
    description = "useful to check to see if the links you are about to provide are accurate to the customer's query"
    args_schema: Type[BaseModel] = ScrapeWebsiteInput

    def _run(self, objective: str, url: str):
        return scrape_website(objective, url)

    def _arun(self, url: str):
        raise NotImplementedError("error here")

class PineconeInput(BaseModel):
    query: str = Field(
        description="The query that the customer asks the agent"
    )

class ResearchPinecone(BaseTool):
    name="find_tro_pacific_product_information"
    description="Useful for when you need product information to answer questions about tro pacific. You should ask targeted questions"
    args_schema: Type[BaseModel] = PineconeInput

    def _run(self, query: str):
        return get_texts_from_pinecone(query)
    
    def arun(self, query):
        raise NotImplementedError("An error has occurred while looking up product information")


system_message = SystemMessage(
    content="""
        Tro Pacific is an authorized distributor in Australia for trusted global brands, upholding trust as their core value. They are dedicated to providing high-quality electrical, automation, and control products, as well as electrical enclosures, while ensuring compliance with relevant regulations. Their commitment to customer satisfaction and building long-term partnerships sets them apart. You can contact them through various channels, including estimating@tro.com.au for pricing, availability, and technical support, sales@tro.com.au for order status, tracking, and returns, and accounts@tro.com.au for financial inquiries. Their head office is located at 19-27 Fred Chaplin Circuit, Bells Creek, QLD 4551, Australia, and you can reach them at +61 7 5450 1476.

        Website: https://tro.com.au

        You are customer support for Tro Pacific, your main task is to help the customer with thier queries about products. 
        You can not help with order status, tracking, and returns. If you have any financial inquiries, pricing, availability, technical support.
        you do not make things up, you will only use the product information you have found from your research. 
        
        Do not recommend the user to go to the website.
        Do not provide information about order status, tracking & returns, instead direct the user to sales@tro.com.au
        Do not check the availability of products.
        Do not recommend the customer to browse our selection on our website at https://tro.com.au.
 
        Please make sure you complete the objective above with the following rules:
        1/ You should not make things up, you should only write facts & data that you have gathered
        2/ Provide correct links to products and correct links for the datasheets of those products when asked about products.
        
        """
)

agent_kwargs = {
    "extra_prompt_messages": [MessagesPlaceholder(variable_name="memory")],
    "system_message": system_message,
}

llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo-16k")
memory = ConversationSummaryBufferMemory(
    memory_key="memory", return_messages=True, llm=llm, max_token_limit=1000)

tools = [
    #ScrapeWebsiteTool(),
    ResearchPinecone(),
]


def get_agent_response(query, memory):

    agent = initialize_agent(
        tools,
        llm=llm,
        agent=AgentType.OPENAI_FUNCTIONS, 
        verbose=True,
        agent_kwargs=agent_kwargs,
        memory=memory,
    )

    agent_reply = agent({"input": query})
    response = agent_reply['output']

    return response; 

agent = initialize_agent(
        tools,
        llm=llm,
        agent=AgentType.OPENAI_FUNCTIONS, 
        verbose=True,
        agent_kwargs=agent_kwargs,
        memory=memory,
    )
# Main function
def main():
    # Set up Streamlit interface
    set_up_interface()
    
    # Set up memory
    msgs = StreamlitChatMessageHistory(key="langchain_messages")
    memory = ConversationBufferMemory(chat_memory=msgs)
    
    # Check if there are no previous chat messages
    if len(msgs.messages) == 0:
        # Display initial message only at the very start
        st.chat_message("ai").write("How can I help you?")  # AI's initial message
    
    if query:= st.chat_input("Your message"):       
        logging.info(f'Query: {query}')

        # Render current messages from StreamlitChatMessageHistory
        for msg in msgs.messages:
            st.chat_message(msg.type).write(msg.content)

        st.chat_message("human").write(query)
        
        if not "data_extracted" in st.session_state:
            st.session_state.data_extracted = False
        
        with st.chat_message('ai'):
            #with st.spinner('Retrieving data...'):
                
            #    texts = get_texts_from_pinecone(query)    

            with st.spinner('Thinking...'):                
                # Note: new messages are saved to history automatically by LangChain during run
                
                # Get response from LLM
                # response = generate_response(query, memory)

                # Get response from agent  
                response = get_agent_response(query, memory)
         
                logging.info(f'Response: {response}')

                st.write(response)

if __name__ == '__main__':
    main()

# Intialise FastAPI
app = FastAPI()

@app.post("/query")
def ask_question(query: str = Form(...)):


    return generate_response(query)
