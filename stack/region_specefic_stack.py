import json
from datetime import datetime
from constructs import Construct
from aws_cdk import (
    Stack, CfnOutput, Aws, CfnTag,
    aws_ec2 as _ec2
)

class CdkRegionSpeceficStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, envir: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        with open("src/configs.json", 'r') as f:
            configs = json.load(f)
            instance_role_name = configs['instance_role_name']
            env_configs = configs["environments"][envir]
            region_specefics = env_configs['region_data'][self.region]

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
            _ec2.Port.tcp(configs["tcp_udp_port"]),
        )
        
        CfnOutput(self, "security_group_id", value=security_group.security_group_id)
        CfnOutput(self, "vpc_subnet_id", value=ovod_vpc.public_subnets[0].subnet_id)

        ### Spot request
        # create spot request with target 0
        # the spot request need to use spot config with user data ... perhaps some issues here
        # - most of the logics will be moved here as infra code
        # upon request the target will be 0 (instead of launching instance)
        #

        # documentation CFN
        # https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ec2-spotfleet.html
        # https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ec2-launchtemplate-launchtemplatedata.html
        # https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ec2-spotfleet-spotfleetrequestconfigdata.html
        # 

        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_ec2/CfnSpotFleet.html
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_ec2/CfnLaunchTemplate.html

        block_device_mapping1 = _ec2.CfnLaunchTemplate.BlockDeviceMappingProperty(
            device_name="xvdb",
            ebs=_ec2.CfnLaunchTemplate.EbsProperty(
                delete_on_termination=True,
                volume_size=8,
                volume_type="gp3"
            )
        )

        from datetime import datetime, timedelta
        now = datetime.now()
        diff = timedelta(weeks=260) # equals roughly to 5 years
        future = now + diff

        instance_role_name = "{}_{}".format(envir, configs['instance_role_name'])

        instance_market_option = _ec2.CfnLaunchTemplate.InstanceMarketOptionsProperty(
            market_type="spot",
            spot_options=_ec2.CfnLaunchTemplate.SpotOptionsProperty(
                instance_interruption_behavior="terminate",
                max_price=configs["max_price"],
                spot_instance_type="persistent",
                valid_until=future.strftime("%Y-%m-%dT%H:%M:%SZ") #YYYY-MM-DDTHH:MM:SSZ #will be in UTC
            )
        )

        instance_requirement = _ec2.CfnLaunchTemplate.InstanceRequirementsProperty(
            burstable_performance="required", # only t2, t3, t3a, t4g
            cpu_manufacturers=["amazon-web-services"], # AWS CPUs
            instance_generations=["current"],
            memory_mib=_ec2.CfnLaunchTemplate.MemoryMiBProperty(max=1, min=0),
            v_cpu_count=_ec2.CfnLaunchTemplate.VCpuCountProperty(max=2, min=0)
        )

        instance_tag1 = _ec2.CfnLaunchTemplate.TagSpecificationProperty( 
                resource_type="resourceType",
                tags=[CfnTag(
                    key="Name",
                    value="OpenVPN OnDemand Instance"
                )]
            )


        with open("src/userdata.sh", 'r') as f:
            user_data_raw = f.read()

        user_data = user_data_raw.format(
            1 if envir == 'dev' else 1, #debug_mode
            "{}-{}".format(envir, configs["s3_bucket_name"]), #artifact_bucket
            self.region, #region
            configs["first_username"] #FIRST_USER_NAME
        )

        launch_template_data = _ec2.CfnLaunchTemplate.LaunchTemplateDataProperty(
            block_device_mappings=[block_device_mapping1],
            iam_instance_profile=_ec2.CfnLaunchTemplate.IamInstanceProfileProperty(name=instance_role_name),
            image_id=region_specefics['image_id'],
            instance_initiated_shutdown_behavior="terminate",
            instance_market_options=instance_market_option,
            instance_requirements=instance_requirement,
            key_name=region_specefics['ssh_key_name'],
            security_group_ids=[security_group.security_group_id],
            tag_specifications=[instance_tag1], #tag instances and volumes on launch
            # user_data=user_data
        )

        # Resource handler returned message: "Following LaunchTemplateSpecifications are either malformed or 
        # does not exist: [LaunchTemplateId: LaunchTemplate, Version: 1]. <===
        # (Service: Ec2, Status Code: 400, Request ID: a93a60bf-969c-4ab8-bf9e-8c4de73b1d48, Extended Request ID: null)" (RequestToken: e674a6d5-e92f-3d4d-e5b4-25b2
        # d64a1e2f, HandlerErrorCode: GeneralServiceException)

        launch_template = _ec2.CfnLaunchTemplate(self, "LaunchTemplate", launch_template_data=launch_template_data)

        launch_template_config = _ec2.CfnSpotFleet.LaunchTemplateConfigProperty(
            launch_template_specification=_ec2.CfnSpotFleet.FleetLaunchTemplateSpecificationProperty(
                version=launch_template.attr_latest_version_number,
                launch_template_id=launch_template.ref
            )
        )

        fleet_role_name = "{}".format(configs['fleet_role_name']) #to be updated as not supporting different environments #better to create it 
        generic_role_arn = "arn:aws:iam::{}:role/NAME".format(Aws.ACCOUNT_ID)
        fleet_role_arn = generic_role_arn.replace("NAME", fleet_role_name)

        # we need to add some additional logic for seamless transmission of old instance ot the new instance
        # probably have to use the subdomain again
        # also need to reuse the client cert (so the openvpn client retry succeed)
        # also need to reuse the server certs (so the openvpn client retry succeed)
        spot_maintenance_strategy = _ec2.CfnSpotFleet.SpotMaintenanceStrategiesProperty(
            capacity_rebalance=_ec2.CfnSpotFleet.SpotCapacityRebalanceProperty(
                replacement_strategy="launch-before-terminate",
                termination_delay=7200
            )
        )

        spot_fleet = _ec2.CfnSpotFleet(self, "MyCfnSpotFleet",
            spot_fleet_request_config_data=_ec2.CfnSpotFleet.SpotFleetRequestConfigDataProperty(
                iam_fleet_role=fleet_role_arn,
                target_capacity=0, # default is 0 but will be changed to 1 by lambda function
                allocation_strategy="lowestPrice",
                excess_capacity_termination_policy="default", # terminated instances if you decrease the target capacity
                instance_interruption_behavior="terminate",
                # launch_specifications=[launch_specifications], # either launch_specifications or launch_template_configs
                launch_template_configs=[launch_template_config],
                on_demand_allocation_strategy="lowestPrice",
                on_demand_max_total_price=configs["max_price"],
                on_demand_target_capacity=0,
                replace_unhealthy_instances=True,
                spot_maintenance_strategies=spot_maintenance_strategy,
                spot_max_total_price=configs["max_price"],
                spot_price=configs["max_price"],
                target_capacity_unit_type="units",
                terminate_instances_with_expiration=True,
                type="maintain"
            )
        )

        spot_fleet.node.add_dependency(launch_template)