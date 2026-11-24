# 오늘의 작은 운세

띠별 운세와 한국어 별자리 운세를 한곳에서 보고, 포춘쿠키와 숨은 쪽지로 하루를 가볍게 시작하는 웹사이트입니다.

**[사이트 바로가기 →](https://momyment.github.io/little-fortune/)**

[별자리 운세 보기](https://momyment.github.io/little-fortune/horoscope/) · [업데이트 실행 내역](https://github.com/momyment/little-fortune/actions) · [수집 스크립트 안내](scripts/README.md)

## 즐길 수 있는 기능

- **띠별 운세** — 날짜별 운세 이미지를 보고, 출생연도를 입력해 내 띠의 운세를 확인할 수 있습니다.
- **별자리 운세** — 아사히 방송의 별자리 순위, 운세, 행운 아이템을 한국어로 읽고 생일로 내 별자리를 찾을 수 있습니다.
- **오늘의 포춘쿠키** — 쿠키를 열어 랜덤 메시지를 뽑아볼 수 있습니다.
- **숨은 쪽지 찾기** — 페이지에 숨은 쪽지를 찾아 메시지와 ‘오늘의 한 곡’을 만날 수 있습니다.

## 운세 업데이트

GitHub Actions의 **Daily fortune** 워크플로에 매일 한국 시간 오전 **6시 30분**, **8시 30분** 수집 일정이 설정되어 있습니다. 실제 실행과 자료 반영 시각은 GitHub Actions의 대기 시간과 원본 게시 시점에 따라 달라질 수 있습니다.

| 항목 | 출처 | 저장 위치 |
| --- | --- | --- |
| 띠별 운세 사진 | 신비사주 `@sinbi_saju` | `fortunes/YYYY-MM-DD.jpg` |
| 사진 날짜와 원본 게시물 정보 | 신비사주 게시물 | `fortune-index.json` |
| 한국어 별자리 운세 | 아사히 방송 | `horoscope-editions.json` |

별자리 운세는 방송일 자료를 기준으로 추가됩니다. 새 자료가 없는 날짜에는 다른 날짜를 선택해 저장된 운세를 볼 수 있습니다.

## 수동으로 업데이트하기

1. [Daily fortune 실행 화면](https://github.com/momyment/little-fortune/actions/workflows/daily-fortune.yml)을 엽니다.
2. **Run workflow**를 누르고 수집할 날짜를 `YYYY-MM-DD` 형식으로 입력합니다. 비우면 한국 시간 기준 오늘 날짜를 사용합니다.
3. 실행 결과와 로그를 확인합니다. 인스타그램 자동 탐색이 실패하면 `fortune_shortcode`에 원본 게시물 주소의 코드를 지정할 수 있습니다.

입력값과 번역 방식, 실패 시 확인할 내용은 [수집 스크립트 안내](scripts/README.md)에 정리되어 있습니다.

## 저장소 구성

| 경로 | 내용 |
| --- | --- |
| `index.html`, `horoscope/`, `_next/` | 웹페이지와 빌드 파일 |
| `fortunes/` | 날짜별 띠별 운세 사진 |
| `fortune-index.json` | 운세 사진의 날짜 및 원본 게시물 목록 |
| `horoscope-editions.json` | 날짜별 한국어 별자리 운세 |
| `scripts/` | 운세 수집·번역 스크립트와 안내 |
| `.github/workflows/` | GitHub Actions 업데이트 설정 |

사이트는 `main` 브랜치의 루트 디렉터리를 GitHub Pages로 게시합니다. 이 저장소에는 배포된 정적 파일과 수집 스크립트가 들어 있습니다.

## 출처

- 띠별 운세 이미지 — [신비사주 인스타그램](https://www.instagram.com/sinbi_saju/)
- 별자리 운세 — [아사히 방송 ‘おはよう朝日です’](https://www.asahi.co.jp/ohaasa/week/horoscope/)

운세 이미지와 원문 콘텐츠의 권리는 각 원저작자에게 있습니다.
