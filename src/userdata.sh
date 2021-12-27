#!/bin/bash

export debug_more={}
artifact_bucket={}
ddns_file=/tmp/ddns.sh
bootstrap_file=/tmp/bootstrap.sh
profile_file=/tmp/profile.sh

aws s3 sync s3://$artifact_bucket/scripts/ /tmp/
chmod +x /tmp/*.sh

sed -i "s|UPDATE_URL|{}|" $ddns_file
sed -i "s|DOMAIN_NAME|{}|" $bootstrap_file
sed -i "s|FIRST_USER_NAME|{}|" $bootstrap_file
sed -i "s|ARTIFACTS_S3_BUCKET|$artifact_bucket|" $bootstrap_file
sed -i "s|ARTIFACTS_S3_BUCKET|$artifact_bucket|" $profile_file

source $ddns_file
source $bootstrap_file