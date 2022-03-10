#!/bin/bash

## Variables
export oo_confdir=/tmp/openvpn
export oo_docker_image=damshenas/openvpn:arm64
export oo_ddns_script=/tmp/ddns.sh
export oo_hostport=1897 #TBA use value from config
export oo_hostprotocol=tcp
export oo_server_ip=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
export oo_instace_id=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)

## Update DDNS ASAP
echo "Issuing DDNS update command"
curl -s $oo_ddns_url

## Installing docker
yum update -y
yum install -y docker conntrack
service docker start

# for spot support
mkdir -p $oo_confdir
aws s3 cp s3://$oo_artifact_bucket/interuptions/$oo_region/configs.tar.gz ./
if [ -f "configs.tar.gz" ]; then # check s3 object if exist means we had spot interuption
  tar -xzf configs.tar.gz -C $oo_confdir
  aws s3 rm --recursive s3://$oo_artifact_bucket/interuptions/$oo_region # ensure the first provisions are fresh
fi

## Preparing the keys and running the openvpn server
docker pull $oo_docker_image

if [ ! -f "$oo_confdir/openvpn.conf" ]; then
  echo "Config not found. Generating config."
  docker run -v $oo_confdir:/etc/openvpn --rm $oo_docker_image ovpn_genconfig -u $oo_hostprotocol://$oo_domain:$oo_hostport
fi

if [ ! -f "$oo_confdir/pki/ca.crt" ]; then
  echo "Cert not found. Generating certificates."
  docker run -v $oo_confdir:/etc/openvpn --rm -i -e "EASYRSA_BATCH=1" -e "EASYRSA_REQ_CN=My CN" $oo_docker_image ovpn_initpki nopass
fi

# No need because we are using domain
# sed -i "s/$oo_domain/$oo_server_ip/g" $oo_confdir/ovpn_env.sh
# grep -rl "$oo_domain" $oo_confdir/pki | xargs sed -i "s/$oo_domain/$oo_server_ip/g"

## Replacing the default port before running openvpn
sed -i "s|1194|$oo_hostport|" $oo_confdir/openvpn.conf
sed -i "s|udp|$oo_hostprotocol|" $oo_confdir/openvpn.conf
docker run -v $oo_confdir:/etc/openvpn -d -p $oo_hostport:$oo_hostport/$oo_hostprotocol --cap-add=NET_ADMIN $oo_docker_image

## Add the first profile
sed -i "s|HOST_PORT|$oo_hostport|" $oo_profile_script
sed -i "s|HOST_PROTO|$oo_hostprotocol|" $oo_profile_script
source $oo_profile_script $oo_first_username

## Monitor notice of interuption (for spot instance)
source $oo_notice_script &
notice_script_pid=$!

## Minitor connections
minutes_without_connection=0
max_minutes_without_connection=15

while true
do
  # no_connections=$(ss -tun src :$oo_hostport | grep ESTAB | wc -l)
  # no_connections=$(conntrack -L --proto udp --dport $oo_hostport --status ASSURED)
  # no_connections=$(cat /proc/net/nf_conntrack | grep ASSURED | grep $oo_hostport | wc -l)
  filtertype="ESTABLISHED"
  if [ "$oo_hostprotocol" = "udp" ]; then filtertype="ASSURED"; fi

  no_connections=$(cat /proc/net/nf_conntrack | grep $oo_hostport | grep $filtertype | wc -l)

  if [ $no_connections -ge "1" ]; then
    ((minutes_without_connection=0))
  else
    ((minutes_without_connection++))
  fi  

  if [ $minutes_without_connection -ge $max_minutes_without_connection ]; then

    kill -9 $notice_script_pid # first stop the notice.sh so it will not recive the notice and move the instance date
    echo "shutting down. $minutes_without_connection minutes without connection"

    aws s3 rm --recursive s3://$oo_artifact_bucket/profiles/$oo_region
    
    # finding out the spot_fleet_request_id based on the status (active/modifying)
    # what happens if there are more than 1 spot fleet requets?
    modifying_spot_fleet_request_id=$(aws ec2 describe-spot-fleet-requests --region $oo_region --query 'SpotFleetRequestConfigs[?SpotFleetRequestState==`modifying`].[SpotFleetRequestId]' --output text)
    if [ -n "$modifying_spot_fleet_request_id" ]; then spot_fleet_request_id=$modifying_spot_fleet_request_id; fi

    active_spot_fleet_request_id=$(aws ec2 describe-spot-fleet-requests --region $oo_region --query 'SpotFleetRequestConfigs[?SpotFleetRequestState==`active`].[SpotFleetRequestId]' --output text)
    if [ -n "$active_spot_fleet_request_id" ]; then spot_fleet_request_id=$active_spot_fleet_request_id; fi

    aws ec2 modify-spot-fleet-request --region $oo_region --target-capacity 0 --spot-fleet-request-id $spot_fleet_request_id --output text

    break
  else
    sleep 60
  fi  

done