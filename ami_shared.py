# -*- coding: utf-8 -*-

"""
 Data + functions used by calling lambda functions
"""


#  General libraries
import boto3
import logging
import datetime
import dateutil.parser
import dateutil.tz
import time
import urllib2
import urllib
import json


#  Constants

#  ONLY servers with these tag:value combo are backed-up
TAG_KEY   = 'Environment'
TAG_VALUE = 'production'

#  How long to keep backups (days)
RETENTION_DAYS = 7
#  How often to backup (hours) (NOTE: this is set on 'deploy.sh')
BACKUP_HOURS   = 4

#  How old the "oldest" backup can be before we alert
RETENTION_DAYS_GRACE = 8
#  How much time since "newest" backup before we alert
BACKUP_HOURS_GRACE   = 8

#  Global notification
ARN_TOPIC_ALERT = 'arn:aws:sns:us-east-1:876015318607:alerts'

#  Slack-related
SLACK_WEB_HOOK = 'https://hooks.slack.com/services/GIBBERISH_STRING'            #  ! Change to your own!
SLACK_CHANNEL  = 'ops'                                                          #  ! Change to your own!
SLACK_ICON     = 'robot'
SLACK_JOBNAME  = 'backup-buddy'
TXT_HEADER     = '[ *Server* | _AMI_ID_ | Taken On ]\n'

#  Global objects
ec2 = boto3.client('ec2')
sns = boto3.client('sns')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

#  Timestamp with today's date in UTC
today = datetime.datetime.utcnow().replace(tzinfo=dateutil.tz.tzutc())

#  Global lists
image_status_list     = []
create_success_list   = []
create_failure_list   = []
delete_success_list   = []
delete_failure_list   = []
missing_backup_list   = []
expired_backup_list   = []
no_recent_backup_list = []
#  Hold custom values
variables_list = []


#  Global functions
def image_status_add(instance_id, instance_name, image_id, image_name, create_dt, action, is_success):
    """
    Add items to actions/results list
    """

    image_status_list.append({
        "instance_id":   instance_id,
        "instance_name": instance_name.replace(".guruse.com", ""),
        "image_id":      image_id,
        "image_name":    image_name,
        "create_dt":     create_dt,
        "action":        action,
        "is_success":    is_success
    })
    return


def variables_add(var_title, var_value):
    """
    Add items to variables list
    """

    variables_list.append({
        "var_title":  var_title.upper(),
        "var_value":  var_value
    })
    return


