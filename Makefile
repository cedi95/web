.PHONY: Dockerfile Dockerfile-base Dockerfile-dev Dockerfile-production start restart stop clean tests

Dockerfile: Dockerfile-dev
Dockerfile-base:
	docker build -t studentenportal/studentenportal-base -f Dockerfile-base .

Dockerfile-dev: Dockerfile-base
	docker build -t studentenportal/studentenportal-dev -f Dockerfile-dev .

Dockerfile-production: Dockerfile-base
	docker build -t studentenportal/studentenportal -f Dockerfile-production .

start: Dockerfile-dev
	docker-compose up -d

restart: stop start

stop:
	docker-compose stop

clean: stop
	docker-compose rm

tests: Dockerfile-dev
	docker-compose run --rm studentenportal-dev ./test.sh
