#!/bin/bash

ddns_file=/tmp/ddns.sh
curl -sSL http://freedns.afraid.org/scripts/afraid.aws.sh.txt -o $ddns_file
sed -i 's/UPDATE_URL/{}/' $ddns_file

chmod +x $ddns_file
source $ddns_file

bootstrap_file=/tmp/bootstrap.sh 
curl -sSL https://pastebin.com/raw/w9gXRExG -o $bootstrap_file
sed -i 's/DOMAIN_NAME/{}/' $bootstrap_file

chmod +x $bootstrap_file
source $bootstrap_file