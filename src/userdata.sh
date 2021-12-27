#!/bin/bash
artifact_bucket={}

ddns_file=/tmp/ddns.sh
aws s3api get-object --bucket $artifact_bucket --key {} $ddns_file
sed -i "s|UPDATE_URL|{}|" $ddns_file

chmod +x $ddns_file
source $ddns_file

bootstrap_file=/tmp/bootstrap.sh 
aws s3api get-object --bucket $artifact_bucket --key {} $bootstrap_file
sed -i "s|DOMAIN_NAME|{}|" $bootstrap_file
sed -i "s|ARTIFACTS_S3_BUCKET|$artifact_bucket|" $bootstrap_file
sed -i "s|USERNAME|{}|" $bootstrap_file

chmod +x $bootstrap_file
source $bootstrap_file

export debug_more={}