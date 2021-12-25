import utils, json

def handler(event, context): 
    body = event.get("body")
    username = body.get("username")
    password = body.get("password")
    # need to utilzie the username for creating the profile

    instance_exists = utils.check_if_instance_exists("*OpenVPN*")

    if (instance_exists == "running"): 
        return make_response(200, {"ready": True, "preSignedUrl": utils.gen_s3_url("profiles/user1.ovpn")})
    elif (instance_exists == "pending"): 
        return make_response(201, {"ready": False})

    userdata = utils.generate_ec2_userdata() 
    utils.run_instance(userdata)

    return make_response(202, {"ready": False})

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