def slack_message(color, text_msg, func_name):
    """
    Send message to 'Ops' channel
    """

    #  Global lists
    global create_success_list, create_failure_list
    global delete_success_list, delete_failure_list
    global missing_backup_list, expired_backup_list, no_recent_backup_list

    #  Init strings
    create_success_text, create_failure_text = TXT_HEADER, TXT_HEADER
    delete_success_text, delete_failure_text = TXT_HEADER, TXT_HEADER
    missing_backup_text, expired_backup_text = TXT_HEADER, TXT_HEADER
    no_recent_backup_text = TXT_HEADER

    #  Init JSON payload
    slack_data = {
        "channel": "%s" % SLACK_CHANNEL,
        "attachments": [{
            "icon_emoji": "%s" % SLACK_ICON,
            "color": "%s" % color,
            "fallback": "%s" % text_msg,
            "author_name": "aws_lambda",
            "title": "%s" % SLACK_JOBNAME,
            "pre_text": "%s" % text_msg,
            "text": "%s\n" % text_msg,
            "fields": [],
            "footer": "%s" % func_name,
            "ts": "%i" % int(time.time()),
            "mrkdwn_in": ["text", "pretext", "title", "fields"]
        }]
    }

    #  Draft message/alert per list
    if create_success_list:
        for x in create_success_list:
            create_success_text += '*%s* | _%s_ | %s\n' % (
                x['instance_name'],
                x['image_id'],
                x['create_dt'])

        slack_data['attachments'][0]['fields'].append(
            {
                "title": "Backups taken (`Pass`):",
                "value": "%s\n\n" % create_success_text,
                "short": False
            }
        )

    if create_failure_list:
        for x in create_failure_list:
            create_failure_text += '%s | -- | --\n' % x['instance_name']

        slack_data['attachments'][0]['fields'].append(
            {
                "title": "Backups NOT taken (`Fail`):",
                "value": "%s\n\n" % create_failure_text,
                "short": False
            }
        )

    if delete_success_list:
        for x in delete_success_list:
            delete_success_text += '*%s* | _%s_ | %s\n' % (
                x['instance_name'],
                x['image_id'],
                x['create_dt'])

        slack_data['attachments'][0]['fields'].append(
            {
                "title": "Expired backups deleted (`Pass`):",
                "value": "%s\n\n" % delete_success_text,
                "short": False
            }
        )

    if delete_failure_list:
        for x in delete_failure_list:
            delete_failure_text += '*%s* | _%s_ | %s\n' % (
                x['instance_name'],
                x['image_id'],
                x['create_dt'])

        slack_data['attachments'][0]['fields'].append(
            {
                "title": "Expired backups NOT deleted (`Fail`):",
                "value": "%s\n\n" % delete_failure_text,
                "short": False
            }
        )

    if missing_backup_list:
        for x in missing_backup_list:
            missing_backup_text += '%s | -- | --\n' % x['instance_name']

        slack_data['attachments'][0]['fields'].append(
            {
                "title": "Server(s) with NO backups (`Fail`):",
                "value": "%s\n\n" % missing_backup_text,
                "short": False
            }
        )

    if expired_backup_list:
        for x in expired_backup_list:
            expired_backup_text += '*%s* | _%s_ | %s\n' % (
                x['instance_name'],
                x['image_id'],
                x['create_dt'])

        slack_data['attachments'][0]['fields'].append(
            {
                "title": "Expired backups left behind (`Fail`):",
                "value": "%s\n\n" % expired_backup_text,
                "short": False
            }
        )

    if no_recent_backup_list:
        for x in no_recent_backup_list:
            no_recent_backup_text += '*%s* | _%s_ | %s\n' % (
                x['instance_name'],
                x['image_id'],
                x['create_dt'])

        slack_data['attachments'][0]['fields'].append(
            {
              "title": "Server(s) missing recent backups taken (`Fail`):",
              "value": "%s\n\n" % no_recent_backup_text,
              "short": False
            }
        )

    #  Post to Slack
    try:
        data = json.dumps(slack_data)
        req = urllib2.Request(
            SLACK_WEB_HOOK,
            data,
            {'Content-Type': 'application/json'}
        )
        f = urllib2.urlopen(req)
        response = f.read()
        f.close()
    except Exception as e:
        logger.error('WTF! Unable to send message to Slack')
        logger.exception(e)

    return


