.PHONY: all data profile engine analyze figures html test clean

PY := python

all: engine analyze figures html

data:
	@mkdir -p data
	@if [ ! -f data/olist_orders_dataset.csv ]; then \
	  echo "fetching Olist dataset from Olist's GitHub org..."; \
	  rm -rf .tmp_olist && git clone --depth 1 \
	    https://github.com/olist/work-at-olist-data.git .tmp_olist && \
	  cp .tmp_olist/datasets/*.csv data/ && \
	  rm -f data/olist_geolocation_dataset.csv && rm -rf .tmp_olist; \
	else echo "data already present"; fi

profile:
	$(PY) src/profile.py

engine:
	$(PY) src/engine.py

analyze:
	$(PY) src/analyze.py

figures:
	$(PY) src/figures.py

html:
	$(PY) src/build_html.py

test:
	$(PY) -m pytest tests/ -q

clean:
	rm -rf out figures revenue_definition_audit.html __pycache__ \
	       src/__pycache__ tests/__pycache__ .pytest_cache
