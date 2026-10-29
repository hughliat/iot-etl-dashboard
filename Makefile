PY := python3
PY ?= python

.PHONY: install run run-stress test benchmark clean

install:
	$(PY) -m pip install -r requirements.txt

run:
	$(PY) -m src.cli run --scale default

run-stress:
	$(PY) -m src.cli run --scale stress

test:
	$(PY) -m pytest -q

benchmark:
	$(PY) -m src.cli benchmark --scale stress

clean:
	rm -rf output data
