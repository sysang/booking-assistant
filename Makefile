SHELL=/bin/zsh
.SILENT: help

help:
	echo "Commands:"
	echo "- train"
	echo "- test"

testrasachatbot:
	docker exec ailab zsh -c 'TIMESTAMP="$(shell date +%Y%m%d\[\]%H%M%S)" && cd /workspace/rasachatbot/botserver-app && rasa test core --out="results/$$TIMESTAMP"'

trainrasachatbot:
	docker exec ailab zsh -c 'cd /workspace/rasachatbot/botserver-app && rasa train --augmentation 0 -v'

restartcontainers:
	docker restart rasachatbot-rasa-x-1 && docker restart rasachatbot-action-server-1

train: trainrasachatbot restartcontainers

test: testrasachatbot
