import os
import streamlit as st
import json
import requests
import langsmith

from langchain.chains.summarize import load_summarize_chain
from langchain.prompts import PromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.agents import AgentType, initialize_agent, ConversationalChatAgent, AgentExecutor
from langchain.callbacks import StreamlitCallbackHandler
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.memory.chat_message_histories import StreamlitChatMessageHistory
from langchain.tools import DuckDuckGoSearchRun
from langchain.schema import SystemMessage
from bs4 import BeautifulSoup
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type
from app import get_texts_from_pinecone
from config import setup_logging

# Set browserless api key
browserless_api_key = os.environ.get('BROWSERLESS_API_KEY', os.getenv('BROWSERLESS_API_KEY'))

# Configure logger 
logging = setup_logging()

def set_up_interface():
    """
    Sets up the Streamlit interface for the Tro Pacific Customer Support Assistant.
    """
    st.set_page_config(page_title="Tro Pacific Customer Support Assistant")
    st.markdown(" <div style='display:flex;align-items: center;'><img style='height:70px;margin-left: 15px;margin-right:20px;' src='https://terrapinn-cdn.com/tres/pa-images/10660/a0A4G00001foQKaUAM_org.png?20221213020720' /><div style='text-align:left;font-weight: 600;font-size:29px'>Tro Pacific Customer Support Assistant</div></div>", unsafe_allow_html=True)

def scrape_website(objective: str, url: str, browserless_api_key: str):
    """
    Scrapes a website and provides a summary based on the objective if the content is too large.
    
    Args:
        objective (str): The original objective & task that the user gives to the agent.
        url (str): The URL of the website to be scraped.
        browserless_api_key (str): The API key for browserless.io.
    
    Returns:
        str: The scraped website content or a summary based on the objective.
    """
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
    post_url = f"https://chrome.browserless.io/content?token={browserless_api_key}"
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

def summary(objective: str, content: str):
    """
    Generates a summary of the provided content based on the given objective.
    
    Args:
        objective (str): The objective or task.
        content (str): The content to be summarized.
    
    Returns:
        str: The generated summary.
    """
    llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo-16k-0613")
    text_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n"], chunk_size=10000, chunk_overlap=500)
    docs = text_splitter.create_documents([content])
    map_prompt = f"""
    Write a summary of the following text for {objective}:
    "{content}"
    SUMMARY:
    """
    map_prompt_template = PromptTemplate(
        template=map_prompt, input_variables=["text"])
    summary_chain = load_summarize_chain(
        llm=llm,
        chain_type='map_reduce',
        map_prompt=map_prompt_template,
        combine_prompt=map_prompt_template,
        verbose=True
    )
    output = summary_chain.run(input_documents=docs)
    return output
class ScrapeWebsiteInput(BaseModel):
    """
    Inputs for the 'scrape_website' tool.
    
    Args:
        objective (str): The objective & task that users give to the agent.
        url (str): The URL of the website to be scraped.
    """
    objective: str = Field(
        description="The objective & task that users give to the agent")
    url: str = Field(description="The URL of the website to be scraped")

class ScrapeWebsiteTool(BaseTool):
    name = "scrape_website"
    description = "Useful for checking the accuracy of provided links in response to customer queries."
    args_schema: Type[BaseModel] = ScrapeWebsiteInput

    def _run(self, objective: str, url: str):
        """
        Executes the 'scrape_website' tool with the provided objective and URL.

        Args:
            objective (str): The objective & task.
            url (str): The URL to be scraped.

        Returns:
            Any: The result of the 'scrape_website' operation.
        """
        return scrape_website(objective, url)

    def _arun(self, url: str):
        raise NotImplementedError("This method is not implemented yet.")

class PineconeInput(BaseModel):
    """
    Inputs for 'ResearchPinecone' tool.
    
    Args:
        query (str): The query that the customer asks the agent.
    """
    query: str = Field(
        description="The query that the customer asks the agent")

