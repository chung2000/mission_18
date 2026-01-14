import streamlit as st
import requests
import pandas as pd
import datetime  # 날짜 설정을 위해 상단에 추가 필요

# FastAPI 서버 주소 (로컬 실행 시 기본값)
# 배포 시에는 실제 백엔드 URL로 변경해야 합니다.
BACKEND_URL = "http://localhost:8000"

st.set_page_config(page_title="영화 리뷰 감성 분석 서비스", layout="wide")

# --- 1. URL 쿼리 파라미터 감지 (상세 페이지 전환용) ---
# st.query_params를 통해 현재 클릭된 영화 ID가 있는지 확인합니다.
query_params = st.query_params
clicked_movie_id = query_params.get("movie_id")

st.title("🎬 AI 영화 리뷰 감성 분석 서비스")
st.markdown("---")

# --- 2. 사이드바: 영화 추가 기능 ---
with st.sidebar:
    st.header("➕ 새 영화 등록")
    with st.form("movie_form"):
        title = st.text_input("영화 제목")
        director = st.text_input("감독")
        genre = st.text_input("장르")
        ##release_date = st.date_input("개봉일")
        release_date = st.date_input(
            "개봉일",
            value=datetime.date(2000, 1, 1),  # 기본 표시 날짜
            min_value=datetime.date(1900, 1, 1),  # 최소 선택 가능 날짜 (1900년까지 확대)
            max_value=datetime.date(2100, 1, 1)  # 최대 선택 가능 날짜
        )
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

# --- 3. 메인 화면 로직 ---

# [CASE A] 상세 페이지 모드 (URL에 movie_id가 있을 때)
if clicked_movie_id:
    m_id = int(clicked_movie_id)

    if st.button("⬅️ 목록으로 돌아가기"):
        st.query_params.clear()  # 쿼리 파라미터 삭제하여 목록으로 복귀
        st.rerun()

    res = requests.get(f"{BACKEND_URL}/movies/")
    movie = next((m for m in res.json() if m['id'] == m_id), None)

    if movie:
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(movie['poster_url'], use_container_width=True)
        with col2:
            st.title(movie['title'])
            st.subheader(f"감독: {movie['director']}")
            st.write(f"**장르**: {movie['genre']} | **개봉일**: {movie['release_date']}")
            st.markdown("---")

            # 리뷰 필터링 및 분석 결과 표시
            rev_res = requests.get(f"{BACKEND_URL}/reviews/recent")
            if rev_res.status_code == 200:
                m_reviews = [r for r in rev_res.json() if r['movie_id'] == m_id]
                if m_reviews:
                    pos_count = sum(1 for r in m_reviews if r['sentiment'] == "POSITIVE")
                    st.metric("AI 긍정 지수", f"{(pos_count / len(m_reviews)) * 100:.1f}%", f"{len(m_reviews)}개의 리뷰")
                    for r in m_reviews:
                        with st.chat_message("user"):
                            st.write(f"{'😊' if r['sentiment'] == 'POSITIVE' else '🤔'} {r['content']}")
                else:
                    st.info("아직 리뷰가 없습니다.")

# [CASE B] 기본 탭 모드 (목록/작성/히스토리)
else:
    tabs = st.tabs(["🎥 영화 목록", "✍️ 리뷰 작성", "📊 리뷰 히스토리"])

    # 1. 영화 목록 탭 (이미지 클릭 기능 포함)
    with tabs[0]:
        st.subheader("현재 상영 중인 영화 (포스터를 클릭하세요)")
        response = requests.get(f"{BACKEND_URL}/movies/")
        if response.status_code == 200:
            movies = response.json()
            if not movies:
                st.info("등록된 영화가 없습니다.")
            else:
                cols = st.columns(4)
                for idx, movie in enumerate(movies):
                    with cols[idx % 4]:
                        # --- 핵심: HTML <a> 태그를 이용한 이미지 클릭 구현 ---
                        # 클릭 시 URL에 ?movie_id=X 가 붙게 됩니다.
                        html_code = f"""
                        <a href="/?movie_id={movie['id']}" target="_self" style="text-decoration: none;">
                            <img src="{movie['poster_url']}" style="width: 100%; border-radius: 10px; transition: 0.3s; cursor: pointer;">
                            <p style="color: white; text-align: center; font-weight: bold; margin-top: 5px;">{movie['title']}</p>
                        </a>
                        """
                        st.markdown(html_code, unsafe_allow_html=True)

                        # 삭제 버튼은 별도로 유지
                        if st.button("삭제", key=f"del_{movie['id']}", use_container_width=True):
                            requests.delete(f"{BACKEND_URL}/movies/{movie['id']}")
                            st.rerun()
        else:
            st.error("데이터 로드 실패")

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