# 매일 자동 수집

담당자 컴퓨터를 켜지 않아도, GitHub Actions가 매일 아침 운세를 수집해
이 레포에 커밋합니다.

## 어떻게 돌아가는지

| 수집 항목 | 출처 | 방식 |
|---|---|---|
| 띠별 운세 이미지 | 인스타그램 `@sinbi_saju` | 공개 임베드 페이지(`instagram.com/sinbi_saju/embed/`, 로그인 불필요)에서 오늘 날짜 캡션의 포스트를 찾아 `fortunes/YYYY-MM-DD.jpg`로 저장하고, shortcode를 `fortune-index.json`에 기록 |
| 별자리 운세 12개 | 아사히 방송(ABC, `おはよう朝日です`) 공식 JSON (`asahi.co.jp/data/ohaasa2020/horoscope.json`) | 순위·별자리·일본어 원문·행운 아이템을 읽어 한국어로 번역 후 `horoscope-editions.json`에 추가 |

스케줄: 매일 **06:30 KST** 본 실행 + **08:30 KST** 백업 실행
(`.github/workflows/daily-fortune.yml`). 두 실행 모두 이미 수집된
날짜는 건너뛰므로 중복 커밋이 없습니다.

### 왜 빌드 없이 데이터만 커밋해도 되나요

이 레포에는 빌드된 결과물만 있고 Next.js 소스가 없습니다. 그래도 되는
이유는 두 페이지가 데이터를 빌드 타임이 아니라 **브라우저에서**
읽어오기 때문입니다.

- 띠별 운세 페이지: `fetch("/fortune-index.json", {cache: "no-store"})`
  후 `/fortunes/<날짜>.jpg` 로드. shortcode는 인스타그램 원문 링크에만 사용.
- 별자리 운세 페이지: `fetch("/horoscope-editions.json", {cache: "no-store"})`
  후 날짜로 해당 회차를 찾아 표시.

그래서 `fortune-index.json`, `horoscope-editions.json`,
`fortunes/*.jpg` 세 가지만 갱신하면 사이트에 바로 반영되고,
`index.html`의 어제 날짜 같은 정적 HTML은 첫 화면용일 뿐 로드 직후
새 데이터로 바뀝니다. GitHub Pages도 `main` 푸시마다 자동 배포됩니다.

## 수동 실행 / 다시 수집

Actions > Daily fortune > Run workflow에서:

- `date`: `YYYY-MM-DD` (KST). 비우면 오늘. 과거 날짜 재수집(백필)도 가능.
- `fortune_shortcode`: 인스타그램 자동 탐색이 막혔을 때 포스트
  shortcode를 직접 지정. `instagram.com/p/<shortcode>/` 주소의
  `<shortcode>` 부분입니다.
- `wait_minutes`: 오늘 운세가 아직 안 올라왔을 때 기다릴 시간(기본 120분).

로컬에서도 바로 실행할 수 있습니다 (Python 3.11+, 의존성 없음).

```bash
python3 scripts/scrape_daily.py --date 2026-11-24 --wait-minutes 0
python3 scripts/scrape_daily.py --date 2026-11-24 --fortune-shortcode DgFpujpjEQE
```

이미 수집된 날짜는 다시 실행해도 아무것도 바꾸지 않습니다.

## 별자리 번역 방식과 한계

아사히 원문은 일본어이고, 매일 문장이 새로 쓰입니다. 기존 12개 회차를
대조해 보니 문장·행운 아이템이 거의 반복되지 않아(144개 중 문장 중복 0개),
사전만으로는 번역이 안 됩니다. 그래서 기계 번역을 씁니다.

- **요약 문장**: DeepL 키가 있으면 DeepL로 일어 → 한국어 직역(1회 호출).
  없으면 Google Translate로 일어 → 영어 → 한국어 피벗 번역. 일어 →
  한국어 직역은 이 구어체 운세 문장을 자주 망가뜨립니다
  (`チャンスが舞い込む` → `기회가 춤춘다`, `ヤル気` → `짜증`).
  피벗은 기존 사람이 번역한 문장과 비교했을 때 대부분 가깝게 나옵니다.
  다만 말투가 `~예요`가 아니라 `~습니다`가 되거나, 일부 문장이 어색할
  수 있습니다.
