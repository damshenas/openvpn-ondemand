import utils, json

def handler(event, context): 
    sbody = event.get("body")
    jbody = json.loads(sbody)
    username = jbody.get("username")
    password = jbody.get("password")

    if not username or not password:
        return make_response(401, {"status": 'auth_failed'})

    authenticated = utils.is_login_valid(username, password)
    if not authenticated: 
        return make_response(401, {"status": 'auth_failed'})

    utils.update_last_login(username)
    instance_status, instance_id = utils.check_if_instance_exists("*OpenVPN*")

    preSignedUrl = utils.gen_s3_url("profiles/{}.ovpn".format(username))

    if not instance_status: 
        userdata = utils.generate_ec2_userdata(username) 
        utils.run_instance(userdata)
        return make_response(202, {"status": "created", "preSignedUrl": preSignedUrl})
    elif instance_status == "running": 
        utils.add_profile(username, instance_id)
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