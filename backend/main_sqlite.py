import sqlite3
import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from transformers import pipeline

app = FastAPI(title="Movie Review AI API (SQLite3)")

# --- 1. 경로 및 DB 설정 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "movie_app.db")
# 기존 JSON 파일 경로 (데이터 마이그레이션용)
MOVIES_JSON = os.path.join(BASE_DIR, "data", "movies.json")
REVIEWS_JSON = os.path.join(BASE_DIR, "data", "reviews.json")


# --- 2. DB 초기화 및 테이블 생성 ---
def get_db_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # 결과를 딕셔너리 형태로 받기 위함
    return conn


def init_db():
    conn = get_db_conn()
    cursor = conn.cursor()
    # 영화 테이블
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS movies
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       title
                       TEXT,
                       director
                       TEXT,
                       genre
                       TEXT,
                       release_date
                       TEXT,
                       poster_url
                       TEXT
                   )
                   """)
    # 리뷰 테이블
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS reviews
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       movie_id
                       INTEGER,
                       movie_title
                       TEXT,
                       content
                       TEXT,
                       sentiment
                       TEXT,
                       sentiment_score
                       REAL,
                       created_at
                       TEXT,
                       FOREIGN
                       KEY
                   (
                       movie_id
                   ) REFERENCES movies
                   (
                       id
                   )
                       )
                   """)

    # [데이터 마이그레이션] 기존 JSON이 있으면 DB로 이전
    cursor.execute("SELECT COUNT(*) FROM movies")
    if cursor.fetchone()[0] == 0:
        if os.path.exists(MOVIES_JSON):
            print("Migrating movies.json to SQLite...")
            with open(MOVIES_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
                for m in data:
                    cursor.execute(
                        "INSERT INTO movies (id, title, director, genre, release_date, poster_url) VALUES (?,?,?,?,?,?)",
                        (m.get('id'), m.get('title'), m.get('director'), m.get('genre'), m.get('release_date'),
                         m.get('poster_url')))

        if os.path.exists(REVIEWS_JSON):
            print("Migrating reviews.json to SQLite...")
            with open(REVIEWS_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
                for r in data:
                    cursor.execute(
                        "INSERT INTO reviews (movie_id, movie_title, content, sentiment, sentiment_score, created_at) VALUES (?,?,?,?,?,?)",
                        (r.get('movie_id'), r.get('movie_title'), r.get('content'), r.get('sentiment'),
                         r.get('sentiment_score'), r.get('created_at')))

    conn.commit()
    conn.close()


# 서버 시작 시 DB 초기화
init_db()

# --- 3. AI 모델 로드 ---
print("Loading AI Model...")
classifier = pipeline("sentiment-analysis", model="monologg/koelectra-small-v3-discriminator")
print("Model Loaded!")


# --- 4. 데이터 모델 ---
class MovieCreate(BaseModel):
    title: str
    director: str
    genre: str
    release_date: str
    poster_url: str


class ReviewCreate(BaseModel):
    movie_id: int
    content: str


# --- 5. API 엔드포인트 ---

@app.get("/movies/")
def get_movies():
    conn = get_db_conn()
    movies = conn.execute("SELECT * FROM movies").fetchall()
    conn.close()
    return [dict(row) for row in movies]


@app.post("/movies/")
def create_movie(movie: MovieCreate):
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO movies (title, director, genre, release_date, poster_url) VALUES (?, ?, ?, ?, ?)",
        (movie.title, movie.director, movie.genre, movie.release_date, movie.poster_url)
    )
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"id": new_id, **movie.dict()}


@app.delete("/movies/{movie_id}")
def delete_movie(movie_id: int):
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM movies WHERE id = ?", (movie_id,))
    cursor.execute("DELETE FROM reviews WHERE movie_id = ?", (movie_id,))  # Cascade Delete
    conn.commit()
    conn.close()
    return {"message": "Movie and related reviews deleted"}


@app.post("/reviews/")
def create_review(review: ReviewCreate):
    conn = get_db_conn()
    movie = conn.execute("SELECT title FROM movies WHERE id = ?", (review.movie_id,)).fetchone()
    if not movie:
        conn.close()
        raise HTTPException(status_code=404, detail="Movie not found")

    prediction = classifier(review.content)[0]
    label = "POSITIVE" if prediction['label'] == 'LABEL_1' else "NEGATIVE"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO reviews (movie_id, movie_title, content, sentiment, sentiment_score, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (review.movie_id, movie['title'], review.content, label, round(prediction['score'], 4), now)
    )
    conn.commit()
    conn.close()
    return {"status": "success"}


@app.get("/reviews/")
def get_reviews(movie_id: Optional[int] = None):
    conn = get_db_conn()
    if movie_id:
        rows = conn.execute("SELECT * FROM reviews WHERE movie_id = ? ORDER BY created_at DESC", (movie_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM reviews ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/reviews/recent")
def get_recent_reviews(limit: int = 10):
    conn = get_db_conn()
    rows = conn.execute("SELECT * FROM reviews ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)