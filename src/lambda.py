import json, boto3, os

ssm_client = boto3.client('ssm', 'us-east-1')
ec2_client = boto3.client('ec2','us-east-1')

domain_name = ssm_client.get_parameter(Name=os.environ['ssm_domain_name'])['Parameter']['Value']
update_url = ssm_client.get_parameter(Name=os.environ['ssm_ddns_update_key'])['Parameter']['Value']
ec2_role = os.environ['ovod_ec2_instance_role']
artifacts_bucket = os.environ['artifacts_bucket']

def handler(event, context):
    userdata = file_get_contents("userdata.sh").format(domain_name, update_url)
    run_instance(userdata)
    print(userdata)

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/plain'
        },
        'body': 'cool'
    }

def file_get_contents(filename):
    with open(filename) as f:
        return f.read()

def run_instance(userdata):
    return ec2_client.run_instances(
        BlockDeviceMappings=[
            {
                'DeviceName': 'xvdb',
                'Ebs': {
                    'DeleteOnTermination': True,
                    'VolumeSize': 8,
                    'VolumeType': 'gp2',
                },
            },
        ],
        ImageId="ami-0a1eddae0b7f0a79f",
        InstanceType="t4g.nano",
        MaxCount=1,
        MinCount=1,
        SecurityGroupIds=[os.environ['security_group_id']],

        SubnetId=os.environ['vpc_subnet_id'],
        UserData=userdata,

        DisableApiTermination=False,

        InstanceInitiatedShutdownBehavior='terminate',

        TagSpecifications=[
            {
                'ResourceType': 'instance',
                'Tags': [
                    {
                        'Key': 'Name',
                        'Value': 'OpenVPN OnDemand Instance'
                    },
                ]
            },
        ],

        # InstanceMarketOptions={
        #     'MarketType': 'spot',
        #     'SpotOptions': {
        #         'MaxPrice': 'string',
        #         'SpotInstanceType': 'one-time'|'persistent',
        #         'BlockDurationMinutes': 123,
        #         'ValidUntil': datetime(2015, 1, 1),
        #         'InstanceInterruptionBehavior': 'hibernate'|'stop'|'terminate'
        #     }
        # },
    )