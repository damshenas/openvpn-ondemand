import boto3, os, time, json

class main:
    def __init__(self, username, name, ec2_region, region_specefics, region):
        self.username = username
        self.ec2_region = ec2_region
        self.name = name
        self.environment = os.environ['environment']
        self.artifacts_bucket = os.environ['artifacts_bucket']
        self.dynamodb_table = os.environ['dynamodb_table_name']
        self.ssm_client = boto3.client('ssm', ec2_region)
        self.ec2_client = boto3.client('ec2',ec2_region)
        self.s3_client = boto3.client('s3',region)
        self.ddb_client = boto3.client('dynamodb',region)
        self.debug_mode = 0 if os.environ['debug_mode'] == 'true' else 1 # this will be done using environment of the stack

    def upload_bash_scripts(self):
        for f in ["bootstrap.sh", "profile.sh", "notice.sh"]: 
            self.uplaod_script_to_s3(f)

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

    def find_active_spot_fleet_requests(self):
        response = []
        sf_requests = self.ec2_client.describe_spot_fleet_requests().get("SpotFleetRequestConfigs")
        for sf_req in sf_requests:
            if sf_req.get("SpotFleetRequestState") == "active":
                response.append({
                    "fleet_request_id": sf_req.get("SpotFleetRequestId"),
                    "request_status": sf_req.get("SpotFleetRequestState"),
                    "activity_status": sf_req.get("ActivityStatus"),
                    "target_capacity": sf_req.get("SpotFleetRequestConfig").get("TargetCapacity")
                })
        return response

    # simply returns all active instances requested by spot fleet request id
    def find_active_spot_instances(self, sf_req_id):
        response = []
        # https://docs.aws.amazon.com/cli/latest/reference/ec2/describe-spot-fleet-instances.html
        sf_active_instances = self.ec2_client.describe_spot_fleet_instances(SpotFleetRequestId=sf_req_id).get("ActiveInstances")
        for active_instance in sf_active_instances:
            response.append({
                "instance_id": active_instance.get("InstanceId"),
                "instance_type": active_instance.get("InstanceType"),
                "instance_request_id": active_instance.get("SpotInstanceRequestId"),
                "instance_health": active_instance.get("InstanceHealth")
            })
        return response

    # returns all active spot instance requests including the instance id
    # has more details compared to find_active_spot_instances
    def find_active_spot_instance_requests(self):
        response = []
        # https://docs.aws.amazon.com/cli/latest/reference/ec2/describe-spot-instance-requests.html
        sf_instance_requests = self.ec2_client.describe_spot_instance_requests()
        for sf_instance_req in sf_instance_requests:
            if sf_instance_req.get("State") == "active":
                response.append({
                    "instance_request_id": sf_instance_req.get("SpotInstanceRequestId"),
                    "instance_id": sf_instance_req.get("InstanceId"),
                    "status": sf_instance_req.get("Status").get("Code"),
                })
        return response

    # Finding if an instance is already running and suitable to be used
    # + what if status is "pending_fulfillment"
    # + what if the instance is being created
    # + what if 2 people request with small delay (race condition)
    # + use tags to find the instances
    def find_useable_instance(self):
        sf_requests = self.find_active_spot_fleet_requests()
        for sf_req in sf_requests:
            if sf_req.get("target_capacity") == 1 and sf_req.get("activity_status") == "fulfilled":
                sf_request_id = sf_req.get("fleet_request_id")
                active_instances = self.find_active_spot_instances(sf_request_id)
                if len(active_instances) > 0:
                    instance_id = active_instances[0].get("instance_id")
                    return [instance_id, sf_request_id]
        # this is a bad practice because if we have 2 active request we will pick the first one!!
        # better to use instance tages or pulling by instance
        return [None, sf_requests[0].get("fleet_request_id")]

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

    def increase_spot_instance_target_capacity(self, sf_request_id):
        return self.ec2_client.modify_spot_fleet_request(
            SpotFleetRequestId=sf_request_id,
            TargetCapacity=1,
            OnDemandTargetCapacity=0,
        )