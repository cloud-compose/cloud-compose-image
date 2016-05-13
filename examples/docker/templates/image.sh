#!/bin/bash
{% include "yum.epel_repo.sh" %}
{% include "yum.upgrade.sh" %}
{% include "docker.install.sh" %}
{% include "docker-compose.install.sh" %}
{% include "datadog.install.sh" %}
