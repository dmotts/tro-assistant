<div style="width:100%;text-align:center">
  <img src="https://terrapinn-cdn.com/tres/pa-images/10660/a0A4G00001foQKaUAM_org.png?20221213020720" alt="Tro Pacific Logo" />
</div>

# Tro Pacific Customer Support Assistant

## Setup instructions

### Clone from [GitHub](https://github.com/dmotts/tro-assitant)

```shell
$ git clone https://github.com/dmotts/tro-assistant.git
$ cd tro-assistant/
```

### Configure the environment variables

To run this application, you need to set the following environment variables:

- `FIREFOX_LOCATION`: Path to your Firefox installation.
- `OPENAI_API_KEY`: Your OpenAI API key.
- `BROWSERLESS_API_KEY`: Your Browserless API key.
- `PINECONE_API_KEY`: Your Pinecone API key.
- `PINECONE_ENVIRONMENT`: Your Pinecone environment.
- `SERPER_API_KEY`: Your Serper API key.
- `LANGCHAIN_ENDPOINT`: Your Langchain endpoint.
- `LANGCHAIN_API_KEY`: Your Langchain API key.

You can set these environment variables by

1. **Using a .env File**: Create a `.env` file in the project root directory and add your environment variables like this:

   ```plaintext
   FIREFOX_LOCATION=/path/to/firefox
   OPENAI_API_KEY=your-openai-api-key
   BROWSERLESS_API_KEY=your-browserless-api-key
   PINECONE_API_KEY=your-pinecone-api-key
   PINECONE_ENVIRONMENT=your-pinecone-environment
   SERPER_API_KEY=your-serper-api-key
   LANGCHAIN_ENDPOINT=your-langchain-endpoint
   LANGCHAIN_API_KEY=your-langchain-api-key
    ```

### Install and run using [Docker](https://www.docker.com/)

```shell
$ docker build -t streamlit-agent:1.0 .
$ docker container run -p 8503:8503 -d --env-file .env streamlit-agent:1.0
```

Then, the web app will be available at `http://localhost:8503/`

To shut down the web app when you're done, you can find the process running your container with

```shell
$ docker ps | grep 'streamlit-agent:1.0'
6d1871137019        streamlit-agent:1.0       "/bin/sh -c 'streaml…"   8 minutes ago       Up 8 minutes        0.0.0.0:8503->8503/tcp   <weird_name>
```

Then stop that process with the following command.

```shell
$ docker kill <weird_name>
```

To view the logs
```shell
$ docker logs <weird_name>
```
