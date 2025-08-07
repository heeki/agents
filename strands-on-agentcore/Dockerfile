FROM public.ecr.aws/docker/library/python:3.12-slim
WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
RUN pip install aws-opentelemetry-distro>=0.10.0

# signal that this is running in Docker for host binding logic
ENV DOCKER_CONTAINER=1
ENV AWS_REGION=us-east-1
ENV AWS_DEFAULT_REGION=us-east-1

# create non-root user
RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore

EXPOSE 8080

# copy entire project (respecting .dockerignore)
COPY . .

CMD ["opentelemetry-instrument", "python", "src/agent.py"]
