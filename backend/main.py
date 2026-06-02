from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str

@app.get("/")
def root():
    return {"status": "DokterGPT API Running"}

@app.post("/ask")
def ask(req: QueryRequest):

    return {
        "answer": f"Mock response for: {req.query}",
        "latency": 0.23,
        "sources": [
            {
                "title": "Mock Clinical Paper",
                "doi": "10.000/mock",
                "score": 0.91
            }
        ]
    }