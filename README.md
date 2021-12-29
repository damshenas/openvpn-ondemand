
# Open VPN On-Demand (OVOD)

The main objective of this project is to provide cheap and reliable VPN solution. You can deploy this solution using AWS CDK.

The solution provisions different AWS resources such as: S3, Lambda, SSM Params, API Gateway and EC2 instances. EC@ instance is launch from the lambda function and is auto terminated if not being used.

Cost estimation for all setup is (with low usage assumptions) ~ $3 per month. Of course this can change depend on the hours the server is running and amount of data communicated. Please check the following link for more information: https://calculator.aws/#/estimate?id=0a424fee9a16e4880ecd8310f97c2993d1cad0e2