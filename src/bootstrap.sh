#!/bin/bash

#Installing docker
yum update -y
yum install -y docker conntrack
service docker start

confdir=/tmp/openvpn
hostport=1897
hostprotocol=tcp
dimage=damshenas/openvpn:arm64
profile_script=/tmp/profile.sh
domain=none.example.com #Just place holder as we will not use a domain 

mkdir -p $confdir
aws s3 cp s3://ARTIFACTS_S3_BUCKET/openvpn.tar.gz ./
tar -xvzf openvpn.tar.gz -C $confdir

# preparing the keys and running the openvpn server
docker pull $dimage

if [ ! -f "$confdir/openvpn.conf" ]; then
  echo "Config not found. Generating config."
  docker run -v $confdir:/etc/openvpn --rm $dimage ovpn_genconfig -u $hostprotocol://$domain:$hostport
fi

if [ ! -f "$confdir/pki/ca.crt" ]; then
  echo "Cert not found. Generating certificates."
  docker run -v $confdir:/etc/openvpn --rm -i -e "EASYRSA_BATCH=1" -e "EASYRSA_REQ_CN=My CN" $dimage ovpn_initpki nopass
fi

server_ip=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)

sed -i "s/$domain/$server_ip/g" $confdir/ovpn_env.sh
grep -rl "$domain" $confdir/pki | xargs sed -i "s/$domain/$server_ip/g"

# replacing the default port before running openvpn
sed -i "s|1194|$hostport|" $confdir/openvpn.conf
sed -i "s|udp|$hostprotocol|" $confdir/openvpn.conf
docker run -v $confdir:/etc/openvpn -d -p $hostport:$hostport/$hostprotocol --cap-add=NET_ADMIN $dimage

# add the first profile
sed -i "s|HOST_PORT|$hostport|" $profile_script
sed -i "s|HOST_PROTO|$hostprotocol|" $profile_script
source $profile_script FIRST_USER_NAME

# minitor connections
minutes_without_connection=0
max_minutes_without_connection=15

while true
do
  # no_connections=$(ss -tun src :$hostport | grep ESTAB | wc -l)
  # no_connections=$(conntrack -L --proto udp --dport $hostport --status ASSURED)
  # no_connections=$(cat /proc/net/nf_conntrack | grep ASSURED | grep $hostport | wc -l)
  filtertype="ESTABLISHED"
  if [ "$hostprotocol" = "udp" ]; then filtertype="ASSURED"; fi

  no_connections=$(cat /proc/net/nf_conntrack | grep $hostport | grep $filtertype | wc -l)

  if [ $no_connections -ge "1" ]; then
    ((minutes_without_connection=0))
  else
    ((minutes_without_connection++))
  fi  

  if [ $minutes_without_connection -ge $max_minutes_without_connection ]; then
    echo "shutting down. $minutes_without_connection minutes without connection"
    aws s3 rm --recursive s3://ARTIFACTS_S3_BUCKET/profiles/REGION
    poweroff
  else
    sleep 60
  fi  

done