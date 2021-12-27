import boto3, os, time

region = 'us-east-1'

ssm_client = boto3.client('ssm', region)
ec2_client = boto3.client('ec2',region)
s3_client = boto3.client('s3',region)
ddb_client = boto3.client('dynamodb',region)

domain_name = ssm_client.get_parameter(Name=os.environ['ssm_domain_name'])['Parameter']['Value']
update_url = ssm_client.get_parameter(Name=os.environ['ssm_ddns_update_key'])['Parameter']['Value']
ec2_role = os.environ['ovod_ec2_instance_role']
artifacts_bucket = os.environ['artifacts_bucket']
dynamodb_table = os.environ['dynamodb_table_name']

def generate_ec2_userdata(username):
    bootstrap_script = uplaod_to_s3("bootstrap.sh")
    ddns_script = uplaod_to_s3("ddns.sh")
    return file_get_contents("userdata.sh").format(
        artifacts_bucket, ddns_script, update_url, bootstrap_script, domain_name, username
    )

def file_get_contents(filename):
    with open(filename) as f:
        return f.read()

def uplaod_to_s3(file_path):
    target_key = "scripts/{}".format(file_path.split('/')[-1])
    if check_s3_obj(target_key): return target_key # if exist skip uploading scripts # should we?
    s3_client.upload_file(file_path, artifacts_bucket, target_key)
    return target_key

def check_s3_obj(target_key):
    objs = s3_client.list_objects_v2(
        Bucket=artifacts_bucket,
        Prefix=target_key,
    )
    return objs['KeyCount']

def is_login_valid(username, password):
    response = ddb_client.get_item(
        TableName=dynamodb_table,
        Key={'username': {'S': username}}
    )
    return 'Item' in response

def update_last_login(username):
    return ddb_client.update_item(
        TableName=dynamodb_table, 
        Key={'username': {'S': username}},
        UpdateExpression="SET last_login = :ll",
        ExpressionAttributeValues={':ll': {"N": str(int(time.time()))}} 
    )

def check_if_instance_exists(name): # name example: *OpenVPN*
    response = ec2_client.describe_instances(
        Filters=[{'Name': 'tag:Name', 'Values': [name]}])

    if len(response["Reservations"]) > 0:
        for reservation in response["Reservations"]:
            for instance in reservation["Instances"]:
                if instance["State"]["Name"] == "running":  return "running"
                if instance["State"]["Name"] == "pending":  return "pending"

    return False

def gen_s3_url(key_name): #create presigned url
    return s3_client.generate_presigned_url('get_object', 
        Params={'Bucket': artifacts_bucket, 'Key': key_name},
        ExpiresIn=1800)

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
        KeyName="n.virginia.def.key", #just for debugging change the key name. production does not need this.

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

        IamInstanceProfile={'Arn': ec2_role},

        # InstanceMarketOptions={ # to save costs
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