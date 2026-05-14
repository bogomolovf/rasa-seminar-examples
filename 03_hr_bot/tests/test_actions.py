"""Unit tests для actions/actions.py.

Промпт 9: проверяем чистые helper-функции (`_parse_salary`, `_normalize_skills`,
`EMAIL_RE`) и assessment-движок (`_run_assessment` под 3 сценария: pass, fail,
alternative).

Запуск: `make test` или `pytest tests/ -v` из директории `03_hr_bot`.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any, Dict, List, Optional

import pytest

# Делаем actions.actions импортируемым: добавляем корень примера (03_hr_bot/)
# в sys.path, иначе pytest не найдёт пакет `actions`.
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from actions.actions import (  # noqa: E402  — import после sys.path тюнинга
    EMAIL_RE,
    _load_roles,
    _normalize_skills,
    _parse_salary,
    _run_assessment,
    _split_skills,
)


# ── Test doubles ───────────────────────────────────────────────────────────────
# _run_assessment вызывает `tracker.get_slot(...)` и `dispatcher.utter_message(...)`,
# поэтому достаточно минимальных stand-in'ов вместо полноценного rasa-mock'а.

class MockTracker:
    """Минимальный tracker: только get_slot из заранее заданного dict."""

    def __init__(self, slots: Dict[str, Any]) -> None:
        self._slots = slots

    def get_slot(self, name: str) -> Any:
        return self._slots.get(name)


class MockDispatcher:
    """Минимальный dispatcher: записывает все utter_message-вызовы в список."""

    def __init__(self) -> None:
        self.messages: List[Dict[str, Any]] = []

    def utter_message(self, **kwargs: Any) -> None:
        self.messages.append(kwargs)


def _find_slot_set(events: List[Dict[str, Any]], slot_name: str) -> Optional[Any]:
    """Вытаскивает значение SlotSet(<slot_name>, ...) из списка events.

    SlotSet — это namedtuple-подобный dict с ключами `event`, `name`, `value`.
    Возвращает значение последнего SlotSet'а по этому имени (имитирует поведение
    tracker'а, который применяет события по порядку)."""
    last_value = None
    for ev in events:
        # rasa_sdk.events.SlotSet возвращает dict({"event": "slot", "name": ..., "value": ...})
        if isinstance(ev, dict) and ev.get("event") == "slot" and ev.get("name") == slot_name:
            last_value = ev.get("value")
    return last_value


# ── _parse_salary ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("150000", 150000.0),
        ("150 000", 150000.0),
        ("150к", 150000.0),
        ("150 тысяч", 150000.0),
        ("150 000 ₽", 150000.0),
        ("200к рублей", 200000.0),
        ("300 000 руб", 300000.0),
        ("150_000", 150000.0),
    ],
)
def test_parse_salary_valid(raw: str, expected: float) -> None:
    """Корректные форматы зарплаты парсятся в float рублей."""
    assert _parse_salary(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "много",
        "qwerty",
        "   ",
        None,
    ],
)
def test_parse_salary_invalid(raw: Any) -> None:
    """Пустые/нечисловые строки возвращают None."""
    assert _parse_salary(raw) is None


# ── _normalize_skills ─────────────────────────────────────────────────────────

def test_normalize_skills_canonicalization() -> None:
    """Список навыков нормализуется: lower-case, strip, дедуп с сохранением порядка."""
    result = _normalize_skills(["Python", "SQL", "PyTorch", "python"])
    assert result == ["python", "sql", "pytorch"]


def test_normalize_skills_handles_empty_and_nested() -> None:
    """Пустой ввод → пустой список; вложенные списки распаковываются."""
    assert _normalize_skills([]) == []
    assert _normalize_skills(None) == []
    # Один уровень вложенности распаковывается.
    assert _normalize_skills([["Python", "SQL"], "pytorch"]) == ["python", "sql", "pytorch"]


