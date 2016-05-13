cat <<- 'EOF' > /etc/yum.repos.d/datadog.repo
[datadog]
name = Datadog, Inc.
baseurl = http://yum.datadoghq.com/rpm/x86_64/
enabled=1
gpgcheck=0
EOF
yum makecache
yum install -y datadog-agent git
usermod -aG docker dd-agent
mv /etc/dd-agent/conf.d/docker_daemon.yaml.example /etc/dd-agent/conf.d/docker_daemon.yaml
git clone https://github.com/WPMedia/dd-agent.git /tmp/dd-agent
/bin/cp -rf /tmp/dd-agent/checks.d/docker_daemon.py /opt/datadog-agent/agent/checks.d
