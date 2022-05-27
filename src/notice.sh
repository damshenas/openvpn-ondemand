#!/bin/bash

while true; do
  if [ -z $(curl -Is http://169.254.169.254/latest/meta-data/spot/instance-action | head -1 | grep 404 | cut -d ' ' -f 2) ]; then
    cd $oo_confdir
    tar -czf /tmp/profiles.tar.gz pki/index.txt pki/reqs pki/private pki/issued pki/certs_by_serial
    aws s3 cp /tmp/profiles.tar.gz s3://$oo_artifact_bucket/interuptions/$oo_region/profiles.tar.gz 
    echo "Uploaded the profiles. Ready for interuption." && date
    break
  else
    sleep 5 # recommended to check for the interuptions notice every 5 seconds
  fi
done