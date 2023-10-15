# Use a specific version of Ubuntu as the base image (e.g., 20.04 LTS)
FROM ubuntu:22.04

# Update the package list and install required packages
RUN apt-get update && \
    apt-get install -y python3.10 python3-pip graphviz

# Expose the default Streamlit port
EXPOSE 8503

# Set the working directory within the container
WORKDIR /tro-assistant

# Copy the requirements file and install dependencies
COPY requirements.txt ./requirements.txt
RUN pip3 install -r requirements.txt

# Copy the application files into the container
COPY . .

# Set environment variables for Streamlit
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

# Configure Streamlit (if needed)
RUN mkdir -p /root/.streamlit
RUN bash -c 'echo -e "[general]\nemail = \"\"\n" > /root/.streamlit/credentials.toml'
RUN bash -c 'echo -e "[server]\nenableCORS = false\n" > /root/.streamlit/config.toml'

# Define the command to run the Streamlit app
CMD ["streamlit", "run", "--server.port", "8503", "streamlit_agent.py"]
