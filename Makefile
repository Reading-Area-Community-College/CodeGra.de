TEST_FILE ?= ./psef_test/
TEST_FLAGS ?=
FORMAT_FLAGS ?= -rip
SHELL = /bin/bash
PYTHON ?= python3
ENV = source ./env/bin/activate;

env:
	virtualenv --python=$(PYTHON) ./env

.PHONY: install-deps
install-deps: install-pip-deps install-npm-deps

.PHONY: install-pip-deps
install-pip-deps: env/.last_update
env/.last_update: requirements.txt | env
	$(ENV) pip3 install -r $<
	@date > $@

.PHONY: install-npm-deps
install-npm-deps: node_modules/.last_update
node_modules/.last_update: package.json
	npm install
	@date >$@

.PHONY: test-setup
test-setup:
	mkdir -p /tmp/psef/uploads
	mkdir -p /tmp/psef/mirror_uploads

.PHONY: test
test: install-pip-deps test-setup
	$(ENV) DEBUG=on pytest -n auto -vvvvv --cov psef --cov-report term-missing $(TEST_FLAGS) $(TEST_FILE)

.PHONY: test_quick
test_quick: TEST_FLAGS += -x
test_quick: test

.PHONY: reset_db
reset_db:
	DEBUG_ON=True ./.scripts/reset_database.sh
	$(MAKE) db_upgrade
	$(MAKE) test_data

.PHONY: migrate
migrate: install-pip-deps
	$(ENV) DEBUG_ON=True $(PYTHON) manage.py db migrate
	$(ENV) DEBUG_ON=True $(PYTHON) manage.py db edit
	$(MAKE) db_upgrade

.PHONY: db_upgrade
db_upgrade: install-pip-deps
	$(ENV) DEBUG_ON=True $(PYTHON) manage.py db upgrade

.PHONY: test_data
test_data: install-pip-deps
	$(ENV) DEBUG_ON=True $(PYTHON) manage.py test_data

.PHONY: start_dev_celery
start_dev_celery: install-pip-deps
	$(ENV) DEBUG=on celery worker --app=runcelery:celery -E -l info

.PHONY: start_dev_server
start_dev_server: install-pip-deps
	$(ENV) DEBUG=on ./.scripts/start_dev.sh python

.PHONY: start_dev_npm
start_dev_npm: install-npm-deps privacy_statement
	DEBUG=on ./.scripts/start_dev.sh npm

.PHONY: privacy_statement
privacy_statement: install-pip-deps src/components/PrivacyNote.vue
src/components/PrivacyNote.vue:
	$(ENV) ./.scripts/generate_privacy.py

.PHONY: build_front-end
build_front-end: install-npm-deps privacy_statement
	npm run build

.PHONY: seed_data
seed_data: install-pip-deps
	$(ENV) DEBUG_ON=True $(PYTHON) manage.py seed

.PHONY: format
format: install-pip-deps
	$(ENV) yapf $(FORMAT_FLAGS) ./psef ./psef_test

.PHONY: shrinkwrap
shrinkwrap:
	npm shrinkwrap --dev

.PHONY: lint
lint: lint-py lint-js

.PHONY: lint-py
lint-py: install-pip-deps
	$(ENV) pylint psef --rcfile=setup.cfg

.PHONY: lint-js
lint-js: install-npm-deps privacy_statement
	npm run lint

.PHONY: mypy
mypy:
	$(ENV) mypy ./psef/
