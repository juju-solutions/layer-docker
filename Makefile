#!/usr/bin/make

all: lint unit_test


.PHONY: apt_prereqs
apt_prereqs:
	@# Need tox, but don't install the apt version unless we have to (don't want to conflict with pip)
	@which tox >/dev/null || sudo apt-get install -y python-tox

lint: apt_prereqs
	@tox --notest
	@.tox/py34/bin/flake8 $(wildcard hooks reactive lib unit_tests tests tactics)
	@charm proof

unit_test: apt_prereqs
	@echo Starting tests...
	tox
