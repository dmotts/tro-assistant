# base image
# a little overkill but need it to install dot cli for dtreeviz
FROM ubuntu:22.04

# ubuntu installing - python, pip, graphviz, nano, libpq (for psycopg2)
RUN apt-get update &&\
    apt-get install python3.10 -y &&\
    apt-get install python3-pip -y &&\
    apt-get install graphviz -y

# exposing default port for streamlit
EXPOSE 8503

# making directory of app
WORKDIR /tro-assistant

# copy over requirements
COPY requirements.txt ./requirements.txt

# install pip then packages
RUN pip3 install -r requirements.txt

# copying all files over
COPY . .

# set environment variables 

# cmd to launch app when container is run
CMD streamlit run -p 8503 streamlit_agent.py

# streamlit-specific commands for config
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
RUN mkdir -p /root/.streamlit
RUN bash -c 'echo -e "\
[general]\n\
email = \"\"\n\
" > /root/.streamlit/credentials.toml'

RUN bash -c 'echo -e "\
[server]\n\
enableCORS = false\n\
" > /root/.streamlit/config.toml'