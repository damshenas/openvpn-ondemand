#!/bin/bash

export debug_mode={}
artifact_bucket={}
bootstrap_file=/tmp/bootstrap.sh
profile_file=/tmp/profile.sh

aws s3 sync s3://$artifact_bucket/scripts/ /tmp/
chmod +x /tmp/*.sh

vi $bootstrap_file -c "set ff=unix" -c ":wq"
vi $profile_file -c "set ff=unix" -c ":wq"

sed -i "s|FIRST_USER_NAME|{}|" $bootstrap_file
sed -i "s|ARTIFACTS_S3_BUCKET|$artifact_bucket|" $bootstrap_file
sed -i "s|ARTIFACTS_S3_BUCKET|$artifact_bucket|" $profile_file

source $bootstrap_file