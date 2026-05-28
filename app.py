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
    # 1. 상태에 따라 최상단 제목 분리 (마지막 페이지 번호가 11로 밀림)
    if st.session_state.stage < 11:
        st.title("실험 참여 페이지")
    else:
        st.title("VP-tts 실험 종료 및 제출 완료")

    # [Stage 0] 인구통계 및 참여 코드 확인
    if st.session_state.stage == 0:
        with st.form("demography"):
            st.session_state.data['name'] = st.text_input("참여자 이름")
            # access_code = st.text_input("실험 참여 코드", type="password") 
            # # 생년월일: UI 캘린더 위젯(date_input)보다 text_input에 텍스트 형식을 강제하는 것이 입력 속도가 빠릅니다.
            st.session_state.data['birth_date'] = st.text_input("생년월일 (예: 010101)", max_chars=6)
            st.session_state.data['phone'] = st.text_input("전화번호 (예: 010-0000-0000)", max_chars=13)
            st.session_state.data['gender'] = st.radio(
                "성별", 
                options=["남성", "여성", "기타/응답 거부"],
                index=None,
                horizontal=True
            )
            # # 상담 경험 유무: 예/아니요 형태의 이진 범주형 데이터는 철자 오류를 막기 위해 반드시 Radio 버튼 사용
            st.session_state.data['clinical_experience'] = st.radio(
                "실제 환자 상담 경험 유무", 
                options=["예", "아니요"],
                horizontal=True
            )
            
            # # 자격증: 다수의 자격증과 급수를 자유롭게 적을 수 있도록 넓은 영역의 text_area 사용
            st.session_state.data['certifications'] = st.text_area(
                "보유하고 있는 상담 및 정신의학 자격증 전체 기재",
                placeholder="정확한 명칭과 급수를 기재해 주십시오. (예: 임상심리사 1급, 청소년상담사 2급)\n해당 사항이 없을 경우 '없음'이라고 기재해 주십시오."
            )
            if st.form_submit_button("다음 단계로"):
                if not st.session_state.data['name'] or not st.session_state.data['birth_date'] or not st.session_state.data['certifications']:
                    st.warning("모든 인구통계 및 배경 정보 항목을 빠짐없이 입력해 주십시오.")
                    st.stop()
                
                # 코드 검증
                # if access_code != "HCI2026": 
                #     st.error("올바른 참여 코드가 아닙니다. 연구자에게 문의하십시오.")
                #     st.stop()
                
                # 통과 시 안내사항 페이지로 이동
                st.session_state.stage = 1
                st.rerun()

    # [Stage 1] 실험 안내사항 (새로 추가된 페이지)
    elif st.session_state.stage == 1:
        st.subheader("📢 실험 진행 안내사항")
        st.markdown(":blue[본 실험은 영상의 음성과 아바타의 모션(Influence Cues)을 평가하므로, 반드시 **이어폰을 착용하거나 스피커 볼륨을 켠 상태**로 진행해 주십시오.]")
        st.markdown(":blue[원활한 구동을 위해 가급적 **PC 환경의 Chrome 브라우저** 사용을 권장합니다.]")        
        st.write("위 안내사항을 모두 확인하셨다면 아래 버튼을 눌러 본 실험을 시작해 주십시오.")
        
        # 여기서 '실험 시작'을 눌러야만 비로소 구글 시트 통신 및 그룹 할당 진행
        if st.button("안내사항 확인 및 실험 시작"):
            with st.spinner("실험 환경을 설정 중입니다..."):
                client = get_gspread_client()
                sheet = client.open("ExperimentDB").worksheet("groups")
                data = pd.DataFrame(sheet.get_all_records())
                
                min_group = data.loc[data['count'].idxmin()]
                st.session_state.video_order = GROUPS[min_group['group_id']]
                st.session_state.data['group_id'] = min_group['group_id']
                
                # 그룹 카운트 자동 증가
                row_index = data.index[data['group_id'] == min_group['group_id']][0] + 2
                sheet.update_cell(row_index, 2, int(min_group['count']) + 1)
                
                # 첫 번째 영상 페이지(Stage 2)로 이동
                st.session_state.stage = 2
                st.rerun()

    # [Stage 2~9] 영상 및 설문 (기존 1~8에서 밀림)
    elif 2 <= st.session_state.stage <= 9:
        idx = st.session_state.stage - 2
        video_id = st.session_state.video_order[idx]
        
        # 진행도 표시 (1/8 ~ 8/8)
        st.write(f"### {idx + 1} / 8")

        st.markdown("**📌 영상 시청 전 안내사항**")
        st.markdown("본 영상은 **주요우울장애(Major Depressive Disorder)** 환자가 임상 연구를 위해 인터뷰어 없이 자신의 상태를 녹음하는 **독백(Monologue)** 상황입니다. 영상 속 환자는 자신의 현재 감정과 과거 이력, 증상의 강도 및 지속 기간, 그리고 이러한 증상이 일상생활에 미치는 영향 등을 스스로 진술하고 있습니다.")
        st.markdown("**영상을 시청하고 아래 평가 항목에 답변해 주십시오.**")
        st.write("")

        st.video(f"videos/{video_id}.mp4")

        with st.form(f"survey_{idx}"):
            st.subheader("1. 임상적 증상 평가")
            st.session_state.data[f"{video_id}_severity"] = st.radio("Severity (증상 심각도)", ["None", "Mild", "Moderate", "Severe"])
            st.session_state.data[f"{video_id}_influence"] = st.multiselect("Influence Cues (위 평가에 영향을 준 주요 단서)", ["Text(내용)", "Eye&Head movement(시선 움직임)", "Face(표정)", "Body Behavior(행동)"])
            st.session_state.data[f"{video_id}_influence_detail"] = st.text_area(
                "위 단서를 선택한 구체적인 이유를 적어주세요.",
                placeholder="예: 특정 대화 내용이 헷갈렸다, 고개를 끄덕이는 모션이 부자연스러웠다, 시선 처리가 자연스러웠다 등"
            )
            st.divider()
            st.subheader("2. 모의 환자 종합 평가")
            st.session_state.data[f"{video_id}_humanlikeness"] = st.radio(
                "**인간미** [모의 환자는 발화 과정에서 흔히 볼 수 있는 특성을 보였는가, 아니면 자동적인 존재처럼 보였는가?]",
                [
                    "5 - 매우 인간과 유사함: 풍부하고 미묘하며 예측 불가능한 행동(감정, 미묘한 어조 변화, 적절한 망설임)을 보임.",
                    "4 - 대체로 인간과 유사함: 감정 표현이나 반응 패턴에 약간의 불일치가 있을 뿐, 전반적으로 인간과 유사하게 행동함.",
                    "3 - 다소 인간과 유사함: 인간과 유사한 경향을 보이지만, 때때로 정해진 각본대로 행동하거나 자연스러운 행동 변화가 부족함.",
                    "2 - 약간 인간과 유사함: 종종 기계적인 느낌을 주며, 경직된 패턴, 반복적인 표현, 부자연스러운 반응을 보임.",
                    "1 - 인간과 닮지 않음: 감정적 미묘함, 상황 인식 및 자발성이 부족하여 일관되게 인위적인 모습을 보임."
                ], index=None
            )
            
            # 2. 자연스러움
            st.session_state.data[f"{video_id}_naturalness"] = st.radio(
                "**자연스러움** [모의 환자의 발화 방식(음성, 표정, 제스처 등)이 실제 사람들의 행동과 일치했습니까?]",
                [
                    "5 - 매우 자연스러움: 말하는 방식, 어조 및 표현이 실제와 완벽하게 일치하며 전혀 어색함이 없음.",
                    "4 - 대체로 자연스러움: 대체로 현실적인 방식으로 말하며, 부자연스러운 표현은 가끔씩만 나타남.",
                    "3 - 다소 자연스러움: 말 흐름은 적절하지만, 때때로 경직되거나 지나치게 격식적인 언어를 사용함.",
                    "2 - 다소 부자연스러움: 발화나 움직임이 부자연스럽고 로봇 같거나 대본처럼 느껴져 현실감이 떨어짐.",
                    "1 - 부자연스러움: 모든 동작과 발화가 기계적이고 상황에 맞지 않아 인위적으로 느껴짐."
                ], index=None
            )
            
            # 3. 유창성
            st.session_state.data[f"{video_id}_fluency"] = st.radio(
                "**유창성** [모의 환자가 자신의 상태나 증상을 일관성 있고 매끄럽게 설명했습니까?]",
                [
                    "5 - 매우 유창함: 최소한의 멈춤, 일관성 있고 구조적이며 매끄러운 방식으로 말을 이어감.",
                    "4 - 대체로 유창함: 내용이 일반적으로 매끄럽고 구조가 잘 잡혀 있으며 흐름을 방해하지 않는 수준의 사소한 불일치만 있음.",
                    "3 - 다소 유창함: 일부 내용이 단편적이거나 약간 어색하지만 대체로 이해할 수 있음.",
                    "2 - 약간 유창함: 부자연스러운 멈춤이 잦고 맥락이 튀는 부분이 있어 내용을 파악하는 데 방해가 됨.",
                    "1 - 유창하지 않음: 논리적 일관성이 전혀 없고, 자주 단절되거나 불안전하거나 무의미한 답변을 함."
                ], index=None
            )
            st.divider()
            
            st.subheader("3. 추가 피드백")
            st.session_state.data[f"{video_id}_feedback_pros"] = st.text_area("좋았던 점 (Strengths)", placeholder="모의 환자의 긍정적인 부분이나 현실적이었던 점을 적어주세요.")
            st.session_state.data[f"{video_id}_feedback_cons"] = st.text_area("부족했던 점 (Weaknesses)", placeholder="개선이 필요한 부분이나 부자연스러웠던 점을 적어주세요.")
            
            if st.form_submit_button("다음 영상으로"):
                influence_val = st.session_state.data.get(f"{video_id}_influence", [])
                influence_detail_val = st.session_state.data.get(f"{video_id}_influence_detail", "").strip()
                pros_val = st.session_state.data.get(f"{video_id}_feedback_pros", "").strip()
                cons_val = st.session_state.data.get(f"{video_id}_feedback_cons", "").strip()

                if (st.session_state.data[f"{video_id}_severity"] is None or
                    not influence_val or
                    not influence_detail_val or
                    st.session_state.data[f"{video_id}_humanlikeness"] is None or
                    st.session_state.data[f"{video_id}_naturalness"] is None or
                    st.session_state.data[f"{video_id}_fluency"] is None or
                    not pros_val or
                    not cons_val):
                    
                    st.error("객관식 평가 문항 및 주관식 피드백(이유, 장점, 단점)을 모두 작성해 주십시오.")
                    st.stop()
                st.session_state.stage += 1
                st.rerun()

    # [Stage 10] 최종 저장 프로세스 (기존 9에서 밀림)
    elif st.session_state.stage == 10:
        with st.spinner("데이터를 서버에 기록 중입니다. 잠시만 기다려주세요..."):
            client = get_gspread_client()
            sheet = client.open("ExperimentDB").worksheet("logs")
            
            # 1. 타임스탬프 추가
            st.session_state.data['timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 2. 헤더 순서 정의 (시트의 A열부터 순서대로)
            ordered_keys = ['timestamp', 'name', 'birth_date', 'phone', 'gender', 'clinical_experience', 'certifications', 'group_id']
            videos = ["M0", "M1", "M2", "M3", "F0", "F1", "F2", "F3"]
            
            # [수정된 부분] 세분화된 7개의 변수를 모두 담도록 완벽히 동기화
            for v in videos:
                ordered_keys.extend([
                    f"{v}_severity", 
                    f"{v}_influence", 
                    f"{v}_influence_detail", 
                    f"{v}_humanlikeness", 
                    f"{v}_naturalness", 
                    f"{v}_fluency", 
                    f"{v}_feedback_pros", 
                    f"{v}_feedback_cons"
                ])
            
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
            st.session_state.stage = 11
            st.rerun()

    # [Stage 11] 실험 완료 화면 (기존 10에서 밀림)
    elif st.session_state.stage == 11:
        st.balloons()
        st.success("실험이 모두 완료되었습니다.")
        st.write("참여해 주셔서 감사합니다. 창을 닫아주셔도 좋습니다.")

def admin_dashboard():
    st.write("### 관리자 페이지")
    # ... 대시보드 로직 ...

if __name__ == "__main__":
    main()