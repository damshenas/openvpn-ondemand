import boto3, os, time

class main:
    def __init__(self, username, ec2_region, region='us-east-1'):
        self.region = 'us-east-1'
        self.sshkeyname = 'default.key'
        self.ec2_region = region
        self.username = username
        self.ec2_client = boto3.client('ec2',ec2_region)
        self.ssm_client = boto3.client('ssm', region)
        self.s3_client = boto3.client('s3',region)
        self.ddb_client = boto3.client('dynamodb',region)
        self.ec2_role = os.environ['ovod_ec2_instance_role']
        self.artifacts_bucket = os.environ['artifacts_bucket']
        self.dynamodb_table = os.environ['dynamodb_table_name']
        self.debug_mode = 0 if os.environ['debug_mode'] == 'true' else 1

    def generate_ec2_userdata(self):
        for f in ["bootstrap.sh", "profile.sh"]: 
            self.uplaod_to_s3(f)
        return self.file_get_contents("userdata.sh").format(
            self.debug_mode, self.artifacts_bucket, self.username 
        )

    def file_get_contents(self, filename):
        with open(filename) as f:
            return f.read()

    def uplaod_to_s3(self, file_path):
        target_key = "scripts/{}".format(file_path.split('/')[-1])
        if not self.debug_mode and self.check_s3_obj(target_key): return target_key # if exist and not debugging skip uploading scripts
        self.s3_client.upload_file(file_path, self.artifacts_bucket, target_key)
        return target_key

    def check_s3_obj(self, target_key):
        objs = self.s3_client.list_objects_v2(
            Bucket=self.artifacts_bucket,
            Prefix=target_key,
        )
        return objs['KeyCount']

    def is_login_valid(self, password):
        response = self.ddb_client.get_item(
            TableName=self.dynamodb_table,
            Key={'username': {'S': self.username}}
        )

        return True if 'Item' in response and response['Item']['password']['S'] == password else False

    def update_last_login(self):
        return self.ddb_client.update_item(
            TableName=self.dynamodb_table, 
            Key={'username': {'S': self.username}},
            UpdateExpression="SET last_login = :ll",
            ExpressionAttributeValues={':ll': {"N": str(int(time.time()))}} 
        )

    def check_if_instance_exists(self, name): # name example: *OpenVPN*
        instances = self.ec2_client.describe_instances( Filters=[{'Name': 'tag:Name', 'Values': [name]}])

        if len(instances["Reservations"]) > 0:
            for reservation in instances["Reservations"]:
                for instance in reservation["Instances"]:
                    if instance["State"]["Name"] == "running":  return ["running", instance["InstanceId"]]
                    if instance["State"]["Name"] == "pending":  return ["pending", instance["InstanceId"]]

        return ["", ""]

    def gen_s3_url(self, key_name): #create presigned url
        return self.s3_client.generate_presigned_url('get_object', 
            Params={'Bucket': self.artifacts_bucket, 'Key': key_name},
            ExpiresIn=1800)

    def add_profile(self, instance_id):
        return self.ssm_client.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            TimeoutSeconds=300,
            Comment='Creating profile for user {} in instance {}'.format(self.username, instance_id),
            Parameters={'commands': ['source /tmp/profile.sh {}'.format(self.username)]})

    def run_instance(self, userdata):
        instance = self.ec2_client.run_instances(
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
            KeyName=self.sshkeyname,

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

            IamInstanceProfile={'Arn': self.ec2_role},

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


        return instance['Instances'][0]['InstanceId']