# ── EMAIL_RE ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "email",
    [
        "ivan@example.com",
        "ivan.petrov@example.co.uk",
        "ivan+filter@gmail.com",
        "i_p@sub.domain.org",
    ],
)
def test_email_regex_valid(email: str) -> None:
    """EMAIL_RE матчит валидные email-адреса."""
    assert EMAIL_RE.match(email) is not None


@pytest.mark.parametrize(
    "email",
    [
        "ivan",
        "ivan@",
        "@example.com",
        "ivan@example",
        "ivan example.com",
        "",
    ],
)
def test_email_regex_invalid(email: str) -> None:
    """EMAIL_RE отвергает невалидные строки."""
    assert EMAIL_RE.match(email) is None


# ── _split_skills (CSV-parsing для required_skills) ───────────────────────────

def test_split_skills_basic() -> None:
    """`Python;SQL;PyTorch` → {python, sql, pytorch}."""
    assert _split_skills("Python;SQL;PyTorch") == {"python", "sql", "pytorch"}


def test_split_skills_empty() -> None:
    """Пустая строка → пустое множество (PM без required_skills)."""
    assert _split_skills("") == set()
    assert _split_skills(None) == set()


# ── _load_roles — sanity check CSV ────────────────────────────────────────────

def test_load_roles_contains_all_five() -> None:
    """В roles_requirements.csv должны быть все 5 ролей."""
    roles = _load_roles()
    assert set(roles.keys()) == {"pm", "da", "de", "ds", "mlops"}
    assert roles["ds"]["alternative_role"] == "da"


# ── _run_assessment ───────────────────────────────────────────────────────────

def test_run_assessment_pass() -> None:
    """DS, 5 лет, [python, scikit-learn, pytorch], 200k → decision=pass."""
    tracker = MockTracker({
        "candidate_name": "Иван Петров",
        "years_experience": 5.0,
        "skills": ["python", "scikit-learn", "pytorch"],
        "expected_salary": 200000.0,
        "desired_role": "ds",
    })
    dispatcher = MockDispatcher()
    events = _run_assessment(dispatcher, tracker, desired_role="ds")
    assert _find_slot_set(events, "assessment_decision") == "pass"
    # Сообщение пользователю должно быть отправлено хотя бы одно.
    assert len(dispatcher.messages) >= 1


def test_run_assessment_fail() -> None:
    """DS, 0 лет, [python] → decision=fail (недостаточно опыта)."""
    tracker = MockTracker({
        "candidate_name": "Мария Иванова",
        "years_experience": 0.0,
        "skills": ["python"],
        "expected_salary": 180000.0,
        "desired_role": "ds",
    })
    dispatcher = MockDispatcher()
    events = _run_assessment(dispatcher, tracker, desired_role="ds")
    assert _find_slot_set(events, "assessment_decision") == "fail"


def test_run_assessment_alternative() -> None:
    """DS, 5 лет, [sql, python, tableau] → decision=alternative (DA)."""
    tracker = MockTracker({
        "candidate_name": "Сергей Морозов",
        "years_experience": 5.0,
        "skills": ["sql", "python", "tableau"],
        "expected_salary": 150000.0,
        "desired_role": "ds",
    })
    dispatcher = MockDispatcher()
    events = _run_assessment(dispatcher, tracker, desired_role="ds")
    assert _find_slot_set(events, "assessment_decision") == "alternative"
    # Должны выставить и название альтернативы (для подстановки в utter).
    assert _find_slot_set(events, "alternative_role_name") == "Data Analyst"


def test_run_assessment_unknown_role_returns_fail() -> None:
    """Несуществующая роль в CSV → decision=fail + сообщение об ошибке."""
    tracker = MockTracker({
        "candidate_name": "Анон",
        "years_experience": 5.0,
        "skills": ["python"],
        "expected_salary": 150000.0,
        "desired_role": "nonexistent",
    })
    dispatcher = MockDispatcher()
    events = _run_assessment(dispatcher, tracker, desired_role="nonexistent")
    assert _find_slot_set(events, "assessment_decision") == "fail"
