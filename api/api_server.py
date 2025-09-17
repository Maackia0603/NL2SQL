from contextlib import asynccontextmanager
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from sql_graph.text2sql_graph import make_graph


class AskRequest(BaseModel):
    question: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with make_graph() as graph:
        app.state.graph = graph
        yield


app = FastAPI(lifespan=lifespan)

# CORS 设置
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/ask")
async def ask(req: AskRequest) -> Dict[str, Any]:
    outputs: List[str] = []
    # 增加递归限制，防止无限循环
    config = {"recursion_limit": 50}
    async for event in app.state.graph.astream(
        {"messages": [{"role": "user", "content": req.question}]},
        stream_mode="values",
        config=config,
    ):
        msg = event["messages"][-1]
        content = getattr(msg, "content", None)
        outputs.append(content if isinstance(content, str) else str(content))
    return {"outputs": outputs, "final": outputs[-1] if outputs else ""}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.api_server:app", host="127.0.0.1", port=9000, reload=True)