- **행운 아이템**: `scripts/glossary.json`을 먼저 봅니다. 기존 12개
  회차의 사람 번역을 일본어 원문과 대조해 만든 120개(색상·음식·물건)
  항목입니다. 없는 항목은 기계 번역(일어 → 한국어 직역)으로 처리합니다.
- **원문 보존**: 각 항목에 `ja_summary` / `ja_lucky`로 일본어 원문을
  함께 저장합니다. 번역이 어색하면 원문을 보고 사람이 고칠 수 있고,
  나중에 번역 방식을 바꿀 때도 원본이 남아 있습니다.

### 번역 API: DeepL 키 권장 (2026-11-25 사고 이후)

키 없이 쓰는 Google Translate 무료 엔드포인트는 공유·데이터센터 IP에
HTTP 429(Too Many Requests)를 자주 반환합니다. 2026-11-25 첫 실전에서
바로 터졌습니다. 그날은 띠별 운세 이미지는 커밋됐지만, 별자리 번역이
첫 항목(白菜)에서 429를 받아 전체 별자리 수집이 실패했습니다.
스크립트는 재시도(최대 5회, 지수 백오프) 후에도 안 되면 그날 별자리를
건너뛰고 실패로 표시합니다. 다음 실행(백업 스케줄 또는 수동 재실행,
날짜 지정 가능)이 나중에 채웁니다.

제일 확실한 해결책은 DeepL 무료 API 키입니다. 인증 방식이라 429가
없고, 일어 → 한국어 품질도 좋습니다.

1. [deepl.com](https://www.deepl.com/)에서 무료 계정 만들기
   (신용카드 불필요, 월 50만 자 무료. 이 작업은 하루 ~2,000자 사용)
2. API 키 발급 후 레포 **Settings > Secrets and variables >
   Actions > New repository secret**에서 이름 `DEEPL_API_KEY`로 등록
3. 끝. 워크플로가 자동으로 키를 넘기고, 키가 있으면 DeepL을 쓰고
   없으면 Google Translate(재시도 포함)로 돌아갑니다.

번역 방식을 바꾸고 싶으면 `scripts/scrape_daily.py`의
`translate_summary()` / `translate_text()` 부분만 바꾸면 됩니다.

## 주말 처리

- 띠별 운세(인스타그램): 토·일에도 올라오므로 매일 수집합니다.
- 별자리 운세(아사히): 월~금 아침 방송만 있어 토·일 회차가 없습니다
  (기존에도 11/14·11/15 없음). 주말에는 별자리를 건너뛰고 실패로
  처리하지 않습니다.

## 실패하면

워크플로는 수집이 끝나지 않으면 실패로 표시됩니다(담당자에게 Actions
실패 메일이 갑니다). 로그에서 어느 쪽이 문제인지 확인하세요.

- **인스타그램 임베드 페이지가 막힌 경우**: 인스타그램이 데이터센터 IP를
  막을 수 있습니다. 그날은 수동 실행에서 `fortune_shortcode`를
  지정해 다시 돌리면 됩니다.
- **아사히 JSON이 아직 안 올라온 경우**: 08:30 백업 실행이 다시
  시도합니다. 그래도 안 되면 수동 실행으로 날짜를 지정해 다시 돌리세요.
- **번역 429 (Google Translate Too Many Requests)**: 키 없이 쓰는
  Google 번역이 공유 IP를 막은 경우입니다. 몇 시간 뒤 수동 실행으로
  날짜를 지정해 다시 돌리면 대개 됩니다. 자주 반복되면 위의 DeepL
  키를 등록하는 게 확실합니다.
- **부분 수집**: 한쪽만 성공해도 성공한 쪽은 커밋됩니다. 나머지는
  다음 실행이 채웁니다.

## 머지 후 체크리스트

1. 레포 Settings > Actions > General > Workflow permissions에서
   **Read and write permissions**가 켜져 있는지 확인하세요.
   (꺼져 있으면 봇이 커밋을 못 합니다. 워크플로 파일의
   `permissions: contents: write`는 이 설정을 넘지 못합니다.)
2. 머지 다음 날 아침, `fortunes/<날짜>.jpg` 커밋이 생겼는지 한 번만
   확인하면 됩니다. 이후로는 컴퓨터를 켜지 않아도 됩니다.
3. 번역이 어색한 날이 있으면 `horoscope-editions.json`에서 해당 날짜의
   `summary`만 직접 고쳐 커밋하면 됩니다. `ja_summary`가 원문입니다.
