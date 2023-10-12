import os
import time
import glob
import shutil
import datetime
import streamlit as st
import pinecone

from config import setup_logging
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
from langchain.chat_models import ChatOpenAI
from langchain.chains.summarize import load_summarize_chain
from langchain.schema import SystemMessage

from fastapi import FastAPI, Form

# Configure logger 
logging = setup_logging()

# Configure OpenAI api key
openai_api_key = os.getenv("OPENAI_API_KEY")

# Intialise Pinecone
pinecone.init(
    api_key=os.getenv("PINECONE_API_KEY"),
    environment=os.getenv("PINECONE_ENVIRONMENT")
)

# Set embeddings
embeddings = OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY"))

# Set index name
index_name="tro-pacific"

if index_name not in pinecone.list_indexes():
    # Create new pinecone index
    pinecone.create_index(
        name=index_name,
        metric="cosine",
        dimension=1536
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

def get_context_chunks(text, header_tag='##',header='Product Information'):
    headers_to_split_on = [
        (header_tag, header) 
    ]

    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on)
    context_chunks = markdown_splitter.split_text(text)

    logging.info(f'context chunks: {context_chunks}')

    return context_chunks

def get_text_chunks(text, metadata={}):
    chunk_size = 10000
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

def store_pdf_data_to_pinecone():
    
    docs_directory = os.path.join(os.getcwd(), '/docs')  
    
    # Get pdf documents from 'docs' directory
    pdf_files = glob.glob(os.path.join(docs_directory, '*.pdf'))
    
    p = 1
    total_pdfs = len(pdf_files)
    # Get data from pdf files
    for pdf_file in pdf_files:
        with open(pdf_file, 'rb') as file:
            # Perform processing on each PDF file
        
            logging.info(f'Retrieving pdf file data...')
        
            pdf_data = get_pdf_text([file])
            
            # Split data to chunks

            logging.info(f'Splitting pdf file data into chunks...')
            
            pdf_data_chunks = get_text_chunks(pdf_data, metadata={'Document Type': 'PDF'})

            # Add chunks to pinecone index
            
            logging.info(f'Adding pdf data chunks to Pinecone...')
            
            Pinecone.from_documents(pdf_data_chunks, embeddings, index_name=index_name)
            
            logging.info(f'({p} / {total_pdfs})')
            
            p = p + 1

def store_website_data_to_pinecone():

    # Get Urls for scrapping
    urls = get_urls()
    success_scrapes = []
    failed_scrapes = []

    # Get data from pdf files
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

    logging.info(f'Pinecone Docs: {vectorstore}')

    texts = vectorstore.similarity_search(query)

    retriever = vectorstore.as_retriever(search_type="mmr")
    matched_docs = retriever.get_relevant_documents(query)
 
    joined_docs = ""
    for i, d in enumerate(matched_docs):
        print(f"\n## Document {i}\n")
        print(d.page_content)
        joined_docs = ''.join(d.page_content)

    texts = joined_docs

    logging.info(f'Pinecone joined docs: {texts}')

    return texts    


system_message = SystemMessage(
    content="""You are customer support for Tro Pacific, who can do detailed research on any topic and produce facts based results; 
           you do not make things up, you will try as hard as possible to gather facts & data to back up the research
            
            Please make sure you complete the objective above with the following rules:
            1/ You should do enough research to gather as much information as possible about the objective
            2/ If there are url of relevant links & articles, you will scrape it to gather more information
            3/ After scraping & search, you should think "is there any new things i should search & scraping based on the data I collected to increase research quality?" If answer is yes, continue; But don't do this more than 3 iteratins
            4/ You should not make things up, you should only write facts & data that you have gathered
            5/ In the final output, You should include all reference data & links to back up your research; You should include all reference data & links to back up your research
            6/ In the final output, You should include all reference data & links to back up your research; You should include all reference data & links to back up your research"""
)

agent_kwargs = {
    "extra_prompt_messages": [MessagesPlaceholder(variable_name="memory")],
    "system_message": system_message,
}

llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo-16k-0613")
memory = ConversationSummaryBufferMemory(
    memory_key="memory", return_messages=True, llm=llm, max_token_limit=1000)

agent = initialize_agent(
    llm=llm,
    agent=AgentType.OPENAI_FUNCTIONS,
    verbose=True,
    agent_kwargs=agent_kwargs,
    memory=memory,
)



def set_up_interface():
    # Set up Streamlit interface
    st.markdown("<div style='text-align:center;'> <img style='width:340px;' src='https://www.ipenclosures.com.au/wp-content/uploads/IP-EnclosuresNZ-Logo-.png.webp' /></div>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align:center;'>IP Enclosures AI Assistant</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;'>Welcome to IP Enclosures AI Assistant! Please feel free to ask any question.</p>", unsafe_allow_html=True)

