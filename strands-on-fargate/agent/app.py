import boto3
import logging
import os
import uvicorn
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import StreamingResponse, PlainTextResponse
from pydantic import BaseModel
from strands import Agent
from strands.models import BedrockModel

name = os.getenv("AGENT_NAME", "test")
logging.getLogger(name).setLevel(logging.INFO)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s (%(name)s) [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
app = FastAPI(title="Strands on Fargate")
session = boto3.Session()
model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
    # model_id="us.amazon.nova-lite-v1:0",
    max_tokens=1000,
    temperature=0.5,
    session=session
)
agent = Agent(
    model=model
)

class PromptRequest(BaseModel):
    prompt: str

async def run_agent_and_stream_response(prompt: str):
    result = agent.stream_async(prompt)
    async for chunk in result:
        if 'data' in chunk:
            logging.info(f"{chunk['data']} ({len(chunk['data'])} characters)")
            yield (chunk['data'])

@app.get('/ping')
def health_check():
    return {"message": "pong"}

@app.post("/invocations")
async def agent_invocation(request: PromptRequest):
    logging.info(f"request payload: {request}")
    try:
        if not request.prompt:
            raise HTTPException(status_code=400, detail="no prompt provided")
        return StreamingResponse(
            run_agent_and_stream_response(request.prompt),
            media_type="text/plain"
        )
    except Exception as e:
        logging.error(f"error running agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host=host, port=port)