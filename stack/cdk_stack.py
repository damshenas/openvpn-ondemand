from aws_cdk import (
    aws_s3 as _s3,
    aws_iam as _iam,
    aws_ssm as _ssm,
    Stack
)

from aws_cdk.aws_apigateway import (
    RestApi,
    LambdaIntegration,
    MockIntegration,
    PassthroughBehavior
)

from aws_cdk.aws_lambda import (
    Code,
    Function,
    Runtime
)

from constructs import Construct

class CdkStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        ## SSM Param Store
        ssm_domain_name = _ssm.StringParameter(self, "OVOD_DOMAIN_NAME",
            string_value="something.something.com", 
            description="Domain Name for the OpenVPN. Need manual override. Default is None."
        )

        ssm_ddns_update_url = _ssm.StringParameter(self, "OVOD_DDNS_UPDATE_URL",
            string_value="https://freedns.afraid.org/dynamic/update.php?something", 
            description="Update URL for the DDNS (more info on freedns.afraid.org). Need manual override. Default is None."
        )
        
        ### S3 core
        artifacts_bucket = _s3.Bucket(self, "ovod-artifacts")

        artifacts_bucket.add_cors_rule(
            allowed_methods=[_s3.HttpMethods.POST],
            allowed_origins=["*"] # add API gateway web resource URL
        )

        ### IAM policies
        ovod_lambda_policy = _iam.PolicyStatement(
            effect=_iam.Effect.ALLOW, 
            resources=['*'],
            actions=[
                "ec2:RunInstances", 
                "ec2:TerminateInstances", 
                "ec2:StartInstances",
                "ec2:StopInstances",
                "ec2:CreateTags", 
                "ec2:DescribeInstances",
                "ec2:DescribeInstanceStatus",
                "ec2:DescribeAddresses", 
                "ec2:AssociateAddress",
                "ec2:DisassociateAddress",
                "ec2:DescribeRegions",
                "ec2:DescribeAvailabilityZones",
                "iam:PassRole"
            ])

        ovod_ec2_policy = _iam.PolicyStatement(
            effect=_iam.Effect.ALLOW, 
            resources=['*'],
            actions=[
                "s3:GetObjectAcl",
                "s3:GetObject"            
            ])

        ### IAM roles
        ovod_ec2_instance_role = _iam.Role(self, "ovod_ec2_instance_role",
            role_name="ovod_ec2_instance_role",
            assumed_by=_iam.ServicePrincipal("ec2.amazonaws.com"))

        ovod_ec2_instance_role.add_to_policy(ovod_ec2_policy)

        ### api gateway core
        api_gateway = RestApi(self, 'ovod_APIGW', rest_api_name='OpenVPNOnDemand')
        api_gateway_resource = api_gateway.root.add_resource("ovod")
        api_gateway_root = api_gateway_resource.add_resource('get')
        self.add_cors_options(api_gateway_root)

        ### lambda function
        openvpn_builder_lambda = Function(self, "ovod_builder",
            function_name="ovod_builder",
            runtime=Runtime.PYTHON_3_7,
            environment={
                "artifacts_bucket": artifacts_bucket.bucket_name,
                "ssm_domain_name": ssm_domain_name.parameter_name,
                "ssm_ddns_update_key": ssm_ddns_update_url.parameter_name,
                "ovod_ec2_instance_role": ovod_ec2_instance_role.role_arn
            },
            handler="lambda.handler",
            code=Code.from_asset("./src"))

        artifacts_bucket.grant_put(openvpn_builder_lambda, objects_key_pattern="scripts/*")
        ssm_domain_name.grant_read(openvpn_builder_lambda)
        ssm_ddns_update_url.grant_read(openvpn_builder_lambda)
        openvpn_builder_lambda.add_to_role_policy(ovod_lambda_policy)

        openvpn_builder_lambda_integration = LambdaIntegration(
            openvpn_builder_lambda,
            proxy=True,
            integration_responses=[{
                'statusCode': '200',
               'responseParameters': {
                   'method.response.header.Access-Control-Allow-Origin': "'*'",
                }
            }])

        api_gateway_root.add_method('GET', openvpn_builder_lambda_integration,
            method_responses=[{
                'statusCode': '200',
                'responseParameters': {
                    'method.response.header.Access-Control-Allow-Origin': True,
                }
            }])

    def add_cors_options(self, apigw_resource):
        apigw_resource.add_method('OPTIONS', MockIntegration(
            integration_responses=[{
                'statusCode': '200',
                'responseParameters': {
                    'method.response.header.Access-Control-Allow-Headers': "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'",
                    'method.response.header.Access-Control-Allow-Origin': "'*'",
                    'method.response.header.Access-Control-Allow-Methods': "'GET,OPTIONS'"
                }
            }
            ],
            passthrough_behavior=PassthroughBehavior.WHEN_NO_MATCH,
            request_templates={"application/json":"{\"statusCode\":200}"}
        ),
        method_responses=[{
            'statusCode': '200',
            'responseParameters': {
                'method.response.header.Access-Control-Allow-Headers': True,
                'method.response.header.Access-Control-Allow-Methods': True,
                'method.response.header.Access-Control-Allow-Origin': True,
                }
            }
        ],
    )