#!/usr/bin/env python3
import os
import aws_cdk as cdk
from stack.cdk_stack import CdkStack

app = cdk.App()
CdkStack(app, "CdkStack", env={'region': 'us-east-1'})

app.synth()
