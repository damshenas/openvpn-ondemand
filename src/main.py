import utils

def handler(event, context):

    instance_exists = utils.check_if_instance_exists("*OpenVPN*")
    if (instance_exists): 
        message = "We are good to go." if instance_exists == "running" else "The server is initializing."
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html'
            },
            'body': utils.generate_response_body(message) 
        }

    userdata = utils.generate_ec2_userdata() 
    utils.run_instance(userdata)

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/html'
        },
        'body': utils.generate_response_body("The server is initializing.") 
    }
