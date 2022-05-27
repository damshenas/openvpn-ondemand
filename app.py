#!/usr/bin/env python3
import json, os
from aws_cdk import (Environment, App)

from stack.main_stack import CdkMainStack
from stack.region_specefic_stack import CdkRegionSpeceficStack

envir = 'dev' if not 'env' in os.environ else os.environ['env'].lower()

with open("src/configs.json", 'r') as f:
    configs = json.load(f)
    name = configs['app_name']
    env_configs = configs["environments"][envir]
    region_specefics = env_configs['region_data']
    default_region = env_configs['default_region']
    default_account = os.environ.get("CDK_DEFAULT_ACCOUNT")

app = App()

stack_id = "{}{}MainStack".format(envir.capitalize(), name)
default_environment = Environment(region=default_region, account=default_account)
main_stack = CdkMainStack(app, stack_id, envir, env=default_environment)

for region in region_specefics.keys():
    stack_id = "{}{}SpeceficStack{}".format(envir.capitalize(), name, region.replace('-',''))
    regional_environment = Environment(region=region, account=default_account)
    CdkRegionSpeceficStack(app, stack_id, envir, env=regional_environment) 

app.synth()
