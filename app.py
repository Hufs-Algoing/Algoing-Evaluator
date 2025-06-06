import sys
import asyncio
from contextlib import asynccontextmanager
import os
import traceback
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from main import main
from playwright.async_api import async_playwright

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

load_dotenv()

playwright = None
browser = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global playwright, browser
    playwright = await async_playwright().start()
    browser = await playwright.firefox.launch(headless=True)
    print("브라우저 실행")

    yield

    await browser.close()
    await playwright.stop()
    print("브라우저 종료")

app = FastAPI(lifespan=lifespan)

class SubmitRequest(BaseModel):
    bojId: str
    bojPassword: str
    code: str
    language: str
    problemNum: int

@app.post("/start")
async def start(data: SubmitRequest):
    try:

        capsolver_key = os.getenv("CAPSOLVER_KEY")

        result, correct = await main(
            browser,
            data.bojId, data.bojPassword, data.code, data.language, data.problemNum, capsolver_key
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



