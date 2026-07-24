from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass


@dataclass(slots=True)
class GeneratedText:
    title: str
    body: str
    raw: str
    model: str
    used_mock: bool


class OpenAITextService:
    def __init__(
        self,
        *,
        model: str,
        mock_mode: bool,
        api_key: str | None = None,
    ) -> None:
        self.model = model.strip() or "gpt-5-mini"
        self.mock_mode = mock_mode
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

    def generate(self, prompt: str) -> GeneratedText:
        if self.mock_mode or not self.api_key:
            return self._mock_generate(prompt)

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "openai 패키지가 설치되지 않았습니다. requirements.txt를 설치해 주세요."
            ) from exc

        client = OpenAI(api_key=self.api_key)
        response = client.responses.create(
            model=self.model,
            instructions=(
                "한국어 콘텐츠 작성 도우미입니다. 반드시 JSON 객체만 반환하세요. "
                '형식은 {"title":"제목","body":"본문"}입니다. '
                "사실이 확인되지 않은 내용은 단정하지 마세요."
            ),
            input=prompt,
        )
        raw = str(response.output_text).strip()
        title, body = self._parse_json_or_text(raw)
        return GeneratedText(
            title=title,
            body=body,
            raw=raw,
            model=self.model,
            used_mock=False,
        )

    def _mock_generate(self, prompt: str) -> GeneratedText:
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        region_match = re.search(r"지역\s*[:：]\s*(.+)", prompt)
        keyword_match = re.search(r"키워드\s*[:：]\s*(.+)", prompt)
        region = region_match.group(1).strip() if region_match else "지역"
        keyword = keyword_match.group(1).strip() if keyword_match else "핵심 정보"
        angle = int(digest[:2], 16) % 4
        angle_text = ["체크리스트", "실무 가이드", "놓치기 쉬운 포인트", "단계별 정리"][angle]
        title = f"{region} {keyword}, {angle_text}로 차근차근 확인하기"
        body = (
            f"{region}에서 {keyword}와 관련된 상황을 마주했을 때는 서두르기보다 "
            "필요한 정보를 순서대로 정리하는 것이 중요합니다. 이 글은 기능 검증용 "
            "Mock 모드에서 생성된 샘플 콘텐츠이며, 실제 게시 전에는 사실관계와 최신 "
            "정보를 반드시 확인해야 합니다.\n\n"
            "## 1. 먼저 현재 상황을 기록합니다\n"
            "발생 시점, 장소, 관련 자료를 한곳에 정리합니다. 사진을 다룰 때는 개인을 "
            "식별할 수 있는 얼굴이나 번호판이 노출되지 않도록 별도 처리합니다.\n\n"
            "## 2. 필요한 절차를 구분합니다\n"
            "당장 해야 할 일과 추가 확인이 필요한 일을 나누면 누락을 줄일 수 있습니다. "
            "기관이나 업체에 문의할 내용은 메모해 두는 편이 좋습니다.\n\n"
            "## 3. 결과물을 다시 검토합니다\n"
            "제목과 본문의 중복 여부, 개인정보 노출 여부, 저장 위치를 확인한 뒤 활용합니다. "
            "특히 자동 생성된 문장은 실제 상황과 다를 수 있으므로 최종 검수 과정이 필요합니다.\n\n"
            f"정리하면 {keyword} 관련 콘텐츠는 정확성, 개인정보 보호, 재확인 절차를 함께 "
            "고려해야 안정적으로 운영할 수 있습니다."
        )
        raw = json.dumps({"title": title, "body": body}, ensure_ascii=False)
        return GeneratedText(
            title=title,
            body=body,
            raw=raw,
            model="mock-local",
            used_mock=True,
        )

    @staticmethod
    def _parse_json_or_text(raw: str) -> tuple[str, str]:
        candidates = [raw]
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            candidates.insert(0, match.group(0))

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            title = str(parsed.get("title", "")).strip()
            body = str(parsed.get("body", "")).strip()
            if title and body:
                return title, body

        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        if not lines:
            raise ValueError("AI 응답이 비어 있습니다.")
        title = re.sub(r"^(제목|title)\s*[:：]\s*", "", lines[0], flags=re.I)
        body = "\n".join(lines[1:]).strip()
        if not body:
            raise ValueError("AI 응답에서 본문을 찾지 못했습니다.")
        return title, body
