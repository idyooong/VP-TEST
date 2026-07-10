import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import datetime
import base64
import time

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
    "group_A": ["F0", "F1"], 
    "group_B": ["F0", "F1"],
    "group_C": ["F0", "F1"],
    "group_D": ["F0", "F1"],
    "group_E": ["F0", "F1"],
    "group_F": ["F0", "F1"],
    "group_H": ["F0", "F1"]
}

# [주의] 각 영상별 실제 설계된 정답 기입
GROUND_TRUTH = {
    "F0": {"diagnosis": "주요우울장애(MDD)", "severity": "None(없음)"},
    "F1": {"diagnosis": "주요우울장애(MDD)", "severity": "Mild(경도))"},
}

VIDEO_LENGTHS = {
    "M0": 64, "M1": 42, "M2": 58, "M3": 75,
    "F0": 79, "F1": 72, "F2": 42, "F3": 78
}

def main():
    st.set_page_config(page_title="HCI 실험", layout="wide")
    hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            header {visibility: hidden;}
            footer {visibility: hidden;}
            .viewerBadge_container {display: none !important;}
            </style>
            """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)

    if 'stage' not in st.session_state:
        st.session_state.stage = 0
        st.session_state.data = {}
        st.session_state.video_order = None

    participant_view()

def participant_view():
    # ---------------------------------------------------------
    # [Stage 0] 섹션 1: 기본 인적 사항 및 배경 설문
    # ---------------------------------------------------------
    if st.session_state.stage == 0:
        st.title("가상환자 평가 실험")
        st.subheader("기본 인적 사항")
        with st.form("demography"):
            st.session_state.data['name'] = st.text_input("**성함**")
            st.session_state.data['gender'] = st.radio("**성별**", options=["남성", "여성"], index=None, horizontal=True)
            st.session_state.data['birth_date'] = st.text_input("**생년월일 (예: 010101)**", max_chars=6)
            st.session_state.data['major'] = st.text_input("**전공 분야 및 소속 (예: 의학과, 간호학과, 심리학과 등)**")
            st.session_state.data['clinical_experience'] = st.radio(
                "**실제 환자 상담 경험 유무**", 
                options=["예", "아니요"],
                index=None,
                horizontal=True
            )
            st.session_state.data['clinical_years'] = st.number_input(
                "**임상 경력 년차 (※ 상담 경험 '예' 응답자만 기재)**", 
                min_value=0, # '아니요'인 사람을 위해 0을 허용
                max_value=50,    
                value=0,         
                step=1
            )

            st.session_state.data['certifications'] = st.text_area(
                "**보유하고 있는 상담 및 정신의학 자격증 전체 기재**",
                placeholder="정확한 명칭과 급수를 기재해 주십시오. (예: 임상심리사 1급, 청소년상담사 2급)\n해당 사항이 없을 경우 '없음'이라고 기재해 주십시오."
            )

            st.session_state.data['communication_difficulty'] = st.text_area(
                "8. 환자 면담 및 의사소통과 관련된 경험 또는 예상되는 어려움을 간략히 적어주십시오.",
                placeholder="[임상/실습 경험이 있는 경우] 실제 환자나 모의 환자 면담 시 진단 과정이나 의사소통에서 가장 큰 어려움을 느꼈던 경험을 적어주십시오.\n"
                            "[임상/실습 경험이 없는 경우] 향후 정신질환 환자를 대면할 때, 진단 과정이나 의사소통 측면에서 가장 어려울 것으로 예상되는 점을 자유롭게 적어주십시오."
            )

            
            st.markdown("**귀하는 과거에 임상 실습이나 면담 훈련을 위해 다음과 같은 '환자 시뮬레이션 훈련'을 경험해 본 적이 있습니까? (해당하는 것 모두 선택)**")
            
            # 피드백 1 반영: 항목 전개 및 기타 텍스트 입력칸 구현
            cb_none = st.checkbox("경험 없음")
            cb_peer = st.checkbox("동료 및 선후배 간의 역할극 (Peer Role-playing)")
            cb_sp = st.checkbox("표준화 환자 (SP, 훈련된 모의 환자 연기자) 대면 면담")
            cb_text = st.checkbox("텍스트 기반 환자 시나리오 챗봇")
            cb_vp = st.checkbox("화면 속 아바타/가상 환자(Virtual Patient) 시뮬레이션 프로그램")
            cb_video = st.checkbox("사전 녹화된 실제 환자 또는 모의 환자 영상 관찰 훈련")
            cb_other = st.checkbox("기타")
            
            other_text = ""
            if cb_other:
                other_text = st.text_input("기타 사항을 구체적으로 기재해 주십시오.")

            if st.form_submit_button("다음 단계로"):
                required_keys = ['name', 'gender', 'birth_date', 'major', 'clinical_experience', 'certifications', 'communication_difficulty']
                if not all(st.session_state.data.get(k) for k in required_keys):
                    st.warning("모든 인적 사항 항목을 빠짐없이 입력해 주십시오.")
                    st.stop()
                
                selected_experiences = []
                if cb_none: selected_experiences.append("경험 없음")
                if cb_peer: selected_experiences.append("동료/선후배 역할극")
                if cb_sp: selected_experiences.append("표준화 환자 대면 면담")
                if cb_text: selected_experiences.append("텍스트 챗봇")
                if cb_vp: selected_experiences.append("가상 환자 프로그램")
                if cb_video: selected_experiences.append("영상 관찰 훈련")
                if cb_other: 
                    if not other_text.strip():
                        st.error("'기타'를 선택하신 경우 내용을 기재해 주십시오.")
                        st.stop()
                    selected_experiences.append(f"기타: {other_text}")

                if len(selected_experiences) == 0:
                    st.error("8번 문항에 대해 최소 한 개 이상의 항목을 선택해 주십시오.")
                    st.stop()

                if "경험 없음" in selected_experiences and len(selected_experiences) > 1:
                    st.error("'경험 없음'과 다른 훈련 경험을 동시에 선택할 수 없습니다. 응답을 논리적으로 수정해 주십시오.")
                    st.stop()

                st.session_state.data['simulation_experience'] = selected_experiences
                st.session_state.stage = 1
                st.rerun()

    # ---------------------------------------------------------
    # [Stage 1] 실험 안내사항
    # ---------------------------------------------------------
    elif st.session_state.stage == 1:
        st.title("가상환자 평가 실험")
        st.subheader("📢 실험 진행 안내사항")
        st.markdown(
            "<div style='color: #1f77b4; font-size: 16px; margin-bottom: 15px;'>"
            "1. 본 실험은 영상의 음성과 아바타의 모션을 평가하므로, 반드시 <b>이어폰을 착용한 상태</b>로 진행해 주십시오.</div>"
            "<div style='color: #1f77b4; font-size: 16px; margin-bottom: 15px;'>"
            "2. 실험 도중 절대로 <b>'새로고침(F5)'</b>이나 <b>'뒤로 가기'</b> 버튼을 누르지 마십시오.</div>"
            "<div style='color: #1f77b4; font-size: 16px; margin-bottom: 25px;'>"
            "3. 도중에 창을 닫으면 데이터가 소실됩니다. <b>반드시 한 번에 끝까지 진행해 주십시오.</b></div>", 
            unsafe_allow_html=True
        )
        
        if st.button("안내사항 확인 및 실험 시작"):
            with st.spinner("실험 환경을 설정 중입니다..."):
                client = get_gspread_client()
                sheet = client.open("ExperimentDB").worksheet("groups")
                data = pd.DataFrame(sheet.get_all_records())
                
                min_group = data.loc[data['count'].idxmin()]
                st.session_state.video_order = GROUPS[min_group['group_id']]
                st.session_state.data['group_id'] = min_group['group_id']
                
                row_index = data.index[data['group_id'] == min_group['group_id']][0] + 2
                sheet.update_cell(row_index, 2, int(min_group['count']) + 1)
                
                st.session_state.stage = 2
                st.rerun()

    # ---------------------------------------------------------
    # Stage 계산식 (총 N개의 영상 기준)
    # Phase 1 (진단): Stage 2 ~ (2 + N - 1)
    # Intermission (정답 공개): Stage (2 + N)
    # Phase 2 (시스템 평가): Stage (2 + N + 1) ~ (2 + 2N)
    # Final (종합 평가): Stage (2 + 2N + 1)
    # Save & Done: Stage (2 + 2N + 2) & (2 + 2N + 3)
    # ---------------------------------------------------------
    else:
        N = len(st.session_state.video_order)
        phase1_end = 2 + N - 1
        intermission_stage = 2 + N
        phase2_end = 2 + 2 * N
        final_stage = 2 + 2 * N + 1
        save_stage = 2 + 2 * N + 2
        done_stage = 2 + 2 * N + 3

        # ---------------------------------------------------------
        # [Phase 1] 임상적 진단 및 증상 평가 (영상별 순차 진행)
        # ---------------------------------------------------------
        if 2 <= st.session_state.stage <= phase1_end:
            video_idx = st.session_state.stage - 2
            video_id = st.session_state.video_order[video_idx]
            required_time = VIDEO_LENGTHS.get(video_id, 60)
            
            st.title("[Phase 1] 진단 평가")
            st.write(f"###  임상적 진단 및 증상 평가: {video_idx + 1} / {N}")
            # st.markdown("#### ")
            st.info("*가상 환자 영상을 시청하신 후, 이를 바탕으로 아래 질문에 답해 주십시오.*")

            if f"play_started_{video_id}_p1" not in st.session_state:
                st.session_state[f"play_started_{video_id}_p1"] = False
                st.session_state[f"start_time_{video_id}_p1"] = 0
                st.session_state[f"unlocked_{video_id}_p1"] = False

            if not st.session_state[f"play_started_{video_id}_p1"]:
                if st.button("▶️ 영상 시청 시작", key=f"start_btn_{video_id}_p1"):
                    st.session_state[f"play_started_{video_id}_p1"] = True
                    st.session_state[f"start_time_{video_id}_p1"] = time.time()
                    st.rerun()
                st.stop()
            else:
                video_path = f"videos/{video_id}.mp4"
                with open(video_path, "rb") as v_file:
                    video_bytes = v_file.read()
                encoded_video = base64.b64encode(video_bytes).decode()
                
                controls = "autoplay" if not st.session_state[f"unlocked_{video_id}_p1"] else 'controls controlsList="nodownload noplaybackrate" disablePictureInPicture'
                video_html = f"""
                    <div style="display: flex; justify-content: center; width: 100%;">
                        <video style="width: 100%; height: 85vh; max-width: none; object-fit: contain; margin-bottom: 25px;" {controls}>
                            <source src="data:video/mp4;base64,{encoded_video}" type="video/mp4">
                        </video>
                    </div>
                """
                st.markdown(video_html, unsafe_allow_html=True)

                # 진단 평가는 영상을 끝까지 봐야만 오픈됨
                if not st.session_state[f"unlocked_{video_id}_p1"]:
                    st.warning("영상이 종료된 후 아래 버튼을 눌러 평가 문항을 여십시오.")
                    if st.button("평가 문항 열기", key=f"unlock_btn_{video_id}_p1"):
                        if time.time() - st.session_state[f"start_time_{video_id}_p1"] < required_time:
                            st.error("아직 영상 시청이 완료되지 않았습니다.")
                        else:
                            st.session_state[f"unlocked_{video_id}_p1"] = True
                            st.rerun()
                    st.stop()

            with st.form(f"survey_part1_{video_id}"):
                st.markdown("**9. 이 환자의 가장 가능성 높은 질환(진단명)은 무엇이라고 생각하십니까?**")
                st.session_state.data[f"{video_id}_q9_category"] = st.selectbox(
                    "대분류 선택",
                    ["없음", "신경발달 장애", "조현병 스펙트럼 및 기타 정신병적 장애", "양극성 및 관련 장애", "우울장애", 
                     "불안장애", "강박 및 관련 장애", "외상 및 스트레스 관련 장애", "해리 장애", "신체 증상 관련 장애", 
                     "급식 및 섭식 장애", "배설 장애", "수면-각성 장애", "성기능 부전", "성별 불쾌감", 
                     "파괴적, 충동조절 및 품행 장애", "물질관련 및 중독 장애", "신경인지 장애", "성격장애", "변태성욕 장애", "기타"],
                    index=None
                )
                st.session_state.data[f"{video_id}_q9_detail"] = st.text_input("세부 질환명 서술 (예: 공황장애, 알츠하이머병 등)")

                st.session_state.data[f"{video_id}_q10_severity"] = st.radio(
                    "**1. 이 환자의 전반적인 증상 심각도(Severity)는 어느 정도라고 평가하십니까?**", 
                    ["None (증상 없음)", "Mild (경도)", "Moderate (중등도)", "Severe (중증)"], index=None
                )

                st.session_state.data[f"{video_id}_q11_cues"] = st.multiselect(
                    "**2. 위와 같이 진단 및 심각도를 판단하는 데 '가장 큰 영향'을 미친 주요 단서(Cues)를 모두 선택해 주십시오.**", 
                    ["발화 내용 (Text/Speech Content)", "목소리 톤 및 속도 (Voice/Prosody)", 
                     "표정 및 시선 처리 (Facial Expression & Eye movement)", "신체적 움직임 및 자세 (Body movement/Posture)", 
                     "환자의 외양 및 옷차림 (Appearance)"]
                )
                
                st.session_state.data[f"{video_id}_q12_reason"] = st.text_area("**3. 위 단서를 선택한 구체적인 이유를 적어주십시오.**")

                if st.form_submit_button("평가 제출 및 다음 단계로"):
                    req_part1 = [f"{video_id}_q9_category", f"{video_id}_q9_detail", f"{video_id}_q10_severity", f"{video_id}_q11_cues", f"{video_id}_q12_reason"]
                    if not all(st.session_state.data.get(k) for k in req_part1):
                        st.error("모든 평가 문항에 응답해 주십시오.")
                        st.stop()
                    st.session_state.stage += 1
                    st.rerun()

        # ---------------------------------------------------------
        # [Intermission] 정답 일괄 공개
        # ---------------------------------------------------------
        elif st.session_state.stage == intermission_stage:
            st.title("[안내] 가상 환자 설계 정답 공개")
            st.success("귀하의 임상적 진단 평가(Phase 1)가 모두 완료되었습니다.")
            
            st.markdown("### 각 가상 환자별 실제 설계된 질환/심각도")
            for idx, vid in enumerate(st.session_state.video_order):
                gt_diag = GROUND_TRUTH.get(vid, {}).get("diagnosis", "미상")
                gt_sev = GROUND_TRUTH.get(vid, {}).get("severity", "미상")
                st.write(f"- **환자 {idx + 1}**: 질환 - {gt_diag} / 심각도 - {gt_sev}")
            
            st.markdown("---")
            st.warning("""
            **[다음 단계 진행 안내]**
            이후의 설문은 위에서 확인하신 **'설계된 정답'을 기준**으로, 
            가상 환자 시스템이 실제 질환의 특성을 얼마나 잘 구현했는지 시스템 자체의 완성도를 평가하는 단계입니다.
            각 환자의 영상과 설문지가 한 화면에 동시에 제공되오니, 필요 시 영상을 다시 참고하며 문항에 응답해 주십시오.
            """)
            
            if st.button("시스템 평가(Phase 2) 시작"):
                st.session_state.stage += 1
                st.rerun()

        # ---------------------------------------------------------
        # [Phase 2] 시스템 평가 (섹션 3~6, 설문지 즉시 개방)
        # ---------------------------------------------------------
        elif intermission_stage < st.session_state.stage <= phase2_end:
            video_idx = st.session_state.stage - intermission_stage - 1
            video_id = st.session_state.video_order[video_idx]
            
            gt_diag = GROUND_TRUTH.get(video_id, {}).get("diagnosis", "미상")
            gt_sev = GROUND_TRUTH.get(video_id, {}).get("severity", "미상")

            st.title("[Phase 2] 시스템 평가")
            st.write(f"### 대상 환자 {video_idx + 1} / {N}")
            st.info(f"이 가상 환자의 정답 기준: **[질환: {gt_diag} / 심각도: {gt_sev}]**")

            # 영상 렌더링 (컨트롤바 허용 및 자동 재생 방지)
            video_path = f"videos/{video_id}.mp4"
            with open(video_path, "rb") as v_file:
                video_bytes = v_file.read()
            encoded_video = base64.b64encode(video_bytes).decode()
            
            video_html = f"""
                <div style="display: flex; justify-content: center; width: 100%;">
                    <video style="width: 100%; height: 50vh; max-width: none; object-fit: contain; margin-bottom: 25px;" controls controlsList="nodownload" disablePictureInPicture>
                        <source src="data:video/mp4;base64,{encoded_video}" type="video/mp4">
                    </video>
                </div>
            """
            st.markdown(video_html, unsafe_allow_html=True)

            with st.form(f"survey_part2_{video_id}"):
                st.write("*아래의 모든 평가 기준은 실제 정답값으로 제시된 질환/심각도를 바탕으로 합니다.*")
                st.subheader("가상 환자의 시각/언어적 자연스러움 평가")
                st.write("*임상적 증상을 떠나, 아바타 자체의 완성도와 이질감을 평가해 주십시오.*")
                
                st.session_state.data[f"{video_id}_q14_humanlikeness"] = st.radio(
                    "**1. [인간미/의인화 수준] 가상 환자는 인간 상호작용에서 흔히 볼 수 있는 특성을 보였습니까, 아니면 자동적인 존재처럼 보였습니까?**",
                    [
                        "1점 - 인간과 닮지 않음 (감정적 미묘함, 상황 인식 및 자발성이 부족하여 일관되게 인위적인 모습을 보입니다.)",
                        "2점 - 약간 인간과 유사함 (종종 기계적인 느낌을 주며, 경직된 패턴, 반복적인 표현, 부자연스러운 반응을 보입니다.)",
                        "3점 - 다소 인간과 유사함 (인간과 유사한 경향을 보이지만, 때때로 정해진 각본대로 행동하거나 자연스러운 행동 변화가 부족해 보입니다.)",
                        "4점 - 대체로 인간과 유사함 (감정 표현이나 반응 패턴에 약간의 불일치가 있을 뿐, 전반적으로 인간과 유사한 방식으로 행동합니다.)",
                        "5점 - 매우 인간과 유사함 (실제 인간에게서 볼 수 있는 풍부하고 미묘한 뉘앙스와 예측 불가능한 행동을 보입니다. 반응에는 감정, 미묘한 어조 변화, 적절한 망설임이 포함됩니다.)"
                    ], index=None
                )
                
                st.session_state.data[f"{video_id}_q15_naturalness"] = st.radio(
                    "**2. [시각적 자연스러움] 가상 환자의 의사소통 행동이 실제 사람들의 행동과 일치했습니까?**",
                    [
                        "1점 - 매우 부자연스러움 (기계적이고 부자연스럽거나 상황에 맞지 않는 방식으로 의사소통하여 상호작용이 인위적으로 느껴집니다.)",
                        "2점 - 다소 부자연스러움 (대화가 부자연스럽고, 로봇 같거나, 지나치게 대본처럼 느껴져 현실감이 떨어집니다.)",
                        "3점 - 보통 (환자의 말 흐름은 적절하지만, 때때로 경직되거나 지나치게 격식적인 언어를 사용하여 자연스러움이 떨어집니다.)",
                        "4점 - 대체로 자연스러움 (대체로 현실적인 방식으로 의사소통하며, 부자연스러운 표현이나 상호작용은 가끔씩만 나타납니다.)",
                        "5점 - 매우 자연스러움 (의사소통 방식, 어조 및 표현이 실제 사람 상호작용과 완벽하게 일치합니다. 다양한 대화 신호에 자연스럽게 적응합니다.)"
                    ], index=None
                )
                
                st.session_state.data[f"{video_id}_q16_fluency"] = st.radio(
                    "**3. [발화의 유창성] 가상 환자가 일관성 있고 매끄러운 방식으로 의사소통을 했습니까?**",
                    [
                        "1점 - 전혀 유창하지 않음 (논리적 일관성에 어려움을 겪으며, 자주 단절되거나 불완전하거나 무의미한 답변을 합니다.)",
                        "2점 - 다소 유창하지 않음 (잦은 머뭇거림, 부자연스러운 멈춤 또는 단절된 답변으로 인해 의사소통이 방해받습니다.)",
                        "3점 - 보통 (일부 답변이 단편적이거나 약간 어색하지만 대체로 이해할 수 있습니다.)",
                        "4점 - 대체로 유창함 (답변은 일반적으로 매끄럽고 구조가 잘 잡혀 있으며, 일관성이나 흐름에 있어 사소한 불일치만 있을 뿐입니다.)",
                        "5점 - 매우 유창함 (최소한의 멈춤, 갑작스러운 주제 전환 또는 일관성 부족 없이 일관성 있고 구체적이며 매끄러운 방식으로 의사소통합니다.)"
                    ], index=None
                )

                st.divider()
                st.subheader("가상 환자의 임상적 현실성 평가")
                st.write("*가상 환자가 실제 환자의 특성을 얼마나 잘 반영했는지 1~5점 척도로 평가해 주십시오.*")

                st.session_state.data[f"{video_id}_q17_realism"] = st.radio(
                    "**4. [증상 현실성] 가상 환자가 할당된 질환/심각도과 일치하는 방식으로 증상을 보였습니까?**",
                    [
                        "1점 - 전혀 현실적이지 않음 (질환과 관련 없는 증상을 나타내거나 현실적인 증상이 없습니다.)",
                        "2점 - 다소 비현실적임 (증상이 종종 불완전하거나, 잘못 표현되거나, 피상적으로 표현됩니다.)",
                        "3점 - 보통 (일부 증상은 임상적 기대치와 일치하지만, 다른 증상은 과장되거나, 나타나지 않거나 일관성이 없습니다.)",
                        "4점 - 대체로 현실적임 (대부분의 증상이 정확하게 표현되었으며, 사소한 부정확함이나 세부 정보 누락만 있을 뿐입니다.)",
                        "5점 - 매우 현실적임 (광범위한 질환 관련 증상을 정확하게 나타냅니다.)"
                    ], index=None
                )
                
                st.session_state.data[f"{video_id}_q18_consistency"] = st.radio(
                    "**5. [감정적 일관성] 가상 환자가 할당된 질환/심각도에 맞춰 감정적, 인지적 패턴을 일관되게 유지했습니까?**",
                    [
                        "1점 - 전혀 일관되지 않음 (환자의 감정 표현이 무작위적이거나 모순되어 신뢰성이 떨어집니다.)",
                        "2점 - 다소 일관되지 않음 (감정적 반응의 잦은 불일치는 질환/심각도 수준의 변동과 같은 현실성을 감소시킵니다.)",
                        "3점 - 보통 (때때로 질환/심각도와 일치하지만 가끔 강도나 적절성이 달라지기도 합니다.)",
                        "4점 - 대체로 일관됨 (일반적으로 적절한 감정적 반응을 유지하지만 사소한 편차나 불일치가 있습니다.)",
                        "5점 - 매우 일관됨 (상호작용 내내 일치하는 안정적인 감정적, 인지적 패턴을 유지합니다.)"
                    ], index=None
                )
                
                st.session_state.data[f"{video_id}_q19_cognitive"] = st.radio(
                    "**6. [인지 부하 및 처리 스타일] 가상 환자의 발화가 할당된 질환과 관련된 인지 처리 패턴을 잘 반영했습니까?**",
                    [
                        "1점 - 전혀 반영하지 않음 (질환과 관련된 의미 있는 인지 처리 패턴을 전혀 나타내지 않아 신뢰성이 떨어집니다.)",
                        "2점 - 다소 반영하지 않음 (인지 패턴이 약하게 표현되거나 때로는 알려진 질환 특성과 모순됩니다.)",
                        "3점 - 보통 (일부 질환과 관련된 인지 특성이 존재하지만 일관성 있게 표현되지 않거나 항상 일치하지는 않습니다.)",
                        "4점 - 대체로 반영함 (일반적으로 적절한 인지 처리 패턴을 보이지만 약간의 불일치가 있습니다.)",
                        "5점 - 매우 정확히 반영함 (임상적으로 타당하고 일관된 방식으로 질환과 관련된 인지 패턴을 보여줍니다.)"
                    ], index=None
                )

                st.divider()
                st.subheader("가상 환자 경험에 대한 조사")
                st.write("*이 특정 유형의 가상 환자와의 경험에 대해 답해 주십시오.*")

                st.session_state.data[f"{video_id}_q20_seen_similar"] = st.radio("**7. 위 가상 환자와 유사한 환자를 만나본 적이 있습니까?**", ["예", "아니요"], index=None, horizontal=True)
                st.session_state.data[f"{video_id}_q21_frequency"] = st.radio("**8. 위 가상 환자와 같은 환자를 얼마나 자주 만나십니까?**", ["거의 매일", "일주일에 여러 번", "한 달에 한두 번", "일 년에 한두 번", "만난 적 없음"], index=None)
                st.session_state.data[f"{video_id}_q22_common"] = st.radio("**9. 위 가상 환자와 같은 환자는 실제 임상 현장에서 흔히 볼 수 있습니다.**", ["1점 (전혀 동의하지 않음)", "2점 (동의하지 않음)", "3점 (보통)", "4점 (동의함)", "5점 (매우 동의함)"], index=None, horizontal=True)

                st.divider()
                st.subheader("가상 환자 경험 평가")
                st.write("*이 설문지는 학생들이 가상 환자와의 경험을 평가하기 위한 것으로, 특히 임상적 추론 능력 발달에 초점을 맞추고 있습니다.*")
                
                likert_scales = ["1점 (전혀 동의하지 않음)", "2점 (동의하지 않음)", "3점 (보통/중립)", "4점 (동의함)", "5점 (매우 동의함)", "해당 없음"]
                
                st.markdown("**[환자 대면 및 면담의 진정성]**")
                st.session_state.data[f"{video_id}_q23_authenticity1"] = st.radio("**10. 이 케이스를 진행하는 동안, 나는 실제 의사들이 현실에서 내려야 하는 것과 동일한 결정을 내려야 한다고 느꼈다.**", likert_scales, index=None, horizontal=True)
                st.session_state.data[f"{video_id}_q24_authenticity2"] = st.radio("**11. 이 케이스를 진행하는 동안, 나는 내가 이 환자를 담당하는 주치의라고 느꼈다.**", likert_scales, index=None, horizontal=True)
                
                st.markdown("**[전문적 추론 접근]**")
                st.session_state.data[f"{video_id}_q25_reasoning1"] = st.radio("**12. 나는 환자의 문제를 특징짓기 위해 필요한 정보(병력 등)를 수집하는 데 적극적으로 참여했다.**", likert_scales, index=None, horizontal=True)
                st.session_state.data[f"{video_id}_q26_reasoning2"] = st.radio("**13. 나는 새로운 정보가 주어짐에 따라 환자의 문제에 대한 나의 초기 인상(가설)을 수정하는 데 적극적으로 참여했다.**", likert_scales, index=None, horizontal=True)
                st.session_state.data[f"{video_id}_q27_reasoning3"] = st.radio("**14. 나는 의학 용어를 사용하여 환자의 문제에 대한 짧은 요약을 작성하는 데 적극적으로 참여했다.**", likert_scales, index=None, horizontal=True)
                st.session_state.data[f"{video_id}_q28_reasoning4"] = st.radio("**15. 나는 관찰된 소견들이 나의 감별 진단들을 각각 지지하는지 혹은 반박하는지 고민하는 데 적극적으로 참여했다.**", likert_scales, index=None, horizontal=True)

                st.markdown("**[학습 효과 및 전반적 평가]**")
                st.session_state.data[f"{video_id}_q29_learning1"] = st.radio("**16. 이 케이스를 마친 후, 나는 동일한 증상을 호소하는 실제 환자를 만났을 때 진단을 확정하고 감별해 낼 준비가 더 잘 되었다고 느낀다.**", likert_scales, index=None, horizontal=True)
                st.session_state.data[f"{video_id}_q30_learning2"] = st.radio("**17. 이 케이스를 마친 후, 나는 동일한 증상을 호소하는 실제 환자를 돌볼 준비가 더 잘 되었다고 느낀다.**", likert_scales, index=None, horizontal=True)
                st.session_state.data[f"{video_id}_q31_overall_case"] = st.radio("**18. 전반적으로, 이 케이스를 수행한 것은 가치 있는 학습 경험이었다.**", likert_scales, index=None, horizontal=True)

                if st.form_submit_button("평가 제출 및 다음 단계로"):
                    # 버그의 원인이었던 복잡한 검증 로직을 직관적이고 안전한 리스트 형태로 완벽히 교체했습니다.
                    req_part2 = [
                        f"{video_id}_q14_humanlikeness", f"{video_id}_q15_naturalness", f"{video_id}_q16_fluency",
                        f"{video_id}_q17_realism", f"{video_id}_q18_consistency", f"{video_id}_q19_cognitive",
                        f"{video_id}_q20_seen_similar", f"{video_id}_q21_frequency", f"{video_id}_q22_common",
                        f"{video_id}_q23_authenticity1", f"{video_id}_q24_authenticity2", 
                        f"{video_id}_q25_reasoning1", f"{video_id}_q26_reasoning2", f"{video_id}_q27_reasoning3", f"{video_id}_q28_reasoning4", 
                        f"{video_id}_q29_learning1", f"{video_id}_q30_learning2", f"{video_id}_q31_overall_case"
                    ]
                    
                    if not all(st.session_state.data.get(k) for k in req_part2):
                        st.error("모든 객관식 평가 항목에 빠짐없이 응답해 주십시오.")
                        st.stop()
                    
                    st.session_state.stage += 1
                    st.rerun()

        # ---------------------------------------------------------
        # [Final Phase] 섹션 7: 종합 평가 및 피드백
        # ---------------------------------------------------------
        elif st.session_state.stage == final_stage:
            st.title("가상환자 평가 실험")
            st.subheader("임상 훈련 도구로서의 활용성 및 종합 평가")
            st.info("모든 영상 평가가 완료되었습니다. 마지막으로 본 가상 환자 시스템 전체에 대한 종합적인 의견을 여쭙습니다.")
            
            with st.form("final_comprehensive_survey"):
                st.session_state.data["q31_overall_exp"] = st.radio(
                    "**19. 가상 환자를 사용한 귀하의 전반적인 경험을 1에서 10까지의 척도로 평가해 주십시오. (1점: 매우 나쁨 ~ 10점: 매우 좋음)**", 
                    [str(i) for i in range(1, 11)], index=None, horizontal=True
                )
                st.session_state.data["q32_reuse_intent"] = st.radio(
                    "**20. 향후 훈련 과정 중에 가상 환자를 다시 사용할 의향(관심)이 얼마나 있습니까? (1점: 전혀 관심 없음 ~ 10점: 매우 관심 있음)**", 
                    [str(i) for i in range(1, 11)], index=None, horizontal=True
                )
                
                st.session_state.data["q33_pros"] = st.text_area("**21. 임상 교육 도구로서 본 가상 환자 시스템의 가장 큰 장점은 무엇이라고 생각하십니까?**")
                st.session_state.data["q34_cons"] = st.text_area("**22. 본 가상 환자 시스템에서 이질감을 느꼈던 부분이나, 향후 반드시 개선되어야 할 점이 있다면 자유롭게 제안해 주십시오.**")
                
                if st.form_submit_button("최종 데이터 제출 및 실험 종료"):
                    if not all([st.session_state.data.get("q31_overall_exp"), st.session_state.data.get("q32_reuse_intent"), 
                                st.session_state.data.get("q33_pros"), st.session_state.data.get("q34_cons")]):
                        st.error("모든 종합 평가 문항 및 주관식 피드백을 작성해 주십시오.")
                        st.stop()
                    st.session_state.stage += 1
                    st.rerun()

        # ---------------------------------------------------------
        # [Save Phase] 데이터 저장 로직
        # ---------------------------------------------------------
        elif st.session_state.stage == save_stage:
            with st.spinner("데이터를 서버에 기록 중입니다. 잠시만 기다려주세요..."):
                client = get_gspread_client()
                sheet = client.open("ExperimentDB").worksheet("logs")
                
                st.session_state.data['timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                ordered_keys = ['timestamp', 'name', 'gender', 'birth_date', 'major', 'clinical_experience', 'clinical_years', 'certifications', 'communication_difficulty', 'simulation_experience', 'group_id']
                
                all_videos = ["M0", "M1", "M2", "M3", "F0", "F1", "F2", "F3"]
                for v in all_videos:
                    ordered_keys.extend([
                        f"{v}_q9_category", f"{v}_q9_detail", f"{v}_q10_severity", f"{v}_q11_cues", f"{v}_q12_reason",
                        f"{v}_q13_humanlikeness", f"{v}_q14_naturalness", f"{v}_q15_fluency",
                        f"{v}_q16_realism", f"{v}_q17_consistency", f"{v}_q18_cognitive",
                        f"{v}_q19_seen_similar", f"{v}_q20_frequency", f"{v}_q21_common",
                        f"{v}_q22_authenticity1", f"{v}_q23_authenticity2", f"{v}_q24_reasoning1", f"{v}_q25_reasoning2", f"{v}_q26_reasoning3", f"{v}_q27_reasoning4",
                        f"{v}_q28_learning1", f"{v}_q29_learning2", f"{v}_q30_overall_case"
                    ])
                    
                ordered_keys.extend(["q31_overall_exp", "q32_reuse_intent", "q33_pros", "q34_cons"])
                
                ordered_data = []
                for k in ordered_keys:
                    val = st.session_state.data.get(k, "N/A")
                    if isinstance(val, list):
                        val = ", ".join(map(str, val))
                    ordered_data.append(val)

                sheet.append_row(ordered_data)
                st.session_state.stage += 1
                st.rerun()

        # ---------------------------------------------------------
        # [Done Phase] 완료 화면
        # ---------------------------------------------------------
        elif st.session_state.stage == done_stage:
            st.balloons()
            st.success("설문이 모두 완료되었습니다. 연구에 참여해 주셔서 진심으로 감사드립니다.")
            st.write("안전하게 창을 닫아주셔도 좋습니다.")

if __name__ == "__main__":
    main()