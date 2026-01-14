import json
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="FastAPI")


# --- 6. API 엔드포인트 구현 ---
@app.get("/")
def root():
    return {"message": "Hello World"}

@app.get("/api/hello")
def read_root():
    return {"message": "Hello from FastAPI in backend folder!"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)