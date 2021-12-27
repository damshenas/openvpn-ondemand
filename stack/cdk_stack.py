from constructs import Construct
from aws_cdk import (
    Duration, Stack, RemovalPolicy,
    aws_s3 as _s3,
    aws_iam as _iam,
    aws_ssm as _ssm,
    aws_ec2 as _ec2,
    aws_lambda as _lambda,
    aws_dynamodb as _dydb,
    aws_apigateway as _apigw
)

class CdkStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        ## SSM Param Store
        ssm_domain_name = _ssm.StringParameter(self, "OVOD_DOMAIN_NAME",
            string_value="something.something.com", 
            description="Domain Name for the OpenVPN. Need manual override. Default is None."
        )
        ssm_domain_name.apply_removal_policy(RemovalPolicy.DESTROY) # NOT recommended for production 

        ssm_ddns_update_url = _ssm.StringParameter(self, "OVOD_DDNS_UPDATE_URL",
            string_value="https://freedns.afraid.org/dynamic/update.php?something", 
            description="Update URL for the DDNS (more info on freedns.afraid.org). Need manual override. Default is None."
        )
        ssm_ddns_update_url.apply_removal_policy(RemovalPolicy.DESTROY) # NOT recommended for production 

        ### S3 core
        lifecycle_rule = _s3.LifecycleRule(
                enabled=True,
                expiration=Duration.days(1),
                abort_incomplete_multipart_upload_after=Duration.days(1),
                prefix="profiles"
            )

        artifacts_bucket = _s3.Bucket(self, "ovod-artifacts",
            lifecycle_rules = [lifecycle_rule],
            removal_policy=RemovalPolicy.DESTROY, # NOT recommended for production 
            auto_delete_objects=True,
            block_public_access = _s3.BlockPublicAccess.BLOCK_ALL,
            cors = [ _s3.CorsRule(
                allowed_methods=[ _s3.HttpMethods.GET ],
                allowed_origins=["*"],
            )]
        )

        artifacts_bucket.add_cors_rule(
            allowed_methods=[_s3.HttpMethods.POST],
            allowed_origins=["*"] # add API gateway web resource URL
        )

        ### api gateway core
        # We do not need to set CORS for APIGW as in proxy mode Lambda has to return the relevant headers
        api_gateway = _apigw.RestApi(self, 'ovod_APIGW', 
            rest_api_name='OpenVPNOnDemand'
        )

        ### lambda function
        openvpn_builder_lambda = _lambda.Function(self, "ovod_builder",
            function_name="ovod_builder",
            runtime=_lambda.Runtime.PYTHON_3_7,
            environment={
                "region": self.region,
                "debug_mode": False,
                "artifacts_bucket": artifacts_bucket.bucket_name,
                "ssm_domain_name": ssm_domain_name.parameter_name,
                "ssm_ddns_update_key": ssm_ddns_update_url.parameter_name,
            },
            handler="main.handler",
            code=_lambda.Code.from_asset("./src"))

        artifacts_bucket.grant_put(openvpn_builder_lambda, objects_key_pattern="scripts/*")
        artifacts_bucket.grant_read(openvpn_builder_lambda, objects_key_pattern="profiles/*")
        ssm_domain_name.grant_read(openvpn_builder_lambda)
        ssm_ddns_update_url.grant_read(openvpn_builder_lambda)

        openvpn_builder_lambda_integration = _apigw.LambdaIntegration(
            openvpn_builder_lambda,
            proxy=True)

        api_gateway.root.add_method('POST', openvpn_builder_lambda_integration)

        ### create dynamo table
        dynamodb_table = _dydb.Table(
            self, "openvpn_table",
            partition_key=_dydb.Attribute(
                name="username",
                type=_dydb.AttributeType.STRING
            ),
            billing_mode=_dydb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY # NOT recommended for production 
        )
        openvpn_builder_lambda.add_environment('dynamodb_table_name', dynamodb_table.table_name)
        dynamodb_table.grant_read_write_data(openvpn_builder_lambda)

        ### VPC
        ovod_vpc = _ec2.Vpc(self, 'ovod_vpc',
            cidr = '10.10.0.0/24',
            max_azs = 2,
            enable_dns_hostnames = True,
            enable_dns_support = True, 
            subnet_configuration=[
                _ec2.SubnetConfiguration(
                    name = 'Public-Subent',
                    subnet_type = _ec2.SubnetType.PUBLIC,
                    cidr_mask = 26
                )
            ],
            nat_gateways = 0,
        )

        openvpn_builder_lambda.add_environment('vpc_subnet_id', ovod_vpc.public_subnets[0].subnet_id)

        ### security group
        security_group = _ec2.SecurityGroup(self, "ovod_ec2_security_group",
            vpc = ovod_vpc,
            allow_all_outbound = True
        )

        security_group.add_ingress_rule(
            _ec2.Peer.any_ipv4(),
            _ec2.Port.udp(1194),
        )

        openvpn_builder_lambda.add_environment('security_group_id', security_group.security_group_id)

        ### IAM policies
        ovod_lambda_policy = _iam.PolicyStatement(
            effect=_iam.Effect.ALLOW, 
            resources=['*'], #TBU not secure
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
                "iam:PassRole",
                "s3:ListBucket"
            ])

        ovod_ec2_policy_scripts = _iam.PolicyStatement(
            effect=_iam.Effect.ALLOW, 
            resources=[
                "{}/scripts/*".format(artifacts_bucket.bucket_arn)
            ],
            actions=[
                "s3:GetObject",
            ])

        ovod_ec2_policy_profiles = _iam.PolicyStatement(
            effect=_iam.Effect.ALLOW, 
            resources=[
                "{}/profiles/*".format(artifacts_bucket.bucket_arn)
            ],
            actions=[
                "s3:PutObject",
                "s3:DeleteObject",
            ])

        ovod_ec2_policy_configs = _iam.PolicyStatement(
            effect=_iam.Effect.ALLOW, 
            resources=[
                "{}/openvpn/*".format(artifacts_bucket.bucket_arn)
            ],
            actions=[
                "s3:PutObject",
                "s3:GetObject",
                "s3:PutObject"
            ])

        ovod_ec2_policy_generic = _iam.PolicyStatement(
            effect=_iam.Effect.ALLOW, 
            resources=[artifacts_bucket.bucket_arn],
            actions=[
                "s3:ListBucket"
            ])

        ### IAM roles instance profile
        ovod_ec2_instance_role = _iam.Role(self, "ovod_ec2_instance_role",
            role_name="ovod_ec2_instance_role",
            assumed_by=_iam.ServicePrincipal("ec2.amazonaws.com"))

        ovod_ec2_instance_role.add_to_policy(ovod_ec2_policy_scripts)
        ovod_ec2_instance_role.add_to_policy(ovod_ec2_policy_profiles)
        ovod_ec2_instance_role.add_to_policy(ovod_ec2_policy_configs)
        ovod_ec2_instance_role.add_to_policy(ovod_ec2_policy_generic)

        ovod_ec2_instance_profile = _iam.CfnInstanceProfile(self, "ovod_ec2_instance_profile",
            roles=[ovod_ec2_instance_role.role_name],
        )

        openvpn_builder_lambda.add_to_role_policy(ovod_lambda_policy)
        openvpn_builder_lambda.add_environment('ovod_ec2_instance_role', ovod_ec2_instance_profile.attr_arn)