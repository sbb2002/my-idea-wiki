from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Idea Wiki System")


@app.get("/health")
async def health():
    return {"status": "ok"}
