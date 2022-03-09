import utils, json, os
environment = os.environ['environment'] 

def handler(event, context): 
    sbody = event.get("body")
    jbody = json.loads(sbody)
    username = jbody.get("username")
    password = jbody.get("password")
    ec2_region = jbody.get("region")

    print ("New request by {} for {}".format(username, ec2_region))

    if not username or not password:
        return make_response(401, {"status": 'auth_failed'})

    with open("configs.json", 'r') as f:
        configs = json.load(f)
        name = configs['app_name']
        first_username = configs['first_username'] #just for initial server provisioning
        env_configs = configs["environments"][environment]
        default_region = env_configs['default_region']
        region_specefics = env_configs['region_data']

    if ec2_region not in region_specefics.keys():
        return make_response(402, {"status": 'region_not_supported'})

    utls = utils.main(username, name, ec2_region, region_specefics[ec2_region], default_region)

    authenticated = utls.is_login_valid(password)
    if not authenticated: 
        return make_response(401, {"status": 'auth_failed'})

    utls.update_last_login()
    instance_id, spot_fleet_request_id = utls.find_useable_instance()

    if not instance_id: username = first_username
    preSignedUrl = utls.gen_s3_url("profiles/{}/{}.ovpn".format(ec2_region, username))

    # + make sure the instance really does not exist otherwise the user will never get the profile cert
    if not instance_id: 
        utls.upload_bash_scripts() 
        utls.increase_spot_instance_target_capacity(spot_fleet_request_id)
        return make_response(202, {"status": "created", "preSignedUrl": preSignedUrl})

    utls.add_profile(instance_id)
    return make_response(200, {"status": "running", "preSignedUrl": preSignedUrl})

def make_response(status, response):
    return {
        'statusCode': status,
        'headers': {
            "Content-Type": "text/html",
            "Access-Control-Allow-Headers" : "Content-Type",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "OPTIONS,POST,GET",
            "Content-Type": "application/json; charset=utf-8",
        },
        'body': json.dumps(response) 
    }