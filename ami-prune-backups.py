# -*- coding: utf-8 -*-

"""
Query for expired production AMI images and remove
"""


#  Imports are bundled local to the lambda function
from ami_shared import *


def lambda_handler(event, context):
    """
    Find images to be pruned
    """

    #  Determine Expiration Date for comparison
    expiry_date = today - datetime.timedelta(days=RETENTION_DAYS)
    variables_add(
        var_title = 'Expiration date',
        var_value = expiry_date.isoformat()
    )

    #  Loop thru tagged + stable EC2 images
    images = ec2.describe_images(
        Filters=[
            {
                'Name':   'tag-key',
                'Values': ['instance_id']
            },
            {
                'Name':   'state',
                'Values': ['available']
            }
        ],
        Owners=['self']
    )
    for image in images['Images']:

        #  Get image info
        image_id   = image["ImageId"]
        image_date = dateutil.parser.parse(image["CreationDate"])

        if 'Tags' in image:
            instance_id = [
                tag['Value']
                for tag in image['Tags']
                if tag['Key'] == 'instance_id'
            ][0]
            instance_name = [
                tag['Value']
                for tag in image['Tags']
                if tag['Key'] == 'instance_name'
            ][0]

            #  check if expired
            if image_date < expiry_date:

                #  Deregister image/ami
                try:
                    ec2.deregister_image(
                        ImageId=image_id
                    )
                    logger.info('Great Success! Deleting ami [%s] for instance [%s:%s] created on [%s]' %
                        (image_id, instance_name, instance_id, image_date.isoformat()))

                    #  Record deleted image
                    image_status_add(
                        instance_id   = instance_id,
                        instance_name = instance_name,
                        image_id      = image_id,
                        image_name    = image["Name"],
                        create_dt     = image_date,
                        action        = 'DELETE',
                        is_success    = True
                    )

                    for bdm in image['BlockDeviceMappings']:
                        if 'Ebs' in bdm:
                            snapshot_id = bdm['Ebs']['SnapshotId']

                            #  Delete snapshot
                            try:
                                ec2.delete_snapshot(
                                    SnapshotId=snapshot_id
                                )
                                logger.info('Great Success! Deleting snapshot [%s] created by ami [%s]' %
                                    (snapshot_id, image_id))
                            except Exception as e:
                                logger.error('WTF! Unable to delete snapshot [%s] created by ami [%s]' %
                                    (snapshot_id, image_id))
                                logger.exception(e)

                except Exception as e:
                    logger.error('WTF! Unable to delete ami [%s] for instance [%s:%s] created on [%s]' %
                        (image_id, instance_name, instance_id, image_date.isoformat()))
                    logger.exception(e)

                    #  Record failure
                    image_status_add(
                        instance_id   = instance_id,
                        instance_name = instance_name,
                        image_id      = image_id,
                        image_name    = image["Name"],
                        create_dt     = image_date,
                        action        = 'DELETE',
                        is_success    = False
                    )

    #  Report on actions
    generate_report(__file__, 'Remove expired AMI backups')

    return


#  This allows us to test locally
if __name__ == "__main__":
    logging.basicConfig()
    lambda_handler('event', 'handler')
