import utils, json

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
        region_specefics = configs['region_data']
        name = configs['name']

    if ec2_region not in region_specefics.keys():
        return make_response(402, {"status": 'region_not_supported'})

    utls = utils.main(username, name, ec2_region, region_specefics[ec2_region])

    authenticated = utls.is_login_valid(password)
    if not authenticated: 
        return make_response(401, {"status": 'auth_failed'})

    utls.update_last_login()
    instance_status, instance_id = utls.check_if_instance_exists("*OpenVPN*")

    preSignedUrl = utls.gen_s3_url("profiles/{}.ovpn".format(username))

    if not instance_status: 
        userdata = utls.generate_ec2_userdata() 
        utls.run_instance(userdata)
        return make_response(202, {"status": "created", "preSignedUrl": preSignedUrl})
    elif instance_status == "running": 
        utls.add_profile(instance_id)
        return make_response(200, {"status": "running", "preSignedUrl": preSignedUrl})

    return make_response(201, {"status": instance_status, "preSignedUrl": preSignedUrl})

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