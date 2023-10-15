<div style='display:flex;align-items: center;'><img style='height:70px;margin-left: 15px;margin-right:20px;' src='https://terrapinn-cdn.com/tres/pa-images/10660/a0A4G00001foQKaUAM_org.png?20221213020720' /><h1 style='text-align:left;font-weight: 600;font-size:29px'>Tro Pacific Customer Support Assistant</h1></div>

## Setup instructions

### Clone from [GitHub](https://github.com/dmotts/tro-assitant)

```shell
$ git clone https://github.com/dmotts/tro-assistant.git
$ cd tro-assistant/
```

### Create .env file
```shell
$ touch .env
```

### Install and run using [Docker](https://www.docker.com/)

```shell
$ docker image build -t streamlit-agent:1.0 .
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
