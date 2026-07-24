# 포트폴리오 화면 및 영상 자동 촬영

저장소의 촬영 스크립트는 별도의 임시 SQLite DB와 Mock 데이터로 실제 PySide6 `MainWindow`를 실행합니다. API 키를 사용하지 않으며 촬영용 DB와 결과 파일은 `.tmp/` 아래에서 만든 뒤 자동으로 삭제합니다.

## 스크린샷 생성

다음 명령은 실제 앱의 각 탭을 열고 동일한 창 크기로 8개 PNG를 저장합니다.

```powershell
cd C:\Code\local-content-studio-demo
.\.venv\Scripts\python.exe .\scripts\capture_portfolio_screenshots.py
```

저장 위치는 `docs/assets/screenshots/`입니다.

1. `01_dashboard.png`
2. `02_content_generation.png`
3. `03_mosaic_roi_selection.png`
4. `04_mosaic_result.png`
5. `05_batch_or_second_sample.png`
6. `06_history.png`
7. `07_scheduler.png`
8. `08_settings.png`

## MP4 영상 생성

먼저 개발용 의존성을 설치합니다. `imageio-ffmpeg`는 H.264 인코딩에 필요한 ffmpeg 실행 파일을 함께 제공합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe .\scripts\record_portfolio_demo.py
```

녹화 스크립트는 실제 위젯에 다음 작업을 수행합니다.

1. Mock 서비스와 SQLite를 이용해 가상 콘텐츠·이미지 이력을 준비합니다.
2. 탭 바를 클릭해 콘텐츠 생성 화면으로 이동합니다.
3. 지역과 키워드를 입력하고 `콘텐츠 생성 및 저장` 버튼을 실행합니다.
4. 주차장 샘플을 열고 `QTest` 마우스 이벤트로 얼굴과 번호판 ROI를 드래그합니다.
5. 픽셀 모자이크 미리보기와 결과 저장을 실행합니다.
6. 비 오는 도심 샘플에서 다른 ROI를 지정하고 가우시안 블러 결과를 저장합니다.
7. 콘텐츠·이미지 이력, 활성 스케줄, Mock 설정과 갱신된 대시보드를 차례로 보여줍니다.
8. 앱 창을 캡처한 프레임을 H.264/yuv420p MP4로 인코딩합니다.
9. OpenCV와 ffmpeg로 첫 프레임, 전체 디코딩, 길이, 해상도, 프레임률과 코덱을 검증합니다.
10. 첫 번째 모자이크 비교 구간의 실제 영상 프레임을 썸네일로 추출합니다.

생성 파일은 다음과 같습니다.

```text
docs/assets/demo/
├─ local-content-studio-demo.mp4
└─ video-thumbnail.png
```

현재 영상 설정은 `1280×720`, 24fps, H.264, CRF 27이며 길이는 약 2분 12초입니다. 앱의 논리 창 크기는 `1400×860`이고 Windows 배율이 적용된 실제 창 프레임을 영상 해상도 안에 비율을 유지해 배치합니다.

## 사용하는 가상 데이터

- 지역: 부산 사상구, 부산 북구, 부산 강서구
- 키워드: 사고사진 정리, 차량 접촉 사고, 현장 이미지 관리
- 콘텐츠 생성: OpenAI API를 호출하지 않는 Mock 모드
- 이미지: `sample_data/images/`의 AI 생성 가상 사고 샘플
- 촬영용 DB와 결과: `.tmp/` 아래의 임시 경로

실제 API 키, 이메일, 사용자 홈 경로, 회사 또는 고객사 데이터는 입력하지 않습니다.

## 결과 확인

```powershell
Get-Item .\docs\assets\demo\local-content-studio-demo.mp4 |
    Select-Object Name, Length, LastWriteTime

.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall app scripts
git diff --check
git status --short
```

영상 파일이 커질 경우 `record_portfolio_demo.py`의 CRF 또는 출력 해상도를 조정할 수 있지만, 해상도 `1280×720` 이상과 길이 90~180초 조건은 유지해야 합니다.
