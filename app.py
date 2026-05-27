import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import datetime

# [설정] 구글 시트 클라이언트
def get_gspread_client():
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

GROUPS = {
    "group_A": ["M0", "M1", "M2", "M3", "F0", "F1", "F2", "F3"],
    "group_B": ["M1", "M2", "M3", "F0", "F1", "F2", "F3", "M0"],
    "group_C": ["M2", "M3", "F0", "F1", "F2", "F3", "M0", "M1"],
    "group_D": ["M3", "F0", "F1", "F2", "F3", "M0", "M1", "M2"],
    "group_E": ["F0", "F1", "F2", "F3", "M0", "M1", "M2", "M3"],
    "group_F": ["F1", "F2", "F3", "M0", "M1", "M2", "M3", "F0"],
    "group_G": ["F2", "F3", "M0", "M1", "M2", "M3", "F0", "F1"],
    "group_H": ["F3", "M0", "M1", "M2", "M3", "F0", "F1", "F2"],
}

def main():
    st.set_page_config(page_title="HCI 실험", layout="centered")
    
    if st.query_params.get("admin") == st.secrets["ADMIN_PASS"]:
        admin_dashboard()
        return

    if 'stage' not in st.session_state:
        st.session_state.stage = 0
        st.session_state.data = {}
        st.session_state.video_order = None

    participant_view()

def participant_view():
    # [수정된 부분] Stage 10(완료 화면) 도달 여부에 따라 제목을 다르게 렌더링합니다.
    if st.session_state.stage < 10:
        st.title("실험 참여 페이지")
    else:
        st.title("VP-tts 실험 종료 및 제출 완료") # 필요시 텍스트 수정

    # [Stage 0] 인구통계
    if st.session_state.stage == 0:
        with st.form("demography"):
            st.session_state.data['name'] = st.text_input("참여자 이름/ID")
            st.session_state.data['age'] = st.number_input("나이", 18, 100)
            if st.form_submit_button("실험 시작"):
                client = get_gspread_client()
                sheet = client.open("ExperimentDB").worksheet("groups")
                data = pd.DataFrame(sheet.get_all_records())
                
                min_group = data.loc[data['count'].idxmin()]
                st.session_state.video_order = GROUPS[min_group['group_id']]
                st.session_state.data['group_id'] = min_group['group_id']
                
                # 그룹 카운트 자동 증가
                row_index = data.index[data['group_id'] == min_group['group_id']][0] + 2
                sheet.update_cell(row_index, 2, int(min_group['count']) + 1)
                
                st.session_state.stage = 1
                st.rerun()

    # [Stage 1~8] 영상 및 설문
    elif 1 <= st.session_state.stage <= 8:
        idx = st.session_state.stage - 1
        video_id = st.session_state.video_order[idx]
        st.write(f"### {st.session_state.stage} / 8")
        st.video(f"videos/{video_id}.mp4")

        with st.form(f"survey_{idx}"):
            st.session_state.data[f"{video_id}_severity"] = st.radio("Severity", ["None", "Mild", "Moderate", "Severe"])
            st.session_state.data[f"{video_id}_influence"] = st.multiselect("Influence Cues", ["Text", "Eye&Head", "Face", "Motion"])
            st.session_state.data[f"{video_id}_feedback"] = st.text_area("피드백")
            st.session_state.data[f"{video_id}_realism"] = st.slider("Realism (1~5)", 1, 5)
            
            if st.form_submit_button("다음 영상으로"):
                st.session_state.stage += 1
                st.rerun()

    # [Stage 9] 최종 저장 프로세스
    elif st.session_state.stage == 9:
        # 데이터 처리 중 스피너 표시
        with st.spinner("데이터를 서버에 기록 중입니다. 잠시만 기다려주세요..."):
            client = get_gspread_client()
            sheet = client.open("ExperimentDB").worksheet("logs")
            
            # 1. 타임스탬프 추가
            st.session_state.data['timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 2. 헤더 순서 정의 (시트의 A열부터 순서대로)
            ordered_keys = ['timestamp', 'name', 'age', 'group_id']
            videos = ["M0", "M1", "M2", "M3", "F0", "F1", "F2", "F3"]
            for v in videos:
                ordered_keys.extend([f"{v}_severity", f"{v}_influence", f"{v}_feedback", f"{v}_realism"])
            
            # 3. 데이터 추출 및 전처리 (리스트형 방지)
            ordered_data = []
            for k in ordered_keys:
                val = st.session_state.data.get(k, "N/A")
                if isinstance(val, list):
                    val = ", ".join(map(str, val))
                ordered_data.append(val)

            # 시트에 전송
            sheet.append_row(ordered_data)
            
            # 4. 상태 변경 및 화면 새로고침
            st.session_state.stage = 10
            st.rerun() 

    # [Stage 10] 실험 완료 화면
    elif st.session_state.stage == 10:
        st.balloons()
        st.success("실험이 모두 완료되었습니다. 데이터가 정상적으로 저장되었습니다.")
        st.write("참여해 주셔서 감사합니다. 창을 닫아주셔도 좋습니다.")

def admin_dashboard():
    st.write("### 관리자 페이지")
    # ... 대시보드 로직 ...

if __name__ == "__main__":
    main()