import boto3, os, time, json

class main:
    def __init__(self, username, name, ec2_region, region_specefics, region='us-east-1'):
        self.username = username
        self.ec2_region = ec2_region
        self.name = name
        self.env = os.environ['env']
        # self.artifacts_bucket = os.environ['artifacts_bucket']
        # self.ec2_role = os.environ['ec2_instance_role']
        self.dynamodb_table = os.environ['dynamodb_table_name']
        # self.debug_mode = 0 if os.environ['debug_mode'] == 'true' else 1 # this will be done using env of the stack

        self.ssm_client = boto3.client('ssm', ec2_region)
        self.ec2_client = boto3.client('ec2',ec2_region)
        # self.security_group_id, self.vpc_subnet_id = self.get_vpc_sg()
        # self.ssh_key_name =  region_specefics['ssh_key_name']
        # self.image_id =  region_specefics['image_id']

        self.s3_client = boto3.client('s3',region)
        self.ddb_client = boto3.client('dynamodb',region)

    def generate_ec2_userdata(self):
        for f in ["bootstrap.sh", "profile.sh", "notice.sh"]: 
            self.uplaod_script_to_s3(f)
        # return self.file_get_contents("userdata.sh").format(
        #     self.debug_mode, self.artifacts_bucket, self.ec2_region, self.username
        # )

    def file_get_contents(self, filename):
        with open(filename) as f:
            return f.read()

    def uplaod_script_to_s3(self, file_path):
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

    def check_if_spot_target_exists(self):
        spot_fleet_request_status = ""
        spot_fleet_activity_status = ""
        spot_fleet_request_id = ""

        spot_fleet_requests = self.ec2_client.describe_spot_fleet_requests().get("SpotFleetRequestConfigs")

        for spot_fleet_request in spot_fleet_requests:
            spot_fleet_request_status = spot_fleet_request.get("SpotFleetRequestState")
            spot_fleet_activity_status = spot_fleet_request.get("ActivityStatus")
            spot_fleet_request_id = spot_fleet_request.get("SpotFleetRequestId")
            
            if spot_fleet_request_status == "active":
                if spot_fleet_activity_status == "fulfilled":
                    return [spot_fleet_request_id, spot_fleet_request_status, spot_fleet_activity_status]

                # what if status is "pending_fulfillment"
                # the instance is being created
                # what if spot instance is not available?!!

            elif spot_fleet_request.get("SpotFleetRequestState") == "modifying":
                pass 
                # need to handle when 2 people request with small delay and the first change the instance to modifying
                # if we return false, target is changed to 1 which is fine, but the user will never get the profile cert

    def check_if_instance_exists_query_ec2(self, name): # name example: *OpenVPN*
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

    def add_target_spot_instance(self, SpotFleetRequestId):
        return self.ec2_client.modify_spot_fleet_request(
            SpotFleetRequestId=SpotFleetRequestId,
            TargetCapacity=1,
            OnDemandTargetCapacity=0,
        )