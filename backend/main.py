import json
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from transformers import pipeline

app = FastAPI(title="Movie Review AI API")

# --- 1. 파일 경로 설정 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MOVIES_FILE = os.path.join(BASE_DIR, "data", "movies.json")

# --- 2. 데이터 로드 함수 ---
def load_movies():
    if os.path.exists(MOVIES_FILE):
        with open(MOVIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# --- 1. AI 모델 로드 (경량화된 한국어 감성 분석 모델) ---
# 모델 로딩은 서버 시작 시 한 번만 실행됩니다.
print("Loading AI Model...")
classifier = pipeline(
    "sentiment-analysis",
    model="monologg/koelectra-small-v3-discriminator"
)
print("Model Loaded Successfully!")

# --- 2. 임시 데이터 저장소 (DB 대신 리스트 사용) ---
# 초기 로드
movies = load_movies()
reviews = []

# 다음 ID 설정을 위해 현재 영화 중 가장 높은 ID + 1 계산
movie_id_counter = max([m["id"] for m in movies], default=0) + 1


# --- 3. 데이터 모델(Pydantic) 정의 ---
class MovieCreate(BaseModel):
    title: str
    director: str
    genre: str
    release_date: str
    poster_url: str


class ReviewCreate(BaseModel):
    movie_id: int
    content: str


# --- 4. API 엔드포인트 구현 ---

# [영화 관련 API]
@app.get("/movies/")
def get_movies():
    return movies


@app.post("/movies/")
def create_movie(movie: MovieCreate):
    global movie_id_counter
    new_movie = movie.dict()
    new_movie["id"] = movie_id_counter
    movies.append(new_movie)
    movie_id_counter += 1
    return new_movie


@app.delete("/movies/{movie_id}")
def delete_movie(movie_id: int):
    global movies
    movies = [m for m in movies if m["id"] != movie_id]
    return {"message": "Movie deleted"}


# [리뷰 및 감성 분석 API]
@app.post("/reviews/")
def create_review(review: ReviewCreate):
    # 1. 해당 영화가 있는지 확인
    movie = next((m for m in movies if m["id"] == review.movie_id), None)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    # 2. AI 감성 분석 수행
    prediction = classifier(review.content)[0]
    # 모델 출력값에 따라 LABEL_0, LABEL_1 또는 POSITIVE, NEGATIVE로 나옵니다.
    # 여기서는 간단히 점수에 따라 가공합니다.
    label = "POSITIVE" if prediction['label'] == 'LABEL_1' else "NEGATIVE"

    new_review = {
        "movie_id": review.movie_id,
        "movie_title": movie["title"],
        "content": review.content,
        "sentiment": label,
        "sentiment_score": round(prediction['score'], 4),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    reviews.append(new_review)
    return new_review


@app.get("/reviews/recent")
def get_recent_reviews():
    # 최신순으로 10개 반환
    return reviews[::-1][:10]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)