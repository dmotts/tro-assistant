import os
import streamlit as st

from langchain.agents import initialize_agent, Tool
from langchain.agents import AgentType
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationSummaryBufferMemory
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.summarize import load_summarize_chain
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type
from bs4 import BeautifulSoup
import requests
import json
from langchain.schema import SystemMessage
from fastapi import FastAPI

browserless_api_key = os.getenv("BROWSERLESS_API_KEY")
serper_api_key = os.getenv("SERP_API_KEY")

# 1. Tool for search


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

def get_agent(llm=llm, memory=memory):
    agent = initialize_agent(
        tools,
        llm=llm,
        agent=AgentType.OPENAI_FUNCTIONS, 
        verbose=True,
        agent_kwargs=agent_kwargs,
        memory=memory,
    )

    return agent

agent = get_agent()

# Intialise FastAPI
app = FastAPI()
@app.get("/")
#def researchAgent(query: Query):
def researchAgent():
    #query = query.query
    query = """
        "https://www.ls-electric.com/support/download-center" 
        
        On this website, you should find a link to [Device]_Electric_Product_EN_C19912-63-202309.pdf(18.91MB). Can you confirm an provide the href link?
        
        """
    
    content = agent({"input": query})
    actual_content = content['output']
    return actual_content
