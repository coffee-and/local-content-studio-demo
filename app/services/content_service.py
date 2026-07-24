from __future__ import annotations

import hashlib
import os
import re
from difflib import SequenceMatcher
from typing import Any

from app.database import Database, utc_now
from app.models import ContentRequest, ContentResult
from app.services.openai_service import OpenAITextService
from app.services.storage_service import StorageService


def normalize_text(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[^0-9a-z가-힣 ]+", "", value)
    return value


def text_hash(value: str) -> str:
    return hashlib.sha256(normalize_text(value).encode("utf-8")).hexdigest()


class DuplicateContentError(RuntimeError):
    pass


class ContentService:
    def __init__(self, db: Database, storage: StorageService) -> None:
        self.db = db
        self.storage = storage
        self._session_api_key: str | None = None

    def set_session_api_key(self, value: str | None) -> None:
        self._session_api_key = value.strip() if value else None
        if self._session_api_key:
            os.environ["OPENAI_API_KEY"] = self._session_api_key

    def generate(self, request: ContentRequest) -> ContentResult:
        prompt = self.db.get_prompt(request.prompt_id)
        if not prompt:
            raise ValueError("사용할 프롬프트가 없습니다.")

        region = request.region.strip()
        keyword = request.keyword.strip()
        if request.use_rotation:
            region = self.db.next_rotation_item("region")
            keyword = self.db.next_rotation_item("keyword")
        if not region or not keyword:
            raise ValueError("지역과 키워드를 입력하거나 자동 로테이션을 선택해 주세요.")

        model = self.db.get_setting("openai_model") or "gpt-5-mini"
        mock_mode = (self.db.get_setting("mock_mode") or "1") == "1"
        threshold = float(self.db.get_setting("duplicate_threshold") or "0.88")
        api = OpenAITextService(
            model=model,
            mock_mode=mock_mode,
            api_key=self._session_api_key,
        )

        base_prompt = self._render_prompt(str(prompt["template"]), region, keyword)
        latest_error: Exception | None = None

        for attempt in range(2):
            rendered = base_prompt
            if attempt:
                rendered += (
                    "\n\n이전 생성 결과와 겹치지 않도록 제목의 관점, 문단 순서, "
                    "표현을 바꾸고 새로운 사례 중심으로 작성하세요."
                )
            try:
                generated = api.generate(rendered)
                duplicate_score, exact_duplicate = self._duplicate_score(
                    generated.title, generated.body
                )
                if exact_duplicate or duplicate_score >= threshold:
                    raise DuplicateContentError(
                        f"기존 콘텐츠와 유사합니다. 유사도 {duplicate_score:.2f}"
                    )

                metadata: dict[str, Any] = {
                    "created_at": utc_now(),
                    "source": request.source,
                    "prompt_id": prompt["id"],
                    "prompt_name": prompt["name"],
                    "region": region,
                    "keyword": keyword,
                    "model": generated.model,
                    "used_mock": generated.used_mock,
                    "duplicate_score": duplicate_score,
                }
                output_dir = self.storage.save_content(
                    region=region,
                    keyword=keyword,
                    title=generated.title,
                    body=generated.body,
                    metadata=metadata,
                )
                generation_id = self.db.insert_generation(
                    {
                        "created_at": metadata["created_at"],
                        "source": request.source,
                        "prompt_id": prompt["id"],
                        "region": region,
                        "keyword": keyword,
                        "title": generated.title,
                        "body": generated.body,
                        "title_hash": text_hash(generated.title),
                        "body_hash": text_hash(generated.body),
                        "duplicate_score": duplicate_score,
                        "model": generated.model,
                        "used_mock": 1 if generated.used_mock else 0,
                        "output_dir": str(output_dir),
                        "status": "success",
                        "error": None,
                    }
                )
                return ContentResult(
                    generation_id=generation_id,
                    title=generated.title,
                    body=generated.body,
                    region=region,
                    keyword=keyword,
                    model=generated.model,
                    output_dir=output_dir,
                    duplicate_score=duplicate_score,
                    used_mock=generated.used_mock,
                )
            except DuplicateContentError as exc:
                latest_error = exc
                continue
            except Exception as exc:
                latest_error = exc
                break

        error_text = str(latest_error or "콘텐츠 생성에 실패했습니다.")
        self.db.insert_generation(
            {
                "created_at": utc_now(),
                "source": request.source,
                "prompt_id": prompt["id"],
                "region": region,
                "keyword": keyword,
                "title": "",
                "body": "",
                "title_hash": "",
                "body_hash": "",
                "duplicate_score": 1.0 if isinstance(latest_error, DuplicateContentError) else 0,
                "model": model,
                "used_mock": 1 if mock_mode else 0,
                "output_dir": None,
                "status": "failed",
                "error": error_text,
            }
        )
        raise RuntimeError(error_text)

    def _duplicate_score(self, title: str, body: str) -> tuple[float, bool]:
        title_digest = text_hash(title)
        body_digest = text_hash(body)
        normalized_title = normalize_text(title)
        normalized_body = normalize_text(body)[:2000]
        max_score = 0.0
        exact = False
        for row in self.db.recent_generations(200):
            if row["title_hash"] == title_digest or row["body_hash"] == body_digest:
                exact = True
                max_score = 1.0
                break
            title_score = SequenceMatcher(
                None, normalized_title, normalize_text(str(row["title"]))
            ).ratio()
            body_score = SequenceMatcher(
                None, normalized_body, normalize_text(str(row["body"]))[:2000]
            ).ratio()
            score = title_score * 0.7 + body_score * 0.3
            max_score = max(max_score, score)
        return max_score, exact

    @staticmethod
    def _render_prompt(template: str, region: str, keyword: str) -> str:
        rendered = template.replace("{region}", region).replace("{keyword}", keyword)
        if "지역:" not in rendered:
            rendered += f"\n지역: {region}"
        if "키워드:" not in rendered:
            rendered += f"\n키워드: {keyword}"
        return rendered
