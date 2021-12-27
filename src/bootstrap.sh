#!/bin/bash

#Installing docker
yum update -y
yum install -y docker conntrack
service docker start

confdir=/tmp/openvpn
ovpnport=1194
domain="DOMAIN_NAME" #TBU
dimage=damshenas/openvpn:arm64

mkdir -p $confdir
aws s3 sync s3://ARTIFACTS_S3_BUCKET/openvpn $confdir

# preparing the keys and running the openvpn server
docker pull $dimage

if [ ! -f "$confdir/openvpn.conf" ]; then
  echo "Config not found. Generating config."
  docker run -v $confdir:/etc/openvpn --rm $dimage ovpn_genconfig -u udp://$domain
fi

if [ ! -f "$confdir/pki/ca.crt" ]; then
  echo "Cert not found. Generating certificates."
  docker run -v $confdir:/etc/openvpn --rm -i -e "EASYRSA_BATCH=1" -e "EASYRSA_REQ_CN=My CN" $dimage ovpn_initpki nopass
fi

docker run -v $confdir:/etc/openvpn -d -p $ovpnport:$ovpnport/udp --cap-add=NET_ADMIN $dimage

# add the first profile
source /tmp/profile.sh FIRST_USER_NAME

# minitor connections
minutes_without_connection=0
max_minutes_without_connection=15

while true
do
  # no_connections=$(ss -tun src :$ovpnport | grep ESTAB | wc -l)
  # no_connections=$(conntrack -L --proto udp --dport 1194 --status ASSURED)
  no_connections=$(cat /proc/net/nf_conntrack | grep ASSURED | grep 1194 | wc -l)

  if [ $no_connections -ge "1" ]; then
    ((minutes_without_connection=0))
  else
    ((minutes_without_connection++))
  fi  

  if [ $minutes_without_connection -ge $max_minutes_without_connection ]; then
    echo "shutting down. $minutes_without_connection minutes without connection"
    aws s3 rm --recursive s3://ARTIFACTS_S3_BUCKET/profiles/
    poweroff
  else
    sleep 60
  fi  

done