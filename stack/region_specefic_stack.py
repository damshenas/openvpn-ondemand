import json
from datetime import datetime
from constructs import Construct
from aws_cdk import (
    Stack, Aws, Expiration, RemovalPolicy, Duration,
    aws_ec2 as _ec2,
    aws_iam as _iam,
)

class CdkRegionSpeceficStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, envir: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        with open("src/configs.json", 'r') as f:
            configs = json.load(f)
            env_configs = configs["environments"][envir]
            region_specefics = env_configs['region_data'][self.region]

        ### VPC
        ovod_vpc = _ec2.Vpc(self, '{}_ovod_vpc'.format(envir),
            cidr = '10.10.0.0/24',
            max_azs = 5,
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

        block_device = _ec2.BlockDevice(
            device_name="xvdb",
            volume=_ec2.BlockDeviceVolume.ebs(
                volume_size=8, 
                delete_on_termination=True, 
                volume_type=_ec2.EbsDeviceVolumeType.GP3
            )
        )

        valid_until = Expiration.after(Duration.days(730)) #roughly 2 years

        launch_template_spot_options = _ec2.LaunchTemplateSpotOptions(
            interruption_behavior=_ec2.SpotInstanceInterruption.TERMINATE,
            max_price=configs["max_price"],
            request_type=_ec2.SpotRequestType.ONE_TIME
            # request_type=_ec2.SpotRequestType.PERSISTENT,
            # valid_until=valid_until
        )

        instance_role_name = "{}_{}".format(envir, configs['instance_role_name'])

        with open("stack/userdata.sh", 'r') as f:
            user_data_raw = f.read()

        user_data = user_data_raw.format(
            1 if envir == 'dev' else 1, #debug_mode
            "{}-{}".format(envir, configs["s3_bucket_name"]), #artifact_bucket
            self.region, #region
            configs["first_username"] #FIRST_USER_NAME
        )

        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_ec2/MachineImage.html

        machine_image_config = _ec2.MachineImage.latest_amazon_linux(
            cached_in_context=True,
            generation=_ec2.AmazonLinuxGeneration.AMAZON_LINUX_2,
            kernel=_ec2.AmazonLinuxKernel.KERNEL5_X,
            edition=_ec2.AmazonLinuxEdition.STANDARD,
            virtualization=_ec2.AmazonLinuxVirt.HVM,
            storage=_ec2.AmazonLinuxStorage.GENERAL_PURPOSE,
            cpu_type=_ec2.AmazonLinuxCpuType.ARM_64
        )

        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_ec2/LaunchTemplate.html

        launch_template = _ec2.LaunchTemplate(self, "{}_ovod_launch_remplate".format(envir),
            # launch_template_name='',
            block_devices=[block_device],
            instance_initiated_shutdown_behavior=_ec2.InstanceInitiatedShutdownBehavior.TERMINATE,
            instance_type=_ec2.InstanceType.of(_ec2.InstanceClass.BURSTABLE4_GRAVITON, _ec2.InstanceSize.NANO),
            machine_image=machine_image_config,
            role=_iam.Role.from_role_name(self, "ovod_role_ec2", role_name=instance_role_name),
            key_name=region_specefics['ssh_key_name'],
            security_group=security_group,
            spot_options=launch_template_spot_options,
            user_data=_ec2.UserData.custom(user_data)
        )

        launch_template.apply_removal_policy(RemovalPolicy.DESTROY)

        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_ec2/CfnSpotFleet.html

        launch_template_config = _ec2.CfnSpotFleet.LaunchTemplateConfigProperty(
            launch_template_specification=_ec2.CfnSpotFleet.FleetLaunchTemplateSpecificationProperty(
                version=launch_template.latest_version_number,
                launch_template_id=launch_template.launch_template_id
            ),
            overrides=[_ec2.CfnSpotFleet.LaunchTemplateOverridesProperty(
                subnet_id="subnet-062fc05baec1eb838,subnet-082ecc568362c0f40,subnet-0a5bfc27a7a287a85"
                # subnet_id=ovod_vpc.select_subnets(subnet_type=_ec2.SubnetType.PUBLIC).subnet_ids
            )]
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
                on_demand_max_total_price=str(configs["max_price"]),
                on_demand_target_capacity=0,
                replace_unhealthy_instances=True,
                spot_maintenance_strategies=spot_maintenance_strategy,
                spot_max_total_price=str(configs["max_price"]),
                spot_price=str(configs["max_price"]),
                # target_capacity_unit_type="units", # can only be specified with InstanceRequi rements.
                terminate_instances_with_expiration=True,
                # tag_specifications=[instance_tag1],
                # valid_until=valid_until.date.strftime('%Y-%m-%dT%H:%M:%SZ'),
                # type="maintain"
            )
        )
