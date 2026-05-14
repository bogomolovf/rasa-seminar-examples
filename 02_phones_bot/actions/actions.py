import logging
from pathlib import Path
from typing import Any, Dict, List, Text

import pandas as pd
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

logger = logging.getLogger(__name__)

PHONES_CSV = Path(__file__).parent.parent / "phones.csv"

# Соответствие канонических значений spec_type → заголовок для ответа
SPEC_LABELS: Dict[str, str] = {
    "screen":    "Экран",
    "camera":    "Камера",
    "battery":   "Батарея",
    "ram":       "ОЗУ",
    "storage":   "Память",
    "processor": "Процессор",
    "price":     "Цена, руб.",
}


def _load_phones() -> pd.DataFrame:
    """Загружает базу телефонов из CSV."""
    return pd.read_csv(PHONES_CSV)


def _find_phone(df: pd.DataFrame, model: str) -> pd.Series | None:
    """Ищет телефон в CSV по названию (без учёта регистра).

    Стратегия:
    1. Точное совпадение (case-insensitive) — самое надёжное.
    2. Fallback: частичное совпадение; при нескольких матчах выбираем САМОЕ ДЛИННОЕ
       название в CSV (чтобы «iPhone 15 Pro» не превращался в «iPhone 15»).
    """
    q = model.lower().strip()
    exact = df[df["model"].str.lower() == q]
    if not exact.empty:
        return exact.iloc[0]

    mask = df["model"].str.lower().str.contains(q, regex=False, na=False)
    if not mask.any():
        return None
    candidates = df[mask]
    return candidates.loc[candidates["model"].str.len().idxmax()]


def _pick_longest_phone_entity(tracker: Tracker) -> str | None:
    """Из всех phone_model-сущностей последнего сообщения выбирает самую длинную.

    Защита от случая, когда несколько extractor'ов дают разные значения
    (например, DIET: 'iPhone 15 Pro', Regex: 'iPhone 15').
    """
    entities = tracker.latest_message.get("entities", []) if tracker.latest_message else []
    values = [e["value"] for e in entities if e.get("entity") == "phone_model" and e.get("value")]
    if not values:
        return None
    return max(values, key=len)


def _format_all_specs(phone: pd.Series) -> str:
    """Форматирует все характеристики телефона в читаемый текст."""
    lines = [f"{phone['model']} ({phone['brand']}):"]
    for col, label in SPEC_LABELS.items():
        lines.append(f"  • {label}: {phone[col]}")
    return "\n".join(lines)


def _format_single_spec(phone: pd.Series, spec_type: str) -> str:
    """Форматирует одну характеристику телефона."""
    label = SPEC_LABELS[spec_type]
    value = phone[spec_type]
    return f"{phone['model']} — {label}: {value}"


class ActionGetPhoneSpecs(Action):
    """Возвращает характеристики телефона из CSV-базы.

    Слот phone_model обязателен (заполняется формой phone_form).
    Слот spec_type опционален: если задан — возвращает одну характеристику,
    иначе — все характеристики.
    """

    def name(self) -> Text:
        return "action_get_phone_specs"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        # Если в текущем сообщении есть несколько phone_model-entities (конфликт
        # экстракторов) — берём самое длинное значение; иначе fallback на слот.
        phone_model = _pick_longest_phone_entity(tracker) or tracker.get_slot("phone_model")
        spec_type: str | None = tracker.get_slot("spec_type")

        if not phone_model:
            dispatcher.utter_message(text="Не удалось определить модель телефона.")
            return []

        try:
            df = _load_phones()
        except FileNotFoundError:
            logger.error("Файл %s не найден", PHONES_CSV)
            dispatcher.utter_message(text="Ошибка: база данных телефонов не найдена.")
            return [SlotSet("phone_model", None), SlotSet("spec_type", None)]

        phone = _find_phone(df, phone_model)

        if phone is None:
            dispatcher.utter_message(
                text=f"Телефон «{phone_model}» не найден в базе. "
                     f"Уточните название модели."
            )
            return [SlotSet("phone_model", None), SlotSet("spec_type", None)]

        if spec_type and spec_type in SPEC_LABELS:
            text = _format_single_spec(phone, spec_type)
        else:
            text = _format_all_specs(phone)

        dispatcher.utter_message(text=text)

        # Сбрасываем слоты после ответа, чтобы следующий вопрос начинался чисто
        return [SlotSet("phone_model", None), SlotSet("spec_type", None)]
