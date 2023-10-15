# Use a specific version of Ubuntu as the base image (e.g., 20.04 LTS)
FROM ubuntu:22.04

# Set environment variables for Streamlit
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

# Update the package list and install required packages
RUN apt-get update && \
    apt-get install -y python3.10 python3-pip graphviz && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Create a non-root user for running the application
RUN useradd -m -s /bin/bash streamlituser

# Set the working directory within the container
WORKDIR /tro-assistant

# Copy the application files into the container
COPY . .

# Install Python dependencies for your application
RUN pip3 install --no-cache-dir -r requirements.txt

# Expose the default Streamlit port
EXPOSE 8503

# Switch to the non-root user for added security
USER streamlituser

# Define the command to run the Streamlit app
CMD ["streamlit", "run", "--server.port", "8503", "streamlit_agent.py"]
