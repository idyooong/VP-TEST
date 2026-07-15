import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import datetime
import base64, time

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
    "group_A": ["M0", "F1", "M3", "F2", "F0", "M1", "F3", "M2"], 
    "group_B": ["F1", "M3", "F2", "F0", "M1", "F3", "M2", "M0"], 
    "group_C": ["M3", "F2", "F0", "M1", "F3", "M2", "M0", "F1"], 
    "group_D": ["F2", "F0", "M1", "F3", "M2", "M0", "F1", "M3"], 
    "group_E": ["F0", "M2", "F3", "M1", "M0", "F2", "M3", "F1"], 
    "group_F": ["M2", "F3", "M1", "M0", "F2", "M3", "F1", "F0"], 
    "group_G": ["F3", "M1", "M0", "F2", "M3", "F1", "F0", "M2"], 
    "group_H": ["M1", "M0", "F2", "M3", "F1", "F0", "M2", "F3"], 
}

def main():
    st.set_page_config(page_title="HCI 실험", layout="wide") # layout="centered"
    hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;} /* 우측 상단 햄버거 메뉴 숨김 */
            header {visibility: hidden;} /* 상단 헤더 공간 전체(깃허브 아이콘 포함) 숨김 */
            footer {visibility: hidden;} /* 하단 'Made with Streamlit' 워터마크 숨김 */
            .viewerBadge_container {display: none !important;}
            .viewerBadge_link {display: none !important;}
            [data-testid="viewerBadge"] {display: none !important;}
            [data-testid="stToolbar"] {display: none !important;}
            </style>
            """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)

    if 'stage' not in st.session_state:
        st.session_state.stage = 0
        st.session_state.data = {}
        st.session_state.video_order = None

    participant_view()

def participant_view():
    # 1. 상태에 따라 최상단 제목 분리
    if st.session_state.stage < 11:
        st.title("가상환자 평가 실험")
    else:
        st.title("VP-tts 실험 종료 및 제출 완료")

    # [Stage 0] 인구통계 및 참여 코드 확인
    if st.session_state.stage == 0:
        with st.form("demography"):
            st.session_state.data['name'] = st.text_input("참여자 이름")
            st.session_state.data['birth_date'] = st.text_input("생년월일 (예: 010101)", max_chars=6)
            st.session_state.data['phone'] = st.text_input("전화번호 (예: 010-0000-0000)", max_chars=13)
            st.session_state.data['gender'] = st.radio(
                "성별", 
                options=["남성", "여성"],
                index=None,
                horizontal=True
            )
            st.session_state.data['clinical_experience'] = st.radio(
                "실제 환자 상담 경험 유무", 
                options=["예", "아니요"],
                index=None,
                horizontal=True
            )
            st.session_state.data['clinical_years'] = st.number_input(
                "임상 경력 년차 (※ 상담 경험 '예' 응답자만 기재)", 
                min_value=0, # '아니요'인 사람을 위해 0을 허용
                max_value=50,    
                value=0,         
                step=1
            )

            st.session_state.data['certifications'] = st.text_area(
                "보유하고 있는 상담 및 정신의학 자격증 전체 기재",
                placeholder="정확한 명칭과 급수를 기재해 주십시오. (예: 임상심리사 1급, 청소년상담사 2급)\n해당 사항이 없을 경우 '없음'이라고 기재해 주십시오."
            )
            if st.form_submit_button("다음 단계로"):
                if not st.session_state.data['name'] or not st.session_state.data['birth_date'] or not st.session_state.data['phone'] or not st.session_state.data['gender'] or not st.session_state.data['certifications']:
                    st.warning("모든 인구통계 및 배경 정보 항목을 빠짐없이 입력해 주십시오.")
                    st.stop()
                if st.session_state.data['clinical_experience'] == "예" and st.session_state.data['clinical_years'] <= 0:
                    st.error("⚠️ 환자 상담 경험이 '예'라고 응답하셨습니다. 아래 '임상 경력(년차)' 칸에 실제 경력을 1년 이상으로 기재해 주십시오.")
                    st.stop() # 여기서 코드 실행을 멈추고 피험자가 수정할 때까지 대기함
                    
                # (옵션) 경험이 '아니요'인데 경력이 기재된 경우의 역방향 방어
                if st.session_state.data['clinical_experience'] == "아니요" and st.session_state.data['clinical_years'] > 0:
                    st.error("⚠️ 환자 상담 경험이 '아니요'인 경우 임상 경력은 0이어야 합니다.")
                    st.stop()
                # 통과 시 안내사항 페이지로 이동
                st.session_state.stage = 1
                st.rerun()

    # [Stage 1] 실험 안내사항 (새로 추가된 페이지)
    elif st.session_state.stage == 1:
        st.subheader("📢 실험 진행 안내사항")
        # st.markdown(":blue[1. 본 실험은 영상의 음성과 아바타의 모션(Influence Cues)을 평가하므로, 반드시 **이어폰을 착용한 상태**로 진행해 주십시오.]")
        # st.markdown(":red[2. 실험 도중 절대로 **‘새로고침(F5)’**이나 **‘뒤로 가기’** 버튼을 누르지 마십시오.]") 
        # st.markdown(":red[3. 도중에 창을 닫으면 데이터가 소실되어 실험을 처음부터 다시 시작해야 합니다. **반드시 한 번에 끝까지 진행해 주십시오.**]")   
        st.markdown(
            "<div style='color: #1f77b4; font-size: 16px; margin-bottom: 15px;'>"
            "1. 본 실험은 영상의 음성과 아바타의 모션을 평가하므로, 반드시 <b>이어폰을 착용한 상태</b>로 진행해 주십시오."
            "</div>", 
            unsafe_allow_html=True
        )

        st.markdown(
            "<div style='color: #d62728; font-size: 16px; margin-bottom: 15px;'>"
            "2. 실험 도중 절대로 <b>'새로고침(F5)'</b>이나 <b>'뒤로 가기'</b> 버튼을 누르지 마십시오."
            "</div>", 
            unsafe_allow_html=True
        )

        st.markdown(
            "<div style='color: #d62728; font-size: 16px; margin-bottom: 25px;'>"
            "3. 도중에 창을 닫으면 데이터가 소실되어 실험을 처음부터 다시 시작해야 합니다. <b>반드시 한 번에 끝까지 진행해 주십시오.</b>"
            "</div>", 
            unsafe_allow_html=True
        )    
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

    # [Stage 2~9] 영상 및 설문
    elif 2 <= st.session_state.stage <= 9:
        idx = st.session_state.stage - 2
        video_id = st.session_state.video_order[idx]
        
        # 진행도 표시 (1/8 ~ 8/8)
        st.write(f"### {idx + 1} / 8")

        st.markdown("**📌 영상 시청 전 안내사항**")
        st.markdown("본 영상은 **주요우울장애(Major Depressive Disorder)** 환자가 임상 연구를 위해 인터뷰어 없이 자신의 상태를 녹음하는 **독백(Monologue)** 상황입니다. 영상 속 환자는 자신의 현재 감정과 과거 이력, 증상의 강도 및 지속 기간, 그리고 이러한 증상이 일상생활에 미치는 영향 등을 스스로 진술하고 있습니다.")
        st.markdown("**영상(2분 이내)을 시청하고 아래 평가 항목에 답변해 주십시오.**")
        st.write("")

        VIDEO_LENGTHS = {
            "M0": 64, "M1": 42, "M2": 58, "M3": 75,
            "F0": 79, "F1": 72, "F2": 42, "F3": 78
        }
        required_time = VIDEO_LENGTHS.get(video_id, 60)

        # 초기 상태 정의
        if f"play_started_{video_id}" not in st.session_state:
            st.session_state[f"play_started_{video_id}"] = False
            st.session_state[f"start_time_{video_id}"] = 0
            st.session_state[f"unlocked_{video_id}"] = False

        video_style = "width: 100%; height: 85vh; max-width: none; object-fit: contain; margin-bottom: 25px;"
        # 1. 영상을 아직 시작하지 않은 상태
        if not st.session_state[f"play_started_{video_id}"]:
            st.info("아래 버튼을 누르면 영상이 즉시 재생됩니다.")
            if st.button("▶️ 영상 시청 시작", key=f"start_btn_{video_id}"):
                st.session_state[f"play_started_{video_id}"] = True
                st.session_state[f"start_time_{video_id}"] = time.time()
                st.rerun()
            st.stop() # 시작 전에는 아래 폼 렌더링 차단

        # 2. 버튼을 눌러 영상이 시작된 상태
        else:
            # HTML5 <video> 태그를 이용해 '컨트롤 바'를 물리적으로 삭제하고 강제 자동재생
            video_path = f"videos/{video_id}.mp4"
            with open(video_path, "rb") as v_file:
                video_bytes = v_file.read()
            encoded_video = base64.b64encode(video_bytes).decode()
            
            if not st.session_state[f"unlocked_{video_id}"]:
                # 2-1. 설문 잠금 상태 (1회차 시청 중): 컨트롤 바 원천 차단, 강제 자동재생
                # video_html = f"""
                #     <video width="100%" autoplay>
                #         <source src="data:video/mp4;base64,{encoded_video}" type="video/mp4">
                #     </video>
                # """
                video_html = f"""
                    <div style="display: flex; justify-content: center; width: 100%;">
                        <video style="{video_style}" autoplay>
                            <source src="data:video/mp4;base64,{encoded_video}" type="video/mp4">
                        </video>
                    </div>
                """
            else:
                # 2-2. 설문 해제 상태 (시청 완료 후): 컨트롤 바(controls) 생성 및 리플레이 허용
                # video_html = f"""
                #     <video width="100%" controls controlsList="nodownload noplaybackrate" disablePictureInPicture>
                #         <source src="data:video/mp4;base64,{encoded_video}" type="video/mp4">
                #     </video>
                # """
                video_html = f"""
                    <div style="display: flex; justify-content: center; width: 100%;">
                        <video style="{video_style}" controls controlsList="nodownload noplaybackrate" disablePictureInPicture>
                            <source src="data:video/mp4;base64,{encoded_video}" type="video/mp4">
                        </video>
                    </div>
                """
            st.markdown(video_html, unsafe_allow_html=True)
            # 3. 설문 폼 잠금 제어
            if not st.session_state[f"unlocked_{video_id}"]:
                st.warning("영상이 종료된 후 아래 버튼을 눌러 평가 문항을 여십시오.")
                if st.button("평가 문항 열기", key=f"unlock_btn_{video_id}"):
                    elapsed = time.time() - st.session_state[f"start_time_{video_id}"]
                    
                    if elapsed < required_time:
                        remain = int(required_time - elapsed)
                        st.error(f"아직 영상 시청이 완료되지 않았습니다. 영상 시청 완료 후 다시 시도해 주십시오.")
                    else:
                        st.session_state[f"unlocked_{video_id}"] = True
                        st.rerun()
                st.stop() # 영상 길이가 안 지났으면 설문 폼 렌더링 차단

        with st.form(f"survey_{idx}"):
            st.subheader("1. 임상적 증상 평가")
            st.markdown("**Q1. 화면 속 환자의 우울 증상 심각성을 4단계 중 하나로 선택해 주십시오.**")
            st.session_state.data[f"{video_id}_severity"] = st.radio("**Severity (증상 심각도)**", ["None", "Mild", "Moderate", "Severe"], index=None)

            st.write("") 
            st.markdown("**Q2. 심각도를 판단하는 데 가장 큰 영향을 미친 요소를 모두 선택해 주십시오. (다중 선택 가능)**")
            st.session_state.data[f"{video_id}_influence"] = st.multiselect("**Influence Cues**", ["Text(발화 내용)", "Eye&Head movement(시선 및 고개 움직임)", "Face(표정)", "Body Behavior(신체 행동)"])
            
            st.session_state.data[f"{video_id}_influence_detail"] = st.text_area(
                "위 단서를 선택한 구체적인 이유를 적어주세요.",
                placeholder="예: 특정 대화 내용이 헷갈렸다, 고개를 끄덕이는 모션이 부자연스러웠다, 시선 처리가 자연스러웠다 등"
            )
            st.divider()
            st.subheader("2. 가상 환자 종합 평가")
            st.session_state.data[f"{video_id}_humanlikeness"] = st.radio(
                "**Q3. 인간미** [가상 환자는 발화 과정에서 흔히 볼 수 있는 특성을 보였는가, 아니면 자동적인 존재처럼 보였는가?]",
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
                "**Q4. 자연스러움** [가상 환자의 발화 방식(음성, 표정, 제스처 등)이 실제 사람들의 행동과 일치했습니까?]",
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
                "**Q5. 유창성** [가상 환자가 자신의 상태나 증상을 일관성 있고 매끄럽게 설명했습니까?]",
                [
                    "5 - 매우 유창함: 최소한의 멈춤, 일관성 있고 구조적이며 매끄러운 방식으로 말을 이어감.",
                    "4 - 대체로 유창함: 내용이 일반적으로 매끄럽고 구조가 잘 잡혀 있으며 흐름을 방해하지 않는 수준의 사소한 불일치만 있음.",
                    "3 - 다소 유창함: 일부 내용이 단편적이거나 약간 어색하지만 대체로 이해할 수 있음.",
                    "2 - 약간 유창함: 부자연스러운 멈춤이 잦고 맥락이 튀는 부분이 있어 내용을 파악하는 데 방해가 됨.",
                    "1 - 유창하지 않음: 논리적 일관성이 전혀 없고, 자주 단절되거나 불안전하거나 무의미한 답변을 함."
                ], index=None
            )
            st.subheader("3. 가상 환자 심층 품질 평가")
    
            # -----------------------------------------------------------------
            # 문항 1: 감정적 일관성 (Emotional Consistency)
            # -----------------------------------------------------------------
            st.markdown("**Q6. 가상 환자가 영상 내내 질환에 맞춰 일관된 감정적, 인지적 패턴을 지속적으로 보였습니까?**")
            
            consistency_options = [
                "5 - 매우 일관됨: 영상 내내 안정적이고 일관된 감정적, 인지적 패턴을 유지합니다.",
                "4 - 대체로 일관됨: 일반적으로 적절한 감정적 반응을 유지하지만 사소한 편차가 있습니다.",
                "3 - 어느 정도 일관성 있음: 감정 표현이 때때로 일관되지만 가끔 강도나 적절성이 달라지기도 합니다.",
                "2 - 약간 일관성 있음: 감정적 반응의 잦은 불일치로 인해 현실성이 감소합니다.",
                "1 - 일관성 없음: 감정 표현이 무작위적이거나 모순되어 신뢰성이 떨어집니다."
            ]
            
            st.session_state.data[f"{video_id}_consistency"] = st.radio(
                label="감정적 일관성 평가",
                options=consistency_options,
                index=None,
                label_visibility="collapsed"  # 위 markdown 지시문과 중복되므로 라벨은 숨김 처리
            )
            
            st.write("")  # 문항 간 시각적 여백 확보
            
            # -----------------------------------------------------------------
            # 문항 2: 증상 현실성 (Symptom Realism)
            # -----------------------------------------------------------------
            st.markdown("**Q7. 가상 환자가 우울증에 대한 임상적 관찰과 일치하는 방식으로 증상(예:정서적 둔마, 무쾌감 등)을 보였습니까?**")
            
            realism_options = [
                "5 - 매우 현실적임: 실제 우울증 임상 관찰과 일치하는 광범위한 우울증 증상을 정확하게 나타냅니다.",
                "4 - 대체로 사실적: 대부분의 증상이 정확하게 표현되었으며, 사소한 부정확함이나 세부 정보 누락만 있습니다.",
                "3 - 어느 정도 현실적: 일부 증상은 임상적 기대치와 일치하지만, 다른 증상은 과장되거나 나타나지 않습니다.",
                "2 - 약간 현실적: 증상이 종종 불완전하거나, 잘못 표현되거나, 피상적으로 표현됩니다.",
                "1 - 비현실적임: 현실적인 우울증 증상이 없거나 우울증과 관련 없는 증상을 나타냅니다."
            ]
            
            st.session_state.data[f"{video_id}_realism"] = st.radio(
                label="증상 현실성 평가",
                options=realism_options,
                index=None,
                label_visibility="collapsed"  # 위 markdown 지시문과 중복되므로 라벨은 숨김 처리
            )
            st.divider()
            
            st.subheader("4. 추가 피드백")
            st.markdown("**Q8. 영상 속 가상 환자의 표정, 행동, 발화 내용, 음성 등에 대해 긍정적인 부분과 개선이 필요한 부분을 작성해 주십시오.**")

            st.session_state.data[f"{video_id}_feedback_pros"] = st.text_area("좋았던 점 (Strengths)", placeholder="가상 환자의 긍정적인 부분이나 현실적이었던 점을 적어주세요.")
            st.session_state.data[f"{video_id}_feedback_cons"] = st.text_area("부족했던 점 (Weaknesses)", placeholder="개선이 필요한 부분이나 부자연스러웠던 점을 적어주세요.")
            
            if st.form_submit_button("다음 영상으로"):
                influence_val = st.session_state.data.get(f"{video_id}_influence", [])
                influence_detail_val = st.session_state.data.get(f"{video_id}_influence_detail", "").strip()
                pros_val = st.session_state.data.get(f"{video_id}_feedback_pros", "").strip()
                cons_val = st.session_state.data.get(f"{video_id}_feedback_cons", "").strip()

                if (st.session_state.data.get(f"{video_id}_severity") is None or
                    not influence_val or
                    not influence_detail_val or
                    st.session_state.data.get(f"{video_id}_humanlikeness") is None or
                    st.session_state.data.get(f"{video_id}_naturalness") is None or
                    st.session_state.data.get(f"{video_id}_fluency") is None or
                    st.session_state.data.get(f"{video_id}_consistency") is None or
                    st.session_state.data.get(f"{video_id}_realism") is None or
                    not pros_val or
                    not cons_val):
                    
                    st.error("객관식 평가 문항 및 주관식 피드백(이유, 장점, 단점)을 모두 작성해 주십시오.")
                    st.stop()
                st.session_state.stage += 1
                st.rerun()

    elif st.session_state.stage == 10:
        st.subheader("마지막 단계: 전체 시스템 종합 평가")
        st.info("모든 영상 평가가 완료되었습니다. 마지막으로 본 가상 환자 시스템 전체에 대한 종합적인 의견을 여쭙습니다.")
        
        with st.form("final_comprehensive_survey"):
            st.markdown("**Q. 오늘 시청한 8개의 주요우울장애(MDD) 가상 환자 독백 영상들이 본인의 임상적 관찰력 및 추론 능력을 향상시키는 데 도움이 되었습니까?**")
            st.session_state.data["final_clinical_utility"] = st.radio(
                "임상적 유용성", 
                [
                    "5 - 매우 도움이 됨", 
                    "4 - 대체로 도움이 됨", 
                    "3 - 보통", 
                    "2 - 별로 도움 되지 않음", 
                    "1 - 전혀 도움 되지 않음"
                ],
                index=None,
                label_visibility="collapsed"
            )
            
            st.write("") # 여백
            
            st.markdown("**Q. (선택 사항) 향후 이 가상 환자 시스템을 실제 임상 교육이나 훈련용으로 도입한다면, 어떤 기능이 추가되거나 개선되면 좋을지 자유롭게 제안해 주십시오.**")
            st.session_state.data["final_suggestion"] = st.text_area(
                "시스템 개선 제안",
                placeholder="예: 독백뿐만 아니라 직접 질문할 수 있는 대화 기능이 필요하다, 환자의 과거 병력지(Chart)도 함께 제공되면 좋겠다 등",
                label_visibility="collapsed"
            )
            
            # 최종 제출 버튼
            submitted = st.form_submit_button("최종 데이터 제출 및 실험 종료")
            if submitted:
                if st.session_state.data["final_clinical_utility"] is None:
                    st.error("객관식 평가 항목에 응답해 주십시오.")
                else:
                    st.session_state.stage = 11
                    st.rerun()

    # [Stage 10] 최종 저장 프로세스 (기존 9에서 밀림)
    elif st.session_state.stage == 11:
        with st.spinner("데이터를 서버에 기록 중입니다. 잠시만 기다려주세요..."):
            client = get_gspread_client()
            sheet = client.open("ExperimentDB").worksheet("logs")
            
            st.session_state.data['timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            ordered_keys = ['timestamp', 'name', 'birth_date', 'phone', 'gender', 'clinical_experience', 'clinical_years', 'certifications', 'group_id']
            videos = ["M0", "M1", "M2", "M3", "F0", "F1", "F2", "F3"]
            
            for v in videos:
                ordered_keys.extend([
                    f"{v}_severity", 
                    f"{v}_influence", 
                    f"{v}_influence_detail", 
                    f"{v}_humanlikeness", 
                    f"{v}_naturalness", 
                    f"{v}_fluency", 
                    f"{v}_consistency",
                    f"{v}_realism",
                    f"{v}_feedback_pros", 
                    f"{v}_feedback_cons"
                ])
            ordered_keys.extend([
                "final_clinical_utility",
                "final_suggestion"
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
            st.session_state.stage = 12
            st.rerun()
    # [Stage 11] 실험 완료 화면
    elif st.session_state.stage == 12:
        st.balloons()
        st.success("실험이 모두 완료되었습니다.")
        st.write("참여해 주셔서 감사합니다. 창을 닫아주셔도 좋습니다.")

if __name__ == "__main__":
    main()