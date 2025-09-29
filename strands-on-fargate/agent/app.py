import logging
import os
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import StreamingResponse, PlainTextResponse
from pydantic import BaseModel
import uvicorn
from strands import Agent

name = os.getenv("AGENT_NAME", "test")
logging.getLogger(name).setLevel(logging.INFO)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s (%(name)s) [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
app = FastAPI(title="Strands on Fargate")
agent = Agent()

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