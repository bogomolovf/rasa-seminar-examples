# 03_hr_bot — Makefile
# Промпт 9: train/validate/test/clean — минимальный контракт. Используем
# binary из conda venv напрямую (./.venv не имеет bin/activate скрипта),
# чтобы make работал и из shell без активированного окружения.

VENV   := /Users/fedorbogomolov/Desktop/examples/.venv
RASA   := $(VENV)/bin/rasa
PYTHON := $(VENV)/bin/python
PYTEST := $(VENV)/bin/python -m pytest

.PHONY: train validate test clean all

train:
	$(RASA) train --quiet

validate:
	$(RASA) data validate

# Прогоняет regression-stories через rasa test (отчёты в results/), затем
# pytest на actions-helper'ы. Если хотя бы один шаг падает — make прерывается.
test:
	$(RASA) test --stories tests/test_stories.yml --out results/
	$(PYTEST) tests/ -v

clean:
	rm -rf models .rasa results

all: validate train test
