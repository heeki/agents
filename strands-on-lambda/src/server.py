import logging
import os
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel
from strands import Agent, tool
from strands_tools import http_request

# define a system prompt
name = os.getenv("AGENT_NAME", "test")
logging.getLogger(name).setLevel(logging.INFO)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s (%(name)s) [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
app = FastAPI(title="Strands on Lambda")

SYSTEM_PROMPT = """You are a general purpose helpful assistant.
"""
agent = Agent(
    system_prompt=SYSTEM_PROMPT,
    tools=[http_request],
)

class PromptRequest(BaseModel):
    prompt: str

@app.post('/strands')
async def get_strands(request: PromptRequest):
    logging.info(f"request payload: {request}")
    try:
        if not request.prompt:
            raise HTTPException(status_code=400, detail="no prompt provided")
        response = agent(request.prompt)
        content = str(response)
        return PlainTextResponse(content=content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def run_agent_and_stream_response(prompt: str):
    result = agent.stream_async(prompt)
    async for chunk in result:
        if 'data' in chunk:
            logging.info(f"{chunk['data']} ({len(chunk['data'])} characters)")
            yield (chunk['data'])

@app.post('/strands-streaming')
async def get_strands_streaming(request: PromptRequest):
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