def get_prompt_template(docs):
    template = """
        Background Information:
        Tro Pacific are authorised distributors for trusted global brands.

        As distributors in Australia for trusted global brands, you can be confident and assured that we provide the highest quality product that is certified and compliant with relevant statutory regulations in Australia.

        Tro means TRUST and this is the core of our success. Trust is our core value. It is our deeply engrained principle that guides behaviour, decisions and actions of our entire organisation.


        We aim to be a world-class trusted business partner offering quality and value in everything we do. Our technical customer support professionals aim to provide 100% customer satisfaction. We transform customer relationships into high performance partnerships to ensure that our customers achieve success. With decades of experience, we continue to build trust and confidence within the markets we serve. It is our industry knowledge and experience coupled with our commitment to personal service that enables Tro Pacific to meet your needs.

        ELECTRICAL. AUTOMATION. CONTROL.

        Tro Pacific is a leading stockist of industrial electrical, automation and control system products and is also a leading Australian stockist of a full range of electrical enclosures.

        As authorised distributors in Australia for many trusted global brands, you can be confident and assured that we provide the highest quality product that is certified and compliant with relevant statutory regulations in Australia.

        Tro Pacific consistently aims to provide quality product and service that meets customer, statutory and regulatory requirements while aiming to enhance customer satisfaction in accordance with the requirements of ISO9001:2015.
    
        Contact our friendly customer service team for quotes, price lists, product information and general inquiries the contact details or form below:

        PHONE - 1300 876 722

        Pricing, availability & technical support - estimating@tro.com.au

        Order status, tracking & returns - sales@tro.com.au

        Accounts & financial - accounts@tro.com.au

        Tro Pacific Holdings Pty Ltd t/a Tro Pacific

        ABN 94 168 980 854

        HEAD OFFICE
        19-27 Fred Chaplin Circuit, Bells Creek QLD 4551 Australia

        Phone: +61 7 5450 1476

        NSW WAREHOUSE
        Unit 5, 2-8 South St Rydalmere, NSW 2116 Australia


        """
    template += "Context: "
    template += ''.join(docs) # convert docs from list to str
    
    template += """You are an customer support assistant for Tro Pacific. Assist the customer when asked queries. Find the best solution for the customer. 
        
        Only make suggestions to products that are of Tro Pacific or a reseller/distributor/partner of Tro Pacific. 
        
        Please make your answers short and concise when possible. 

        Respond in a light friendly but professional tone.
        
        Use that infomation to find the best solution to the USER's query.

        Please follow the following instructions:
        
        - BEFORE ANSWERING THE QUESTION, ASK A FOLLOW UP QUESTION.
        
        - USE THE CONTEXT PROVIDED TO ANSWER THE USER QUESTION. DO NOT MAKE ANYTHING UP.
        
        - IF RELEVANT, BREAK YOUR ANSWER DO INTO STEPS
        
        - If suitable to the answer, provide any recommendations to products from Tro Pacific's website or any of their partners/distributors/resellers if listed on their website.
        
        - FORMAT YOUR ANSWER IN MARKDOWN
        
        - ALWAYS ASK FOLLOW UP QUESTIONS!

        - DO NOT MAKE ANYTHING UP    

        - From the content provided, do the following to provide the user with a solution to their query:
            - DO NOT MAKE ANYTHING UP ONLY USE THE CONTENT PROVIDED TO ANSWER THE USER QUESTIONS, IF YOU CAN'T FIND A SUITABLE, RELATED ANSWER
            THEN GIVE THE USER DIRECTIONS ON HOW THEY MAY FIND A SOLUTION TO THEIR QUERY.
            
        DO NOT PROVIDE A SUGGESTION TO ANY PRODUCT THAT IS NOT LISTED ON TRO PACIFIC OR ANY OF THEIR PARTNERS/DISTRIBUTORS/RESELLERS.
        
        DO NOT MAKE ANYTHING UP, ONLY USE THE CONTEXT PROVIDED!!

        DO NOT MAKE PRODUCT SUGGESTIONS TO THE ANY COMPETITOR'S PRODUCTS.
      
        DO NOT MENTION THE TERMS "on our website"

        DO NOT RECOMMEND USER TO GO TO THE WEBSITE.

        IF YOUR RESPONSE INCLUDES A PRODUCT, PROVIDE THE LINK TO THE PRODUCT AND THE LINKS FOR ALL OF THE DATA SHEETS FOR THAT PRODUCT

        {history}
        Human: {human_input}
        AI: """
        
    return template

def generate_response(query, memory=ConversationBufferMemory()):
 
    # Store info in Pinecone index
    logging.info(f'About to retrieve content from Pinecone...')

    # IF new info
        # Add info to pinecone
    
    texts = get_texts_from_pinecone(query)    

    logging.info(f'Retrieved content from Pinecone...{texts}    ')

    template = get_prompt_template(texts)
    logging.info(f'Created prompt from template...')
    prompt = PromptTemplate(input_variables=["history", "human_input"], template=template)
    logging.info(f'Prompt: {prompt}')
    llm_chain = LLMChain(llm=OpenAI(model='gpt-3.5-turbo-16k', openai_api_key=openai_api_key), prompt=prompt, memory=memory)
    logging.info(f'Running llm chain...')

    response = llm_chain.run(query)

    logging.info(f'Query: {query}')
    logging.info(f'Response: {response}')
    
    return response

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
            with st.spinner('Thinking...'):                
                # Note: new messages are saved to history automatically by LangChain during run
                response = generate_response(query, memory)
                
                logging.info(f'Response: {response}')

                st.write(response)

if __name__ == '__main__':
    main()

# Intialise FastAPI
app = FastAPI()

@app.post("/query")
def ask_question(query: str = Form(...)):
    return generate_response(query)
