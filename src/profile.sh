#!/bin/bash

username=$1

# create username cert and profile if not exist. And upload to s3. 
if [ ! -f "$oo_confdir/pki/reqs/$username.req" ]; then
  docker run -v $oo_confdir:/etc/openvpn --rm -i $oo_docker_image easyrsa build-client-full $username nopass
  docker run -v $oo_confdir:/etc/openvpn --rm $oo_docker_image ovpn_getclient $username > $username.ovpn
  docker run -v $oo_confdir:/etc/openvpn --rm $oo_docker_image ovpn_listclients | grep $username
  sed -i "s|1194|$oo_hostport|" $username.ovpn
  sed -i "s|udp|$oo_hostprotocol|" $username.ovpn
  aws s3 cp $username.ovpn s3://$oo_artifact_bucket/profiles/$oo_region/$username.ovpn
fi

