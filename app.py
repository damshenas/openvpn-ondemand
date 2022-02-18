#!/usr/bin/env python3
import json, os, aws_cdk as cdk
from stack.main_stack import CdkMainStack
from stack.region_specefic_stack import CdkRegionSpeceficStack

envir = 'dev' if not 'env' in os.environ else os.environ['env']

with open("src/configs.json", 'r') as f:
    configs = json.load(f)
    name = configs['app_name']
    env_configs = configs["environments"][envir]
    region_specefics = env_configs['region_data']
    region = env_configs['default_region']

app = cdk.App()
stack_id = "{}{}MainStack".format(envir.capitalize(), name)
main_stack = CdkMainStack(app, stack_id, envir, env={'region': region})

for reg in region_specefics.keys():
    stack_id = "{}{}SpeceficStack{}".format(envir.capitalize(), name, reg.replace('-',''))
    CdkRegionSpeceficStack(app, stack_id, envir, env={'region': reg}) 

app.synth()