def send_via_email(script_file, title):
    """
    Format report with AMI/image status
    """
    if image_status_list:

        #  Get current AWS region
        sess = boto3.session.Session()

        #  Header
        report_msg = []
        report_msg.append('-' * 40)
        report_msg.append('BACKUP-BUDDY STATUS REPORT')
        report_msg.append('-' * 40)
        report_msg.append('{:13} : '.format('AWS REGION') + '{:16}'.format(sess.region_name))
        report_msg.append('{:13} : '.format('DATE-TIME')  + '{:16}'.format(today.isoformat()))
        report_msg.append('{:13} : '.format('ITEMS')      + '{0}'.format(len(image_status_list)))
        report_msg.append('{:13} : '.format('TITLE')      + '{:16}'.format(title))
        report_msg.append('{:13} : '.format('SCRIPT')     + '{:16}'.format(script_file))
        report_msg.append('-' * 40)

        #  Add custom variables
        if variables_list:
            for var in variables_list:
                report_msg.append('{:13} : '.format(var['var_title']) + '{:16}'.format(var['var_value']))
            report_msg.append('-' * 40)

        report_msg.append('')
        report_msg.append('')

        if create_success_list:
            report_msg.append('Backups taken (Pass):')
            report_msg.append('-' * 120)
            report_msg.append(
                '{:21} | '.format('INSTANCE') +
                '{:21} | '.format('AMI ID') +
                '{:25} | '.format('TIMESTAMP') +
                '{:60}   '.format('COMPLETED')
            )
            report_msg.append('-' * 120)
            for x in create_success_list:
                report_msg.append(
                    '{:21} | '.format(x['instance_name']) +
                    '{:21} | '.format(x['image_id']) +
                    '{:25} | '.format(x['create_dt'].isoformat()) +
                    '{:60}   '.format(str(x['is_success']))
                )
            report_msg.append('-' * 120)
            report_msg.append('{:>21} | Items(s)'.format(len(create_success_list)))
            report_msg.append('')
            report_msg.append('')

        if create_failure_list:
            report_msg.append('Backups NOT taken (Fail):')
            report_msg.append('-' * 120)
            report_msg.append(
                '{:21} | '.format('INSTANCE') +
                '{:21} | '.format('AMI ID') +
                '{:25} | '.format('TIMESTAMP') +
                '{:60}   '.format('COMPLETED')
            )
            report_msg.append('-' * 120)
            for x in create_failure_list:
                report_msg.append(
                    '{:21} | '.format(x['instance_name']) +
                    '{:21} | '.format(x['image_id']) +
                    '{:25} | '.format(x['create_dt'].isoformat()) +
                    '{:60}   '.format(str(x['is_success']))
                )
            report_msg.append('-' * 120)
            report_msg.append('{:>21} | Items(s)'.format(len(create_failure_list)))
            report_msg.append('')
            report_msg.append('')

        if delete_success_list:
            report_msg.append('Expired backups deleted (Pass):')
            report_msg.append('-' * 120)
            report_msg.append(
                '{:21} | '.format('INSTANCE') +
                '{:21} | '.format('AMI ID') +
                '{:25} | '.format('TIMESTAMP') +
                '{:60}   '.format('COMPLETED')
            )
            report_msg.append('-' * 120)
            for x in delete_success_list:
                report_msg.append(
                    '{:21} | '.format(x['instance_name']) +
                    '{:21} | '.format(x['image_id']) +
                    '{:25} | '.format(x['create_dt'].isoformat()) +
                    '{:60}   '.format(str(x['is_success']))
                )
            report_msg.append('-' * 120)
            report_msg.append('{:>21} | Items(s)'.format(len(delete_success_list)))
            report_msg.append('')
            report_msg.append('')

        if delete_failure_list:
            report_msg.append('Expired backups NOT deleted (Fail):')
            report_msg.append('-' * 120)
            report_msg.append(
                '{:21} | '.format('INSTANCE') +
                '{:21} | '.format('AMI ID') +
                '{:25} | '.format('TIMESTAMP') +
                '{:60}   '.format('COMPLETED')
            )
            report_msg.append('-' * 120)
            for x in delete_failure_list:
                report_msg.append(
                    '{:21} | '.format(x['instance_name']) +
                    '{:21} | '.format(x['image_id']) +
                    '{:25} | '.format(x['create_dt'].isoformat()) +
                    '{:60}   '.format(str(x['is_success']))
                )
            report_msg.append('-' * 120)
            report_msg.append('{:>21} | Items(s)'.format(len(delete_failure_list)))
            report_msg.append('')
            report_msg.append('')

        if missing_backup_list:
            report_msg.append('Server(s) with NO backups (Fail):')
            report_msg.append('-' * 120)
            report_msg.append(
                '{:21} | '.format('INSTANCE') +
                '{:21} | '.format('AMI ID') +
                '{:25} | '.format('TIMESTAMP') +
                '{:60}   '.format('COMPLETED')
            )
            report_msg.append('-' * 120)
            for x in missing_backup_list:
                report_msg.append(
                    '{:21} | '.format(x['instance_name']) +
                    '{:21} | '.format(x['image_id']) +
                    '{:25} | '.format(x['create_dt'].isoformat()) +
                    '{:60}   '.format(str(x['is_success']))
                )
            report_msg.append('-' * 120)
            report_msg.append('{:>21} | Items(s)'.format(len(missing_backup_list)))
            report_msg.append('')
            report_msg.append('')

        if expired_backup_list:
            report_msg.append('Expired backups left behind (Fail):')
            report_msg.append('-' * 120)
            report_msg.append(
                '{:21} | '.format('INSTANCE') +
                '{:21} | '.format('AMI ID') +
                '{:25} | '.format('TIMESTAMP') +
                '{:60}   '.format('COMPLETED')
            )
            report_msg.append('-' * 120)
            for x in expired_backup_list:
                report_msg.append(
                    '{:21} | '.format(x['instance_name']) +
                    '{:21} | '.format(x['image_id']) +
                    '{:25} | '.format(x['create_dt'].isoformat()) +
                    '{:60}   '.format(str(x['is_success']))
                )
            report_msg.append('-' * 120)
            report_msg.append('{:>21} | Items(s)'.format(len(expired_backup_list)))
            report_msg.append('')
            report_msg.append('')

        if no_recent_backup_list:
            report_msg.append('Server(s) missing recent backups taken (Fail):')
            report_msg.append('-' * 120)
            report_msg.append(
                '{:21} | '.format('INSTANCE') +
                '{:21} | '.format('AMI ID') +
                '{:25} | '.format('TIMESTAMP') +
                '{:60}   '.format('COMPLETED')
            )
            report_msg.append('-' * 120)
            for x in no_recent_backup_list:
                report_msg.append(
                    '{:21} | '.format(x['instance_name']) +
                    '{:21} | '.format(x['image_id']) +
                    '{:25} | '.format(x['create_dt'].isoformat()) +
                    '{:60}   '.format(str(x['is_success']))
                )
            report_msg.append('-' * 120)
            report_msg.append('{:>21} | Items(s)'.format(len(no_recent_backup_list)))
            report_msg.append('')
            report_msg.append('')

        #  Send report via SNS notification
        sns.publish(
            TopicArn = ARN_TOPIC_ALERT,
            Subject  = "Backup-Buddy Status Report [%s] @ [%s]" % (sess.region_name, today.strftime('%Y-%m-%d %H:%M %Z')),
            Message  = "\n".join(report_msg))
    else:
        #  Alles klar, herr kommissar!
        logger.info('Woo-hoo! No errors reported!')

    return


