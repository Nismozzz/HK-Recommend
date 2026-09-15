from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from pathlib import Path

from .agent import model_agent
from .schedule_store import add_course, delete_course, get_school, import_csv, list_courses

# Resolve configuration relative to this module, so starting uvicorn from the
# repository root still loads backend/.env.
load_dotenv(Path(__file__).with_name('.env'))


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class ManualCourse(BaseModel):
    weekday: int = Field(ge=0, le=6)
    course_code: str = Field(min_length=1, max_length=80)
    start_time: str
    end_time: str


class CsvImport(BaseModel):
    csv_text: str = Field(min_length=1, max_length=200000)


app = FastAPI(title="HK Recommend Agent API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "hk-recommend-agent"}


@app.post("/api/chat")
def chat(request: ChatRequest):
    return model_agent(request.message)


@app.get("/api/schedule")
def schedule_list():
    return {"courses": list_courses()}


@app.get("/api/profile")
def profile():
    """Return the persisted school so the UI can restore the user's context."""
    return {"school": get_school(), "has_schedule": bool(list_courses())}


@app.post("/api/schedule/manual")
def schedule_manual(course: ManualCourse):
    return {"course": add_course(course.model_dump())}


@app.post("/api/schedule/csv")
def schedule_csv(payload: CsvImport):
    return {"courses": import_csv(payload.csv_text)}


@app.delete("/api/schedule/{course_id}")
def schedule_delete(course_id: int):
    return {"deleted": delete_course(course_id)}
