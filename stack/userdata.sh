#!/bin/bash

export debug_mode={}
artifact_bucket={}
region={}
bootstrap_file=/tmp/bootstrap.sh
profile_file=/tmp/profile.sh
notice_file=/tmp/notice.sh

aws s3 sync s3://$artifact_bucket/scripts/ /tmp/
chmod +x /tmp/*.sh

vi $bootstrap_file -c "set ff=unix" -c ":wq"
vi $profile_file -c "set ff=unix" -c ":wq"
vi $notice_file -c "set ff=unix" -c ":wq"

sed -i "s|_FIRST_USER_NAME_|{}|" $bootstrap_file
sed -i "s|_ARTIFACTS_S3_BUCKET_|$artifact_bucket|" $bootstrap_file
sed -i "s|_ARTIFACTS_S3_BUCKET_|$artifact_bucket|" $profile_file
sed -i "s|_ARTIFACTS_S3_BUCKET_|$artifact_bucket|" $notice_file
sed -i "s|_REGION_|$region|" $bootstrap_file
sed -i "s|_REGION_|$region|" $profile_file
sed -i "s|_REGION_|$region|" $notice_file

source $bootstrap_file