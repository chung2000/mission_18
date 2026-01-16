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
DATA_DIR = os.path.join(BASE_DIR, "data")
MOVIES_FILE = os.path.join(DATA_DIR, "movies.json")
REVIEWS_FILE = os.path.join(DATA_DIR, "reviews.json")

# data 폴더가 없으면 생성
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)


# --- 2. 데이터 로드 및 저장 유틸리티 ---
def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def save_json(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- 2. 임시 데이터 저장소 (DB 대신 리스트 사용) ---
# --- 3. 초기 데이터 로드 ---
print("Initializing Data...")
movies = load_json(MOVIES_FILE)
reviews = load_json(REVIEWS_FILE)

# 다음 ID 설정을 위해 현재 영화 중 가장 높은 ID + 1 계산
movie_id_counter = max([m["id"] for m in movies], default=0) + 1

# --- 1. AI 모델 로드 (경량화된 한국어 감성 분석 모델) ---
# 모델 로딩은 서버 시작 시 한 번만 실행됩니다.
print("Loading AI Model...")
classifier = pipeline(
    "sentiment-analysis",
    model="monologg/koelectra-small-v3-discriminator"
)
print("Model Loaded Successfully!")
print("Server Ready!")


# --- 5. 데이터 모델(Pydantic) ---
class MovieCreate(BaseModel):
    title: str
    director: str
    genre: str
    release_date: str
    poster_url: str


class ReviewCreate(BaseModel):
    movie_id: int
    content: str


# --- 6. API 엔드포인트 구현 ---
@app.get("/")
def root():
    return {"message": "Movie Review AI API is running"}

@app.get("/api/hello")
def read_root():
    return {"message": "Hello from FastAPI in backend folder!"}

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

    # 영화 추가 시 파일에 저장(백업)
    save_json(MOVIES_FILE, movies)

    movie_id_counter += 1
    return new_movie


# ... (상단 import 및 load_json, save_json 유틸리티는 동일)

# [영화 삭제 API]
@app.delete("/movies/{movie_id}")
def delete_movie(movie_id: int):
    global movies, reviews
    # 1. 영화 존재 여부 확인
    movie_exists = any(m["id"] == movie_id for m in movies)
    if not movie_exists:
        raise HTTPException(status_code=404, detail="Movie not found")

    # 2. 영화 삭제 및 데이터 갱신
    movies = [m for m in movies if m["id"] != movie_id]
    save_json(MOVIES_FILE, movies)

    # 3. (옵션) 삭제된 영화에 달린 리뷰도 함께 삭제 (Cascade Delete)
    reviews = [r for r in reviews if r["movie_id"] != movie_id]
    save_json(REVIEWS_FILE, reviews)

    return {"message": f"Movie {movie_id} and its reviews have been deleted."}


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

    # 메모리에 추가 후 파일에 즉시 백업
    reviews.append(new_review)
    save_json(REVIEWS_FILE, reviews)

    return new_review


@app.get("/reviews/")
def get_all_reviews(movie_id: Optional[int] = None):
    """
    모든 리뷰를 최신순으로 가져옵니다.
    movie_id가 쿼리 파라미터로 들어오면 해당 영화의 리뷰만 필터링합니다.
    """
    # 전체 리뷰를 최신순으로 정렬
    sorted_reviews = reviews[::-1]

    if movie_id is not None:
        return [r for r in sorted_reviews if r["movie_id"] == movie_id]

    return sorted_reviews


@app.get("/reviews/recent")
def get_recent_reviews(limit: int = 10):
    """최신 리뷰를 지정된 개수만큼 가져옵니다. (기본 10개)"""
    return reviews[::-1][:limit]

# (기타 삭제 등의 API도 동일하게 save_json을 호출하도록 구성)
# [리뷰 삭제 API]
@app.delete("/reviews/")
def delete_all_reviews():
    global reviews
    reviews = []
    save_json(REVIEWS_FILE, reviews)
    return {"message": "All reviews have been deleted."}


# [리뷰 개별 삭제 API]
@app.delete("/reviews/{index}")
def delete_specific_review(index: int):
    global reviews
    try:
        # 최신순 정렬 상태에서의 인덱스일 경우를 대비해 로직 확인 필요
        # 여기서는 원본 리스트의 인덱스를 기준으로 삭제합니다.
        reviews.pop(index)
        save_json(REVIEWS_FILE, reviews)
        return {"message": "Review deleted"}
    except IndexError:
        raise HTTPException(status_code=404, detail="Review index out of range")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)