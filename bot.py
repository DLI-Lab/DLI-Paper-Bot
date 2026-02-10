import os
import re
import arxiv
import fitz  # PyMuPDF
import requests
from io import BytesIO
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# 클라이언트 및 앱 초기화
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
app = App(token=os.environ["SLACK_BOT_TOKEN"])

# 아카이브 ID 추출 정규식
ARXIV_REGEX = r"arxiv\.org\/(?:abs|pdf)\/(\d{4}\.\d{4,5})"

def extract_intro_from_pdf(arxiv_id):
    """PDF를 다운로드하고 Introduction 섹션만 추출합니다."""
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    try:
        response = requests.get(pdf_url, timeout=30)
        if response.status_code != 200: return None

        doc = fitz.open(stream=BytesIO(response.content), filetype="pdf")
        full_text = ""
        # 인트로는 보통 앞부분에 있으므로 4페이지까지만 탐색
        for page in doc[:4]:
            full_text += page.get_text("text", sort=True)
        
        # Introduction 섹션 탐색 및 다음 섹션 전까지 자르기
        intro_match = re.search(r"(?:\d\.?\s+)?(Introduction|INTRODUCTION|Background)", full_text)
        if intro_match:
            start_idx = intro_match.start()
            # 다음 섹션 (2. Related Work 등) 지점 탐색
            next_sec_match = re.search(r"(?:\d\.?\s+)?(Related Work|Related work|Methodology|Proposed|BACKGROUND)", full_text[start_idx + 100:])
            if next_sec_match:
                return full_text[start_idx : start_idx + 100 + next_sec_match.start()]
            return full_text[start_idx : start_idx + 5000] # 다음 섹션을 못 찾으면 5000자 제한
        return full_text[:4000] # 인트로 제목을 못 찾으면 초반부 반환
    except Exception as e:
        print(f"PDF Parsing Error: {e}")
        return None

def get_paper_title(arxiv_id):
    """arxiv API를 사용해 논문 제목을 가져옵니다."""
    try:
        search = arxiv.Search(id_list=[arxiv_id])
        paper = next(arxiv.Client().results(search))
        return paper.title
    except Exception as e:
        print(f"arxiv API Error: {e}")
        return None

def get_summary_from_llm(title, text):
    """추출된 텍스트를 기반으로 핵심 요약을 생성합니다."""
    try:
        response = client.responses.create(
            model="gpt-5",
            reasoning={"effort": "medium"},
            input=[
                {"role": "system", "content": "너는 AI 분야 전문 연구원이야. 논문의 서론(Introduction)을 읽고 한국어로 요약해줘.\n형식은 다음을 반드시 지켜 (Slack mrkdwn 기준):\n- 제목은 논문 제목을 그대로 사용.\n- 제목과 섹션명은 *bold* 처리.\n- 각 섹션의 내용은 하위 bullet(◦)로 세분화하여 가독성 있게 작성.\n- 아래 포맷 그대로 반환.\n\n*<제목>*: 논문 제목\n*<요약>*:\n• *연구 배경*:\n  ◦ 기존에 어떤 문제가 있었는가?\n  ◦ 왜 이 연구가 필요한가?\n• *핵심 아이디어*:\n  ◦ 어떤 방법/모델/프레임워크를 제안하는가?\n  ◦ 어떻게 작동하는가?\n• *차별점*:\n  ◦ 기존 연구 대비 무엇이 다른가?\n  ◦ 어떤 성과/개선이 있는가?"},
                {"role": "user", "content": f"논문 제목: {title}\n\nIntroduction text:\n{text}"}
            ],
        )
        return response.output_text
    except Exception as e:
        return f"요약 생성 중 오류 발생: {e}"

@app.event("message")
def handle_message(event, say):
    print(f"수신된 메시지: {event.get('text')}")
    text = event.get("text", "")
    match = re.search(ARXIV_REGEX, text)
    
    if match:
        arxiv_id = match.group(1)
        channel = event['channel']
        ts = event['ts']
        # 봇이 처리 중임을 알림 (이모지 반응)
        app.client.reactions_add(channel=channel, name="eyes", timestamp=ts)

        title = get_paper_title(arxiv_id)
        intro_text = extract_intro_from_pdf(arxiv_id)
        if intro_text:
            summary = get_summary_from_llm(title or arxiv_id, intro_text)
            result = (
                f"📄 *논문 분석 결과 ({arxiv_id})*\n\n"
                f"{summary}\n\n"
                f"🔗 <https://arxiv.org/abs/{arxiv_id}|원문 링크>"
            )
            say(text=result, thread_ts=ts)
        else:
            say(text="PDF를 불러오거나 파싱하는 데 실패했습니다.", thread_ts=ts)

        # 완료: 눈 이모지 제거 → 체크 이모지 추가
        app.client.reactions_remove(channel=channel, name="eyes", timestamp=ts)
        app.client.reactions_add(channel=channel, name="white_check_mark", timestamp=ts)

if __name__ == "__main__":
    print("⚡️ 슬랙 봇이 가동되었습니다! 소켓 모드 연결 시도 중...")
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    print("✅ 소켓 모드 핸들러가 준비되었습니다.")
    handler.start()