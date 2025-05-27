import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


import os
import traceback
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from main import main

load_dotenv()

app = FastAPI()

class SubmitRequest(BaseModel):
    email: str
    password: str
    code: str
    language: str
    problemNum: int

@app.post("/start")
async def start(data: SubmitRequest):
    try:

        capsolver_key = os.getenv("capsolver_key")

        result, correct = await main(
            data.email, data.password, data.code, data.language, data.problemNum, capsolver_key
        )

        return {
            "message": result,
            "correct": correct
        }

    except Exception as e:
        print("Exception occurred:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e) or "Unknown error")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000)



