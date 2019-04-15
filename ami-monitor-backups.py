# -*- coding: utf-8 -*-

"""
Query "Environment" tag for EC2 production resources and image
Check that AMIs for these instances are being:
- Taken regularly and are recent/fresh
- Disposed of after X number of days
"""


#  Imports are bundled local to the lambda function
from ami_shared import *


def instance_ami_add(instance_ami_list, image_id, image_name, image_create_dt):
    """
    List of AMIs for an instance
    """
    instance_ami_list.append({
        "image_id":        image_id,
        "image_name":      image_name,
        "image_create_dt": dateutil.parser.parse(image_create_dt)
    })
    return


def lambda_handler(event, context):
    """
    Find instances with AMIs
    """

    #  Date range limits (earliest & latest)
    recent_backup_date  = today - datetime.timedelta(hours=BACKUP_HOURS_GRACE)
    expired_backup_date = today - datetime.timedelta(days=RETENTION_DAYS_GRACE)
    variables_add(
        var_title = 'Latest backup date',
        var_value = recent_backup_date.isoformat()
    )
    variables_add(
        var_title = 'Oldest backup date',
        var_value = expired_backup_date.isoformat()
    )

    #  Find EC2 instances with backup tag
    instances = ec2.describe_instances(
        Filters=[{
            'Name': 'tag:%s'  % (TAG_KEY),
            'Values': [TAG_VALUE]
        }]
    )
    for instance in [i for r in instances['Reservations'] for i in r['Instances']]:

        #  Sanitize instance name
        instance_name = [
            tag['Value']
            for tag in instance['Tags']
            if tag['Key'] == 'Name'
        ][0].strip()
        if ":" in instance_name:
            instance_name = instance_name.split(":")[1].strip()

        #  Find completed AMIS for this instance and dump into array
        images = ec2.describe_images(
            Filters=[
                {
                    'Name': 'tag:instance_id',
                    'Values': [instance["InstanceId"]]
                },
                {
                    'Name': 'state',
                    'Values': ['available']
                }
            ]
        )
        instance_ami_list = []
        for image in images['Images']:
            instance_ami_add(
                instance_ami_list = instance_ami_list,
                image_id          = image['ImageId'],
                image_name        = image['Name'],
                image_create_dt   = image['CreationDate']
            )

        if instance_ami_list:
            #
            #  Found AMI backups for this instance:
            #  - Sort list by Creation DT
            #  - Check newest AMI for missing backups
            #  - Check oldest AMI for expired backups missing pruning
            #

            #  Sort AMI list by "creation date" descending (most recent backup, first)
            instance_ami_list_sorted = sorted(instance_ami_list, key=lambda k: k['image_create_dt'], reverse=True)

            #
            #  Find most recent AMI and figure out if it's recent
            #
            image_create_dt = instance_ami_list_sorted[0]['image_create_dt']
            if image_create_dt < recent_backup_date:
                image_status_add(
                    instance_id   = instance["InstanceId"],
                    instance_name = instance_name,
                    image_id      = instance_ami_list_sorted[0]['image_id'],
                    image_name    = instance_ami_list_sorted[0]['image_name'],
                    create_dt     = image_create_dt,
                    action        = 'CHECK_RECENT',
                    is_success    = False
                )
                logger.error('WTF! Last backup for server=%s, instance_id=%s taken on [%s]', instance_name, instance["InstanceId"], image_create_dt)

            #
            #  Find expired AMIs NOT being removed
            #  i.e., AMI creation date is older than computed expiration date
            #        (expiration date = now - retention grace period)
            #
            for expired_list in [
                i
                for i in instance_ami_list_sorted
                if i['image_create_dt'] < expired_backup_date
            ]:
                image_status_add(
                    instance_id   = instance["InstanceId"],
                    instance_name = instance_name,
                    image_id      = expired_list['image_id'],
                    image_name    = expired_list['image_name'],
                    create_dt     = expired_list['image_create_dt'],
                    action        = 'CHECK_EXPIRED',
                    is_success    = False
                )
                logger.error('WTF! Expired backup for server=%s, instance_id=%s taken on [%s]',
                    instance_name,
                    instance["InstanceId"],
                    expired_list['image_create_dt'])
        else:
            #  No AMIs found!
            image_status_add(
                instance_id   = instance["InstanceId"],
                instance_name = instance_name,
                image_id      = None,
                image_name    = None,
                create_dt     = None,
                action        = 'CHECK_MISSING',
                is_success    = False
            )
            logger.error('WTF! No AMIs found for server=%s, instance_id=%s', instance_name, instance_id)

    #  Report on actions
    generate_report(
        script_file=__file__,
        title='Monitor AMI backups',
        email_report=True)

    return


#  This allows us to test locally
if __name__ == "__main__":
    #  Ignore lambda timeout when testing
    logging.basicConfig()
    lambda_handler('event', 'handler')
