#!/bin/bash

## Installing docker
yum update -y
yum install -y docker conntrack
service docker start

## Variables
confdir=/tmp/openvpn
hostport=1897 #TBA use value from config
hostprotocol=tcp
dimage=damshenas/openvpn:arm64
profile_script=/tmp/profile.sh
notice_script=/tmp/notice.sh
domain=none.example.com #Just place holder as we will not use a domain 

## Updating variable place holders for other scripts
# would be nice to keep all variables in a single place

# for spot support
mkdir -p $confdir
aws s3 cp s3://_ARTIFACTS_S3_BUCKET_/interuptions/_REGION_/configs.tar.gz ./
if [ -f "configs.tar.gz" ]; then # check s3 object if exist means we had spot interuption
  tar -xzf configs.tar.gz -C $confdir
  aws s3 rm --recursive s3://_ARTIFACTS_S3_BUCKET_/interuptions/_REGION_ # ensure the first provisions are fresh
fi

## Preparing the keys and running the openvpn server
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
# instace_id=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)

sed -i "s/$domain/$server_ip/g" $confdir/ovpn_env.sh
grep -rl "$domain" $confdir/pki | xargs sed -i "s/$domain/$server_ip/g"

## Replacing the default port before running openvpn
sed -i "s|1194|$hostport|" $confdir/openvpn.conf
sed -i "s|udp|$hostprotocol|" $confdir/openvpn.conf
docker run -v $confdir:/etc/openvpn -d -p $hostport:$hostport/$hostprotocol --cap-add=NET_ADMIN $dimage

## Add the first profile
sed -i "s|HOST_PORT|$hostport|" $profile_script
sed -i "s|HOST_PROTO|$hostprotocol|" $profile_script
source $profile_script _FIRST_USER_NAME_

## Monitor notice of interuption (for spot instance)
source $notice_script &
notice_script_pid=$!

## Minitor connections
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

    kill -9 $notice_script_pid # first stop the notice.sh so it will not recive the notice and move the instance date
    echo "shutting down. $minutes_without_connection minutes without connection"

    aws s3 rm --recursive s3://_ARTIFACTS_S3_BUCKET_/profiles/_REGION_
    
    # finding out the spot_fleet_request_id based on the status (active/modifying)
    # what happens if there are more than 1 spot fleet requets?
    modifying_spot_fleet_request_id=$(aws ec2 describe-spot-fleet-requests --region _REGION_ --query 'SpotFleetRequestConfigs[?SpotFleetRequestState==`modifying`].[SpotFleetRequestId]' --output text)
    if [ -n "$modifying_spot_fleet_request_id" ]; then spot_fleet_request_id=$modifying_spot_fleet_request_id; fi

    active_spot_fleet_request_id=$(aws ec2 describe-spot-fleet-requests --region _REGION_ --query 'SpotFleetRequestConfigs[?SpotFleetRequestState==`active`].[SpotFleetRequestId]' --output text)
    if [ -n "$active_spot_fleet_request_id" ]; then spot_fleet_request_id=$active_spot_fleet_request_id; fi

    aws ec2 modify-spot-fleet-request --region _REGION_ --target-capacity 0 --spot-fleet-request-id $spot_fleet_request_id --output text

    break
  else
    sleep 60
  fi  

done