from constructs import Construct
from aws_cdk import (
    Duration, Stack, RemovalPolicy, PhysicalName,
    aws_s3 as _s3,
    aws_iam as _iam,
    aws_logs as _logs,
    aws_lambda as _lambda,
    aws_dynamodb as _dydb,
    aws_apigateway as _apigw,
)

class CdkMainStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        ### S3 core
        lifecycle_rule = _s3.LifecycleRule(
                enabled=True,
                expiration=Duration.days(1),
                abort_incomplete_multipart_upload_after=Duration.days(1),
                prefix="profiles"
            )

        self.artifacts_bucket = _s3.Bucket(self, "ovod-artifacts",
            bucket_name = PhysicalName.GENERATE_IF_NEEDED,
            lifecycle_rules = [lifecycle_rule],
            removal_policy=RemovalPolicy.DESTROY, # NOT recommended for production 
            auto_delete_objects=True,
            block_public_access = _s3.BlockPublicAccess.BLOCK_ALL,
            cors = [ _s3.CorsRule(
                allowed_methods=[ _s3.HttpMethods.GET ],
                allowed_origins=["*"],
            )]
        )

        self.artifacts_bucket.add_cors_rule(
            allowed_methods=[_s3.HttpMethods.POST],
            allowed_origins=["*"] # add API gateway web resource URL
        )

        ### api gateway core
        # We do not need to set CORS for APIGW as in proxy mode Lambda has to return the relevant headers
        api_gateway = _apigw.RestApi(self, 'ovod_APIGW', 
            rest_api_name='OpenVPNOnDemand'
        )

        ### lambda function
        self.openvpn_builder_lambda = _lambda.Function(self, "ovod_builder",
            function_name="ovod_builder",
            runtime=_lambda.Runtime.PYTHON_3_9,
            architecture=_lambda.Architecture.ARM_64,
            log_retention=_logs.RetentionDays.THREE_MONTHS,
            timeout=Duration.seconds(10),
            environment={
                "region": self.region,
                "debug_mode": 'false',
                "artifacts_bucket": self.artifacts_bucket.bucket_name
            },
            handler="main.handler",
            code=_lambda.Code.from_asset("./src"))

        self.artifacts_bucket.grant_put(self.openvpn_builder_lambda, objects_key_pattern="scripts/*")
        self.artifacts_bucket.grant_read(self.openvpn_builder_lambda, objects_key_pattern="profiles/*")

        openvpn_builder_lambda_integration = _apigw.LambdaIntegration(
            self.openvpn_builder_lambda,
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
        self.openvpn_builder_lambda.add_environment('dynamodb_table_name', dynamodb_table.table_name)
        dynamodb_table.grant_read_write_data(self.openvpn_builder_lambda)

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
                "s3:ListBucket",
                "ssm:SendCommand"
            ])

        self.openvpn_builder_lambda.add_to_role_policy(ovod_lambda_policy)


        ### IAM policies
        ovod_ec2_policy_scripts = _iam.PolicyStatement(
            effect=_iam.Effect.ALLOW, 
            resources=[
                "{}/*".format(self.artifacts_bucket.bucket_arn)
            ],
            actions=[
                "s3:GetObject",
            ])

        ovod_ec2_policy_profiles = _iam.PolicyStatement(
            effect=_iam.Effect.ALLOW, 
            resources=[
                "{}/profiles/*".format(self.artifacts_bucket.bucket_arn)
            ],
            actions=[
                "s3:PutObject",
                "s3:DeleteObject",
            ])

        ovod_ec2_policy_generic = _iam.PolicyStatement(
            effect=_iam.Effect.ALLOW, 
            resources=[self.artifacts_bucket.bucket_arn],
            actions=[
                "s3:ListBucket"
            ])

        ### IAM roles instance profile 
        ovod_ec2_instance_role = _iam.Role(self, "ovod_ec2_instance_role",
            role_name="ovod_ec2_instance_role",
            managed_policies=[
                _iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
            ],
            assumed_by=_iam.ServicePrincipal("ec2.amazonaws.com"))

        ovod_ec2_instance_role.add_to_policy(ovod_ec2_policy_scripts)
        ovod_ec2_instance_role.add_to_policy(ovod_ec2_policy_profiles)
        ovod_ec2_instance_role.add_to_policy(ovod_ec2_policy_generic)

        ovod_ec2_instance_profile = _iam.CfnInstanceProfile(self, "ovod_ec2_instance_profile",
            roles=[ovod_ec2_instance_role.role_name],
        )

        self.openvpn_builder_lambda.add_environment('ec2_instance_role', ovod_ec2_instance_profile.attr_arn)