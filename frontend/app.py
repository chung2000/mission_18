import streamlit as st
import requests
import pandas as pd

# FastAPI 서버 주소 (로컬 실행 시 기본값)
# 배포 시에는 실제 백엔드 URL로 변경해야 합니다.
BACKEND_URL = "http://localhost:8000"

st.set_page_config(page_title="영화 리뷰 감성 분석 서비스", layout="wide")

st.title("🎬 AI 영화 리뷰 감성 분석 서비스")
st.markdown("---")

# 사이드바: 영화 추가 기능
with st.sidebar:
    st.header("➕ 새 영화 등록")
    with st.form("movie_form"):
        title = st.text_input("영화 제목")
        director = st.text_input("감독")
        genre = st.text_input("장르")
        release_date = st.date_input("개봉일")
        poster_url = st.text_input("포스터 이미지 URL")

        submit_movie = st.form_submit_button("영화 등록")

        if submit_movie:
            movie_data = {
                "title": title,
                "director": director,
                "genre": genre,
                "release_date": str(release_date),
                "poster_url": poster_url
            }
            response = requests.post(f"{BACKEND_URL}/movies/", json=movie_data)
            if response.status_code == 200:
                st.success("영화가 등록되었습니다!")
                st.rerun()
            else:
                st.error("등록 실패: 백엔드 서버를 확인하세요.")

# 메인 화면: 영화 목록 및 리뷰 관리
tabs = st.tabs(["🎥 영화 목록", "✍️ 리뷰 작성", "📊 리뷰 히스토리"])

# 1. 영화 목록 탭
with tabs[0]:
    st.subheader("현재 상영 중인 영화")
    response = requests.get(f"{BACKEND_URL}/movies/")
    if response.status_code == 200:
        movies = response.json()
        if not movies:
            st.info("등록된 영화가 없습니다.")
        else:
            cols = st.columns(3)
            for idx, movie in enumerate(movies):
                with cols[idx % 3]:
                    ##st.image(movie['poster_url'], use_container_width=True)
                    st.image(movie['poster_url'], width=200)
                    ##st.bold(movie['title'])
                    st.caption(f"{movie['genre']} | {movie['director']}")
                    if st.button(f"삭제", key=f"del_{movie['id']}"):
                        requests.delete(f"{BACKEND_URL}/movies/{movie['id']}")
                        st.rerun()
    else:
        st.error("데이터를 불러올 수 없습니다.")

# 2. 리뷰 작성 탭 (감성 분석 포함)
with tabs[1]:
    st.subheader("리뷰 남기기")
    response = requests.get(f"{BACKEND_URL}/movies/")
    if response.status_code == 200:
        movies = response.json()
        movie_options = {m['title']: m['id'] for m in movies}

        selected_movie_title = st.selectbox("영화를 선택하세요", options=list(movie_options.keys()))
        review_content = st.text_area("리뷰 내용을 입력하세요", placeholder="이 영화 정말 재밌어요!")

        if st.button("리뷰 등록 및 AI 분석"):
            if review_content:
                review_data = {
                    "movie_id": movie_options[selected_movie_title],
                    "content": review_content
                }
                # 리뷰 등록 API 호출 (이때 백엔드에서 감성 분석 수행)
                res = requests.post(f"{BACKEND_URL}/reviews/", json=review_data)
                if res.status_code == 200:
                    result = res.json()
                    st.success("리뷰 등록 완료!")

                    # 분석 결과 표시
                    sentiment = result['sentiment']  # 'POSITIVE' or 'NEGATIVE'
                    score = result['sentiment_score']

                    if sentiment == "POSITIVE":
                        st.balloons()
                        st.info(f"😊 AI 분석 결과: **긍정적**인 리뷰입니다! (신뢰도: {score:.2f})")
                    else:
                        st.warning(f"🤔 AI 분석 결과: **부정적**인 리뷰입니다. (신뢰도: {score:.2f})")
                else:
                    st.error("리뷰 등록에 실패했습니다.")
            else:
                st.warning("내용을 입력해주세요.")

# 3. 리뷰 히스토리 탭
with tabs[2]:
    st.subheader("최근 리뷰 히스토리")
    res = requests.get(f"{BACKEND_URL}/reviews/recent")
    if res.status_code == 200:
        recent_reviews = res.json()
        if recent_reviews:
            df = pd.DataFrame(recent_reviews)
            # 보기 좋게 열 이름 변경
            df = df[['movie_title', 'content', 'sentiment', 'created_at']]
            st.table(df)
        else:
            st.write("아직 작성된 리뷰가 없습니다.")