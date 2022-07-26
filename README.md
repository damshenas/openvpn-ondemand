
# Open VPN On-Demand (OVOD)

The main objective of this project is to provide cheap and reliable VPN solution. You can deploy this solution using AWS CDK.

The solution provisions different AWS resources such as: S3, Lambda, SSM Params, API Gateway and EC2 instances (Spot). EC2 instance is launched using Spot Request with target capacity increased by the lambda function; and is auto terminated if not being used.

# Prerequisites
1- aws cli
2- aws cdk
3- aws account
4- configuration of aws cli

# Configs

## Domain and DDNS
You have the option to use route53 or alternatively use any DDNS service (i.e. afraid.org)
export AFRAID_DDNS_UPDATE_URL="http://username:password@sync.afraid.org/u/?h=REGION.my.to&ip=EPIP"
export AFRAID_BASE_URL=the domain i.e. my.to

## CDK
xport CDK_DEFAULT_ACCOUNT=111111111111
export CDK_DEFAULT_REGION=us-east-1
cdk bootstrap aws://$CDK_DEFAULT_ACCOUNT/$CDK_DEFAULT_REGION

# Usage
clone the repo
cdk synth
cdk deploy --all --require-approval=never

# Cleanup
cdk destroy --all --force

# Approximate monthly cost:
Assumed Data Transfer (egress): 30GB
Assumed Hours Usage: 30 hours
Cost estimation for all setup is (with low usage assumptions) ~ $3 per month. Of course this can change depend on the hours the server is running and amount of data communicated. Please check the following link for more information: https://calculator.aws/#/estimate?id=e63c6e4818ca642f5d461be96f9a0e190c1a42ef
