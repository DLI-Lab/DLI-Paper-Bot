# DLI Paper Bot

Slack 채널에 arxiv 논문 링크가 올라오면 자동으로 Introduction을 분석하여 한국어 요약을 쓰레드에 달아주는 봇입니다.

## 동작 방식

1. Slack 메시지에서 arxiv 링크 감지 (abs/pdf 모두 지원)
2. 👀 이모지로 처리 중 표시
3. arxiv API로 논문 제목 조회
4. PDF 다운로드 후 Introduction 섹션 추출
5. LLM(GPT)으로 한국어 요약 생성
6. 원본 메시지의 쓰레드에 요약 댓글 작성
7. ✅ 이모지로 완료 표시

## 요약 출력 형식

```
*<제목>*: 논문 제목
*<요약>*:
• *연구 배경*:
  ◦ 기존에 어떤 문제가 있었는가?
  ◦ 왜 이 연구가 필요한가?
• *핵심 아이디어*:
  ◦ 어떤 방법/모델/프레임워크를 제안하는가?
  ◦ 어떻게 작동하는가?
• *차별점*:
  ◦ 기존 연구 대비 무엇이 다른가?
  ◦ 어떤 성과/개선이 있는가?
```

## 설정

### 환경변수

`.env` 파일을 프로젝트 루트에 생성합니다.

```env
OPENAI_API_KEY=sk-...
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
```

### Slack App 권한

- **Socket Mode**: 활성화
- **Event Subscriptions**: `message.channels`, `message.groups`
- **Bot Token Scopes**: `channels:history`, `chat:write`, `reactions:read`, `reactions:write`

## 실행

### Docker (권장)

```bash
docker build -t arxiv-summary-bot .
docker run -d --name arxiv-bot --env-file .env --restart always arxiv-summary-bot
```

### 로컬

```bash
pip install -r requirements.txt
python bot.py
```

## 로컬 테스트

Slack 연결 없이 PDF 파싱 + LLM 요약 로직만 테스트할 수 있습니다.

```bash
# arxiv ID로 테스트
python test_logic.py 2512.23675

# 링크로 테스트
python test_logic.py https://arxiv.org/abs/2512.23675
```

`OPENAI_API_KEY`가 없으면 1~2단계(제목 조회, PDF 파싱)만 실행됩니다.

## 프로젝트 구조

```
├── bot.py            # Slack 봇 메인
├── test_logic.py     # 로컬 테스트 스크립트
├── Dockerfile
├── requirements.txt
├── .env              # 환경변수 (git 제외)
└── start.bash        # 빌드/실행 스크립트 (git 제외)
```
