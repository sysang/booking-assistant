SHELL=/bin/zsh
.SILENT: help
.SILENT: test_actions_booking_service

help:
	echo "Commands:"
	echo "- train"
	echo "- test"
	echo "- dryrun"

tensorboard:
	./tensorboard.sh

testrasachatbot:
	docker exec ailab zsh -c 'TIMESTAMP="$(shell date +%Y%m%d\[\]%H%M%S)" && cd /workspace/rasachatbot/botserver-app && rasa test core --out="results/$$TIMESTAMP"'

trainrasachatbot:
	make archive_trainrasachabot
	docker exec ailab zsh -c 'cd /workspace/rasachatbot/botserver-app && rasa train --augmentation 0 -v'

tensorboard_dir := botserver-app/tensorboard/current
log_dir = botserver-app/tensorboard/$(shell cd botserver-app/models/ && ls -td *.tar.gz | head -1)/
archive_trainrasachabot:
	test -d $(tensorboard_dir) && mv $(tensorboard_dir) $(log_dir) || echo 'Do not need to move current dir.'
	mkdir -p $(tensorboard_dir) && chmod 777 $(tensorboard_dir)

restartcontainers:
	docker restart rasachatbot-rasa-x-1 && docker restart rasachatbot-action-server-1

train: trainrasachatbot restartcontainers

core:
	docker exec ailab zsh -c 'cd /workspace/rasachatbot/botserver-app && rasa train core --augmentation 0 -v'

dryrun:
	docker exec ailab zsh -c 'cd /workspace/rasachatbot/botserver-app && rasa train --dry-run'

test:
	cd botserver-app && python test_runner.py --model=$(model) --testfile=$(testfile)

testall:
	-rm -f botserver-app/tests/reports/current/*
	make query_hotel_room_01_schema_test model=$(M)
	make query_hotel_room_02_sorting_test model=$(M)
	make query_hotel_room_03_chitchat_revisebkinfo_test model=$(M)
	make query_hotel_room_04_revise_invalid_bkinfo_test model=$(M)
	make query_hotel_room_05_donecollecting_revisebkinfo_test model=$(M)
	make query_hotel_room_06_jumpin_information_collecting_test model=$(M)
	make query_hotel_room_07_chitchat_faq_test model=$(M)
	make query_hotel_room_08_chitchat_smalltalk_test model=$(M)
	make query_hotel_room_09_chitchat_outofscope_test model=$(M)
	make query_hotel_room_10_chitchat_nlufallback_test model=$(M)
	make query_hotel_room_11_terminate_booking_test model=$(M)
	make query_hotel_room_12_execution_rejectedof_bkinfo_form_test model=$(M)
	make query_hotel_room_13_bkinfo_area_nlu_test model=$(M)

query_hotel_room_01_schema_test:
	export testfile=query_hotel_room_01_schema; \
	make test testfile=$$testfile model=$(M)

query_hotel_room_02_sorting_test:
	export testfile=query_hotel_room_02_sorting; \
	make test testfile=$$testfile model=$(M)

query_hotel_room_03_chitchat_revisebkinfo_test:
	export testfile=query_hotel_room_03_chitchat_revisebkinfo; \
	make test testfile=$$testfile model=$(M)

query_hotel_room_04_revise_invalid_bkinfo_test:
	export testfile=query_hotel_room_04_revise_invalid_bkinfo; \
	make test testfile=$$testfile model=$(M)

query_hotel_room_05_donecollecting_revisebkinfo_test:
	export testfile=query_hotel_room_05_donecollecting_revisebkinfo; \
	make test testfile=$$testfile model=$(M)

query_hotel_room_06_jumpin_information_collecting_test:
	export testfile=query_hotel_room_06_jumpin_information_collecting; \
	make test testfile=$$testfile model=$(M)

query_hotel_room_07_chitchat_faq_test:
	export testfile=query_hotel_room_07_chitchat_faq; \
	make test testfile=$$testfile model=$(M)

query_hotel_room_08_chitchat_smalltalk_test:
	export testfile=query_hotel_room_08_chitchat_smalltalk; \
	make test testfile=$$testfile model=$(M)

query_hotel_room_09_chitchat_outofscope_test:
	export testfile=query_hotel_room_09_chitchat_outofscope; \
	make test testfile=$$testfile model=$(M)

query_hotel_room_10_chitchat_nlufallback_test:
	export testfile=query_hotel_room_10_chitchat_nlufallback; \
	make test testfile=$$testfile model=$(M)

query_hotel_room_11_terminate_booking_test:
	export testfile=query_hotel_room_11_terminate_booking; \
	make test testfile=$$testfile model=$(M)

query_hotel_room_12_execution_rejectedof_bkinfo_form_test:
	export testfile=query_hotel_room_12_execution_rejectedof_bkinfo_form; \
	make test testfile=$$testfile model=$(M)

query_hotel_room_13_bkinfo_area_nlu_test:
	export testfile=query_hotel_room_13_bkinfo_area_nlu; \
	make test testfile=$$testfile model=$(M)

copyaddons:
	docker cp botserver-app/addons rasachatbot-rasa-production-1:/app

test_actions_fsm_botmemo_booking_progress:
	docker exec rasachatbot-action-server-1 bash -c 'python -c "from actions.fsm_botmemo_booking_progress import __test__; __test__();"'

test_actions_duckling_service:
	docker exec rasachatbot-action-server-1 bash -c 'export TEST_FUNC=$(uit) && python -c "$$(grep  --regexp=__pytest__ -A 1 actions/duckling_service.py | tail -n 1)"'

test_actions_booking_service:
	docker exec rasachatbot-action-server-1 bash -c 'export TEST_FUNC=$(uit) && python -c "$$(grep  --regexp=__pytest__ -A 1 actions/booking_service.py | tail -n 1)"'

unittest_action_server:
	docker exec rasachatbot-action-server-1 bash -c 'export TEST_FUNC=$(uit) && python -c "$$(grep  --regexp=__pytest__ -A 1 actions/$(filepath) | tail -n 1)"'

install_ssl_certificate:
	docker exec rasachatbot-nginx-1 bash -c '/etc/certbot/acme.sh --issue -d dsysang.site --nginx /etc/nginx/conf.d/rasax.nginx --home /etc/certbot/ --server buypass'
	docker exec rasachatbot-nginx-1 bash -c '/etc/certbot/acme.sh --install-cert -d dsysang.site --fullchain-file /etc/certs/fullchain.pem --key-file /etc/certs/privkey.pem --home /etc/certbot/'

# files := file1 file2
# some_file: $(files)
# 	echo "Look at this variable: " $(files)
# 	touch some_file

# file1:
# 	touch file1
# file2:
# 	touch file2
