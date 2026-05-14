"""Custom actions HR-бота.

Скелет: на Промпте 2 все классы — заглушки, чтобы `rasa train` не ругалась
на undefined actions, объявленные в `domain.yml`. Реальная логика появится:

- `ActionResetInterview`        → Промпт 7 (sad-paths, restart-flow)
- `ValidateInterviewForm`       → Промпт 3 (валидация имени/email), Промпты 4–5
- `ActionAssessCandidate`       → Промпт 6 (assessment engine + CSV)
- `ActionOfferAlternativeRole`  → Промпт 6 (альтернативная роль)

Стиль соответствует `02_phones_bot/actions/actions.py`: type hints, logging,
docstring на каждый класс.
"""

import logging
from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import FormValidationAction

logger = logging.getLogger(__name__)


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

    На Промпте 2 — пустая заглушка (форма пока без required_slots, валидировать
    нечего). В Промптах 3–5 появятся методы `validate_<slot>` для каждого из
    шести обязательных слотов (см. DESIGN.md §7.1).
    """

    def name(self) -> Text:
        return "validate_interview_form"
