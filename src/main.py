import utils, json

def handler(event, context): 
    sbody = event.get("body")
    jbody = json.loads(sbody)
    username = jbody.get("username")
    password = jbody.get("password")
    ec2_region = jbody.get("region")

    if not username or not password:
        return make_response(401, {"status": 'auth_failed'})

    if ec2_region not in ['us-east-1', 'ap-south-1', 'eu-central-1']:
        return make_response(402, {"status": 'region_not_supported'})

    utls = utils.main(username, ec2_region)

    authenticated = utls.is_login_valid(username, password)
    if not authenticated: 
        return make_response(401, {"status": 'auth_failed'})

    utls.update_last_login(username)
    instance_status, instance_id = utls.check_if_instance_exists("*OpenVPN*")

    preSignedUrl = utls.gen_s3_url("profiles/{}.ovpn".format(username))

    if not instance_status: 
        userdata = utls.generate_ec2_userdata(username) 
        utls.run_instance(userdata)
        return make_response(202, {"status": "created", "preSignedUrl": preSignedUrl})
    elif instance_status == "running": 
        utls.add_profile(username, instance_id)
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