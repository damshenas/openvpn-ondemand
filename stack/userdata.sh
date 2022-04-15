#!/bin/bash

## Variables
export oo_debug_mode={}
export oo_artifact_bucket={}
export oo_region={}
export oo_first_username={}
export oo_ddns_url={}
export oo_domain={} #=none.example.com
export oo_bootstrap_script=/tmp/bootstrap.sh
export oo_profile_script=/tmp/profile.sh
export oo_notice_script=/tmp/notice.sh
export oo_temdir=/tmp

yum install aws-cli -y

aws s3 sync s3://$oo_artifact_bucket/scripts/ $oo_temdir/

for script_file in $oo_temdir/*.sh; do
    vi $script_file -c "set ff=unix" -c ":wq"
    chmod +x $script_file
done

source $oo_bootstrap_script