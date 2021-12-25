#!/bin/bash

#Installing docker
sudo yum update -y
sudo amazon-linux-extras -y install docker
sudo yum install -y docker
sudo service docker start
sudo usermod -a -G docker ec2-user

confdir=/tmp/openvpn
ovpnport=1194
domain="DOMAIN_NAME" #TBU
user=user1
dimage=damshenas/openvpn:arm64

# preparing the keys and running the openvpn server
mkdir -p $confdir
docker pull $dimage
docker run -v $confdir:/etc/openvpn --rm $dimage ovpn_genconfig -u udp://$domain
docker run -v $confdir:/etc/openvpn --rm -i -e "EASYRSA_BATCH=1" -e "EASYRSA_REQ_CN=My CN" $dimage ovpn_initpki nopass
docker run -v $confdir:/etc/openvpn -d -p $ovpnport:$ovpnport/udp --cap-add=NET_ADMIN $dimage
docker run -v $confdir:/etc/openvpn --rm -i $dimage easyrsa build-client-full $user nopass
docker run -v $confdir:/etc/openvpn --rm $dimage ovpn_getclient $user > $user.ovpn
docker run -v $confdir:/etc/openvpn --rm $dimage ovpn_listclients | grep $user

# upload the openvpn config to s3
aws s3 cp $user.ovpn s3://ARTIFACTS_S3_BUCKET/profiles/$user.ovpn

# minitor connections
minutes_without_connection=0
max_minutes_without_connection=15

while true
do
  no_connections=$(ss -tun src :$ovpnport | grep ESTAB | wc -l)

  if [ "$no_connections" -ge 1 ]; then
    ((minutes_without_connection=0))
  else
    ((minutes_without_connection++))
  fi  

  if [ "$minutes_without_connection" -ge $max_minutes_without_connection ]; then
    echo "shutting down. $minutes_without_connection minutes without connection"
    aws s3 rm s3://ARTIFACTS_S3_BUCKET/profiles/$user.ovpn
    poweroff
  else
    sleep 60
  fi  

done