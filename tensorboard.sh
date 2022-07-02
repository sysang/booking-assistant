#! /usr/bin/zsh

docker exec -it ailab zsh -c 'cd /workspace/rasachatbot/botserver-app  && tensorboard --port=8888 --host=0.0.0.0 --logdir=tensorboard'
