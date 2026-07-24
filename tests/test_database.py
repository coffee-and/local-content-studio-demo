from pathlib import Path

from app.database import Database


def make_db(tmp_path: Path) -> Database:
    return Database(tmp_path / "test.db", tmp_path / "output")


def test_seed_defaults(tmp_path: Path) -> None:
    db = make_db(tmp_path)
    assert db.get_setting("mock_mode") == "1"
    assert db.list_prompts()
    assert db.list_rotation_items("region")
    assert db.list_rotation_items("keyword")


def test_rotation_returns_enabled_values(tmp_path: Path) -> None:
    db = make_db(tmp_path)
    first = db.next_rotation_item("region")
    second = db.next_rotation_item("region")
    assert first
    assert second
    assert first != second


def test_schedule_can_be_created(tmp_path: Path) -> None:
    db = make_db(tmp_path)
    prompt_id = db.list_prompts()[0]["id"]
    schedule_id = db.create_schedule(
        name="테스트",
        interval_minutes=5,
        prompt_id=prompt_id,
        use_rotation=True,
        fixed_region="",
        fixed_keyword="",
    )
    assert schedule_id > 0
    assert db.get_schedule(schedule_id)["name"] == "테스트"
