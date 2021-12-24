import utils

def handler(event, context):

    if (utils.check_if_instance_exists()): 
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html'
            },
            'body': utils.generate_response_body("We are good to go.") 
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
