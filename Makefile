SHELL=/bin/zsh
.SILENT: help

help:
	echo "Commands:"
	echo "- train"
	echo "- test"
	echo "- dryrun"

testrasachatbot:
	docker exec ailab zsh -c 'TIMESTAMP="$(shell date +%Y%m%d\[\]%H%M%S)" && cd /workspace/rasachatbot/botserver-app && rasa test core --out="results/$$TIMESTAMP"'

trainrasachatbot:
	docker exec ailab zsh -c 'cd /workspace/rasachatbot/botserver-app && rasa train --augmentation 0 -v'

restartcontainers:
	docker restart rasachatbot-rasa-x-1 && docker restart rasachatbot-action-server-1

train: trainrasachatbot restartcontainers

dryrun:
	docker exec ailab zsh -c 'cd /workspace/rasachatbot/botserver-app && rasa train --dry-run'

test:
	cd botserver-app && python test_runner.py --model=$(model) --testfile=$(testfile)

query_hotel_room_test:
	make test testfile=query_hotel_room model=$(model)
