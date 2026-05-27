import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# [설정] 구글 시트 연결 (Streamlit Cloud의 Secrets 활용)
def get_gspread_client():
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

GROUPS = {
    "group_A": ["v1", "v2", "v3", "v4", "v5", "v6", "v7", "v8"],
    "group_B": ["v2", "v3", "v4", "v5", "v6", "v7", "v8", "v1"],
    "group_C": ["v3", "v4", "v5", "v6", "v7", "v8", "v1", "v2"],
    "group_D": ["v4", "v5", "v6", "v7", "v8", "v1", "v2", "v3"],
    "group_E": ["v5", "v6", "v7", "v8", "v1", "v2", "v3", "v4"],
    "group_F": ["v6", "v7", "v8", "v1", "v2", "v3", "v4", "v5"],
    "group_G": ["v7", "v8", "v1", "v2", "v3", "v4", "v5", "v6"],
    "group_H": ["v8", "v1", "v2", "v3", "v4", "v5", "v6", "v7"],
}

def main():
    st.set_page_config(page_title="HCI 실험", layout="centered")
    
    # URL 파라미터로 관리자 접속 (?admin=password)
    if st.query_params.get("admin") == st.secrets["ADMIN_PASS"]:
        admin_dashboard()
    else:
        participant_view()

def participant_view():
    st.title("실험 참여 페이지")
    
    # 1. 세션별 순서 배정 (최초 접속 시에만 수행)
    if 'video_order' not in st.session_state:
        client = get_gspread_client()
        sheet = client.open("ExperimentDB").worksheet("groups")
        data = pd.DataFrame(sheet.get_all_records())
        
        # 가장 인원 적은 그룹 자동 선택
        min_group = data.loc[data['count'].idxmin()]
        st.session_state.video_order = GROUPS[min_group['group_id']]
        st.session_state.group_id = min_group['group_id']
        
        # 카운트 1 증가
        sheet.update_cell(data.index[data['group_id'] == min_group['group_id']][0] + 2, 2, int(min_group['count']) + 1)

    # 2. 영상 재생 및 설문 로직
    idx = st.session_state.get('idx', 0)
    if idx < len(st.session_state.video_order):
        st.write(f"### 현재 영상: {idx+1} / 8")
        st.video(st.session_state.video_order[idx])
        
        # 설문지 (간단 예시)
        score = st.slider("영상의 몰입도를 평가해주세요", 1, 5, 3)
        if st.button("다음 영상으로"):
            # DB 로그 저장 (개인정보 보호 위해 ID는 랜덤 생성 등 권장)
            st.session_state.idx += 1
            st.rerun()
    else:
        st.success("모든 실험이 완료되었습니다.")

def admin_dashboard():
    st.title("🛡️ 실험 관리자 대시보드")
    client = get_gspread_client()
    sheet = client.open("ExperimentDB").worksheet("groups")
    df = pd.DataFrame(sheet.get_all_records())
    st.write("### 현재 그룹별 배정 현황")
    st.table(df)
    
    if st.button("참여자 결과 데이터 가져오기"):
        logs = client.open("ExperimentDB").worksheet("logs").get_all_records()
        st.dataframe(pd.DataFrame(logs))

if __name__ == "__main__":
    main()