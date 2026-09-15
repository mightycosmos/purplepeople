# Purple People

> 오늘도 당신의 알고리즘은 반대편 뉴스를 숨겼습니다

좌파 성향 언론 3곳과 우파 성향 언론 3곳이 **오늘 메인에 올린 기사**를 매일 수집해,
같은 하루를 두 진영이 어떻게 다르게 앞세웠는지 나란히 보여주는 인스타그램 카드뉴스 8장을
자동으로 만들어 텔레그램으로 보내는 파이프라인입니다.

키워드 검색이 아니라 **각 언론사가 스스로 1면에 올린 것**을 그대로 가져오는 것이 핵심입니다.
어떤 주제를 다룰지 우리가 고르지 않기 때문에, 진영별 의제 설정 차이가 그대로 드러납니다.

---

## 목차

1. [동작 흐름](#동작-흐름)
2. [수집 대상 언론사](#수집-대상-언론사)
3. [카드뉴스 디자인 규격](#카드뉴스-디자인-규격)
4. [설치](#설치)
5. [환경 변수](#환경-변수)
6. [실행](#실행)
7. [모듈별 상세](#모듈별-상세)
8. [문제 해결](#문제-해결)

---

## 동작 흐름

```
scraper.py        →  llm_processor.py  →  image_gen.py     →  notifier.py
메인 뉴스 6건 수집    카드 8장 원고 생성    PNG 8장 렌더링      텔레그램 전송
(RSS / HTML 파싱)    (GPT-4o 구조화 출력)  (Jinja2+Playwright)  (send_media_group)
```

`main.py`가 네 단계를 순서대로 호출하며, 각 단계에서 기대한 개수(좌우 3건씩 / 카드 8장 / 이미지 8장)가
나오지 않으면 즉시 중단합니다. 반쯤 만들어진 카드뉴스가 발행되는 것을 막기 위함입니다.

---

## 수집 대상 언론사

| 진영 | 언론사 | 수집 방식 | 주소 |
|---|---|---|---|
| Left | 한겨레 | RSS | `hani.co.kr/rss/` |
| Left | 경향신문 | RSS | `khan.co.kr/rss/rssdata/total_news.xml` |
| Left | 오마이뉴스 | RSS | `rss.ohmynews.com/rss/ohmynews.xml` |
| Right | 조선일보 | RSS | `chosun.com/arc/outboundfeeds/rss/?outputType=xml` |
| Right | 중앙일보 | HTML | `joongang.co.kr/` 홈페이지 직접 파싱 |
| Right | 동아일보 | RSS | `rss.donga.com/total.xml` |

언론사 목록은 `scraper.py`의 `MEDIA_SOURCES`에서 바꿀 수 있습니다.

### 언론사별 예외 처리

**중앙일보 — 홈페이지 파싱**
쓸 수 있는 RSS가 없습니다(`rss.joins.com`은 빈 피드, `/rss`는 404). 그래서 홈페이지 HTML에서
`^https://www\.joongang\.co\.kr/article/\d+$` 패턴에 맞는 첫 링크를 메인 기사로 봅니다.
이때 썸네일용 제목과 본제목이 한 `<a>` 안에 중복으로 들어가 제목이 두 번 반복되므로
`_dedupe_title()`이 앞뒤 절반이 같은 문자열을 잘라냅니다.

**조선일보 — Arc Fusion CMS**
본문이 DOM에 없고 `Fusion.globalContent = {...};` 형태의 인라인 JSON 안에 들어 있습니다.
`_extract_fusion_body()`가 이 블록을 정규식으로 꺼내 파싱한 뒤 `content_elements` 중
`type == "text"`인 것만 모아 본문을 복원합니다.

### 연성 기사 필터

피드 최상단이 스포츠·연예면 좌우 대조가 무의미해집니다. `_is_hard_news()`가 두 가지로 걸러냅니다.

- **카테고리**: 스포츠, 야구, 축구, 연예, 방송, 영화, 문화, 웹툰, 게임, 여행, 칼럼, 사설, 오피니언, 포토 등
- **URL 패턴**: `star.ohmynews`, `/sports/`, `/entertainment/`, `/culture/`, `/life/`, `/travel/`, `/photo/`, `/opinion/`

조건에 걸리면 다음 아이템으로 넘어가며, 경성 기사가 나올 때까지 피드를 훑습니다.

### 본문 추출 순서

1. Fusion JSON (200자 넘게 나오면 채택)
2. `BODY_SELECTORS` CSS 선택자 순회 — `div.article-text`, `#articleBody`, `.art_body`,
   `.at_contents`, `section.article-body`, `[itemprop="articleBody"]`, `#article_body`,
   `.news_view`, `article` 등. 가장 긴 결과를 고르되 400자를 넘으면 조기 종료합니다.
3. 그래도 200자 미만이면 페이지의 모든 `<p>`를 이어 붙이는 최후 수단

추출된 텍스트는 `_clean_paragraphs()`를 거칩니다. 20자 미만인 줄과 저작권 고지(`무단 전재`,
`재배포 금지`, `저작권자`, `ⓒ`), 기자 서명, `구독하기`, `관련기사` 같은 잡음 줄을 버립니다.
최종 본문은 4,000자로 자릅니다.

---

## 카드뉴스 디자인 규격

**이 포맷은 확정된 브랜드 디자인입니다.** 기능을 고칠 때 임의로 재디자인하지 마세요.

- 크기: **1080 × 1350** (인스타그램 4:5 세로)
- 폰트: 한글 Pretendard, 로마자 워드마크 Archivo 900

| 장 | 종류 | 배경색 | 페이지 라벨 |
|---|---|---|---|
| 1 | 표지 | 보라 `#412C93` | 없음 |
| 2–4 | 좌측 언론 기사 | 파랑 `#1A3A8C` | `Left 01` · `Left 02` · `Left 03` |
| 5–7 | 우측 언론 기사 | 빨강 `#9B1B21` | `Right 01` · `Right 02` · `Right 03` |
| 8 | 마무리 | 보라 `#412C93` | 없음 |

숫자는 전체 페이지 번호가 아니라 **그 진영의 몇 번째 기사인지**를 뜻합니다.
표지와 마지막 장에는 숫자를 붙이지 않습니다.

모든 장 상단에 흰 바가 있고, 왼쪽에 워드마크 `Purple People`이 배경색과 같은 색으로 들어갑니다.
기사 카드만 오른쪽 끝에 `Left`/`Right` + 두 자리 숫자가 붙습니다.

### 표지 (고정 문구)

```
오늘도 당신의 알고리즘은
반대편 뉴스를 숨겼습니다

편향의 시대를 향한 평범한 저항
오늘 하루, 좌우 언론의 엇갈린 메인 뉴스를
Purple People이 대조해드립니다
```

### 기사 카드 (2–7장)

- **제목**: 14~24자, 마침표 없음. 원 기사 제목을 베끼지 않고 우리 말로 다시 쓴 헤드라인.
  **제목만 읽어도 무슨 일인지 알 수 있어야 합니다.** 주체와 사건이 드러나야 하고,
  `논란`·`사연`·`이슈` 같은 말로 주제만 가리키면 안 됩니다.
  (`지적장애 가족의 비극적 사연` ✗ → `중랑구 지적장애 형제 숨진 채 발견` ✓)
- **본문**: 줄바꿈 없는 **한 문단**. 공백 포함 110~130자, 문장 3~5개가 이어집니다.
  줄을 어디서 나눌지는 브라우저에 맡기고 원고에서 직접 끊지 않습니다.
- 무슨 일이 있었는지로 시작해 연결어로 배경과 반응을 잇고 쟁점이나 전망으로 닫습니다.
  한 호흡으로 읽히는 것이 목표이고, 짧은 문장을 툭툭 나열하지 않습니다.
- **모든 문장은 명사형 어미로 끝냅니다.** `~했다/~된다/~있다`가 아니라 `~했음/~됨/~있음`입니다.
  다만 서술어를 빼고 명사만 나열해서는 안 됩니다.
- 문장 사이에는 마침표를 찍되 문단 끝에는 찍지 않습니다(코드에서도 한 번 더 제거).
- **언론사 이름은 어디에도 노출하지 않습니다.**

### 마무리 (8장)

제목 `편향이 느껴지시나요?` 아래 `Left` 2줄, `Right` 2줄로 오늘 각 진영이 무엇에 무게를
실었는지 실제 인물명·사건명과 함께 요약합니다. 두 라벨은 본문과 같은 흰색입니다.
컬러 박스도, 컬러 글자도 쓰지 않습니다(보라 배경에서 선명하지 않았습니다).
요약 줄도 본문과 같은 명사형 어미로 끝냅니다.
바닥에 구분선과 `여러분의 생각을 적어주세요`가 들어갑니다.

### 본문 자동 축소

본문은 한 문단이므로 줄바꿈 위치는 브라우저에 맡기고, `break-keep`으로 단어 중간에서만
끊기지 않게 합니다. 렌더링 직후 실행되는 스크립트가 본문 블록의 `scrollHeight`가
`clientHeight`를 넘으면 글자 크기를 46px에서 30px까지 1px씩 줄여 카드 안에 들어오게 맞춥니다.

---

## 설치

Python 3.13 기준입니다.

```bash
cd purplepeople
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/playwright install chromium
```

`playwright install chromium`을 빼먹으면 이미지 생성 단계에서 실패합니다.

### 의존성

| 패키지 | 용도 |
|---|---|
| `requests` | HTTP 요청 |
| `beautifulsoup4` + `lxml` | HTML/RSS 파싱 (`xml` 파서에 `lxml` 필요) |
| `openai` | GPT-4o 구조화 출력 |
| `pydantic` | 원고 스키마 정의·검증 |
| `Jinja2` | 카드 HTML 템플릿 |
| `playwright` | 헤드리스 크롬으로 카드 캡처 |
| `python-telegram-bot` | 결과 전송 |
| `python-dotenv` | `.env` 로딩 |

---

## 환경 변수

프로젝트 루트에 `.env`를 만듭니다.

```env
OPENAI_API_KEY=sk-...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

`.env`는 절대 커밋하지 마세요. 텔레그램 토큰은 httpx 로그의 요청 URL에도 그대로 찍히므로,
로그를 공유할 일이 있으면 `| grep -v api.telegram.org`로 걸러서 보내세요.

---

## 실행

```bash
./venv/bin/python main.py                    # 전체 파이프라인 (이미지 전송 후 로컬 삭제)
./venv/bin/python main.py --keep-images      # 전송 후에도 output/ 유지
./venv/bin/python main.py --no-telegram      # 이미지만 만들고 전송하지 않음
```

결과물은 `output/card_1.png` ~ `output/card_8.png`입니다.

### 매일 아침 8시 자동 발행

`.github/workflows/daily.yml`이 **매일 08:00 (한국시간)** 파이프라인을 돌려 텔레그램으로 보냅니다.
로컬에 아무것도 띄워둘 필요 없이 깃허브에 코드가 올라가 있으면 동작합니다.

GitHub 크론은 UTC 기준이라 `0 23 * * *`(= 다음 날 08:00 KST)로 걸려 있고, 실행 단계에
`TZ: Asia/Seoul`을 줘서 프롬프트에 들어가는 `오늘 날짜`가 한국 날짜로 잡히게 했습니다.

**한 번만 해두어야 할 설정** — 저장소 **Settings → Secrets and variables → Actions**에서
아래 세 개를 등록합니다. 이게 없으면 워크플로가 실패합니다.

| Secret | 값 |
|---|---|
| `OPENAI_API_KEY` | OpenAI API 키 |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 받을 채팅방 ID |

**Actions** 탭에서 `Daily Card News` → `Run workflow`로 즉시 수동 실행해 볼 수도 있습니다.
생성된 카드 8장은 실행 결과의 artifact(`cards`)로도 7일간 남습니다.

깃허브 크론은 러너가 붐비면 수십 분 늦게 시작될 수 있습니다. 정시 발행이 중요하면
cron 시각을 조금 앞당기세요.

### 단계별 개별 실행

디버깅할 때 각 모듈을 따로 돌릴 수 있습니다.

```bash
./venv/bin/python scraper.py        # 수집된 6건의 제목·링크·본문 앞부분 출력
./venv/bin/python llm_processor.py  # 수집 후 카드 8장 JSON 출력
./venv/bin/python image_gen.py      # 샘플 표지 1장만 렌더링
```

---

## 모듈별 상세

### `scraper.py`

`scrape_main_news()` → `{"left": [...], "right": [...]}`
각 항목은 `{media, title, link, content}`입니다. 위 [수집 대상 언론사](#수집-대상-언론사) 절 참고.

### `llm_processor.py`

`generate_script(news_data)` → 카드 8장의 렌더링 딕셔너리 리스트.

모델은 `gpt-4o-2024-08-06`, `client.beta.chat.completions.parse`의 구조화 출력으로
아래 Pydantic 스키마를 강제합니다.

```python
class NewsCard(BaseModel):
    title: str
    body: str                     # 줄바꿈 없는 한 문단

class Script(BaseModel):
    left_cards: List[NewsCard]    # 정확히 3장
    right_cards: List[NewsCard]   # 정확히 3장
    closing_left: List[str]       # 2줄
    closing_right: List[str]      # 2줄
```

**본문이 문자열 하나인 것이 중요합니다.** 예전에는 `List[str]`로 다섯 줄을 받았는데,
그러면 모델이 줄 단위로 내용을 끊어 담아 카드가 개조식으로 읽혔습니다. 줄 나누기를 원고에서
떼어내 브라우저에 맡기고 모델에게는 문단 하나만 쓰게 하니 글이 한 호흡으로 이어집니다.

**시스템 프롬프트의 절대 규칙**

- 언론사 이름을 어디에도 쓰지 않는다
- 원 기사 제목을 그대로 베끼지 않는다
- 좌우 어느 쪽도 편들지 않고, 해당 기사가 실제로 말한 내용만 쓴다. 없는 사실을 지어내지 않는다

**검증 및 재시도**

생성 후 `_violations()`가 규격을 벗어난 카드를 찾습니다. 제목이 14~24자를 벗어나거나,
본문이 100~165자를 벗어나거나 줄바꿈이 섞인 경우입니다. 하나라도 있으면 모델의 답변과
지적 메시지를 대화에 덧붙여 전체 재작성을 요청합니다(최대 3회).
제목 글자 수를 강제하는 것은 길이 자체가 목적이 아니라, 너무 짧으면 필연적으로
주체와 사건을 담을 수 없어 추상적인 제목이 나오기 때문입니다.
문단 끝 마침표는 모델이 자주 붙이므로 `_news_card()`에서 한 번 더 떼어냅니다.

### `image_gen.py`

`generate_images(script, output_dir="output")` → 저장된 PNG 경로 리스트.
Playwright 크로미움을 헤드리스로 띄우고 뷰포트를 1080×1350으로 고정한 뒤,
카드 딕셔너리를 `templates/template.html`에 렌더링해 `networkidle` + 600ms 대기 후 캡처합니다.
대기 시간은 Tailwind CDN과 웹폰트가 적용될 시간을 벌기 위한 것입니다.

### `templates/template.html`

Jinja2 템플릿 하나가 `kind` 값(`cover` / `closing` / 그 외 기사)에 따라 세 갈래로 분기합니다.
상단 흰 바는 공통이고, 오른쪽 라벨은 `{% if side %}`로 감싸 표지·마무리에서는 그려지지 않습니다.

### `notifier.py`

`send_to_telegram(image_paths, delete_after=True)`
비동기 `send_media_group`을 동기 함수로 감싼 래퍼입니다. 8장을 앨범 하나로 묶어 보내고,
`delete_after=True`면 전송 후 로컬 파일과 빈 `output/` 디렉터리를 정리합니다.

---

## 문제 해결

| 증상 | 원인과 해결 |
|---|---|
| `ModuleNotFoundError: requests` | venv에 설치가 안 됨. `./venv/bin/pip install -r requirements.txt` |
| greenlet 휠 빌드 실패 | 구버전 playwright가 Python 3.13과 비호환. `requirements.txt`의 `playwright>=1.49.0` 확인 |
| RSS에서 기사가 안 잡힘 | `lxml` 미설치. BeautifulSoup의 `xml` 파서가 이걸 요구합니다 |
| 이미지 생성 단계에서 실패 | `./venv/bin/playwright install chromium` 미실행 |
| `Need 3 main articles per side` | 언론사 사이트 구조 변경. `./venv/bin/python scraper.py`로 어느 곳이 비는지 확인 |
| `Body too short for ...` 경고 | 해당 언론사 본문 선택자가 바뀜. `BODY_SELECTORS`에 추가 |
| 스포츠·연예 기사가 메인으로 잡힘 | `SOFT_CATEGORIES` / `SOFT_URL_PATTERN`에 해당 분류 추가 |
| 본문이 개조식으로 끊어짐 | `SYSTEM_PROMPT`의 좋은 예/나쁜 예를 보강. 본문은 문단 하나로 받아야 함 |
| 제목이 추상적임 | `TITLE_MIN`을 올리거나 `SYSTEM_PROMPT`의 제목 나쁜 예/좋은 예를 보강 |
| 매일 8시에 안 옴 | Actions 탭에서 워크플로 로그 확인. 대개 Secrets 누락이거나 크론 지연 |
| 본문이 카드 밖으로 넘침 | 자동 축소 하한이 30px. `BODY_MAX`를 줄이거나 하한을 낮춤 |
| `OPENAI_API_KEY is missing` | `.env` 파일 위치와 키 이름 확인 |
