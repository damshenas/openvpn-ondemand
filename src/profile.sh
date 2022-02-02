#!/bin/bash

user=$1
confdir=/tmp/openvpn
dimage=damshenas/openvpn:arm64
hostport=HOST_PORT
hostprotocol=HOST_PROTO

# create user cert and profile if not exist. And upload to s3. 
if [ ! -f "$confdir/pki/reqs/$user.req" ]; then
  docker run -v $confdir:/etc/openvpn --rm -i $dimage easyrsa build-client-full $user nopass
  docker run -v $confdir:/etc/openvpn --rm $dimage ovpn_getclient $user > $user.ovpn
  docker run -v $confdir:/etc/openvpn --rm $dimage ovpn_listclients | grep $user
  sed -i "s|1194|$hostport|" $user.ovpn
  sed -i "s|udp|$hostprotocol|" $user.ovpn
  aws s3 cp $user.ovpn s3://ARTIFACTS_S3_BUCKET/profiles/REGION/$user.ovpn
fi