class ResearchPinecone(BaseTool):
    name = "Searching for"
    description = "Only use this tool for looking up product information to answer questions about Tro Pacific products."
    args_schema: Type[BaseModel] = PineconeInput

    def _run(self, query: str):
        """
        Executes the 'ResearchPinecone' tool with the provided query.

        Args:
            query (str): The customer's query.

        Returns:
            Any: The result of the 'ResearchPinecone' operation.
        """
        return get_texts_from_pinecone(query)

    def arun(self, query):
        raise NotImplementedError("An error has occurred while looking up product information.")


def main():
    """
    Main function for the Tro Pacific Customer Support Assistant.
    """
    # Set up Streamlit interface
    set_up_interface()
    
    openai_api_key = os.environ.get('OPENAI_API_KEY', os.getenv('OPENAI_API_KEY'))

    msgs = StreamlitChatMessageHistory()
    memory = ConversationBufferMemory(
        chat_memory=msgs, return_messages=True, memory_key="chat_history", output_key="output"
    )

    if len(msgs.messages) == 0:
        msgs.clear()
        msgs.add_ai_message("Hi! Welcome to Tro Pacific! How can I assist you today?")
        st.session_state.steps = {}
    
    avatars = {"human": "user", "ai": "assistant"}
    for idx, msg in enumerate(msgs.messages):
        with st.chat_message(avatars[msg.type]):
            # Render intermediate steps if any were saved
            for step in st.session_state.steps.get(str(idx), []):
                if step[0].tool == "_Exception":
                    continue
                with st.status(f"**{step[0].tool}**: {step[0].tool_input}", state="complete"):
                    st.write(step[0].log)
                    logging.info(f'Step: {step[0].log}')
                    st.write(step[1])
                    logging.info(f'Step: {step[1]}')
                    
            st.write(msg.content)

    if prompt := st.chat_input():
        st.chat_message("user").write(prompt)
        logging.info(f'User: {prompt}')

        llm = ChatOpenAI(model_name="gpt-3.5-turbo-16k", openai_api_key=openai_api_key, streaming=True)
        
        tools = [
            #DuckDuckGoSearchRun(name="Search"),
            #ScrapeWebsiteTool(),
            ResearchPinecone(),
        ]

        system_message = """
                Tro Pacific is an authorized distributor in Australia for trusted global brands, upholding trust as their core value. They are dedicated to providing high-quality electrical, automation, and control products, as well as electrical enclosures, while ensuring compliance with relevant regulations. Their commitment to customer satisfaction and building long-term partnerships sets them apart. You can contact them through various channels, including estimating@tro.com.au for pricing, availability, and technical support, sales@tro.com.au for order status, tracking, and returns, and accounts@tro.com.au for financial inquiries. Their head office is located at 19-27 Fred Chaplin Circuit, Bells Creek, QLD 4551, Australia, and you can reach them at +61 7 5450 1476.

            Website: https://tro.com.au

            "I want you to act as a Tro Pacific representative. Your goal is make the user feel special and provide accurate information. Only use information for your research to answer the user's questions

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

            """

        chat_agent = ConversationalChatAgent.from_llm_and_tools(llm=llm, tools=tools, system_message=system_message)
        
        executor = AgentExecutor.from_agent_and_tools(
            agent=chat_agent,
            tools=tools,
            memory=memory,
            return_intermediate_steps=True,
            handle_parsing_errors=True,
        )

        with st.chat_message("assistant"):
            st_cb = StreamlitCallbackHandler(st.container(), expand_new_thoughts=False)
            response = executor(prompt, callbacks=[st_cb])
            logging.info(f'Agent Response: {response}')
            st.write(response["output"])
            logging.info(f'Agent Answer: {response["output"]}')
            st.session_state.steps[str(len(msgs.messages) - 1)] = response["intermediate_steps"]

if __name__== '__main__':
    main()