#!/usr/bin/env python3
import json, aws_cdk as cdk
from stack.main_stack import CdkMainStack
from stack.region_specefic_stack import CdkRegionSpeceficStack

with open("src/configs.json", 'r') as f:
    configs = json.load(f)
    region_specefics = configs['region_data']
    region = configs['default_region']
    name = configs['app_name']

app = cdk.App()
main_stack = CdkMainStack(app, "{}MainStack".format(name), env={'region':region})

#use bucket name string tbd

for reg in region_specefics.keys():
    stack_id = "{}{}SpeceficStack".format(name, reg.replace('-',''))
    CdkRegionSpeceficStack(app, stack_id, env={'region': reg}) 

app.synth()
