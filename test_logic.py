"""
슬랙 없이 논문 분석 로직만 테스트하는 스크립트.
사용법: python test_logic.py <arxiv 링크 또는 ID>

예시:
  python test_logic.py https://arxiv.org/abs/2512.23675
  python test_logic.py 2512.23675
"""
import sys
import os
import re
import arxiv
import fitz
import requests
from io import BytesIO
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

ARXIV_REGEX = r"arxiv\.org\/(?:abs|pdf)\/(\d{4}\.\d{4,5})"


def extract_intro_from_pdf(arxiv_id):
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    try:
        response = requests.get(pdf_url, timeout=30)
        if response.status_code != 200: return None

        doc = fitz.open(stream=BytesIO(response.content), filetype="pdf")
        full_text = ""
        for page in doc[:4]:
            full_text += page.get_text("text", sort=True)

        intro_match = re.search(r"(?:\d\.?\s+)?(Introduction|INTRODUCTION|Background)", full_text)
        if intro_match:
            start_idx = intro_match.start()
            next_sec_match = re.search(r"(?:\d\.?\s+)?(Related Work|Related work|Methodology|Proposed|BACKGROUND)", full_text[start_idx + 100:])
            if next_sec_match:
                return full_text[start_idx : start_idx + 100 + next_sec_match.start()]
            return full_text[start_idx : start_idx + 5000]
        return full_text[:4000]
    except Exception as e:
        print(f"PDF Parsing Error: {e}")
        return None


def get_paper_title(arxiv_id):
    try:
        search = arxiv.Search(id_list=[arxiv_id])
        paper = next(arxiv.Client().results(search))
        return paper.title
    except Exception as e:
        print(f"arxiv API Error: {e}")
        return None


def get_summary_from_llm(title, text):
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
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


def parse_arxiv_id(user_input):
    match = re.search(ARXIV_REGEX, user_input)
    if match:
        return match.group(1)
    bare = re.match(r"^(\d{4}\.\d{4,5})$", user_input.strip())
    if bare:
        return bare.group(1)
    return None


def main():
    if len(sys.argv) < 2:
        print("사용법: python test_logic.py <arxiv 링크 또는 ID>")
        print("예시:  python test_logic.py 2512.23675")
        sys.exit(1)

    arxiv_id = parse_arxiv_id(sys.argv[1])
    if not arxiv_id:
        print(f"유효한 arxiv ID를 찾을 수 없습니다: {sys.argv[1]}")
        sys.exit(1)

    print(f"{'='*50}")
    print(f"arxiv ID: {arxiv_id}")
    print(f"{'='*50}")

    # 1단계: 논문 제목 가져오기
    print("\n[1/3] 논문 제목 조회 중...")
    title = get_paper_title(arxiv_id)
    if title:
        print(f"  제목: {title}")
    else:
        print("  제목 조회 실패 (arxiv ID를 대신 사용)")

    # 2단계: PDF에서 Introduction 추출
    print("\n[2/3] PDF에서 Introduction 추출 중...")
    intro_text = extract_intro_from_pdf(arxiv_id)
    if intro_text:
        print(f"  추출 성공 ({len(intro_text)}자)")
        print(f"  --- 미리보기 (처음 500자) ---")
        print(f"  {intro_text[:500]}")
        print(f"  ---")
    else:
        print("  PDF 파싱 실패!")
        sys.exit(1)

    # 3단계: LLM 요약 생성
    if "OPENAI_API_KEY" not in os.environ or os.environ["OPENAI_API_KEY"] == "":
        print("\n[3/3] OPENAI_API_KEY가 없어서 LLM 요약을 건너뜁니다.")
        print("  위 1~2단계가 정상이면 로직은 OK입니다.")
        return

    print("\n[3/3] LLM 요약 생성 중...")
    summary = get_summary_from_llm(title or arxiv_id, intro_text)
    print(f"\n{'='*50}")
    print("최종 출력:")
    print(f"{'='*50}")
    print(f"논문 분석 결과 ({arxiv_id})\n")
    print(summary)
    print(f"\n원문 링크: https://arxiv.org/abs/{arxiv_id}")

if __name__ == "__main__":
    main()