def generate_report(script_file, title='', email_report=False):
    """
    Generate report on errors
    """

    #  Global lists
    global create_success_list, create_failure_list
    global delete_success_list, delete_failure_list
    global missing_backup_list, expired_backup_list, no_recent_backup_list

    if image_status_list:
        #
        #  Create lists with different status
        #
        create_success_list = [
            i
            for i in image_status_list
            if i['action'] == 'CREATE' and i['is_success'] is True
        ]
        create_failure_list = [
            i
            for i in image_status_list
            if i['action'] == 'CREATE' and i['is_success'] is False
        ]
        delete_success_list = [
            i
            for i in image_status_list
            if i['action'] == 'DELETE' and i['is_success'] is True
        ]
        delete_failure_list = [
            i
            for i in image_status_list
            if i['action'] == 'DELETE' and i['is_success'] is False
        ]
        missing_backup_list = [
            i
            for i in image_status_list
            if i['action'] == 'CHECK_MISSING'
        ]
        expired_backup_list = [
            i
            for i in image_status_list
            if i['action'] == 'CHECK_EXPIRED'
        ]
        no_recent_backup_list = [
            i
            for i in image_status_list
            if i['action'] == 'CHECK_RECENT'
        ]

        #
        #  Determine message alert level:
        #  - good/green: no errors
        #  - warning/yellow: some errors
        #  - danger/red: all errors
        #
        has_success = [
            i
            for i in image_status_list
            if i['is_success'] is True
        ]
        has_failures = [
            i
            for i in image_status_list
            if i['is_success'] is False
        ]
        if has_success and not has_failures:
            msg_status = 'good'
        elif not has_success and has_failures:
            msg_status = 'danger'
        else:
            msg_status = 'warning'

        #  Slack me!
        slack_message(msg_status, title, script_file)

        #  Send email report
        if email_report:
            send_via_email(script_file, title)
    else:
        #  Alles klar, herr kommissar!
        logger.info('Woo-hoo! No AMI errors reported!')

    return
