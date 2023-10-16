# Use the Python 3.10 image as the base image
FROM python:3.10-slim-bullseye

# Set environment variables for Streamlit
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

ENV HOST=0.0.0.0
 
ENV LISTEN_PORT 8503

# Set the working directory within the container
WORKDIR /tro-assistant

# Copy the application files into the container
COPY . .

# Install Python dependencies for your application
RUN pip install --no-cache-dir -r requirements.txt

# Expose the default Streamlit port
EXPOSE 8503

# Define the command to run the Streamlit app
CMD ["streamlit", "run", "--server.port", "8503", "streamlit_agent.py"]
