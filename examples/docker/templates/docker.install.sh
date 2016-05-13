# docker.install.sh
yum install -y lvm2
cat >/etc/yum.repos.d/docker.repo <<-EOF
[dockerrepo]
name=Docker Repository
baseurl=https://yum.dockerproject.org/repo/main/centos/7
enabled=1
gpgcheck=1
gpgkey=https://yum.dockerproject.org/gpg
EOF
yum install -y yum-versionlock docker-engine-1.10.3-1.el7.centos
yum versionlock docker-engine-1.10.3-1.el7.centos
