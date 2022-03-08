#!/bin/bash

confdir=/tmp/openvpn

while true; do
  if [ -z $(curl -Is http://169.254.169.254/latest/meta-data/spot/instance-action | head -1 | grep 404 | cut -d ' ' -f 2) ]; then
    cd $confdir
    tar -czf /tmp/configs.tar.gz .
    aws s3 cp /tmp/configs.tar.gz s3://_ARTIFACTS_S3_BUCKET_/interuptions/_REGION_/configs.tar.gz 
    echo "Uploaded the configs. Ready for interuption." && date
    break
  else
    sleep 5 # recommended to check for the interuptions notice every 5 seconds
  fi
done