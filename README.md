# Charm Layer for Docker

This repository contains the Charm layer for docker, which is a base layer in
the [Juju composer](https://jujucharms.com/docs/devel/authors-charm-composing).



## Usage

In your charm that inherets docker, the integration can be as simple as placing
the following in your charms `compose.yaml`:

    includes: ['layer:docker']

From here, you simply ammend any hooks/reactive patterns you require to deliver
and manage the lifecycle of your applications docker image.


## Credit

This charm delivers a slightly modified copy of the script contained at:
[https://get.docker.io](https://get.docker.io)

The modifications were raising status messages for Juju so its apparent what is
happening to the end user following along with Juju's extended status feature.


