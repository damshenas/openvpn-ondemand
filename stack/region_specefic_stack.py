from constructs import Construct
from aws_cdk import (
    Stack, CfnOutput,
    aws_iam as _iam,
    aws_s3 as _s3,
    aws_lambda as _lambda,
    aws_ec2 as _ec2
)

class CdkRegionSpeceficStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, envir: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        ### VPC
        ovod_vpc = _ec2.Vpc(self, '{}_ovod_vpc'.format(envir),
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

        ### security group
        security_group = _ec2.SecurityGroup(self, "{}_ovod_ec2_security_group".format(envir),
            vpc = ovod_vpc,
            allow_all_outbound = True
        )

        security_group.add_ingress_rule(
            _ec2.Peer.any_ipv4(),
            _ec2.Port.tcp(1897), #make sure to change it if you changed the default port #TBU
        )
        
        CfnOutput(self, "security_group_id", value=security_group.security_group_id)
        CfnOutput(self, "vpc_subnet_id", value=ovod_vpc.public_subnets[0].subnet_id)
