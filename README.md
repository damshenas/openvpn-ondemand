
# Open VPN On-Demand (OVOD)

The main objective of this project is to provide cheap and reliable VPN solution. You can deploy this solution using AWS CDK.

The solution provisions different AWS resources such as: S3, Lambda, SSM Params, API Gateway and EC2 instances. EC@ instance is launch from the lambda function and is auto terminated if not being used.

