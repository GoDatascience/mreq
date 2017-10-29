# pyor
PyoR Experiment Lab - A plataform to manage experiments.

In datascience, specially when working with Deep Learning, it's common to run experiments that may take hours or even days. If you simply run it in your server, you don't know when it's done running unless you keep checking. And chances are that you will notice it's finished after quite some time. Even worse, you may notice that the experiment didn't work out and you should adjust the parameters and try again. Between each trial, you'll probably lose a lot of time. That's why we created PYOR. With it, you'll be able to enqueue lots of experiments and they will start one after the other or in parallel, depending on your configuration. Even better, when an experiment is done, you can be notified via Telegram.

# Features

- Create Tasks with name, script and auxiliar files. Both Python and R are compatible.
- Enqueue as many experiments as desired by selecting a registered Task and setting the parameters.
- Configure workers and the queues they will consume from. By default, there're two workers: sequential and parallel.
- Be notified when a experiment has been concluded

# How to use

## Prerequisites

You'll only need [Docker](https://docs.docker.com/engine/installation/) and [Docker Compose](https://docs.docker.com/compose/install/) installed in your computer. If you want to use GPU, you'll also need [nvidia-docker](https://github.com/NVIDIA/nvidia-docker/wiki/Installation) and [nvidia-docker-compose](https://github.com/eywalker/nvidia-docker-compose#installing).

## Getting Started

Clone the repository to your server with `git clone`. Then, run `docker-compose up` to start the whole project. If you want GPU support, just run `nvidia-docker-compose up` instead. Doing so will startup the Flask Application, the required MongoDB and Redis, The MRQ-Dashboard and the front-end with Angular 4.

Note that to be able to run any docker command, you need to either use a root user (sudo) or add your user to `docker` group. You can check your user's groups with `groups $USER` and add your user to `docker` group with `sudo usermod -aG docker ${USER}`. After that, you should restart your computer.

To access the WEB interface, to to http://localhost:3000.
