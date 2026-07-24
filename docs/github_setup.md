# GitHub 저장소 생성 정보

## 1. 저장소 기본값

- **Repository name:** `local-content-studio-demo`
- **Description:** `PySide6 Windows desktop demo with OpenAI content generation, OpenCV local mosaic processing, SQLite history, keyword rotation, scheduling, and Drive sync-folder output.`
- **Visibility:** Public
- **Initialize repository:** 전부 체크 해제
  - Add a README: 해제
  - Add .gitignore: 해제
  - Choose a license: 해제
- **Topics:** `python`, `pyside6`, `pyqt`, `opencv`, `openai`, `sqlite`, `desktop-app`, `windows`, `automation`, `computer-vision`, `portfolio`

## 2. 첫 푸시

```powershell
git init
git add .
git commit -m "feat: build local content studio portfolio demo"
git branch -M main
git remote add origin https://github.com/YOUR_ID/local-content-studio-demo.git
git push -u origin main
```

## 3. 추천 커밋 분리

이미 완성된 폴더를 한 번에 올려도 되지만, 작업 이력을 보이고 싶다면 다음처럼 나눕니다.

```text
feat: scaffold PySide6 desktop application
feat: add OpenCV ROI mosaic and auto detection
feat: add OpenAI content generation and mock mode
feat: add SQLite history and duplicate prevention
feat: add persistent scheduler and Drive folder output
chore: add tests, docs, and PyInstaller build script
```

## 4. GitHub 첫 화면에서 확인할 것

- README 이미지가 정상 표시되는지
- Actions나 보안 경고가 없는지
- `.env`, DB, 실제 사진이 커밋되지 않았는지
- About 영역에 설명과 Topics가 들어갔는지
- Releases에 EXE ZIP을 올릴 경우 소스와 동일한 버전인지

## 5. 추천 Release

- Tag: `v0.1.0`
- Title: `Portfolio demo v0.1.0`
- Asset: `LocalContentStudio-Windows-x64.zip`
- 설명: `Mock mode enabled by default. No API key required for the core demo.`
