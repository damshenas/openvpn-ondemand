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
            _ec2.Port.tcp(1897), #make sure to change it if you changed the default port #TBU
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

        # https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/CfnSpotFleet.html
        # https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/CfnSpotFleet.html#aws_cdk.aws_ec2.CfnSpotFleet.SpotFleetRequestConfigDataProperty

        block_device_mapping1 = _ec2.CfnSpotFleet.BlockDeviceMappingProperty(
            device_name="xvdb",
            ebs=_ec2.CfnSpotFleet.EbsBlockDeviceProperty(
                delete_on_termination=True,
                volume_size=8,
                volume_type="gp3"
            )
        )

        instance_role_name = "{}_{}".format(envir, configs['instance_role_name']),

        # instance_requirements = _ec2.CfnSpotFleet.InstanceRequirementsRequestProperty(
        #     burstable_performance="required", # only t2, t3, t3a, t4g
        #     cpu_manufacturers=["amazon-web-services"], # AWS CPUs
        #     instance_generations=["current"],
        #     memory_mi_b=_ec2.CfnSpotFleet.MemoryMiBRequestProperty(max=1, min=0),
        #     v_cpu_count=_ec2.CfnSpotFleet.VCpuCountRangeRequestProperty(max=2, min=0)
        # )

        # https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ec2/CfnLaunchTemplate.html

        instance_market_option = _ec2.CfnLaunchTemplate.InstanceMarketOptionsProperty(
            market_type="spot",
            spot_options=_ec2.CfnLaunchTemplate.SpotOptionsProperty(
                instance_interruption_behavior="terminate",
                max_price=configs["max_price"],
                spot_instance_type="persistent",
                valid_until="validUntil"
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

        launch_template_data = _ec2.CfnLaunchTemplate.LaunchTemplateDataProperty(
            block_device_mappings=[block_device_mapping1],
            iam_instance_profile=_ec2.CfnLaunchTemplate.IamInstanceProfileProperty(name=instance_role_name),
            image_id=region_specefics['image_id'],
            instance_initiated_shutdown_behavior="terminate",
            instance_market_options=instance_market_option,
            instance_requirements=instance_requirement,
            key_name=region_specefics['ssh_key_name'],
            security_group_ids=[security_group.security_group_id],
            tag_specifications=[instance_tag1] #tag instances and volumes on launch
        )

        launch_template = _ec2.CfnLaunchTemplate(self, "LaunchTemplate", launch_template_data=launch_template_data)

        # launch_specifications = _ec2.CfnSpotFleet.SpotFleetLaunchSpecificationProperty(
        #             image_id=region_specefics['image_id'],
        #             block_device_mappings=[block_device_mapping],
        #             iam_instance_profile=_ec2.CfnSpotFleet.IamInstanceProfileSpecificationProperty(arn=instance_role_arn),
        #             instance_requirements=instance_requirements,
        #             # instance_type=["t4g.nano", "t4g.micro"], #If InstanceRequirements is specified, can’t specify InstanceTypes
        #             key_name=region_specefics['ssh_key_name'],
        #             security_groups=[_ec2.CfnSpotFleet.GroupIdentifierProperty(
        #                 group_id=security_group.security_group_id
        #             )],
        #             spot_price=configs["max_price"],
        #             subnet_id="{},{},{}".format(
        #                 ovod_vpc.public_subnets[0].subnet_id,
        #                 ovod_vpc.public_subnets[1].subnet_id,
        #                 ovod_vpc.public_subnets[2].subnet_id
        #             ),
        #             tag_specifications=[_ec2.CfnSpotFleet.SpotFleetTagSpecificationProperty(
        #                 resource_type="resourceType",
        #                 tags=[CfnTag(
        #                     key="Name",
        #                     value="OpenVPN OnDemand Instance"
        #                 )]
        #             )],
        #             # user_data="userData" # trying to keep the logic out of infra so we do not need to redeploy if some logic code is changed
        #         )

        launch_template_config = _ec2.CfnSpotFleet.LaunchTemplateConfigProperty(
            launch_template_specification=_ec2.CfnSpotFleet.FleetLaunchTemplateSpecificationProperty(
                version=launch_template.attr_latest_version_number,
                launch_template_id=launch_template.logical_id,
                launch_template_name=launch_template.launch_template_name
            )
        )

        fleet_role_name = "{}_{}".format(envir, configs['fleet_role_name'])
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

        _ec2.CfnSpotFleet(self, "MyCfnSpotFleet",
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
                target_capacity_unit_type="targetCapacityUnitType",
                terminate_instances_with_expiration=True,
                type="maintain"
            )
        )
