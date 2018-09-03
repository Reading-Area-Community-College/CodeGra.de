TEST_FILE ?= ./psef_test/
TEST_FLAGS ?=
SHELL = /bin/bash
ENV = source ./env/bin/activate;

env:
	virtualenv3 ./env

.PHONY: install-deps
install-deps: install-pip-deps install-npm-deps

install-pip-deps: env/_last_update
env/_last_update: requirements.txt | env
	$(ENV) pip3 install -r $<
	date > $@

install-npm-deps: node_modules/_last_update
node_modules/_last_update: package.json
	npm install
	date >$@

.PHONY: test_setup
test_setup:
	mkdir -p /tmp/psef/uploads
	mkdir -p /tmp/psef/mirror_uploads

.PHONY: test
test: install-pip-deps test_setup
	$(ENV) DEBUG=on pytest -n auto --cov psef --cov-report term-missing $(TEST_FILE) -vvvvv $(TEST_FLAGS)

.PHONY: test_quick
test_quick: TEST_FLAGS += -x
test_quick: install-pip-deps test_setup test

.PHONY: reset_db
reset_db:
	DEBUG_ON=True ./.scripts/reset_database.sh
	$(MAKE) db_upgrade
	$(MAKE) test_data

.PHONY: migrate
migrate: install-pip-deps
	$(ENV) DEBUG_ON=True python3 manage.py db migrate
	$(ENV) DEBUG_ON=True python3 manage.py db edit
	$(MAKE) db_upgrade

.PHONY: db_upgrade
db_upgrade: install-pip-deps
	$(ENV) DEBUG_ON=True python3 manage.py db upgrade

.PHONY: test_data
test_data: install-pip-deps
	$(ENV) DEBUG_ON=True python3 manage.py test_data

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
	$(ENV) DEBUG_ON=True python3 manage.py seed

.PHONY: format
format: install-pip-deps
	$(ENV) yapf -rip ./psef ./psef_test

.PHONY: shrinkwrap
shrinkwrap:
	npm shrinkwrap --dev

.PHONY: lint
lint: install-pip-deps
	$(ENV) pylint psef --rcfile=setup.cfg
