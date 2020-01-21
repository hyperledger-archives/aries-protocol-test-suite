INDY_SDK_VERSION=v1.14.1

NO_COLOR="\x1b[0m"
OK_COLOR="\x1b[32;01m"
ERROR_COLOR="\x1b[31;01m"
WARN_COLOR="\x1b[33;01m"
BLUE_COLOR="\x1b[34;01m"

default: build start login

build:
	@echo $(BLUE_COLOR)Downloading version $(INDY_SDK_VERSION) of the indy-sdk source ...$(NO_COLOR)
	@scripts/download-indy-sdk $(INDY_SDK_VERSION)
	@echo $(BLUE_COLOR)Building docker images ...$(NO_COLOR)
	@cd test-suite/indy-sdk/ci && sed '/USER indy/d' indy-pool.dockerfile > indy-pool2.dockerfile && docker build . -f indy-pool2.dockerfile -t indy-pool
	@docker-compose build
	@echo $(BLUE_COLOR)Built docker images$(NO_COLOR)

start:
	@echo $(BLUE_COLOR)Starting docker containers ...$(NO_COLOR)
	@docker-compose up -d
	@echo $(BLUE_COLOR)Started docker container$(NO_COLOR)

login:
	@echo $(BLUE_COLOR)Logging into the test-suite container ...$(NO_COLOR)
	@docker exec -it test-suite bash
stop:
	@echo $(BLUE_COLOR)Stopping docker containers ...$(NO_COLOR)
	@docker-compose down
	@echo $(BLUE_COLOR)Stopped docker container$(NO_COLOR)
