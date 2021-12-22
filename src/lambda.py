import json

# ami-0c8ae7b6508eff3f4 (64-bit Arm)
# t4g.nano
# t4g.micro (free tier eligible)

domain_name = ""
update_url = ""

def handler(event, context):
    login_page = event["headers"]["Referer"]
    userdata = file_get_contents("userdata.sh").format(domain_name, update_url)

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/plain'
        }
    }

def file_get_contents(filename):
    with open(filename) as f:
        return f.read()

