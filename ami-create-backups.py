# -*- coding: utf-8 -*-

"""
Query "Environment" tag for EC2 production resources and image
"""

#  Imports are bundled local to the lambda function
from ami_shared import *


def lambda_handler(event, context):
    """
    Find instances to image
    """

    #  Timestamp with today's date in UTC
    now = today.strftime("%Y-%m-%dT%H-%M-%S")

    #  Find EC2 instances with specific tag
    instances = ec2.describe_instances(
        Filters=[{
            'Name': 'tag:%s' % (TAG_KEY),
            'Values': [TAG_VALUE]
        }]
    )
    for instance in [i for r in instances['Reservations'] for i in r['Instances']]:

        #  Full instance name
        instance_fullname = [
            tag['Value']
            for tag in instance['Tags']
            if tag['Key'] == 'Name'
        ][0].strip()

        #  Sanitize instance name
        instance_name = instance_fullname
        if ":" in instance_name:
            instance_name = instance_name.split(":")[1].strip()
        if "." in instance_name:
            instance_name = instance_name.split(".")[0].strip()

        #  Get Security Group IDs
        security_groups = [
            security_group['GroupId']
            for security_group in instance['SecurityGroups']
            if security_group['GroupId']
        ]

        #  Create AMI
        ami_name = '%s_%s' % (instance_name, now)
        try:
            image_ami = ec2.create_image(
                InstanceId=instance["InstanceId"],
                Name=ami_name,
                Description='Automated backup for [%s]' % (instance_name),
                NoReboot=True
            )
            if image_ami:
                logger.info('Great Success! AMI [%s:%s] created for instance [%s:%s]' %
                            (ami_name, image_ami["ImageId"], instance_name, instance["InstanceId"]))

                #  Record new image creation
                image_status_add(
                    instance_id=instance["InstanceId"],
                    instance_name=instance_name,
                    image_id=image_ami["ImageId"],
                    image_name=ami_name,
                    create_dt=today,
                    action='CREATE',
                    is_success=True
                )

                #  Add tags to new AMI
                ec2.create_tags(
                    Resources=[image_ami["ImageId"]],
                    Tags=[
                        {
                            'Key': 'Name',
                            'Value': instance_fullname
                        },
                        {
                            'Key': 'instance_id',
                            'Value': instance["InstanceId"]
                        },
                        {
                            'Key': 'instance_name',
                            'Value': instance_name
                        },
                        {
                            'Key': 'instance_type',
                            'Value': instance["InstanceType"]
                        },
                        {
                            'Key': 'instance_keyname',
                            'Value': instance["KeyName"]
                        },
                        {
                            'Key': 'instance_state',
                            'Value': instance["State"]["Name"]
                        },
                        {
                            'Key': 'instance_avail_zone',
                            'Value': instance["Placement"]["AvailabilityZone"]
                        },
                        {
                            'Key': 'instance_sec_groups',
                            'Value': ','.join(security_groups)
                        },
                        {
                            'Key': 'CreatedBy',
                            'Value': 'ami-automation'
                        }
                    ]
                )
            else:
                logger.error('ERR! Unable to create AMI [%s] for instance [%s:%s]' %
                             (ami_name, instance_name, instance["InstanceId"]))

                #  Record image create failure
                image_status_add(
                    instance_id=instance["InstanceId"],
                    instance_name=instance_name,
                    image_id=None,
                    image_name=ami_name,
                    create_dt=today,
                    action='CREATE',
                    is_success=False
                )

        except Exception as e:
            logger.error('ERR! Unable to create AMI [%s] for instance [%s:%s]' %
                         (ami_name, instance_name, instance["InstanceId"]))
            logger.exception(e)

    #  Report on actions
    generate_report(__file__, 'Take AMI backups')

    return


#  This allows us to test locally
if __name__ == "__main__":
    logging.basicConfig()
    lambda_handler('event', 'handler')
