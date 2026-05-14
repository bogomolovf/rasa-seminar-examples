"""Custom actions HR-бота.

Скелет: классы-заглушки, объявленные в `domain.yml`, чтобы `rasa train`
не ругалась на undefined actions. Реальная логика добавляется по промптам:

- `ActionResetInterview`        → Промпт 7 (sad-paths, restart-flow)
- `ValidateInterviewForm`       → Промпт 4 (имя/email) → Промпты 5–6 (остальные слоты)
- `ActionAssessCandidate`       → Промпт 6 (assessment engine + CSV)
- `ActionOfferAlternativeRole`  → Промпт 6 (альтернативная роль)

Стиль соответствует `02_phones_bot/actions/actions.py`: type hints, logging,
docstring на каждый класс.
"""

import logging
import re
from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import FormValidationAction

logger = logging.getLogger(__name__)

# Промпт 4: regex для валидации email. Компилируем один раз на модуль, чтобы
# не платить за пересборку при каждом вызове validate_candidate_email.
EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class ActionResetInterview(Action):
    """Сбрасывает состояние интервью.

    На Промпте 2 — пустая заглушка. В Промпте 7 будет возвращать SlotSet(None)
    для всех слотов, ActiveLoop(None) и FollowupAction("utter_restart_done").
    """

    def name(self) -> Text:
        return "action_reset_interview"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        logger.debug("action_reset_interview: skeleton run (no-op)")
        return []


class ActionAssessCandidate(Action):
    """Оценивает кандидата по `roles_requirements.csv`.

    На Промпте 2 — пустая заглушка. В Промпте 6 будет:
    - читать CSV через pandas,
    - сравнивать слоты `years_experience`, `skills`, `expected_salary`
      с требованиями для `desired_role`,
    - выставлять `assessment_decision` ∈ {pass, fail, alternative}.
    """

    def name(self) -> Text:
        return "action_assess_candidate"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        logger.debug("action_assess_candidate: skeleton run (no-op)")
        return []


class ActionOfferAlternativeRole(Action):
    """Предлагает альтернативную роль, если основная не подошла.

    На Промпте 2 — пустая заглушка. В Промпте 6 возьмёт `alternative_role`
    из CSV и при `affirm` перезапустит оценку на новой роли.
    """

    def name(self) -> Text:
        return "action_offer_alternative_role"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        logger.debug("action_offer_alternative_role: skeleton run (no-op)")
        return []


class ValidateInterviewForm(FormValidationAction):
    """Per-slot валидация `interview_form`.

    Промпт 4: подключены валидаторы для `candidate_name` (минимум 2 токена —
    имя + фамилия) и `candidate_email` (regex `^...@...\\..{2,}$`). Остальные
    слоты (`years_experience`, `skills`, `expected_salary`) будут добавлены
    в Промптах 5–6 (см. DESIGN.md §7.1).
    """

    def name(self) -> Text:
        return "validate_interview_form"

    def validate_candidate_name(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        """Принимает имя, если в строке хотя бы два непустых токена.

        Возвращает {"candidate_name": None} при отказе — форма переспросит
        тот же слот, и пользователь введёт значение заново.
        """
        if not slot_value or not isinstance(slot_value, str):
            logger.debug("validate_candidate_name: empty value, asking again")
            return {"candidate_name": None}

        tokens = [t for t in slot_value.strip().split() if t]
        if len(tokens) < 2:
            logger.debug("validate_candidate_name: only one token %r", slot_value)
            dispatcher.utter_message(response="utter_invalid_name")
            return {"candidate_name": None}

        cleaned = " ".join(tokens)
        logger.debug("validate_candidate_name: accepted %r", cleaned)
        return {"candidate_name": cleaned}

    def validate_candidate_email(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        """Принимает email, если он матчит EMAIL_RE; нормализует к lower-case."""
        if not slot_value or not isinstance(slot_value, str):
            logger.debug("validate_candidate_email: empty value, asking again")
            return {"candidate_email": None}

        candidate = slot_value.strip()
        if not EMAIL_RE.match(candidate):
            logger.debug("validate_candidate_email: bad format %r", candidate)
            dispatcher.utter_message(response="utter_invalid_email")
            return {"candidate_email": None}

        normalized = candidate.lower()
        logger.debug("validate_candidate_email: accepted %r", normalized)
        return {"candidate_email": normalized}
